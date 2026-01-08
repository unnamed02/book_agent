import requests
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import logging
import re
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
def search_and_filter_book(book_name: str, author: str = "") -> str:
    """
    搜索新华书店在线商城并使用 LLM 筛选最匹配的书籍

    Args:
        book_name: 书名
        author: 作者（可选）

    Returns:
        JSON 字符串，包含最匹配的书籍信息 {"title": "书名", "author": "作者", "isbn": "ISBN"}
        如果未找到，返回 {"error": "未找到匹配书籍"}
    """
    logger.info(f"开始搜索并筛选: {book_name}, 作者: {author}")

    try:
        # 调用商城 API 搜索（只用书名）
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
        raw_data = response.text

        # 提取所有搜索结果
        book_titles = re.findall(r'"bookTitle":"((?:\\"|[^"])*)"', raw_data)
        isbns = re.findall(r'"isbn":"((?:\\"|[^"])*)"', raw_data)
        authors_list = re.findall(r'"authoreditor":"((?:\\"|[^"])*)"', raw_data)

        if not book_titles:
            return json.dumps({"error": "未找到搜索结果"}, ensure_ascii=False)

        # 构建候选书籍列表
        candidates = []
        for i in range(min(len(book_titles), len(isbns), len(authors_list))):
            clean_title = re.sub(r'<[^>]+>', '', book_titles[i])
            candidates.append({
                "title": clean_title,
                "author": authors_list[i],
                "isbn": isbns[i]
            })

        # 使用 LLM 筛选最匹配的书籍
        logger.info(f"使用 LLM 筛选《{book_name}》的最佳匹配...")
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        filter_prompt = f"""从以下搜索结果中，选择与目标书籍最匹配的一本。

目标书籍：
- 书名：{book_name}
- 作者：{author if author else "未知"}

搜索结果：
{json.dumps(candidates, ensure_ascii=False, indent=2)}

请选择最匹配的书籍，只返回该书籍的索引（0-{len(candidates)-1}）。
如果没有合适的匹配，返回 -1。

只返回数字，不要其他内容。"""

        filter_result = llm.invoke(filter_prompt).content.strip()

        try:
            selected_idx = int(filter_result)
            if 0 <= selected_idx < len(candidates):
                selected = candidates[selected_idx]
                logger.info(f"✓ LLM 选择了索引 {selected_idx}: {selected['title']}")
                return json.dumps(selected, ensure_ascii=False)
            else:
                # LLM 返回 -1，没有合适的匹配
                logger.warning(f"LLM 未找到《{book_name}》的合适匹配")
                return json.dumps({"error": "未找到匹配书籍"}, ensure_ascii=False)
        except ValueError:
            # LLM 返回格式错误，使用第一个结果
            logger.warning(f"LLM 返回格式错误，使用第一个结果")
            return json.dumps(candidates[0], ensure_ascii=False)

    except Exception as e:
        logger.error(f"搜索并筛选失败: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

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
        
        query = f"{book_name} {author}"

        payload = {
            "searchField": "searchAll",
            "searchContent": query,
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
    
        for i in range(min(len(book_titles), len(prices), len(isbns), len(author_editor))):
            title = re.sub(r'<[^>]+>', '', book_titles[i])
         
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
    result = search_online_shop.invoke({"book_name": "Python编程"})
    print(result)
    result = search_online_shop.invoke({"book_name": "机械设计手册", "author": "成大先"})
    print(result)
    result = search_shop_by_isbn.invoke({"isbn": "9787111473947"})
    print(result)
