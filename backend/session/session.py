"""
会话类
封装单个用户会话的所有状态和功能
"""

from typing import Optional
from datetime import datetime
from collections import deque
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
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

    async def ainvoke(self, user_input: str, model: str = None, temperature: float = None, original_query: str = None) -> str:
        """
        异步调用 LLM

        Args:
            user_input: 用户输入（用于 LLM 调用和内存历史）
            model: 使用的模型（不指定则使用默认模型）
            temperature: 温度参数（不指定则使用默认值）
            original_query: 用户的原始输入（用于保存到 Redis，不指定则保存 user_input）

        Returns:
            LLM 回复内容
        """
        # 使用指定的模型或默认模型
        llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=temperature if temperature is not None else self.default_temperature
        )

        # 添加用户消息到内存历史
        self.conversation_messages.append(HumanMessage(content=user_input))

        # 保存到 Redis（如果提供了 original_query 则保存它，否则保存 user_input）
        if self.redis_client:
            query_to_save = original_query if original_query is not None else user_input
            asyncio.create_task(self._append_message_to_redis("human", query_to_save))

        # 调用 LLM
        response = await llm.ainvoke(self.messages)

        # 添加 AI 消息到内存历史
        self.conversation_messages.append(AIMessage(content=response.content))

        # 保存 AI 回复到 Redis
        if self.redis_client:
            asyncio.create_task(self._append_message_to_redis("ai", response.content))

        return response.content

    async def _append_message_to_redis(self, msg_type: str, content: str):
        """追加单条消息到 Redis List"""
        if not self.redis_client:
            return

        try:
            msg_data = json.dumps({
                "type": msg_type,
                "content": content
            }, ensure_ascii=False)

            # 追加到列表末尾，返回列表长度
            length = await self.redis_client.rpush(self.redis_key, msg_data)

            # 检查是否需要 compact（超过 220 条消息）
            if length > 220:
                await self.redis_client.sadd("needs_compact_list", self.redis_key)
                logger.debug(f"会话 {self.session_id} 已达到 {length} 条消息，已加入 compact 队列")

        except Exception as e:
            logger.error(f"追加消息到 Redis 失败: {e}")

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

            # 获取所有消息
            messages_json = await self.redis_client.lrange(self.redis_key, 0, -1)

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
                        self.conversation_messages.append(AIMessage(content=content))
                except Exception as e:
                    logger.error(f"解析消息失败: {e}")
                    continue

            logger.info(f"✓ 从 Redis 加载了 {len(messages_json)} 条消息")

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
