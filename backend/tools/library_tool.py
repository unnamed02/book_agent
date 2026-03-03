from bs4 import BeautifulSoup
import requests
import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

def search_library_collection(title: str, author: str) -> list:
    """
    查询图书馆馆藏信息

    Args:
        title: 书名
        author: 作者

    Returns:
        馆藏信息列表，每项包含 library, call_number, location, status, total, available
    """

    try:
        # 第一步：搜索图书，获取 bookrecno
        search_url = f"http://112.46.235.64:8082/opac3/search?searchType=standard&isFacet=true&view=standard&rows=10&sortWay=score&sortOrder=desc&hasholding=1&searchWay0=title&searchWay1=author&searchWay2=marc&q0={quote(title)}&q1={quote(author)}&logical0=AND&logical1=AND&logical2=AND&f_curlibcode=BEILIN"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=30)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        books_info = {}

        send_areas = soup.find_all('div', class_='sendToLineOut')

        for area in send_areas:
            book_input = area.find('input', {'name': 'bookIdList', 'type': 'hidden'})
            if not book_input or not book_input.get('value'):
                continue

            bookrecno = book_input['value']

            em_con = area.find('div', class_='sendToEmCon')
            if em_con:
                p_tags = em_con.find_all('p')
                book_title = p_tags[0].get_text(strip=True) if len(p_tags) > 0 else ''
                pub_info = p_tags[1].get_text(strip=True) if len(p_tags) > 1 else ''

                books_info[bookrecno] = {
                    'title': book_title,
                    'pub_info': pub_info
                }

        bookrecnos = list(books_info.keys())

        if not bookrecnos:
            logger.info(f"未找到《{title}》的馆藏信息")
            return []

        # 第二步：获取馆藏详情
        holdings_url = f"http://112.46.235.64:8082/opac3/book/holdingPreviews?bookrecnos={','.join(bookrecnos)}&curLibcodes=BEILIN&return_fmt=json"
        holdings_response = requests.get(holdings_url, headers=headers, timeout=30)
        holdings_data = holdings_response.json()

        # 转换为前端需要的格式
        lib_items = []
        for bookrecno, holdings in holdings_data.get('previews', {}).items():
            book_info = books_info.get(bookrecno, {})
            for holding in holdings:
                if holding.get('curlib') == 'BEILIN':
                    lib_items.append({
                        'title': book_info.get('title', ''),
                        'pub_info': book_info.get('pub_info', ''),
                        'library': holding.get('curlibName', ''),
                        'call_number': holding.get('callno', ''),
                        'location': holding.get('curlocalName', ''),
                        'status': "可借" if holding.get('loanableCount', 0) > 0 else "在馆",
                        'total': holding.get('copycount', 0),
                        'available': holding.get('loanableCount', 0)
                    })

        logger.info(f"找到 {len(lib_items)} 条馆藏记录")
        return lib_items

    except Exception as e:
        logger.error(f"查询馆藏失败: {str(e)}")
        return []


if __name__ == "__main__":
    print("=== 搜索馆藏图书 ===")
    result = search_library_collection("如何阅读一本书", "")
    print(result)
    
    

