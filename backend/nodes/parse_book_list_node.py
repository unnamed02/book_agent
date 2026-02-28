"""
解析书单节点 - 从文本中提取书籍信息
"""

import logging
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def parse_book_list(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 解析书单并获取详情

    1. 用 LLM 从文本中提取书籍信息
    2. 调用 fetch_book_details 获取详情
    """
    logger.info("📍 节点: parse_book_list")

    session = state["session"]
    book_list_text = state.get("book_list_text", "")

    logger.info(f"📝 书单文本长度: {len(book_list_text)}")
    logger.info(f"📝 书单文本内容: {book_list_text[:200]}...")

    if not book_list_text:
        logger.error("没有书单文本")
        state["error"] = "没有书单数据"
        state["recommended_books"] = []
        state["book_cards"] = []
        return state

    # 导入系统提示词
    from prompts.system_prompts import PARSE_BOOK_LIST_PROMPT

    # 设置解析提示词
    session.set_system_context(PARSE_BOOK_LIST_PROMPT)

    try:
        # 使用 LLM 解析书单文本
        response = await session.ainvoke(
            user_input=book_list_text,
            model="qwen-flash",
            temperature=0,
            need_save=False
        )

        logger.info(f"🤖 LLM 解析响应: {response[:300]}...")

        # 提取 JSON
        json_text = response.strip()
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()

        # 提取完整的 JSON 对象
        if "{" in json_text:
            start = json_text.index("{")
            json_text = json_text[start:]
            brace_count = 0
            end_pos = -1
            for i, char in enumerate(json_text):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break
            if end_pos > 0:
                json_text = json_text[:end_pos]

        logger.info(f"📋 提取的 JSON: {json_text[:300]}...")

        # 解析 JSON
        response_data = json.loads(json_text)
        books_data = response_data.get("books", [])

        logger.info(f"📚 解析到的书籍数量: {len(books_data)}")

        if not books_data:
            logger.error("解析到的书单为空")
            state["error"] = "书单为空"
            state["recommended_books"] = []
            state["book_cards"] = []
            return state

        # 转换为标准格式
        books = [
            {
                "title": book.get("title", ""),
                "author": book.get("author", ""),
                "reason": book.get("reason", "")
            }
            for book in books_data
        ]

        state["recommended_books"] = books
        logger.info(f"✓ 解析到 {len(books)} 本书籍: {[b['title'] for b in books]}")

        # 不直接调用 fetch_book_details，而是返回状态
        # 让工作流通过边自动路由到 fetch_book_details 节点
        return state

    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}\n响应: {response[:500]}")
        state["error"] = "JSON 解析失败"
        state["recommended_books"] = []
        state["book_cards"] = []
        return state
    except Exception as e:
        logger.error(f"解析书单失败: {e}", exc_info=True)
        state["error"] = f"解析失败: {str(e)}"
        state["recommended_books"] = []
        state["book_cards"] = []
        return state
