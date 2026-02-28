"""
获取书籍详情节点 - 并行获取豆瓣、馆藏、电子资源信息
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, TYPE_CHECKING
from tools.douban_tool import search_douban_book
from tools.resource_tool import search_digital_resource
from tools.library_tool import search_library_collection

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def fetch_book_details(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 获取书籍详情并构建卡片（推荐和找书共用）

    1. 并行调用豆瓣、馆藏、电子资源工具
    2. 构建书籍卡片数据
    3. 过滤无资源的书籍
    """
    logger.info("📍 节点: fetch_book_details")

    books = state.get("recommended_books", [])
    dialogue_part = state.get("dialogue_response", "")

    logger.info(f"📚 接收到的书籍列表: {books}")
    logger.info(f"📚 书籍数量: {len(books)}")

    if not books:
        logger.warning("没有书籍需要获取详情")
        state["book_cards"] = []
        state["final_response"] = dialogue_part
        return state

    # 并行获取所有书籍的详细信息并构建卡片
    # 超过5本书时不获取豆瓣信息以提升性能
    fetch_douban = len(books) <= 5
    tasks = [_fetch_single_book_detail(book, fetch_douban) for book in books]
    all_books_detail = await asyncio.gather(*tasks)

    # 过滤有效结果并去重，同时构建书籍卡片
    book_cards = []
    books_without_resources = []
    seen_books = set()
    book_titles = []

    for i, detail in enumerate(all_books_detail):
        original_book = books[i]

        # 如果没有获取到详情，记录为未找到
        if not detail or not detail.get("title"):
            books_without_resources.append({
                "title": original_book.get("title", ""),
                "author": original_book.get("author", "")
            })
            continue

        book_key = (detail["title"], detail["author"])
        if book_key in seen_books:
            continue

        seen_books.add(book_key)
        book_titles.append(f"《{detail.get('title', '')}》")

        # 解析电子资源并按平台分组
        resources = _group_resources_by_source(detail.get("digital_resources", "[]"))

        # 解析馆藏信息
        library_items = _format_library_info(detail.get("library_info", "[]"))

        has_library = library_items is not None and len(library_items) > 0
        has_resources = len(resources) > 0

        # 如果既没有馆藏也没有电子资源，放入无资源列表
        if not has_library and not has_resources:
            books_without_resources.append({
                "title": detail.get("title", ""),
                "author": detail.get("author", "")
            })
        else:
            # 构建卡片数据
            book_cards.append({
                **detail,  # 直接展开所有字段
                "hasLibrary": has_library,
                "libraryItems": library_items or [],
                "hasResources": has_resources,
                "resources": resources
            })

    state["book_cards"] = book_cards
    state["books_without_resources"] = books_without_resources
    logger.info(f"✓ 获取 {len(book_cards)} 本书籍的详细信息")

    # 格式化最终响应（用于保存到记忆）
    books_text = "、".join(book_titles) if book_titles else ""

    if dialogue_part and books_text:
        final_response = f"{dialogue_part}\n\n推荐书籍：{books_text}"
    elif dialogue_part:
        final_response = dialogue_part
    elif books_text:
        final_response = f"推荐书籍：{books_text}"
    else:
        final_response = ""

    state["final_response"] = final_response
    logger.info("✓ 书籍详情获取完成")

    return state


async def _fetch_single_book_detail(book: Dict, fetch_douban: bool = True) -> Optional[Dict]:
    """
    获取单本书的详细信息（并行调用三个工具）

    Args:
        book: 书籍信息 {"title": "", "author": "", "reason": ""}
        fetch_douban: 是否获取豆瓣信息

    Returns:
        书籍详情字典，包含所有字段
    """

    title = book.get("title", "")
    author = book.get("author", "")
    reason = book.get("reason", "")

    if not title:
        return None

    try:
        # 并行调用三个工具
        tasks = [
            asyncio.to_thread(search_digital_resource.invoke, {"title": title, "author": author}),
            asyncio.to_thread(search_library_collection.invoke, {"title": title, "author": author})
        ]

        # 只有在需要时才获取豆瓣信息
        if fetch_douban:
            tasks.append(asyncio.to_thread(search_douban_book.invoke, {"title": title, "author": author}))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 解析结果
        digital_resources = results[0] if not isinstance(results[0], Exception) else "[]"
        library_info = results[1] if not isinstance(results[1], Exception) else "[]"
        douban_info = results[2] if fetch_douban and len(results) > 2 and not isinstance(results[2], Exception) else "{}"

        # 解析豆瓣信息
        douban_data = {}
        if douban_info and douban_info != "{}":
            try:
                parsed_douban = json.loads(douban_info)
                # 豆瓣数据格式: {'books': [...]}，取第一本书
                books = parsed_douban.get('books', [])
                if isinstance(books, list) and len(books) > 0:
                    douban_data = books[0]
            except Exception as e:
                logger.error(f"解析豆瓣数据失败 ({title}): {e}")
                   

        # 构建完整的书籍详情
        book_detail = {
            "title": title,
            "author": author,
            "reason": reason,
            "rating": douban_data.get("rating", ""),
            "image": douban_data.get("cover_url", ""),  # 前端使用 image 字段
            "publisher": douban_data.get("publisher", ""),
            "pubdate": douban_data.get("pubdate", ""),
            "isbn": douban_data.get("isbn", ""),
            "summary": douban_data.get("summary", ""),
            "digital_resources": digital_resources,
            "library_info": library_info
        }

        return book_detail

    except Exception as e:
        logger.error(f"获取书籍详情失败 ({title}): {e}")
        return None


def _format_library_info(library_info_json: str) -> Optional[List[Dict]]:
    """格式化馆藏信息为前端需要的格式"""
    try:
        library_list = json.loads(library_info_json)
        if library_list and len(library_list) > 0:
            lib_items = []
            for lib in library_list:
                library = lib.get("library", "")
                call_number = lib.get("call_number", "")
                location = lib.get("location", "")
                status = lib.get("status", "")
                total = lib.get("total", 0)
                available = lib.get("available", 0)

                lib_items.append({
                    'library': library,
                    'call_number': call_number,
                    'location': location,
                    'status': status,
                    'total': total,
                    'available': available
                })
            return lib_items
        else:
            return None
    except Exception as e:
        logger.error(f"格式化馆藏信息失败: {e}")
        return None


def _group_resources_by_source(digital_resources_json: str) -> List[Dict]:
    """将电子资源按平台分组"""
    resources_by_source = {}
    try:
        resource_list = json.loads(digital_resources_json)
        for r in resource_list:
            source = r.get("source", "")
            if source:
                if source not in resources_by_source:
                    resources_by_source[source] = []
                resources_by_source[source].append({
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "author": r.get("author", ""),
                    "publisher": r.get("publisher", "")
                })
    except Exception as e:
        logger.error(f"解析电子资源失败: {e}")

    # 转换为数组格式
    return [
        {"source": source, "books": books_list}
        for source, books_list in resources_by_source.items()
    ]
