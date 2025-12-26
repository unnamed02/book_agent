import httpx
import json
from urllib.parse import quote
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import logging

logger = logging.getLogger(__name__)

# API配置
ISBN_API_BASE = "https://data.isbn.work/openApi/book"
APP_KEY = "dd5e744f6bc348bd87188de4c4d15749"

def extract_book_name(book_name: str) -> str:
    """提取书名，去掉版本号"""
    if not book_name:
        return ""

    try:
        llm = ChatOpenAI(model="Qwen3-8B", temperature=0)
        prompt = f"""从以下书名中去掉版本号信息（如"第X版"、"单行本"等），只保留核心书名。
只返回书名，不要其他内容。

书名：{book_name}"""

        result = llm.invoke(prompt).content.strip()
        return result if result else book_name
    except Exception:
        # 如果 LLM 调用失败（如缺少 API key），直接返回原书名
        return book_name

def _parse_book_record(record: dict, expected_author: str = "") -> dict | None:
    """解析单条书籍记录，如果指定了作者则进行过滤

    Args:
        record: 原始书籍记录
        expected_author: 期望的作者名（用于过滤）

    Returns:
        解析后的书籍字典，如果不匹配作者则返回 None
    """
    book = {
        "isbn": record.get("isbn", ""),
        "title": record.get("bookName", ""),
        "author": record.get("author", ""),
        "publisher": record.get("press", ""),
        "press_date": record.get("pressDate", ""),
        "price": record.get("price", 0) / 100 if record.get("price") else 0,  # 价格转换为元
        "image": record.get("pictures", "[]"),  # JSON字符串数组
        "clc_code": record.get("clcCode", ""),
        "clc_name": record.get("clcName", ""),
        "binding": record.get("binding", ""),
        "pages": record.get("pages", ""),
        "format": record.get("format", ""),
        "edition": record.get("edition", ""),
        "book_desc": record.get("bookDesc", "")
    }

    # 解析图片URL
    try:
        images = json.loads(book["image"])
        book["image"] = images[0] if images else ""
    except:
        book["image"] = ""

    # 如果指定了作者，进行过滤
    if expected_author:
        book_author = book["author"].lower().replace(" ", "").replace("，", "").replace(",", "")
        expected = expected_author.lower().replace(" ", "").replace("，", "").replace(",", "")
        # 检查作者名是否包含或被包含
        if expected not in book_author and book_author not in expected:
            return None

    return book

@tool
def search_isbn_book(book_name: str, author: str = "") -> list[dict]:
    """
    通过书名和作者搜索图书信息，如果有多页结果会获取所有页

    Args:
        book_name: 书名
        author: 作者名（可选）

    Returns:
        书籍列表（list of dict）
    """
    book_name = extract_book_name(book_name)
    try:
        url = f"{ISBN_API_BASE}/page"

        # 第一次请求获取总页数
        params = {
            "current": 1,
            "size": 10,
            "bookName": book_name,
            "appKey": APP_KEY
        }

        if author:
            params["author"] = author

        response = httpx.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if not data.get("success"):
            return []

        records = data.get("data", {}).get("records", [])
        total_pages = int(data.get("data", {}).get("pages", 1))

        # 解析第一页的书籍，并应用作者过滤
        books = [book for book in (_parse_book_record(record, author) for record in records) if book is not None]

        # 如果有多页，继续获取其他页
        if total_pages > 1:
            for page in range(2, min(total_pages + 1, 6)):  # 最多获取5页，避免请求过多
                params["current"] = page
                try:
                    response = httpx.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()

                    if data.get("success"):
                        records = data.get("data", {}).get("records", [])
                        # 同样应用作者过滤
                        page_books = [book for book in (_parse_book_record(record, author) for record in records) if book is not None]
                        books.extend(page_books)
                except Exception as e:
                    logger.warning(f"获取第{page}页时出错: {e}")
                    continue

        return books

    except httpx.TimeoutException:
        logger.error("ISBN API 请求超时")
        return []
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP错误: {e.response.status_code}")
        return []
    except Exception as e:
        logger.error(f"搜索出错: {e}")
        return []


if __name__ == "__main__":
    # 测试搜索
    logging.basicConfig(level=logging.INFO)
    logger.info("测试搜索:")
    result = search_isbn_book.invoke({"book_name": "三体", "author": "刘慈欣"})
    logger.info(f"找到 {len(result)} 本书")
    for i, book in enumerate(result, 1):
        logger.info(f"{i}. {book['title']} / {book['author']} / {book['publisher']}")
