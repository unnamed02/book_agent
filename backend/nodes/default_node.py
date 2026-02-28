"""
默认处理节点 - 处理无法分类的问题
"""

import logging
import json
import asyncio
from typing import TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_default_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理无法分类的问题

    对于无法归类到图书推荐、找书、客服的问题，使用 LLM 回答
    """
    logger.info("📍 节点: handle_default_query")

    session = state["session"]
    user_query = state["user_query"]

    try:
        # 导入系统提示词
        from prompts.system_prompts import DEFAULT_QUERY_SYSTEM_PROMPT

        # 设置系统提示词
        session.set_system_context(DEFAULT_QUERY_SYSTEM_PROMPT)

        logger.info(f"🚀 开始生成默认回复，查询: {user_query[:50]}...")

        # 使用 session.ainvoke 生成回复
        response = await session.ainvoke(
            user_input=user_query,
            model="qwen-flash",
            temperature=0.7,
            need_save=True
        )

        logger.info(f"✓ 默认回复生成完成，长度: {len(response)}")

        state["dialogue_response"] = response
        state["final_response"] = response

    except Exception as e:
        logger.error(f"默认回复生成失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
        state["final_response"] = state["dialogue_response"]

    return state
