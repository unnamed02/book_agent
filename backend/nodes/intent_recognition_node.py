"""
统一意图识别节点 - 合并路由和重写功能
"""

import logging
from typing import TYPE_CHECKING
from prompts.system_prompts import INTENT_RECOGNITION_SYSTEM_PROMPT
from pydantic import BaseModel, Field


class IntentRecognitionResponse(BaseModel):
    """意图识别响应结构"""
    rewritten_query: str = Field(description="重写后的查询文本（如无需重写则与原查询相同）")
    query_type: str = Field(description="查询类型：find_book/book_recommendation/customer_service/default")
    needs_rewrite: bool = Field(description="是否进行了查询重写")


if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def recognize_intent(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 统一意图识别 - 分析查询意图并在需要时重写查询

    功能：
    1. 判断查询是否需要上下文解析（包含指代词）
    2. 如需要，结合对话历史重写查询
    3. 判断查询类型并路由到相应节点
    """
    logger.info("📍 节点: recognize_intent")

    session = state["session"]
    user_query = state["user_query"]

    # 设置意图识别系统提示词
    session.set_system_context(INTENT_RECOGNITION_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        result = await session.ainvoke_structured(
            user_query,
            response_model=IntentRecognitionResponse,
            model="qwen3-max-2026-01-23",
            temperature=0
        )

        # 更新状态
        if result.needs_rewrite:
            logger.info(f"✓ 查询重写: {user_query} → {result.rewritten_query}")
            state["user_query"] = result.rewritten_query

        state["query_type"] = result.query_type
        logger.info(f"✓ 意图识别: type={result.query_type}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"意图识别失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            logger.warning("意图识别触发内容审核，使用默认路由")

        # 失败时使用默认路由
        state["query_type"] = "default"

    return state
