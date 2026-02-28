"""
路由节点 - 智能路由分析用户查询类型
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def route_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点0: 智能路由 - 分析用户查询类型

    判断:
    1. 是否需要上下文解析（rewrite）
    2. 是图书推荐、找书还是客服咨询
    """
    logger.info("📍 节点: route_query")

    session = state["session"]
    user_query = state["user_query"]

    # 导入系统提示词
    from prompts.system_prompts import ROUTE_QUERY_SYSTEM_PROMPT

    # 设置路由系统提示词
    session.set_system_context(ROUTE_QUERY_SYSTEM_PROMPT)

    route_prompt = f"用户查询：{user_query}"

    # 使用普通 ainvoke，不包含历史上下文
    try:
        route_result = await session.ainvoke(
            route_prompt,
            model="qwen-flash",
            temperature=0,
            need_save=False,
            include_history=False  # 路由判断不需要历史上下文
        )

        # 清理结果
        clean_result = route_result.strip()

        # 验证返回的查询类型是否有效
        valid_types = ["rewrite", "find_book", "book_recommendation", "customer_service", "default"]

        if clean_result in valid_types:
            state["query_type"] = clean_result
        else:
            logger.warning(f"无效的查询类型: {clean_result}, 使用默认值")
            state["query_type"] = "default"

        logger.info(f"✓ 路由结果: type={state['query_type']}")

    except Exception as e:
        logger.error(f"路由失败: {e}", exc_info=True)
        state["query_type"] = "default"

    return state
