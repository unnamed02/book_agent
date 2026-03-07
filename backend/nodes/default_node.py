"""
默认处理节点 - 处理无法分类的问题
"""

import logging
import os
from typing import TYPE_CHECKING
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_default_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理无法分类的问题 - 使用通义千问直接回答

    对于无法归类到图书推荐、找书、客服的问题，使用 LLM 直接回答
    """
    logger.info("📍 节点: handle_default_query")

    session = state["session"]
    user_query = state["user_query"]

    try:
        # 导入系统提示词
        from prompts.system_prompts import DEFAULT_QUERY_SYSTEM_PROMPT

        logger.info(f"🚀 开始生成默认回复，查询: {user_query[:50]}...")

        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        # 创建 ChatTongyi 实例，启用联网搜索
        llm = ChatTongyi(
            model="qwen3-max-2026-01-23",
            streaming=True,
            model_kwargs={"enable_search": True}
        )

        # 构建消息列表
        messages = [
            SystemMessage(content=DEFAULT_QUERY_SYSTEM_PROMPT),
            HumanMessage(content=user_query)
        ]

        full_response = ""

        # 流式调用
        async for chunk in llm.astream(messages):
            if chunk.content:  # 确保有内容
                token = chunk.content
                full_response += token
                state["streaming_tokens"].append(token)

        logger.info(f"✓ 默认回复生成完成，长度: {len(full_response)}")

        state["dialogue_response"] = full_response
        state["final_response"] = full_response

    except Exception as e:
        logger.error(f"默认回复生成失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
        state["final_response"] = state["dialogue_response"]

    return state
