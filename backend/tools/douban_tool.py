import requests
import logging
import urllib3
import os
import re
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOUBAN_API_KEY = os.getenv("DOUBAN_API_KEY", "")

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


def search_douban_book(title: str, author: str, use_llm_optimize: bool = True) -> Dict:
    """搜索豆瓣图书评分和评价，返回最佳匹配的书籍信息

    Returns:
        包含 title, rating, subtitle, uri, cover_url 的字典，如果未找到则返回空字典
    """
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

        # 获取第一个结果
        items = data.get("items", [])
        if items:
            target = items[0].get("target", {})
            return {
                "title": target.get("title", ""),
                "rating": target.get("rating", {}).get("value", ""),
                "cover_url": target.get("cover_url", ""),
                "publisher": target.get("publisher", ""),
                "pubdate": target.get("pubdate", ""),
                "isbn": target.get("isbn", ""),
                "subtitle": target.get("card_subtitle", ""),
                "uri": target.get("uri", "").split("/")[-1] if target.get("uri") else ""
            }
        else:
            logger.info(f"未找到《{title}》的豆瓣信息")
            return {}
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return {}

if __name__ == "__main__":
    result = search_douban_book("红楼梦", "曹雪芹")
    print(result)
    
