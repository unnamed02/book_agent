import requests
from langchain_core.tools import tool
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
def search_shop_by_isbn(isbn: str) -> str:
    """通过ISBN搜索文轩"""
    logger.info(f"开始通过ISBN搜索在线商城: {isbn}")
    try:
        import json
        api_url = "https://fx.cnpdx.com/fxpms/commodity/pageQuery"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json;charset=UTF-8"
        }

        payload = {
            "searchField": "searchAll",
            "searchContent": isbn,
            "page": 1,
            "rows": 5
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        data = response.text

        # 提取书名、价格、ISBN、作者
        book_titles = re.findall(r'"bookTitle":"((?:\\"|[^"])*)"', data)
        prices = re.findall(r'"price":((?:\\"|[^"])*),', data)
        isbns = re.findall(r'"isbn":"((?:\\"|[^"])*)"', data)
        authors = re.findall(r'"authoreditor":"((?:\\"|[^"])*)"', data)

        results = []
        for i in range(min(len(book_titles), len(prices), len(isbns), len(authors))):
            if isbn in isbns[i]:
                title = re.sub(r'<[^>]+>', '', book_titles[i])
                results.append({
                    "source": "新华书店在线商城",
                    "title": title,
                    "price": f"¥{prices[i]}",
                    "link": "https://fx.cnpdx.com/s_fxpms/query"
                })

        return json.dumps(results[:3], ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps([], ensure_ascii=False)

@tool
def search_online_shop(book_name: str, author: str = "") -> str:
    """搜索新华书店在线商城购买链接"""
    logger.info(f"开始搜索在线商城: {book_name}, 作者: {author}")
    try:
        import json
        api_url = "https://fx.cnpdx.com/fxpms/commodity/pageQuery"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json;charset=UTF-8"
        }

        payload = {
            "searchField": "searchAll",
            "searchContent": book_name,
            "page": 1,
            "rows": 10
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        data = response.text

        # 提取书名、价格、ISBN、作者
        book_titles = re.findall(r'"bookTitle":"((?:\\"|[^"])*)"', data)
        prices = re.findall(r'"price":((?:\\"|[^"])*),', data)
        isbns = re.findall(r'"isbn":"((?:\\"|[^"])*)"', data)
        author_editor = re.findall(r'"authoreditor":"((?:\\"|[^"])*)"', data)

        results = []
        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', book_name.lower())
        normalized_author = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', author.lower()) if author else ''

        for i in range(min(len(book_titles), len(prices), len(isbns), len(author_editor))):
            title = re.sub(r'<[^>]+>', '', book_titles[i])
            normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', title.lower())
            normalized_author_text = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', author_editor[i].lower())

            title_match = normalized_search in normalized_title or normalized_title in normalized_search
            author_match = not normalized_author or normalized_author in normalized_author_text

            if title_match and author_match:
                results.append({
                    "source": "新华书店在线商城",
                    "title": title,
                    "price": f"¥{prices[i]}",
                    "link": "https://fx.cnpdx.com/s_fxpms/query"
                })

        return json.dumps(results[:5], ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps([], ensure_ascii=False)

if __name__ == "__main__":
    print("=== 测试搜索在线商城 ===")
    result = search_online_shop("Python编程")
    print(result)
    result = search_online_shop.invoke({"book_name": "机械设计手册", "author": "成大先"})
    print(result)
    result = search_shop_by_isbn("9787111473947")
    print(result)
