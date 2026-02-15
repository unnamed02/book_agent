from langchain_core.tools import tool
import requests
import logging
import urllib3
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOUBAN_API_KEY = os.getenv("DOUBAN_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def optimize_query(query: str) -> str:
    """优化豆瓣搜索query - 使用正则表达式替代LLM"""

    # 去掉版本号
    query = re.sub(r'[（(]?第?\s*[0-9一二三四五六七八九十]+\s*版[）)]?', '', query)
    query = re.sub(r'[（(]?修订版|珍藏版|典藏版|精装版|平装版|增订版|新版[）)]?', '', query)

    # 去掉"著"、"编"、"译"、"续"等后缀
    query = re.sub(r'\s*[著编译续注校主编著者]\s*$', '', query)
    query = re.sub(r'\s+[著编译续注校主编著者](?=\s|$)', '', query)

    # 经典名著列表（去掉原作者以提高搜索准确率）
    classics = {
        '红楼梦': ['曹雪芹', '曹雪芹 高鹗'],
        '三国演义': ['罗贯中'],
        '水浒传': ['施耐庵'],
        '西游记': ['吴承恩'],
        '三体': ['刘慈欣']
    }

    for book, authors in classics.items():
        if book in query:
            for author in authors:
                query = query.replace(f'{book} {author}', book)
                query = query.replace(f'{author} {book}', book)

    # 清理多余空格
    query = re.sub(r'\s+', ' ', query).strip()

    logger.info(f"Query优化: '{query}' (正则优化)")
    return query

def extract_first_author(author_string) -> str:
    """提取第一个作者名 - 使用正则表达式"""
    # 处理列表类型
    if isinstance(author_string, list):
        author_string = author_string[0] if author_string else ""

    # 转换为字符串
    author_string = str(author_string) if author_string else ""

    # 处理字符串形式的列表（如 "['吴敬梓']"）
    if author_string.startswith('[') and author_string.endswith(']'):
        # 提取列表中的第一个元素
        match = re.search(r"['\"]([^'\"]+)['\"]", author_string)
        if match:
            author_string = match.group(1)
        else:
            author_string = author_string.strip('[]').strip()

    if not author_string or author_string == "":
        return "未知作者"

    # 去掉后缀
    author = re.sub(r'\s*[（(]?[著编译注校主编著者]+[）)]?\s*$', '', author_string)

    # 提取第一个作者（按常见分隔符）
    author = re.split(r'[,，、;；/]', author)[0].strip()

    return author if author else "未知作者"

def extract_title(title: str) -> str:
    """提取书名，去掉版本号 - 使用正则表达式"""
    if not title:
        return ""

    # 去掉版本号
    title = re.sub(r'[（(]?第?\s*[0-9一二三四五六七八九十]+\s*版[）)]?', '', title)
    title = re.sub(r'[（(]?单行本|修订版|珍藏版|典藏版|精装版|平装版|增订版|新版[）)]?', '', title)

    # 清理多余空格
    title = re.sub(r'\s+', ' ', title).strip()

    return title if title else title


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
            author = extract_first_author(author_raw) if author_raw else "未知作者"
        else:
            title = str(title_raw) if title_raw else "未知书名"
            # 简单处理作者：取列表第一个，去掉常见后缀
            if isinstance(author_raw, list) and author_raw:
                author = str(author_raw[0])
                # 简单去掉后缀
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

