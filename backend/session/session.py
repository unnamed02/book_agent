"""
会话类
封装单个用户会话的所有状态和功能
"""

from typing import Optional, Type
from datetime import datetime
from collections import deque
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from pydantic import BaseModel
import redis.asyncio as redis
import logging
import json
import asyncio

logger = logging.getLogger(__name__)


class Session:
    """
    会话类 - 封装单个用户会话的所有状态

    属性:
        - session_id: 会话ID
        - user_id: 用户ID
        - messages: 对话消息列表
        - last_access: 最后访问时间
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        system_context: str = "你是专业的图书推荐助手。",
        max_history_rounds: int = 10,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        初始化会话

        Args:
            session_id: 会话ID
            user_id: 用户ID
            system_context: 系统上下文
            max_history_rounds: 最大保留对话轮数
            redis_client: Redis客户端（可选）
        """
        self.session_id = session_id
        self.user_id = user_id
        self.last_access = datetime.now()

        # 对话管理相关属性
        self.default_model = "qwen-flash"
        self.default_temperature = 0.7
        self.system_message: Optional[SystemMessage] = None
        self.conversation_messages: deque = deque(maxlen=max_history_rounds * 2)  # 每轮2条消息
        self.max_history_rounds = max_history_rounds
        self.redis_client = redis_client
        self.redis_ttl = 86400
        self.redis_key = f"conversation:{session_id}"

        # 设置系统上下文
        if system_context:
            self.system_message = SystemMessage(content=system_context)

        logger.info(f"✓ 创建会话: {session_id} (用户: {user_id})")

    @property
    def messages(self):
        """动态组合系统消息和对话消息"""
        if self.system_message:
            return [self.system_message] + list(self.conversation_messages)
        return list(self.conversation_messages)

    def update_access_time(self):
        """更新最后访问时间"""
        self.last_access = datetime.now()

    def is_expired(self, timeout_seconds: int = 3600) -> bool:
        """
        检查会话是否过期

        Args:
            timeout_seconds: 超时时间（秒）

        Returns:
            是否过期
        """
        elapsed = (datetime.now() - self.last_access).total_seconds()
        return elapsed > timeout_seconds

    def set_system_context(self, system_prompt: str):
        """
        设置系统上下文（角色描述等）

        Args:
            system_prompt: 系统提示词
        """
        # 更新系统消息
        if system_prompt:
            self.system_message = SystemMessage(content=system_prompt)
            logger.debug("✓ 系统上下文已设置")
        else:
            self.system_message = None

    async def ainvoke(self, user_input: str, model: str = None, temperature: float = None, need_save: bool = True, include_history: bool = True) -> str:
        """
        异步调用 LLM

        Args:
            user_input: 用户输入（用于 LLM 调用和内存历史）
            model: 使用的模型（不指定则使用默认模型）
            temperature: 温度参数（不指定则使用默认值）
            need_save: 是否保存到历史记录
            include_history: 是否包含历史对话上下文

        Returns:
            LLM 回复内容
        """
        # 使用指定的模型或默认模型
        llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=temperature if temperature is not None else self.default_temperature
        )

        # 构建消息列表
        if include_history:
            # 包含历史上下文
            messages = self.messages + [HumanMessage(content=user_input)]
        else:
            # 只包含系统消息和当前输入
            messages = []
            if self.system_message:
                messages.append(self.system_message)
            messages.append(HumanMessage(content=user_input))

        response = await llm.ainvoke(messages)

        # 保存到历史
        if need_save:
            self.conversation_messages.append(HumanMessage(content=user_input))
            self.conversation_messages.append(AIMessage(content=response.content))


        # 异步后台写入到 Redis：将 human/ai 两条消息一次性写入，并在超过阈值时加入 compact 集合，不阻塞响应
        if self.redis_client and need_save:
            human_msg = json.dumps({"type": "human", "content": user_input}, ensure_ascii=False)
            ai_msg = json.dumps({"type": "ai", "content": response.content}, ensure_ascii=False)
            asyncio.create_task(self.bg_write(human_msg, ai_msg))
        return response.content

    async def ainvoke_structured(
        self,
        user_input: str,
        response_model: Type[BaseModel],
        model: str = None,
        temperature: float = None,
        need_save: bool = True
    ) -> BaseModel:
        """
        异步调用 LLM 并返回结构化输出

        Args:
            user_input: 用户输入
            response_model: Pydantic 模型类，定义返回结构
            model: 使用的模型（不指定则使用默认模型）
            temperature: 温度参数（不指定则使用默认值）
            need_save: 是否保存到历史记录

        Returns:
            结构化的响应对象
        """
        # 使用指定的模型或默认模型
        llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=temperature if temperature is not None else self.default_temperature
        )

        # 创建结构化输出的 LLM
        structured_llm = llm.with_structured_output(response_model)

        # 添加用户消息到内存历史
        if need_save:
            self.conversation_messages.append(HumanMessage(content=user_input))

        # 调用结构化输出
        response = await structured_llm.ainvoke(self.messages)

        # 保存 AI 响应
        if need_save:
            # 将响应转为字典，然后转为 JSON 字符串用于存储
            ai_content_dict = response.model_dump()
            ai_content_str = json.dumps(ai_content_dict, ensure_ascii=False)

            self.conversation_messages.append(AIMessage(content=ai_content_str))

            # 异步后台写入到 Redis
            if self.redis_client:
                human_msg = json.dumps({"type": "human", "content": user_input}, ensure_ascii=False)
                ai_msg = json.dumps({"type": "ai", "content": ai_content_str}, ensure_ascii=False)
                asyncio.create_task(self.bg_write(human_msg, ai_msg))

        return response


    async def astream(
        self,
        user_input: str,
        model: str = None,
        temperature: float = None,
        need_save: bool = True,
        include_history: bool = True
    ):
        """
        异步流式调用 LLM，逐 token 返回

        Args:
            user_input: 用户输入
            model: 使用的模型（不指定则使用默认模型）
            temperature: 温度参数（不指定则使用默认值）
            need_save: 是否保存到历史记录
            include_history: 是否包含历史对话上下文

        Yields:
            str: LLM 生成的 token
        """
        # 使用指定的模型或默认模型
        llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=temperature if temperature is not None else self.default_temperature,
            streaming=True  # 启用流式输出
        )

        # 构建消息列表
        if include_history:
            messages = self.messages + [HumanMessage(content=user_input)]
        else:
            messages = []
            if self.system_message:
                messages.append(self.system_message)
            messages.append(HumanMessage(content=user_input))

        # 流式调用
        full_response = ""
        async for chunk in llm.astream(messages):
            if chunk.content:
                full_response += chunk.content
                yield chunk.content

        # 流式完成后保存历史
        if need_save:
            self.conversation_messages.append(HumanMessage(content=user_input))
            self.conversation_messages.append(AIMessage(content=full_response))

            # 异步后台写入到 Redis
            if self.redis_client:
                human_msg = json.dumps({"type": "human", "content": user_input}, ensure_ascii=False)
                ai_msg = json.dumps({"type": "ai", "content": full_response}, ensure_ascii=False)
                asyncio.create_task(self.bg_write(human_msg, ai_msg))


    async def bg_write(self, human, ai):
        length = await self.redis_client.rpush(self.redis_key, human, ai)
        if length > 220:
            await self.redis_client.sadd("needs_compact_list", self.redis_key)
            logger.debug(f"会话 {self.session_id} 已达到 {length} 条消息，已加入 compact 队列")

    async def load_from_redis(self):
        """从 Redis List 加载对话历史（只加载 human 和 ai 消息，system 由代码设置）"""
        if not self.redis_client:
            return

        try:
            # 获取列表长度
            list_len = await self.redis_client.llen(self.redis_key)
            if list_len == 0:
                logger.debug(f"Redis 中没有找到对话历史: {self.redis_key}")
                return

            # 只加载最近的消息，数量为 deque 的最大容量
            max_messages = self.max_history_rounds * 2
            start_index = max(0, list_len - max_messages)

            # 获取最近的消息
            messages_json = await self.redis_client.lrange(self.redis_key, start_index, -1)

            # 清空对话消息（保留 system_message）
            self.conversation_messages.clear()

            for msg_json in messages_json:
                try:
                    msg_data = json.loads(msg_json)
                    msg_type = msg_data["type"]
                    content = msg_data["content"]

                    if msg_type == "human":
                        self.conversation_messages.append(HumanMessage(content=content))
                    elif msg_type == "ai":
                        # 如果 content 是字典，转换为 JSON 字符串
                        if isinstance(content, dict):
                            content = json.dumps(content, ensure_ascii=False)
                        self.conversation_messages.append(AIMessage(content=content))
                except Exception as e:
                    logger.error(f"解析消息失败: {e}")
                    continue

            logger.info(f"✓ 从 Redis 加载了 {len(messages_json)} 条消息（总共 {list_len} 条）")

        except Exception as e:
            logger.error(f"从 Redis 加载对话历史失败: {e}")

    def get_conversation_rounds(self) -> int:
        """获取当前对话轮数"""
        return len(self.conversation_messages) // 2

    def clear_history(self):
        """清空对话历史（系统消息始终保留）"""
        self.conversation_messages.clear()
        logger.debug("对话历史已清空")

    def __repr__(self) -> str:
        return f"Session(id={self.session_id}, user={self.user_id}, rounds={self.get_conversation_rounds()})"
