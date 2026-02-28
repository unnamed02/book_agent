"""
查询重写节点 - 解析上下文依赖的查询
"""

import logging
from typing import TYPE_CHECKING
from prompts.system_prompts import REWRITE_QUERY_SYSTEM_PROMPT
from pydantic import BaseModel, Field


class RewriteQueryResponse(BaseModel):
    """查询重写响应结构"""
    rewritten_query: str = Field(description="重写后的查询文本")
    query_type: str = Field(description="查询类型：find_book/book_recommendation/customer_service/default")

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def rewrite_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 查询重写 - 将指代词替换为具体内容

    例如："最后一本书的作者是谁？" → "《Python编程》的作者是谁？"
    """
    logger.info("📍 节点: rewrite_query")

    session = state["session"]
    user_query = state["user_query"]

    # 导入依赖

    # 设置查询重写系统提示词
    session.set_system_context(REWRITE_QUERY_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        result = await session.ainvoke_structured(
            user_query,
            response_model=RewriteQueryResponse,
            model="qwen3-max-2026-01-23",
            temperature=0
        )

        # 更新状态
        state["user_query"] = result.rewritten_query
        state["query_type"] = result.query_type

        logger.info(f"✓ 查询重写: {user_query} → {result.rewritten_query}")
        logger.info(f"✓ 路由类型: {result.query_type}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"查询重写失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            logger.warning("查询重写触发内容审核，使用默认路由")

        # 失败时使用默认路由
        state["query_type"] = "default"

    return state
