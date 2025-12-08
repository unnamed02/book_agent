import requests
from langchain.tools import tool
import logging
from bs4 import BeautifulSoup
import re
from langchain_openai import ChatOpenAI
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@tool
def search_digital_resource(publisher: str, book_name: str, author: str, isbn: str) -> str:
    """根据出版社 书名 作者 isbn 搜索数字资源"""
    logger.info(f"搜索电子资源 - 书名: {book_name}, 出版社: {publisher}, 作者: {author}, ISBN: {isbn}")

    if "化学工业" in publisher or "化工" in publisher:
        raw_result = search_cidp_resource(book_name, author, isbn)
    elif "人邮" in publisher or "人民邮电" in publisher or "邮电" in publisher:
        raw_result = search_ry_resouce(book_name, author, isbn)
    else:
        return json.dumps([], ensure_ascii=False)

    return filter_resources_with_llm(raw_result, book_name, author)

def filter_resources_with_llm(raw_result: str, book_name: str, author: str) -> str:
    """使用 LLM 过滤搜索结果，只保留相关的"""
    try:
        results = json.loads(raw_result)
        if not results:
            return raw_result

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        prompt = f"""从以下JSON数组中，筛选出与《{book_name}》作者{author}最相关的资源。
如果是单本书，返回最准确的1个结果；如果是丛书，返回全部相关结果。

搜索结果：
{raw_result}

只返回筛选后的JSON数组，保持原格式。"""

        filtered = llm.invoke(prompt).content.strip()
        filtered = re.sub(r'```json\s*|\s*```', '', filtered).strip()
        json.loads(filtered)
        return filtered
    except:
        return raw_result

def search_cidp_resource(book_name: str, author: str = "", isbn: str = "") -> str:
    """搜索化工出版社资源"""
    logger.info(f"开始搜索化工社资源: {book_name}, 作者: {author}, ISBN: {isbn}")
    try:
        import re
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        all_results = []

        # 如果有ISBN，先用ISBN搜索
        if isbn:
            url = f"https://www.cidp.com.cn/web/normalRetrieval/All?searchq={isbn}"
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')

            for tr in soup.select('tr[onclick]')[:5]:
                onclick = tr.get('onclick', '')
                link = onclick.split("'")[1] if "'" in onclick else ''
                title = tr.select_one('td[title]')
                author_td = tr.select('td')[1] if len(tr.select('td')) > 1 else None
                if title and link:
                    author_text = author_td.get_text(strip=True) if author_td else ''
                    author_text = ' '.join(author_text.split())
                    all_results.append({
                        "source": "CIDP制造业数字资源平台",
                        "title": title.get('title'),
                        "author": author_text,
                        "link": f"https://www.cidp.com.cn{link}"
                    })

        # 用书名和作者搜索
        url = f"https://www.cidp.com.cn/web/normalRetrieval/All?searchq={book_name} {author}"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')

        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', book_name.lower())
        normalized_author = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', author.lower()) if author else ''

        for tr in soup.select('tr[onclick]')[:20]:
            onclick = tr.get('onclick', '')
            link = onclick.split("'")[1] if "'" in onclick else ''
            title = tr.select_one('td[title]')
            author_td = tr.select('td')[1] if len(tr.select('td')) > 1 else None

            if title and link:
                title_text = title.get('title')
                normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', title_text.lower())
                author_text = author_td.get_text(strip=True) if author_td else ''
                author_text = ' '.join(author_text.split())
                normalized_author_text = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', author_text.lower())

                title_match = normalized_search in normalized_title or normalized_title in normalized_search
                author_match = not normalized_author or normalized_author in normalized_author_text

                if title_match and author_match:
                    all_results.append({
                        "source": "CIDP制造业数字资源平台",
                        "title": title_text,
                        "author": author_text,
                        "link": f"https://www.cidp.com.cn{link}"
                    })

        unique_results = []
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


def search_ry_resouce(book_name: str, author: str = "", isbn: str = "") -> str:
    """搜索人邮出版社资源"""
    logger.info(f"开始搜索人邮资源: {book_name}, 作者: {author}, ISBN: {isbn}")
    try:
        api_url = "https://ry.chengyiart.cn/api/book/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/json"
        }
        all_results = []

        # 如果有ISBN，先用ISBN搜索
        if isbn:
            payload = {"a": "", "i": "", "k": isbn, "ot": "c", "p": "", "pageIndex": 1, "pageSize": 5}
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            data = response.json()
            for item in data.get("data", {}).get("list", []):
                all_results.append({
                    "source": "人民邮电出版社电子书平台",
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "link": f"https://ry.chengyiart.cn/Player/Detail/{item.get('Id', '')}"
                })

        # 用书名搜索
        payload = {"a": "", "i": "", "k": book_name, "ot": "c", "p": "", "pageIndex": 1, "pageSize": 20}
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        data = response.json()

        normalized_search = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', book_name.lower())

        for item in data.get("data", {}).get("list", [])[:20]:
            title = item.get("title", "")
            normalized_title = re.sub(r'[（）()【】\[\]《》<>""''\s]', '', title.lower())

            if normalized_search in normalized_title or normalized_title in normalized_search:
                all_results.append({
                    "source": "人民邮电出版社电子书平台",
                    "title": title,
                    "author": item.get("author", ""),
                    "link": f"https://ry.chengyiart.cn/Player/Detail/{item.get('Id', '')}"
                })

        unique_results = []
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
    result = search_digital_resource.invoke({"book_name": "机械设计手册", "publisher": "化学工业出版社", "author":"成大先"})
    print(result)
    result = search_digital_resource.invoke({"book_name": "Python编程 第三版", "publisher": "人民邮电出版社", "author": "[美] 埃里克 • 马瑟斯（Eric Matthes）", "isbn": "9787115613639"})
    print(result)

