from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import requests
import logging
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_first_author(author_string: str) -> str:
    """提取第一个作者名"""
    if isinstance(author_string, list):
        author_string = author_string[0] if author_string else ""

    if not author_string or author_string == "":
        return "未知作者"

    llm = ChatOpenAI(model="Qwen3-8B", temperature=0)
    prompt = f"""从以下作者信息中提取第一个作者的名字，去掉"编"、"著"、"译"、"注"、"校"、"主编"、"编著"等后缀。
只返回作者名字，不要其他内容。

作者信息：{author_string}"""

    result = llm.invoke(prompt).content.strip()
    return result if result else "未知作者"

def extract_book_name(book_name: str) -> str:
    """提取书名，去掉版本号"""
    if not book_name:
        return ""

    llm = ChatOpenAI(model="Qwen3-8B", temperature=0)
    prompt = f"""从以下书名中去掉版本号信息（如"第X版"、"单行本"等），只保留核心书名。
只返回书名，不要其他内容。

书名：{book_name}"""

    result = llm.invoke(prompt).content.strip()
    return result if result else book_name


@tool
def search_douban_book(book_name: str,author: str) -> str:
    """搜索豆瓣图书评分和评价 返回三个结果，选其中标题最接近，出版时间最新的，有评分的使用"""
    query = f"{book_name} {author}"
    logger.info(f"开始搜索图书: {query}")
    try:
        url = f"https://frodo.douban.com/api/v2/search/book?q={query}&count=3&apiKey=0ac44ae016490db2204ce0a042db2916"
        headers = {
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html",
            "User-Agent": "MicroMessenger/"
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        data = response.json()

        results = []
        for item in data.get("items", []):
            target = item.get("target", {})
            results.append({
                "title": target.get("title", "未知书名"),
                "rating": target.get("rating", {}).get("value", "暂无评分"),
                "subtitle": target.get("card_subtitle", ""),
                "uri": target.get("uri", "").split("/")[-1]
            })
        logger.info(results)
        return json.dumps({"books": results}, ensure_ascii=False) if results else json.dumps({"error": f"未找到《{book_name}》的信息"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def get_douban_book_detail(uri: str) -> str:
    """获取豆瓣图书详情，包括简介和评价"""
    logger.info(f"开始获取图书详情: {uri}")
    try:
        url = f"https://api.douban.com/v2/book/{uri}"
        params = {"apiKey": "0ac44ae016490db2204ce0a042db2916"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
        data = response.json()
        
        title_raw = data.get("title", "")
        title = extract_book_name(str(title_raw))
        author_raw = data.get("author", "")
        author = extract_first_author(str(author_raw)) if author_raw else "未知作者"

       
        return json.dumps({
            "title": title,
            "author": author,
            "publisher": data.get("publisher", ""),
            "rating": data.get("rating", {}).get("average", ""),
            "isbn": data.get("isbn13", ""),
            "summary": data.get("summary", ""),
            "image": data.get("image", "")
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"获取失败: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

if __name__ == "__main__":
    print("=== 测试搜索图书 ===")
    result = search_douban_book("Python编程")
    print(result)

    print("\n=== 测试获取详情 ===")
    result2 = get_douban_book_detail("36365320")
    print(result2)


