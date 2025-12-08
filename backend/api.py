from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from book_info_chain import process_book_with_chain
import logging
import json
import asyncio
import re
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 会话存储 {session_id: {"history": [...], "last_access": datetime}}
sessions: Dict[str, Dict] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

def get_or_create_session(session_id: str = None) -> tuple[str, List]:
    """获取或创建会话"""
    import uuid

    if not session_id:
        session_id = str(uuid.uuid4())
        sessions[session_id] = {"history": [], "last_access": datetime.now()}
        return session_id, []

    # 清理超过1小时的旧会话
    now = datetime.now()
    to_delete = [sid for sid, data in sessions.items()
                 if (now - data["last_access"]).total_seconds() > 3600]
    for sid in to_delete:
        del sessions[sid]

    if session_id not in sessions:
        sessions[session_id] = {"history": [], "last_access": now}
    else:
        sessions[session_id]["last_access"] = now

    return session_id, sessions[session_id]["history"]

def add_to_history(session_id: str, user_msg: str, assistant_msg: str):
    """添加对话到历史记录"""
    if session_id in sessions:
        sessions[session_id]["history"].append({"user": user_msg, "assistant": assistant_msg})
        # 只保留最近5轮对话
        if len(sessions[session_id]["history"]) > 5:
            sessions[session_id]["history"] = sessions[session_id]["history"][-5:]

@app.post("/chat")
async def chat(request: ChatRequest):
    # 获取或创建会话
    session_id, history = get_or_create_session(request.session_id)

    # 构建上下文
    context = ""
    if history:
        context = "历史对话：\n"
        for h in history[-3:]:  # 最近3轮
            context += f"用户: {h['user']}\n助手: {h['assistant'][:100]}...\n"
        context += "\n"

    # 阶段0: 判断需求是否明确
    clarify_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    clarify_prompt = f"""{context}分析用户的图书需求是否足够明确，可以直接推荐书籍。

用户需求：{request.message}

判断标准：
- 明确：包含具体的主题、领域、技能、兴趣等，或者直接给了书名，例如"Python编程"、"历史小说"、"机器学习入门" ,"找C专家编程"
- 不明确：过于宽泛或模糊，例如"推荐几本书"、"有什么好看的"、"想学习"
- 如果用户在回答之前的澄清问题，结合上下文判断是否已足够明确

如果明确，返回：明确
如果不明确，返回：不明确|[2-3个澄清问题，用|分隔]

例如：
- 不明确|您想了解哪个编程语言？|是入门还是进阶？|偏向实战还是理论？
- 明确"""

    clarify_result = clarify_llm.invoke(clarify_prompt).content.strip()

    if clarify_result.startswith("不明确"):
        parts = clarify_result.split("|")
        questions = parts[1:] if len(parts) > 1 else ["您能具体说明您的阅读兴趣吗？", "您想学习什么主题？", "您偏好哪种类型的书籍？"]

        response_text = f"""我需要了解更多信息来为您推荐合适的书籍：

{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(questions)])}

请告诉我更多详细信息，我会为您精准推荐！"""

        add_to_history(session_id, request.message, response_text)
        return {"response": response_text, "session_id": session_id}

    # 阶段1: 推荐书单
    recommend_llm = ChatOpenAI(model="deepseek-v3.2-exp", temperature=0.7)
    recommend_prompt = f"""{context}你是一位专业的图书推荐专家。请根据用户需求推荐书籍。

用户需求：{request.message}

推荐策略：
1. 如果用户明确指定了书名，只返回名称相符或者相似的书籍
2. 如果用户描述了主题、领域或需求，推荐3-5本相关书籍
3. 如果用户表达了多样化需求，可推荐5本涵盖不同角度的书籍

选书标准：
1. 必须是真实存在的图书，有明确的作者
2. 优先推荐中文版
3. 优先选择经典、权威的书籍


重要：必须严格按照此格式返回（纯JSON，不要用```包裹）：
{{"books": [{{"title": "完整书名", "author": "作者名"}}, ...]}}"""

    book_list_json = recommend_llm.invoke(recommend_prompt).content
    logger.info(book_list_json)

    clean_json = re.sub(r'```json\s*|\s*```', '', book_list_json).strip()
    book_data = json.loads(clean_json)
    books = book_data.get("books", [])
    book_queries = [f"{b['title']} {b['author']}" for b in books]


    tasks = [process_book_with_chain(book) for book in book_queries[:5]]
    all_books_info = await asyncio.gather(*tasks)

    # 过滤空结果和去重
    filtered_books = []
    seen_books = set()
    for info in all_books_info:
        if not info or not info.strip():
            continue
        # 提取标题和作者用于去重
        title_match = re.search(r'### (.+)', info)
        author_match = re.search(r'\*\*作者\*\*：(.+)', info)
        if title_match and author_match:
            title = title_match.group(1).strip()
            author = author_match.group(1).strip()
            book_key = (title, author)
            if book_key not in seen_books:
                seen_books.add(book_key)
                filtered_books.append(info)

    logger.info(f"收集到 {len(filtered_books)} 本有效书籍")

    response_text = "\n\n".join(filtered_books)
    add_to_history(session_id, request.message, response_text)
    return {"response": response_text, "session_id": session_id}

@app.get("/proxy-image")
async def proxy_image(url: str):
    try:
        response = requests.get(url, timeout=10)
        return Response(content=response.content, media_type=response.headers.get('content-type', 'image/jpeg'))
    except:
        return Response(status_code=404)
