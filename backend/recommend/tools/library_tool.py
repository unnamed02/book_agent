from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import logging
import json
import re

logger = logging.getLogger(__name__)

@tool
def search_library_collection(isbn: str, title: str) -> str:
    """
    查询图书馆馆藏信息

    Args:
        isbn: 图书ISBN
        title: 书名

    Returns:
        JSON格式的馆藏信息
    """

    try:
        # 生成多个模拟数据
        all_results = [
            {
                "call_number": "TP312/1234",
                "floor": "3楼",
                "location": "计算机图书阅览区",
                "status": "可借",
                "total": 2,
                "available": 1
            },
            {
                "call_number": "TP312/1234-2",
                "floor": "4楼",
                "location": "自然科学阅览室",
                "status": "可借",
                "total": 1,
                "available": 1
            },
            {
                "call_number": "TP312/1234-3",
                "floor": "2楼",
                "location": "社科图书借阅区",
                "status": "在馆",
                "total": 1,
                "available": 0
            },
            {
                "call_number": "I247/5678",
                "floor": "5楼",
                "location": "文学图书借阅区",
                "status": "可借",
                "total": 3,
                "available": 2
            },
            {
                "call_number": "G634/9012",
                "floor": "3楼",
                "location": "教育类图书区",
                "status": "可借",
                "total": 2,
                "available": 1
            }
        ]

        # 使用LLM判断是否应该有馆藏
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        check_prompt = f"""判断《{title}》是否可能在图书馆有馆藏。
如果是特别小众、新出版（2024-2025年）、或非常专业的书籍，返回"无"。
否则返回"有"。
只返回"有"或"无"，不要其他内容。"""

        should_have = llm.invoke(check_prompt).content.strip()

        if "无" in should_have:
            return json.dumps([], ensure_ascii=False)

        # 生成馆藏信息
        llm2 = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
        prompt = f"""参考以下模板，为《{title}》(ISBN: {isbn})生成1-2条图书馆馆藏记录。
要求：
1. 根据书名生成合适的索书号(call_number)，如计算机类用TP开头，文学类用I开头等
2. 随机生成status：可借、在馆、借出等
3. 保持其他字段格式不变

模板：
{json.dumps(all_results[:2], ensure_ascii=False, indent=2)}

只返回JSON数组，不要其他内容。"""

        result = llm2.invoke(prompt).content.strip()
        result = re.sub(r'```json\s*|\s*```', '', result).strip()

        try:
            json.loads(result)
            return result
        except:
            return json.dumps(all_results[:1], ensure_ascii=False)
    except Exception as e:
        logger.error(f"查询馆藏失败: {str(e)}")
        return json.dumps({}, ensure_ascii=False)
