"""
推荐节点 - 生成人类可读的推荐书单（流式输出）
"""

import logging
import json
import asyncio
from typing import TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage
from prompts.system_prompts import BOOK_RECOMMENDATION_STREAMING_PROMPT

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_recommendation(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 生成人类可读的推荐书单（流式输出）

    生成格式：
    1. 首先，用2-3句话说明推荐思路
    2. 然后，列出推荐的书籍，每本书一行，格式：《书名》 - 作者：推荐理由
    """
    logger.info("📍 节点: handle_recommendation")

    session = state["session"]

    # 从槽位对象中获取推荐主题
    slots_obj = state.get("slots")
    if slots_obj and hasattr(slots_obj, 'topic'):
        topic = slots_obj.topic
    else:
        topic = ""

    # 构建查询输入
    if topic:
        query_input = f"推荐关于{topic}的书籍"
    else:
        # 降级到使用原始查询
        query_input = state["user_query"]

    logger.info(f"从槽位提取的主题: {topic}")

    # 设置人类可读书单生成提示词
    session.set_system_context(BOOK_RECOMMENDATION_STREAMING_PROMPT)

    try:
        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        full_response = ""

        logger.info(f"🚀 开始流式生成推荐，查询: {query_input[:50]}...")

        # 流式生成人类可读的书单
        async for token in session.astream(
            user_input=query_input,
            model="qwen3-max-2026-01-23",
            temperature=0.7,
            need_save=True,
            include_history=False
        ):
            full_response += token
            state["streaming_tokens"].append(token)

        # 保存完整的书单文本
        state["book_list_text"] = full_response
        state["dialogue_response"] = full_response
        logger.info(f"✓ 书单生成完成，长度: {len(full_response)}")
        logger.info(f"📝 生成的书单内容: {full_response[:300]}...")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"推荐生成失败: {error_msg}", exc_info=True)

        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["dialogue_response"] = "抱歉，内容触发了审核。"
        else:
            state["error"] = f"推荐生成失败: {error_msg}"
            state["dialogue_response"] = "抱歉，生成推荐时出现错误。"

        state["book_list_text"] = ""

    return state
