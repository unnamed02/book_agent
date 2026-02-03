from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import requests
import logging
import urllib3
import json
import os
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOUBAN_API_KEY = os.getenv("DOUBAN_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def optimize_query(query: str) -> str:
    """优化豆瓣搜索query"""

    llm = ChatOpenAI(model="Qwen3-8B", temperature=0)
    prompt = f"""请优化以下图书搜索query，使豆瓣搜索更精准：

优化规则：
1. 书名处理：
   - 去掉版本号（如"第3版"、"修订版"、"珍藏版"等）
   - 去掉副标题（保留主标题）

2. 作者处理：
   - 先去掉"著"、"编"、"译"、"续"等后缀词
   - 如有多个作者（用逗号、顿号、"与"等分隔），只保留第一个
   - 去掉外国作者的音译名（如"埃里克·马瑟斯"、"Joshua Bloch"等）
   - 对于家喻户晓的经典名著，如果作者是原作者，去掉作者名以提高搜索准确率
     示例：
     * 「红楼梦 曹雪芹」→「红楼梦」（经典名著原作者）
     * 「三国演义 罗贯中」→「三国演义」（经典名著原作者）
     * 「红楼梦 刘心武」→「红楼梦 刘心武」（续作/点评者，需保留）
     * 「Python编程从入门到实践 埃里克」→「Python编程从入门到实践」（外国作者）

只返回优化后的query，不要任何解释或其他内容。

原query：{query}
优化后："""

    result = llm.invoke(prompt).content.strip()
    logger.info(f"Query优化: '{query}' -> '{result}'")
    return result

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

def extract_title(title: str) -> str:
    """提取书名，去掉版本号"""
    if not title:
        return ""

    llm = ChatOpenAI(model="Qwen3-8B", temperature=0)
    prompt = f"""从以下书名中去掉版本号信息（如"第X版"、"单行本"等），只保留核心书名。
只返回书名，不要其他内容。

书名：{title}"""

    result = llm.invoke(prompt).content.strip()
    return result if result else title


@tool
def search_douban_book(title: str, author: str, use_llm_optimize: bool = True) -> str:
    """搜索豆瓣图书评分和评价 返回三个结果，选其中标题最接近，出版时间最新的，有评分的使用"""
    if use_llm_optimize:
        query = optimize_query(f"{title} {author}")
    else:
        query = f"{title} {author}"

    logger.info(f"开始搜索图书: {query}")
    try:
        url = f"https://frodo.douban.com/api/v2/search/book?q={query}&count=3&apiKey={DOUBAN_API_KEY}"
        headers = {
            "Referer": "https://servicewechat.com/wx2f9b06c1de1ccfca/91/page-frame.html",
            "User-Agent": "MicroMessenger/"
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        data = response.json()

        logger.info(f"*** {response} ***")
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
        return json.dumps({"books": results}, ensure_ascii=False) if results else json.dumps({"error": f"未找到《{title}》的信息"}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@tool
def get_douban_book_detail(uri: str, use_llm_optimize: bool = True) -> str:
    """获取豆瓣图书详情，包括简介和评价"""
    logger.info(f"开始获取图书详情: {uri}")
    try:
        url = f"https://api.douban.com/v2/book/{uri}"
        params = {"apiKey": DOUBAN_API_KEY}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, params=params, headers=headers, timeout=10, verify=False)
        data = response.json()

        title_raw = data.get("title", "")
        author_raw = data.get("author", "")

        logger.info(f"*** {response} ***")
        if use_llm_optimize:
            title = extract_title(str(title_raw))
            author = extract_first_author(str(author_raw)) if author_raw else "未知作者"
        else:
            title = str(title_raw) if title_raw else "未知书名"
            # 简单处理作者：取列表第一个，去掉常见后缀
            if isinstance(author_raw, list) and author_raw:
                author = str(author_raw[0])
                # 简单去掉后缀
                import re
                author = re.sub(r'\s*(著|编|译|注|校|主编|编著).*$', '', author).strip()
            else:
                author = str(author_raw) if author_raw else "未知作者"

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

