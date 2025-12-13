"""
轻量级会话对话管理器
专门用于改进 clarify_llm 和 recommend_llm 的上下文管理
利用 LLM 自带的 Messages API
"""

from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage, BaseMessage
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    轻量级会话对话管理器

    特点:
    1. 利用 LLM 原生 Messages API 自动管理上下文
    2. 支持系统提示词（用户画像）
    3. 自动修剪历史，避免超过上下文窗口
    4. 最小侵入，易于集成
    """

    def __init__(
        self,
        default_model: str = "gpt-4o-mini",
        default_temperature: float = 0.7,
        max_history_rounds: int = 5
    ):
        """
        初始化对话管理器

        Args:
            default_model: 默认使用的模型名称
            default_temperature: 默认温度参数
            max_history_rounds: 最大保留对话轮数
        """
        self.default_model = default_model
        self.default_temperature = default_temperature
        self.messages: List[BaseMessage] = []
        self.max_history_rounds = max_history_rounds

    def set_system_context(self, system_prompt: str):
        """
        设置系统上下文（用户画像、角色描述等）

        Args:
            system_prompt: 系统提示词
        """
        # 移除旧的 SystemMessage
        self.messages = [m for m in self.messages if not isinstance(m, SystemMessage)]

        # 添加新的 SystemMessage（始终在最前面）
        if system_prompt:
            self.messages.insert(0, SystemMessage(content=system_prompt))
            logger.debug("✓ 系统上下文已设置")

    def invoke(self, user_input: str, model: str = None, temperature: float = None) -> str:
        """
        同步调用（兼容原有代码）

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

        # 添加用户消息
        self.messages.append(HumanMessage(content=user_input))

        # 调用 LLM（自动使用所有历史消息）
        response = llm.invoke(self.messages)

        # 保存 AI 回复
        self.messages.append(AIMessage(content=response.content))

        # 自动修剪历史
        self._trim_history()

        return response.content

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

        return response.content

    def _trim_history(self):
        """
        修剪对话历史

        策略:
        - 保留 SystemMessage（用户画像）
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
        logger.debug("🗑️ 对话历史已清空")


def create_conversation_manager(
    user_id: str,
    system_context: Optional[str] = None,
    max_history_rounds: int = 10
) -> ConversationManager:
    """
    创建会话级的对话管理器

    注意：每个 session 只创建一次，所有 LLM 调用共享同一个管理器

    Args:
        user_id: 用户ID
        system_context: 系统上下文（用户画像等）
        max_history_rounds: 最大保留对话轮数

    Returns:
        ConversationManager 实例
    """
    manager = ConversationManager(
        default_model="gpt-4o-mini",  # 默认模型，可以在调用时切换
        default_temperature=0.7,
        max_history_rounds=max_history_rounds
    )

    # 设置系统上下文
    if system_context:
        manager.set_system_context(system_context)

    logger.info(f"✓ 为用户 {user_id} 创建会话对话管理器")

    return manager
