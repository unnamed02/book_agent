"""
找书节点 - 提取书名并准备查询
"""

import logging
import json
import asyncio
from typing import TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_find_book(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 提取书名（找书流程第一步）

    直接查询图书馆馆藏并格式化输出
    """
    logger.info("📍 节点: handle_find_book")

    session = state["session"]
    user_query = state["user_query"]

    # 导入依赖
    from prompts.system_prompts import FIND_BOOK_SYSTEM_PROMPT
    from pydantic import BaseModel, Field
    from typing import List

    # 定义响应模型
    class BookInfo(BaseModel):
        """书籍信息"""
        title: str = Field(description="书名（主标题，不含版本号）")
        author: str = Field(description="作者姓名，如果不确定则为空字符串")

    class ExtractBooksResponse(BaseModel):
        """提取书籍响应结构"""
        books: List[BookInfo] = Field(
            description="提取的书籍列表。重要：如果用户查询的是丛书或系列（如'丁丁历险记'、'三体三部曲'、'哈利波特系列'），且该系列每册有独立书名，必须将每一册作为独立的BookInfo条目返回，不要只返回系列名"
        )

    # 设置提取书名系统提示词
    session.set_system_context(FIND_BOOK_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        response = await session.ainvoke_structured(
            user_input=user_query,
            response_model=ExtractBooksResponse,
            model="qwen3-max-2026-01-23",
            temperature=0,
            need_save=True  # 提取书名不需要保存到历史
        )

        books = [book.model_dump() for book in response.books]
        logger.info(f"提取到 {len(books)} 本书")

        if not books:
            state["error"] = "无法提取书名"
            state["recommended_books"] = []
            state["book_cards"] = []
            state["final_response"] = "抱歉，我没有理解您要找的书名，请提供更明确的书名信息。"
            state["dialogue_response"] = state["final_response"]
            return state

        # 保存提取的书籍列表
        state["recommended_books"] = books
        logger.info(f"✓ 提取 {len(books)} 本书籍")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"找书提取失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["recommended_books"] = []
            state["book_cards"] = []
            state["final_response"] = "抱歉，内容触发了审核。"
            state["dialogue_response"] = state["final_response"]
        else:
            state["error"] = f"提取失败: {error_msg}"
            state["recommended_books"] = []
            state["book_cards"] = []
            state["final_response"] = "抱歉，提取书名时出现错误。"
            state["dialogue_response"] = state["final_response"]

    return state
