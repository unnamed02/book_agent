from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from book_info_chain import process_book_with_chain
from memory_manager import UserMemoryManager
from models import get_db, get_db_manager
from session import SessionManager
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import asyncio
import re
import uuid
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    try:
        db_manager = get_db_manager()
        await db_manager.init_db()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}，记忆功能将不可用")

    yield

    # 关闭时执行
    try:
        db_manager = get_db_manager()
        await db_manager.close()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {e}")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局会话管理器
session_manager = SessionManager(session_timeout=3600)

# 向量数据库（共享实例）
vectorstore = None

def get_vectorstore():
    """获取或创建向量数据库实例"""
    global vectorstore
    if vectorstore is None:
        try:
            embeddings = OpenAIEmbeddings()
            # 连接 Milvus 服务器
            vectorstore = Milvus(
                collection_name="book_recommendations",
                embedding_function=embeddings,
                connection_args={
                    "host": "localhost",
                    "port": "2379"
                },
                auto_id=True
            )
            logger.info("✓ Milvus 向量数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠ Milvus 连接失败: {e}")
            logger.warning("向量检索功能将不可用，但应用可以继续运行")
            vectorstore = None
    return vectorstore

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # 用户ID,支持多用户记忆

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式响应的聊天接口，分阶段返回内容"""

    async def generate():
        # 获取或创建会话
        session = await session_manager.get_or_create_session(
            session_id=request.session_id,
            user_id=request.user_id,
            db=db,
            vectorstore=get_vectorstore()
        )

        # 第一步：返回会话信息
        yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id, 'user_id': session.user_id}, ensure_ascii=False)}\n\n"

        # 根据用户查询增量更新偏好（记忆已在 session 创建时加载）
        await session.update_preferences(request.message)

        # 阶段0: 判断需求是否明确
        # 获取会话级的对话管理器
        conversation_manager = session.conversation_manager

        clarify_prompt = f"""分析用户的图书需求是否足够明确，可以直接推荐书籍。

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

        # 使用 gpt-4o-mini 进行澄清判断（temperature=0 更稳定）
        clarify_result = await conversation_manager.ainvoke(
            clarify_prompt,
            model="gpt-4o-mini",
            temperature=0
        )

        if clarify_result.strip().startswith("不明确"):
            parts = clarify_result.split("|")
            questions = parts[1:] if len(parts) > 1 else ["您能具体说明您的阅读兴趣吗？", "您想学习什么主题？", "您偏好哪种类型的书籍？"]

            response_text = f"""我需要了解更多信息来为您推荐合适的书籍：

{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(questions)])}

请告诉我更多详细信息，我会为您精准推荐！"""

            session.add_to_history(request.message, response_text)

            # 保存交互到记忆
            if session.memory_manager:
                session.memory_manager.save_interaction(request.message, response_text)

            # 返回澄清问题
            yield f"data: {json.dumps({'type': 'message', 'content': response_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return

        # 阶段1: 生成个性化推荐和简短介绍
        # 使用同一个会话级的对话管理器
        conversation_manager = session.conversation_manager

        # 如果有长期记忆，更新系统上下文
        if session.memory_manager:
            memories = session.memory_manager.get_memories()
            if memories:
                long_term = memories.get("long_term_memory", {})
                user_profile = long_term.get("user_profile", "")
                recent_books = long_term.get("recent_recommendations", [])

                if user_profile or recent_books:
                    system_context = f"""你是专业的图书推荐助手。

## 用户画像
{user_profile if user_profile else "新用户"}

## 最近推荐（避免重复）
{', '.join(recent_books[:10]) if recent_books else '无'}

请基于用户画像提供个性化推荐。"""

                    # 更新系统上下文
                    conversation_manager.set_system_context(system_context)

        recommend_prompt = f"""请根据用户需求进行个性化推荐。

用户需求：{request.message}

请按以下格式回答：

先自然且亲切地回应用户的需求，然后直接给出推荐书单的JSON。

JSON格式：
{{"books": [{{"title": "完整书名", "author": "作者名", "reason": "简短推荐理由(20字内)"}}, ...]}}

推荐策略：
1. 如果用户明确指定了书名，只返回名称相符或者相似的书籍
2. 如果用户描述了主题、领域或需求，推荐3-5本相关书籍
3. 考虑用户的阅读历史，避免重复推荐

选书标准：
1. 必须是真实存在的图书，有明确的作者
2. 优先推荐中文版
3. 优先选择经典、权威的书籍

格式要求：
- 对话部分用自然语言，不要加"第一部分"、"第二部分"等标记
- JSON部分不要用```包裹，直接输出"""

        # 使用 deepseek-v3.2-exp 进行推荐（temperature=0.7 更有创意）
        llm_response = await conversation_manager.ainvoke(
            recommend_prompt,
            model="DeepSeek-V3.2-Fast",
            temperature=0.7
        )
        logger.info(f"LLM原始响应: {llm_response}")

        # 解析LLM响应：分离对话部分和JSON部分
        dialogue_part = ""
        json_part = ""

        # 尝试提取JSON部分
        json_match = re.search(r'\{["\']books["\']\s*:\s*\[.*?\]\s*\}', llm_response, re.DOTALL)
        if json_match:
            json_part = json_match.group(0)
            # 对话部分是JSON之前的内容
            dialogue_part = llm_response[:json_match.start()].strip()
        else:
            # 如果没有找到JSON，尝试清理整个响应
            clean_json = re.sub(r'```json\s*|\s*```', '', llm_response).strip()
            try:
                # 尝试直接解析
                json.loads(clean_json)
                json_part = clean_json
            except:
                # 最后尝试：假设整个响应就是JSON
                json_part = llm_response.strip()

        # 解析书单
        try:
            clean_json = re.sub(r'```json\s*|\s*```', '', json_part).strip()

            # 尝试修复常见的JSON格式问题
            # 1. 修复缺少引号的情况：reason: 必读经典 -> reason: "必读经典"
            clean_json = re.sub(r'("reason":\s*)([^",}\]]+)([,}\]])', r'\1"\2"\3', clean_json)
            # 2. 修复已经有引号但格式不对的情况
            clean_json = re.sub(r'("reason":\s*"?)([^"]+?)("?\s*[,}\]])', r'\1\2"\3', clean_json)

            book_data = json.loads(clean_json)
            books = book_data.get("books", [])
            logger.info(f"成功解析 {len(books)} 本书籍")
        except Exception as e:
            logger.error(f"解析书单JSON失败: {e}, JSON: {json_part}")
            # 尝试更宽松的解析：使用正则提取书名和作者
            try:
                import ast
                # 尝试使用 ast.literal_eval (更宽松)
                clean_json = clean_json.replace('true', 'True').replace('false', 'False').replace('null', 'None')
                book_data = ast.literal_eval(clean_json)
                books = book_data.get("books", [])
                logger.info(f"使用 ast 成功解析 {len(books)} 本书籍")
            except:
                # 最后的尝试：正则提取
                logger.warning("尝试使用正则表达式提取书籍信息")
                books = []
                title_pattern = r'"title":\s*"([^"]+)"'
                author_pattern = r'"author":\s*"([^"]+)"'
                reason_pattern = r'"reason":\s*"?([^",}]+)"?'

                titles = re.findall(title_pattern, json_part)
                authors = re.findall(author_pattern, json_part)
                reasons = re.findall(reason_pattern, json_part)

                for i in range(min(len(titles), len(authors))):
                    books.append({
                        "title": titles[i],
                        "author": authors[i],
                        "reason": reasons[i] if i < len(reasons) else "推荐阅读"
                    })
                logger.info(f"正则提取得到 {len(books)} 本书籍")

        if not books:
            # 如果没有书籍，返回错误
            error_msg = "抱歉，我无法为您生成推荐书单。请尝试更具体地描述您的需求。"
            yield f"data: {json.dumps({'type': 'message', 'content': error_msg}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return

        # 第二步：先发送对话部分和简单书单
        if dialogue_part:
            yield f"data: {json.dumps({'type': 'dialogue', 'content': dialogue_part}, ensure_ascii=False)}\n\n"

        # 构建简单书单
        book_list_text = "\n\n".join([
            f"**{i}. {b['title']}** - {b['author']}\n   💡 {b.get('reason', '经典推荐')}"
            for i, b in enumerate(books, 1)
        ])

        yield f"data: {json.dumps({'type': 'books', 'content': book_list_text}, ensure_ascii=False)}\n\n"

        # 第三步：显示正在查询馆藏信息
        yield f"data: {json.dumps({'type': 'status', 'content': '正在为您查询这些书籍的详细信息...'}, ensure_ascii=False)}\n\n"

        # 阶段2: 异步获取详细信息
        logger.info(f"推荐书单: {books}")

        tasks = [process_book_with_chain(b['title'], b['author']) for b in books]
        all_books_info = await asyncio.gather(*tasks)

        # 过滤空结果和去重，同时提取书籍元数据
        filtered_books = []
        book_metadata = []  # 存储书籍元数据（包含ISBN）
        seen_books = set()

        for info in all_books_info:
            if not info or not info.strip():
                continue
            # 提取标题、作者和ISBN
            title_match = re.search(r'###\s+(.+)', info)
            author_match = re.search(r'\*\*作者\*\*：(.+)', info)
            isbn_match = re.search(r'\*\*ISBN\*\*：(.+)', info)

            if title_match and author_match:
                title = title_match.group(1).strip()
                author = author_match.group(1).strip()
                isbn = isbn_match.group(1).strip() if isbn_match else ""

                book_key = (title, author)
                if book_key not in seen_books:
                    seen_books.add(book_key)
                    filtered_books.append(info)
                    book_metadata.append({
                        "title": title,
                        "author": author,
                        "isbn": isbn if isbn and isbn != "未知" else ""
                    })

        logger.info(f"收集到 {len(filtered_books)} 本有效书籍")

        # 第四步：逐本发送详细信息
        for i, book_info in enumerate(filtered_books, 1):
            yield f"data: {json.dumps({'type': 'book_detail', 'content': book_info, 'index': i, 'total': len(filtered_books)}, ensure_ascii=False)}\n\n"

        # 构建完整响应用于历史记录
        if dialogue_part:
            full_response = f"{dialogue_part}\n\n---\n\n" + "\n\n".join(filtered_books)
        else:
            full_response = "\n\n".join(filtered_books)

        session.add_to_history(request.message, full_response)

        # 保存交互到记忆系统
        if session.memory_manager:
            try:
                logger.info(f"开始保存记忆，book_metadata数量: {len(book_metadata)}")

                # 保存到短期记忆
                session.memory_manager.save_interaction(request.message, full_response)

                # 保存到向量数据库
                await session.memory_manager.save_to_vector_store(
                    request.message,
                    full_response,
                    metadata={"session_id": session.session_id}
                )

                # 保存推荐记录到数据库（使用提取的元数据，包含ISBN）
                for i, book_meta in enumerate(book_metadata, 1):
                    try:
                        logger.info(f"添加第 {i}/{len(book_metadata)} 本: {book_meta.get('title')}, ISBN: {book_meta.get('isbn')}")
                        await session.memory_manager.save_recommendation(
                            book=book_meta,
                            user_query=request.message,
                            session_id=session.session_id,
                            auto_commit=False  # 不自动提交
                        )
                    except Exception as e:
                        logger.error(f"添加第 {i} 本书籍失败: {e}")

                # 统一提交所有推荐记录
                try:
                    await session.memory_manager.db_session.commit()
                    logger.info(f"✓ 成功保存 {len(book_metadata)} 条推荐记录到数据库")
                except Exception as e:
                    logger.error(f"✗ 提交推荐记录失败: {e}")
                    await session.memory_manager.db_session.rollback()
                    raise
            except Exception as e:
                logger.error(f"✗ 保存记忆失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning("session.memory_manager 为 None，跳过记忆保存")

        # 第五步：结束标记
        yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/proxy-image")
async def proxy_image(url: str):
    try:
        response = requests.get(url, timeout=10)
        return Response(content=response.content, media_type=response.headers.get('content-type', 'image/jpeg'))
    except:
        return Response(status_code=404)
