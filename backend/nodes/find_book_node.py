"""
找书节点 - 流式输出查找的书籍
"""

import logging
from typing import TYPE_CHECKING
from prompts.system_prompts import FIND_BOOK_SYSTEM_PROMPT

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_find_book(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 生成查找书籍的流式响应

    类似推荐节点，先流式输出告诉用户正在查找哪些书
    然后交给 parse_book_list 节点解析书名
    """
    logger.info("📍 节点: handle_find_book")

    session = state["session"]

    # 从槽位对象中获取书名列表
    slots_obj = state.get("slots")
    if slots_obj and hasattr(slots_obj, 'book_titles'):
        book_titles = slots_obj.book_titles
    else:
        book_titles = []

    # 构建查询输入
    if book_titles:
        query_input = f"查找以下书籍：{', '.join(book_titles)}"
    else:
        # 降级到使用原始查询
        query_input = state["user_query"]

    logger.info(f"📚 从槽位提取的书名: {book_titles}")

    # 设置系统提示词
    session.set_system_context(FIND_BOOK_SYSTEM_PROMPT)

    try:
        # 使用流式输出，让用户看到正在查找的书籍
        book_list_text = ""
        async for chunk in session.astream(
            user_input=query_input,
            model="qwen3-max-2026-01-23",
            temperature=0,
            need_save=True,
            include_history=False
        ):
            book_list_text += chunk

        # 保存生成的书单文本，供后续解析
        state["book_list_text"] = book_list_text
        state["dialogue_response"] = book_list_text
        logger.info(f"✓ 生成查找书籍列表: {len(book_list_text)} 字符")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"生成查找列表失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["book_list_text"] = ""
            state["dialogue_response"] = "抱歉，内容触发了审核。"
        else:
            state["error"] = f"生成失败: {error_msg}"
            state["book_list_text"] = ""
            state["dialogue_response"] = "抱歉，查找书籍时出现错误。"

    return state
