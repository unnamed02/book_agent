from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from book_info_chain import process_book_with_chain
from memory_manager import UserMemoryManager
from models import get_db, get_db_manager
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import asyncio
import re
import uuid
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

# 会话存储 {session_id: {"history": [...], "last_access": datetime, "user_id": str, "memory_manager": UserMemoryManager}}
sessions: Dict[str, Dict] = {}

# 向量数据库（共享实例）
vectorstore = None

def get_vectorstore():
    """获取或创建向量数据库实例"""
    global vectorstore
    if vectorstore is None:
        embeddings = OpenAIEmbeddings()
        vectorstore = Chroma(
            collection_name="book_recommendations",
            embedding_function=embeddings,
            persist_directory="./chroma_db"
        )
    return vectorstore

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # 用户ID,支持多用户记忆

async def get_or_create_session(
    session_id: str = None,
    user_id: str = None,
    db: AsyncSession = None
) -> tuple[str, str, List, Optional[UserMemoryManager]]:
    """获取或创建会话，返回 (session_id, user_id, history, memory_manager)"""

    # 生成默认ID
    if not session_id:
        session_id = str(uuid.uuid4())
    if not user_id:
        user_id = f"user_{session_id}"  # 默认用户ID基于会话ID

    # 清理超过1小时的旧会话
    now = datetime.now()
    to_delete = [sid for sid, data in sessions.items()
                 if (now - data["last_access"]).total_seconds() > 3600]
    for sid in to_delete:
        del sessions[sid]

    # 创建或获取会话
    if session_id not in sessions:
        sessions[session_id] = {
            "history": [],
            "last_access": now,
            "user_id": user_id,
            "memory_manager": None  # 懒加载
        }
    else:
        sessions[session_id]["last_access"] = now

    # 懒加载记忆管理器（仅在有数据库连接时）
    memory_manager = sessions[session_id].get("memory_manager")
    if memory_manager is None and db is not None:
        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            embeddings = OpenAIEmbeddings()
            vectorstore = get_vectorstore()

            memory_manager = UserMemoryManager(
                user_id=user_id,
                db_session=db,
                llm=llm,
                embeddings=embeddings,
                vectorstore=vectorstore
            )
            sessions[session_id]["memory_manager"] = memory_manager
            logger.info(f"为会话 {session_id} 创建记忆管理器")
        except Exception as e:
            logger.warning(f"创建记忆管理器失败: {e}，将使用无记忆模式")
            memory_manager = None
    elif memory_manager is not None and db is not None:
        # 更新已存在的记忆管理器的数据库会话
        memory_manager.db_session = db
        memory_manager.longterm_memory.db_session = db
        logger.debug(f"更新会话 {session_id} 的数据库会话")

    return session_id, user_id, sessions[session_id]["history"], memory_manager

def add_to_history(session_id: str, user_msg: str, assistant_msg: str):
    """添加对话到历史记录"""
    if session_id in sessions:
        sessions[session_id]["history"].append({"user": user_msg, "assistant": assistant_msg})
        # 只保留最近5轮对话
        if len(sessions[session_id]["history"]) > 5:
            sessions[session_id]["history"] = sessions[session_id]["history"][-5:]

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    try:
        db_manager = get_db_manager()
        await db_manager.init_db()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}，记忆功能将不可用")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理资源"""
    try:
        db_manager = get_db_manager()
        await db_manager.close()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {e}")

@app.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    # 获取或创建会话（带记忆管理器）
    session_id, user_id, history, memory_manager = await get_or_create_session(
        session_id=request.session_id,
        user_id=request.user_id,
        db=db
    )

    # 构建上下文
    context = ""
    if history:
        context = "历史对话：\n"
        for h in history[-3:]:  # 最近3轮
            context += f"用户: {h['user']}\n助手: {h['assistant'][:100]}...\n"
        context += "\n"

    # 如果有记忆管理器，加载长期记忆和提取偏好
    memories = {}
    if memory_manager:
        try:
            # 提取并更新用户偏好
            await memory_manager.update_preferences_from_query(request.message)

            # 加载所有记忆
            memories = await memory_manager.load_all_memories(request.message)
            logger.info(f"加载记忆成功，包含 {len(memories)} 个记忆类型")
        except Exception as e:
            logger.error(f"加载记忆失败: {e}")
            memories = {}
    logger.info(f"*** memories: {memories} ***")

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

        # 保存交互到记忆
        if memory_manager:
            memory_manager.save_interaction(request.message, response_text)

        return {"response": response_text, "session_id": session_id, "user_id": user_id}

    # 阶段1: 生成个性化推荐和简短介绍
    recommend_llm = ChatOpenAI(model="deepseek-v3.2-exp", temperature=0.7)

    base_prompt = f"""你是一位专业的图书推荐专家。请根据用户需求进行个性化推荐。

用户需求：{request.message}

请按以下格式回答：

先自然且亲切地回应用户的需求，还可以根据用户画像给出一些学习建议，然后直接给出推荐书单的JSON。

JSON格式：
{{"books": [{{"title": "完整书名", "author": "作者名", "reason": "推荐理由"}}, ...]}}

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

    # 如果有记忆，使用个性化 prompt
    if memory_manager and memories:
        recommend_prompt = memory_manager.build_personalized_prompt(
            request.message,
            base_prompt,
            memories
        )
    else:
        recommend_prompt = f"{context}{base_prompt}"

    llm_response = recommend_llm.invoke(recommend_prompt).content
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
        return {"response": error_msg, "session_id": session_id, "user_id": user_id}

    # 构建初步响应：对话 + 简单书单
    book_list_text = "\n\n".join([
        f"**{i}. {b['title']}** - {b['author']}\n   💡 {b.get('reason', '经典推荐')}"
        for i, b in enumerate(books, 1)
    ])
  
    # 阶段2: 异步获取详细信息
    logger.info(f"推荐书单: {books}")
    book_queries = [f"{b['title']} {b['author']}" for b in books]

    tasks = [process_book_with_chain(book) for book in book_queries[:5]]
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

    # 构建最终响应：对话 + 详细信息
    if dialogue_part:
        # 如果有对话部分，添加到开头
        response_text = f"{dialogue_part}\n\n---\n\n" + "\n\n".join(filtered_books)
    else:
        # 如果没有对话部分（解析失败），只显示详细信息
        response_text = "\n\n".join(filtered_books)

    add_to_history(session_id, request.message, response_text)

    # 保存交互到记忆系统
    if memory_manager:
        try:
            logger.info(f"开始保存记忆，book_metadata数量: {len(book_metadata)}")

            # 保存到短期记忆
            memory_manager.save_interaction(request.message, response_text)

            # 保存到向量数据库
            await memory_manager.save_to_vector_store(
                request.message,
                response_text,
                metadata={"session_id": session_id}
            )

            # 保存推荐记录到数据库（使用提取的元数据，包含ISBN）
            # 批量保存：先全部 add，最后统一 commit
            for i, book_meta in enumerate(book_metadata, 1):
                try:
                    logger.info(f"添加第 {i}/{len(book_metadata)} 本: {book_meta.get('title')}, ISBN: {book_meta.get('isbn')}")
                    await memory_manager.save_recommendation(
                        book=book_meta,
                        user_query=request.message,
                        session_id=session_id,
                        auto_commit=False  # 不自动提交
                    )
                except Exception as e:
                    logger.error(f"添加第 {i} 本书籍失败: {e}")

            # 统一提交所有推荐记录
            try:
                await memory_manager.db_session.commit()
                logger.info(f"✓ 成功保存 {len(book_metadata)} 条推荐记录到数据库")
            except Exception as e:
                logger.error(f"✗ 提交推荐记录失败: {e}")
                await memory_manager.db_session.rollback()
                raise
        except Exception as e:
            logger.error(f"✗ 保存记忆失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.warning("⚠ memory_manager 为 None，跳过记忆保存")

    return {"response": response_text, "session_id": session_id, "user_id": user_id}

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式响应的聊天接口，分阶段返回内容"""

    async def generate():
        # 获取或创建会话（带记忆管理器）
        session_id, user_id, history, memory_manager = await get_or_create_session(
            session_id=request.session_id,
            user_id=request.user_id,
            db=db
        )

        # 第一步：返回会话信息
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id, 'user_id': user_id}, ensure_ascii=False)}\n\n"

        # 构建上下文
        context = ""
        if history:
            context = "历史对话：\n"
            for h in history[-3:]:  # 最近3轮
                context += f"用户: {h['user']}\n助手: {h['assistant'][:100]}...\n"
            context += "\n"

        # 如果有记忆管理器，加载长期记忆和提取偏好
        memories = {}
        if memory_manager:
            try:
                # 提取并更新用户偏好
                await memory_manager.update_preferences_from_query(request.message)

                # 加载所有记忆
                memories = await memory_manager.load_all_memories(request.message)
                logger.info(f"加载记忆成功，包含 {len(memories)} 个记忆类型")
            except Exception as e:
                logger.error(f"加载记忆失败: {e}")
                memories = {}

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

            # 保存交互到记忆
            if memory_manager:
                memory_manager.save_interaction(request.message, response_text)

            # 返回澄清问题
            yield f"data: {json.dumps({'type': 'message', 'content': response_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return

        # 阶段1: 生成个性化推荐和简短介绍
        recommend_llm = ChatOpenAI(model="deepseek-v3.2-exp", temperature=0.7)

        base_prompt = f"""你是一位专业的图书推荐专家。请根据用户需求进行个性化推荐。

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

        # 如果有记忆，使用个性化 prompt
        if memory_manager and memories:
            recommend_prompt = memory_manager.build_personalized_prompt(
                request.message,
                base_prompt,
                memories
            )
        else:
            recommend_prompt = f"{context}{base_prompt}"

        llm_response = recommend_llm.invoke(recommend_prompt).content
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
                logger.info(f"正则提取得到 {len(books)} 本��籍")

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
        book_queries = [f"{b['title']} {b['author']}" for b in books]

        tasks = [process_book_with_chain(book) for book in book_queries[:5]]
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

        add_to_history(session_id, request.message, full_response)

        # 保存交互到记忆系统
        if memory_manager:
            try:
                logger.info(f"开始保存记忆，book_metadata数量: {len(book_metadata)}")

                # 保存到短期记忆
                memory_manager.save_interaction(request.message, full_response)

                # 保存到向量数据库
                await memory_manager.save_to_vector_store(
                    request.message,
                    full_response,
                    metadata={"session_id": session_id}
                )

                # 保存推荐记录到数据库（使用提取的元数据，包含ISBN）
                for i, book_meta in enumerate(book_metadata, 1):
                    try:
                        logger.info(f"添加第 {i}/{len(book_metadata)} 本: {book_meta.get('title')}, ISBN: {book_meta.get('isbn')}")
                        await memory_manager.save_recommendation(
                            book=book_meta,
                            user_query=request.message,
                            session_id=session_id,
                            auto_commit=False  # 不自动提交
                        )
                    except Exception as e:
                        logger.error(f"添加第 {i} 本书籍失败: {e}")

                # 统一提交所有推荐记录
                try:
                    await memory_manager.db_session.commit()
                    logger.info(f"✓ 成功保存 {len(book_metadata)} 条推荐记录到数据库")
                except Exception as e:
                    logger.error(f"✗ 提交推荐记录失败: {e}")
                    await memory_manager.db_session.rollback()
                    raise
            except Exception as e:
                logger.error(f"✗ 保存记忆失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            logger.warning("⚠ memory_manager 为 None，跳过记忆保存")

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
