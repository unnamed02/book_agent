"""
轻量级会话对话管理器
利用 LLM 自带的 Messages API
支持 Redis 持久化
"""

from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
import logging
import json
import asyncio
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    轻量级会话对话管理器

    特点:
    1. 利用 LLM 原生 Messages API 自动管理上下文
    2. 支持系统提示词
    3. 自动修剪历史，避免超过上下文窗口
    4. 支持 Redis 持久化对话历史
    5. 最小侵入，易于集成
    """

    def __init__(
        self,
        session_id: str,
        default_model: str = "gpt-4o-mini",
        default_temperature: float = 0.7,
        max_history_rounds: int = 3,
        redis_client: Optional[redis.Redis] = None,
        redis_ttl: int = 86400  # 默认 24 小时过期
    ):
        """
        初始化对话管理器

        Args:
            session_id: 会话ID，用于 Redis 存储
            default_model: 默认使用的模型名称
            default_temperature: 默认温度参数
            max_history_rounds: 最大保留对话轮数
            redis_client: Redis 客户端（可选）
            redis_ttl: Redis 键过期时间（秒）
        """
        self.session_id = session_id
        self.default_model = default_model
        self.default_temperature = default_temperature
        self.messages: List[BaseMessage] = []
        self.max_history_rounds = max_history_rounds
        self.redis_client = redis_client
        self.redis_ttl = redis_ttl
        self.redis_key = f"conversation:{session_id}"

    def set_system_context(self, system_prompt: str):
        """
        设置系统上下文（角色描述等）

        Args:
            system_prompt: 系统提示词
        """
        # 移除旧的 SystemMessage
        self.messages = [m for m in self.messages if not isinstance(m, SystemMessage)]

        # 添加新的 SystemMessage（始终在最前面）
        if system_prompt:
            self.messages.insert(0, SystemMessage(content=system_prompt))
            logger.debug("✓ 系统上下文已设置")

    async def ainvoke(self, user_input: str, model: str = None, temperature: float = None) -> str:
        """
        异步调用

        Args:
            user_input: 用户输入
            model: 使用的模型（不指定则使用默认模型）
            temperature: 温度参数（不指定则使用默认值）

        Returns:
            LLM 回复内容
        """
        # 使用指定的模型或默认模型
        llm = ChatOpenAI(
            model=model or self.default_model,
            temperature=temperature if temperature is not None else self.default_temperature
        )

        self.messages.append(HumanMessage(content=user_input))

        response = await llm.ainvoke(self.messages)

        self.messages.append(AIMessage(content=response.content))

        self._trim_history()

        # 保存到 Redis（不等待结果，后台执行）
        if self.redis_client:
            asyncio.create_task(self._save_to_redis())

        return response.content

    async def _save_to_redis(self):
        """将对话历史保存到 Redis"""
        if not self.redis_client:
            return

        try:
            # 序列化消息列表
            messages_data = []
            for msg in self.messages:
                if isinstance(msg, SystemMessage):
                    msg_type = "system"
                elif isinstance(msg, HumanMessage):
                    msg_type = "human"
                elif isinstance(msg, AIMessage):
                    msg_type = "ai"
                else:
                    continue

                messages_data.append({
                    "type": msg_type,
                    "content": msg.content
                })

            # 保存到 Redis
            await self.redis_client.setex(
                self.redis_key,
                self.redis_ttl,
                json.dumps(messages_data, ensure_ascii=False)
            )
            logger.debug(f"✓ 对话历史已保存到 Redis: {self.redis_key}")

        except Exception as e:
            logger.error(f"保存对话历史到 Redis 失败: {e}")

    async def load_from_redis(self):
        """从 Redis 加载对话历史"""
        if not self.redis_client:
            return

        try:
            data = await self.redis_client.get(self.redis_key)
            if not data:
                logger.debug(f"Redis 中没有找到对话历史: {self.redis_key}")
                return

            messages_data = json.loads(data)
            self.messages = []

            for msg_data in messages_data:
                msg_type = msg_data["type"]
                content = msg_data["content"]

                if msg_type == "system":
                    self.messages.append(SystemMessage(content=content))
                elif msg_type == "human":
                    self.messages.append(HumanMessage(content=content))
                elif msg_type == "ai":
                    self.messages.append(AIMessage(content=content))

            logger.info(f"✓ 从 Redis 加载了 {len(self.messages)} 条对话历史")

        except Exception as e:
            logger.error(f"从 Redis 加载对话历史失败: {e}")

    def _trim_history(self):
        """
        修剪对话历史

        策略:
        - 保留 SystemMessage
        - 只保留最近 N 轮对话（每轮 = User + Assistant）
        """
        system_msgs = [m for m in self.messages if isinstance(m, SystemMessage)]
        other_msgs = [m for m in self.messages if not isinstance(m, SystemMessage)]

        # 只保留最近 N 轮（每轮 = Human + AI）
        max_messages = self.max_history_rounds * 2
        if len(other_msgs) > max_messages:
            other_msgs = other_msgs[-max_messages:]
            logger.debug(f"✂️ 修剪历史，保留最近 {self.max_history_rounds} 轮对话")

        self.messages = system_msgs + other_msgs

    def get_conversation_rounds(self) -> int:
        """获取当前对话轮数"""
        non_system = [m for m in self.messages if not isinstance(m, SystemMessage)]
        return len(non_system) // 2

    def clear_history(self, keep_system: bool = True):
        """
        清空对话历史

        Args:
            keep_system: 是否保留 SystemMessage
        """
        if keep_system:
            self.messages = [m for m in self.messages if isinstance(m, SystemMessage)]
        else:
            self.messages = []
        logger.debug("对话历史已清空")


def create_conversation_manager(
    session_id: str,
    user_id: str,
    system_context: Optional[str] = None,
    max_history_rounds: int = 10,
    redis_client: Optional[redis.Redis] = None
) -> ConversationManager:
    """
    创建会话级的对话管理器

    注意：每个 session 只创建一次，所有 LLM 调用共享同一个管理器

    Args:
        session_id: 会话ID
        user_id: 用户ID
        system_context: 系统上下文
        max_history_rounds: 最大保留对话轮数
        redis_client: Redis 客户端（可选）

    Returns:
        ConversationManager 实例
    """
    manager = ConversationManager(
        session_id=session_id,
        default_model="gpt-4o-mini",  # 默认模型，可以在调用时切换
        default_temperature=0.7,
        max_history_rounds=max_history_rounds,
        redis_client=redis_client
    )

    # 设置系统上下文
    if system_context:
        manager.set_system_context(system_context)

    logger.info(f"✓ 为用户 {user_id} 创建会话对话管理器 (session: {session_id})")

    return manager
