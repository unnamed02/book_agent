from langchain_core.tools import tool
from bs4 import BeautifulSoup
import requests
import logging
import re
import json
from rapidfuzz import fuzz
from typing import TypedDict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResourceResult(TypedDict):
    """数字资源搜索结果的标准结构"""
    source: str      # 资源来源平台
    title: str       # 书名
    author: str      # 作者
    publisher: str   # 出版社（可选）
    link: str        # 资源链接
    isbn: str        # ISBN（可选）

@tool
def search_digital_resource(publisher: str, title: str, author: str, isbn: str) -> str:
    """根据出版社、书名、作者、ISBN搜索数字资源"""
    logger.info(f"搜索电子资源 - 书名: {title}, 出版社: {publisher}, 作者: {author}, ISBN: {isbn}")

    # 合并掌阅和畅想之星的搜索结果
    zhangyue_list = json.loads(search_zhangyue_resource(title, author))
    cxstar_list = json.loads(search_cxstar_resource(title, author, isbn))
    chineseall_list = json.loads(search_chineseall_resource(title ,author,isbn))

    raw_result = json.dumps(zhangyue_list + cxstar_list + chineseall_list, ensure_ascii=False)
    return filter_resources_with_llm(raw_result, title, author)


def filter_resources_with_llm(raw_result: str, title: str, author: str) -> str:
    """使用 LLM 过滤搜索结果，只保留相关的"""
    try:
        results = json.loads(raw_result)
        if not results:
            return raw_result

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        prompt = f"""从以下JSON数组中，筛选出所有与《{title}》作者{author}相关的资源。
搜索结果：
{raw_result}


只返回筛选后的JSON数组，保持原格式。"""

        filtered = llm.invoke(prompt).content.strip()
        filtered = re.sub(r'```json\s*|\s*```', '', filtered).strip()
        json.loads(filtered)
        return filtered
    except:
        return raw_result


def search_zhangyue_resource(title: str, author: str = "", isbn: str = "") -> str:
    """搜索掌阅资源"""
    logger.info(f"开始搜索掌阅资源: {title}, 作者: {author}, ISBN: {isbn}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        all_results: list[ResourceResult] = []

        # 用书名搜索
        url = f"https://se.zhangyue.com/search/index?appId=0ad6dfa1&keyword={title}"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', title.lower())

        # 查找所有书籍链接 - 结构是 <a href="..."><li>...</li></a>
        book_links = soup.select('ul.pagelist a[href*="/book/detail"]')[:20]

        for link_tag in book_links:
            link = link_tag.get('href', '')

            # 提取书名
            bookname_div = link_tag.select_one('div.bookname')
            title_text = bookname_div.get_text(strip=True) if bookname_div else ''

            # 提取作者
            author_div = link_tag.select_one('div.bk_author')
            author_text = author_div.get_text(strip=True) if author_div else ''

            # 提取出版社
            publisher_div = link_tag.select_one('div.bk_publisher')
            publisher_text = publisher_div.get_text(strip=True) if publisher_div else ''

            if title_text and link:
                normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', title_text.lower())

                # 使用 rapidfuzz 计算相似度（partial_ratio 适合部分匹配）
                title_similarity = fuzz.partial_ratio(normalized_search, normalized_title)

                # 相似度阈值 80 以上才添加
                if title_similarity >= 80:
                    result: ResourceResult = {
                        "source": "掌阅电子书平台",
                        "title": title_text,
                        "author": author_text,
                        "publisher": publisher_text,
                        "isbn": "",  # 掌阅搜索结果不包含ISBN
                        "link": link if link.startswith('http') else f"https://se.zhangyue.com{link}"
                    }
                    all_results.append(result)

        unique_results: list[ResourceResult] = []
        seen = set()
        for item in all_results:
            key = item["link"]
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return json.dumps(unique_results, ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps([], ensure_ascii=False)

def search_cxstar_resource(title: str, author: str = "", isbn: str = "") -> str:
    """搜索畅想之星资源"""
    logger.info(f"开始搜索畅想之星资源: {title}, 作者: {author}, ISBN: {isbn}")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }
        all_results: list[ResourceResult] = []

        # 畅想之星 API 地址
        api_url = "https://www.cxstar.com/esapi/Book/AdvancedSearch"

        # 构建搜索条件
        payload = {
            "searchType": 0,
            "pinst": "1ad691ca0000cc0bce",  # 机构ID，可能需要根据实际情况调整
            "pubdate": "",
            "page": 1,
            "size": 20,
            "publisher": "",
            "type": "",
            "author": author if author else "",
            "sortField": "ORDERNO",
            "sortType": "ASC",
            "aggs": True,
            "searchData": {
                "clauses": [
                    {
                        "field": "Title",
                        "value1": title,
                        "operator": "AND",
                        "value2": "",
                        "type": "Contain",
                        "outOperator": "DEFAULT"
                    }
                ],
                "isbn": isbn if isbn else "",
                "pubStart": "",
                "pubEnd": "",
                "shelfStart": "",
                "shelfEnd": "",
                "readerObject": "",
                "type": [""]
            },
            "ifbg": "0"
        }

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        data = response.json()

        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', title.lower())

        # 解析返回的数据
        for item in data.get("data", []):
            item_title = item.get("title", "")
            # 移除 HTML 标签（如 <em>）
            item_title = re.sub(r'<[^>]+>', '', item_title)

            item_author = item.get("author", "")
            # 移除 HTML 标签
            item_author = re.sub(r'<[^>]+>', '', item_author)

            item_publisher = item.get("publisher", "")
            item_isbn = item.get("isbn", "").replace('-','')
            item_ruid = item.get("ruid", "")

            if item_title:
                normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', item_title.lower())

                # 使用 rapidfuzz 计算相似度
                title_similarity = fuzz.partial_ratio(normalized_search, normalized_title)

                # 相似度阈值 80 以上才添加
                if title_similarity >= 80:
                    result: ResourceResult = {
                        "source": "畅想之星电子书平台",
                        "title": item_title,
                        "author": item_author,
                        "publisher": item_publisher,
                        "isbn": item_isbn,
                        "link": f"https://www.cxstar.com/Book/Detail?ruid={item_ruid}"
                    }
                    all_results.append(result)

        unique_results: list[ResourceResult] = []
        seen = set()
        for item in all_results:
            key = item["link"]
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return json.dumps(unique_results, ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps([], ensure_ascii=False)

def search_chineseall_resource(title: str, author: str = "", isbn: str = "") -> str:
    """搜索中文在线（书香陕西）资源"""
    logger.info(f"开始搜索中文在线资源: {title}, 作者: {author}, ISBN: {isbn}")
    try:
        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json",
            "Connection": "keep-alive",
            "Origin": "https://shanxist.chineseall.cn",
            "Referer": "https://shanxist.chineseall.cn/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "Sx-Token": "G14FvPx0gOXB76S7915I1o3125T1JaC0",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
        }
        all_results: list[ResourceResult] = []

        # 中文在线（书香陕西）API 地址 - URL参数直接拼接
        api_url = "https://shanxist.cahd.chineseall.cn/book/searchBook?searchkey=&page=1&pageSize=15&categoryIds=&publishDates=&publishers=&sortType=0"

        # 构建搜索条件
        payload = []

        # 添加书名搜索条件
        if title:
            payload.append({
                "field": "name",
                "logicOperator": "AND",
                "matchType": "FUZZY",
                "value": title
            })

        # 添加作者搜索条件
        if author:
            payload.append({
                "field": "author",
                "logicOperator": "AND",
                "matchType": "FUZZY",
                "value": author
            })

        # 如果没有任何搜索条件，返回空结果
        if not payload:
            return json.dumps([], ensure_ascii=False)

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        data = response.json()

        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', title.lower())

        # 解析返回的数据
        for item in data.get("list", []):
            item_title = item.get("name", "")
            # 移除 HTML 标签（如 <span class="search_key_highlight">）
            item_title = re.sub(r'<[^>]+>', '', item_title)

            item_author = item.get("author", "")
            # 移除 HTML 标签
            item_author = re.sub(r'<[^>]+>', '', item_author)

            item_publisher = item.get("publisher", "")
            item_isbn = item.get("isbn", "").replace('-', '')
            item_shid = item.get("shId", "")

            if item_title:
                normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', item_title.lower())

                # 使用 rapidfuzz 计算相似度
                title_similarity = fuzz.partial_ratio(normalized_search, normalized_title)

                # 相似度阈值 80 以上才添加
                if title_similarity >= 80:
                    result: ResourceResult = {
                        "source": "书香陕西图书馆（中文在线）",
                        "title": item_title,
                        "author": item_author,
                        "publisher": item_publisher,
                        "isbn": item_isbn,
                        "link": f"https://shanxist.chineseall.cn/book/detail/{item_shid}"
                    }
                    all_results.append(result)

        unique_results: list[ResourceResult] = []
        seen = set()
        for item in all_results:
            key = item["link"]
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return json.dumps(unique_results, ensure_ascii=False)
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return json.dumps([], ensure_ascii=False)


if __name__ == "__main__":
    print("=== 测试搜索电子资源 ===")

    result = search_zhangyue_resource("蛤蟆先生去看心理学医生", "罗伯特·戴博德")
    print(result)
    
    result = search_cxstar_resource("Python编程从入门到实践","Eric Matthes")
    print(result)

    result = search_chineseall_resource("机械设计手册","成大先")
    print(result)
    
    # result = search_digital_resource.invoke({
    #     "publisher": "",
    #     "title": "蛤蟆先生去看心理学医生",
    #     "author": "罗伯特·戴博德",
    #     "isbn": ""
    # })    
    
    # print(result)
