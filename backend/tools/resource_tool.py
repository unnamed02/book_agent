from bs4 import BeautifulSoup
import requests
import logging
import re
import json
from rapidfuzz import fuzz
from typing import TypedDict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

class ResourceResult(TypedDict):
    """数字资源搜索结果的标准结构"""
    source: str      # 资源来源平台
    title: str       # 书名
    author: str      # 作者
    publisher: str   # 出版社（可选）
    link: str        # 资源链接
    isbn: str        # ISBN（可选）

def llm_filter_resources(results: List[ResourceResult], title: str, author: str) -> List[ResourceResult]:
    """
    使用 LLM 对搜索结果进行智能筛选和排序

    Args:
        results: 原始搜索结果列表
        title: 用户搜索的书名
        author: 用户搜索的作者

    Returns:
        筛选和排序后的结果列表
    """
    if not results:
        return results

    try:
        llm = ChatOpenAI(model="qwen-flash", temperature=0)

        # 构建提示词
        results_text = "\n".join([
            f"{i+1}. 书名: {r['title']}, 作者: {r['author']}, 出版社: {r['publisher']}, 来源: {r['source']}"
            for i, r in enumerate(results)
        ])

        prompt = f"""你是一个图书资源筛选专家。用户正在搜索：
书名: {title}
作者: {author}

以下是搜索到的资源列表：
{results_text}

请根据以下标准对结果进行筛选和排序：
1. 书名和作者的匹配度（优先考虑完全匹配或高度相似）

请返回一个 JSON 数组，包含筛选后的结果序号（从1开始），按推荐优先级排序。
只返回 JSON 数组，不要其他文字说明。格式示例: [1, 3, 2]
如果所有结果都不太匹配，返回空数组: []"""

        # 这里使用同步 invoke，因为此函数在 ThreadPoolExecutor 中执行
        response = llm.invoke([HumanMessage(content=prompt)])

        # 解析 LLM 返回的序号列表
        filtered_indices = json.loads(response.content.strip())

        # 根据序号重新排序结果
        filtered_results = [results[i-1] for i in filtered_indices if 0 < i <= len(results)]

        logger.info(f"LLM 筛选: 原始 {len(results)} 条 -> 筛选后 {len(filtered_results)} 条")
        return filtered_results

    except Exception as e:
        logger.warning(f"LLM 筛选失败: {e}，返回原始结果")
        return results

def search_digital_resource(title: str, author: str) -> List[ResourceResult]:
    """根据书名、作者搜索数字资源

    Returns:
        资源列表，每项包含 source, title, author, publisher, link, isbn
    """
    logger.info(f"搜索电子资源 - 书名: {title}, 作者: {author}")

    # 使用线程池并发执行搜索任务
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_zhangyue = executor.submit(search_zhangyue_resource, title, author)
        future_chineseall = executor.submit(search_chineseall_resource, title, author)

        # 获取结果
        zhangyue_list = future_zhangyue.result()
        chineseall_list = future_chineseall.result()

    # 合并所有结果
    all_results = zhangyue_list + chineseall_list

    # 使用 LLM 进行智能筛选
    filtered_results = llm_filter_resources(all_results, title, author)

    return filtered_results

def search_zhangyue_resource(title: str, author: str = "") -> List[ResourceResult]:
    """搜索掌阅资源"""
    logger.info(f"开始搜索掌阅资源: {title}, 作者: {author}")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        all_results: list[ResourceResult] = []

        # 用书名搜索
        url = f"https://se.zhangyue.com/search/index?appId=bec9564c&keyword={title}"
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
                author_similarity = fuzz.partial_ratio(author,author_text)

                # 相似度阈值 80 以上才添加
                if title_similarity >= 80 and author_similarity >= 80:
                    # 将 detail 链接转换为 read 链接
                    if '/book/detail' in link and 'bookId=' in link:
                        book_id = re.search(r'bookId=(\d+)', link).group(1)
                        read_link = f"https://s.zhangyue.com/read?bid={book_id}&appId=bec9564c"
                    else:
                        read_link = link if link.startswith('http') else f"https://se.zhangyue.com{link}"

                    result: ResourceResult = {
                        "source": "掌阅精选",
                        "title": title_text,
                        "author": author_text,
                        "publisher": publisher_text,
                        "isbn": "",
                        "link": read_link
                    }
                    all_results.append(result)

        unique_results: list[ResourceResult] = []
        seen = set()
        for item in all_results:
            key = item["link"]
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return unique_results
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return []

def search_cxstar_resource(title: str, author: str = "") -> str:
    """搜索畅想之星资源"""
    logger.info(f"开始搜索畅想之星资源: {title}, 作者: {author}")
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
                "isbn": "",
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

        return unique_results
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return []

def search_chineseall_resource(title: str, author: str = "") -> List[ResourceResult]:
    """搜索中文在线（书香陕西）资源"""
    logger.info(f"开始搜索中文在线资源: {title}, 作者: {author}")
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
            "Sx-Token": "0f6YHg4mo7F4e357u4B5VW259971Z451",
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
            return []

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
            
            logger.info(item_shid)

            if item_title:
                normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\\s]', '', item_title.lower())

                # 使用 rapidfuzz 计算相似度
                title_similarity = fuzz.partial_ratio(normalized_search, normalized_title)

                # 相似度阈值 80 以上才添加
                if title_similarity >= 80:
                    result: ResourceResult = {
                        "source": "中文在线",
                        "title": item_title,
                        "author": item_author,
                        "publisher": item_publisher,
                        "isbn": item_isbn,
                        "link": f"https://beilin.w.chineseall.cn/book/detail/{item_shid}?topicCode=dbgf_1_0_2_81"
                    }
                    all_results.append(result)

        unique_results: list[ResourceResult] = []
        seen = set()
        for item in all_results:
            key = item["link"]
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return unique_results
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        return []


if __name__ == "__main__":
    print("=== 测试搜索电子资源 ===")

    # result = search_zhangyue_resource("蛤蟆先生去看心理学医生", "罗伯特·戴博德")
    # print(result)
    
    # result = search_cxstar_resource("Python编程从入门到实践","Eric Matthes")
    # print(result)

    result = search_chineseall_resource("我只要少许","简")
    print(result)

    # result = search_digital_resource("机械设计手册", "成大先")
    # print(result)
