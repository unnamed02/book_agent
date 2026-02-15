from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from utils.models import get_db, get_db_manager
from session.session import SessionManager
from graph_workflow import stream_recommendation_workflow
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import uuid
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

# 统一配置日志等级
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
    expose_headers=["*"],
)

# 全局会话管理器
session_manager = SessionManager(session_timeout=3600)

@app.get("/")
async def root():
    """健康检查端点"""
    return {"status": "ok", "message": "Book recommendation API is running"}

# 向量数据库（共享实例）
vectorstore = None
kb_vectorstore = None  # 知识库向量数据库

def get_vectorstore():
    """获取或创建向量数据库实例（用于用户记忆）"""
    global vectorstore
    if vectorstore is None:
        try:
            embeddings = OpenAIEmbeddings()
            # 使用本地 Milvus Lite（SQLite 存储）
            vectorstore = Milvus(
                collection_name="book_recommendations",
                embedding_function=embeddings,
                connection_args={"uri": "./milvus_memory.db"},
                auto_id=True
            )
            logger.info("✓ Milvus 用户记忆向量数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠ Milvus 用户记忆连接失败: {e}")
            logger.warning("向量检索功能将不可用，但应用可以继续运行")
            vectorstore = None
    return vectorstore

def get_kb_vectorstore():
    """获取或创建知识库向量数据库实例（用于 RAG）"""
    global kb_vectorstore
    if kb_vectorstore is None:
        try:
            embeddings = OpenAIEmbeddings()
            # 使用本地 Milvus Lite（SQLite 存储）
            kb_vectorstore = Milvus(
                collection_name="customer_service_kb",
                embedding_function=embeddings,
                connection_args={"uri": "./milvus_kb.db"},
                auto_id=True
            )
            logger.info("✓ Milvus 知识库向量数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠ Milvus 知识库连接失败: {e}")
            logger.warning("RAG 客服功能将不可用，将使用默认客服模式")
            kb_vectorstore = None
    return kb_vectorstore

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # 用户ID,支持多用户记忆

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式响应的聊天接口（使用 LangGraph 工作流）"""

    async def generate():
        # 获取或创建会话
        session = await session_manager.get_or_create_session(
            session_id=request.session_id,
            user_id=request.user_id,
            db=db,
            vectorstore=get_vectorstore()
        )

        # 初始化 RAG 服务（懒加载）
        # await session.initialize_rag_service(kb_vectorstore=get_kb_vectorstore())

        # 使用 LangGraph 工作流执行推荐流程
        async for event in stream_recommendation_workflow(
            user_query=request.message,
            session_id=session.session_id,
            user_id=session.user_id,
            conversation_manager=session.conversation_manager,
            rag_service=session.rag_service  # 传递 RAG 服务
        ):
            # 将事件转换为 SSE 格式并发送
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        # 保存对话历史（可选，LangGraph 内部已处理）
        # 这里可以添加额外的清理或后处理逻辑

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.get("/proxy-image")
async def proxy_image(url: str):
    """代理图片请求，主要用于豆瓣图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://book.douban.com/'
        }
        response = requests.get(url, headers=headers, timeout=10)
        logger.info(response)
        response.raise_for_status()
        return Response(
            content=response.content,
            media_type=response.headers.get('content-type', 'image/jpeg')
        )
    except Exception as e:
        logger.error(f"代理图片失败: {url}, 错误: {str(e)}")
        return Response(status_code=404)
