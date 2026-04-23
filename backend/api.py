from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_milvus import Milvus
from utils.models import get_db, get_db_manager
from session.session_manager import SessionManager
from graph_workflow_streaming import stream_recommendation_workflow_enhanced
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
import uuid
import requests
import redis.asyncio as redis
import os
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from session.compact import run_compact_scheduler

# 统一配置日志等级
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.root.setLevel(logging.INFO)
logger = logging.getLogger(__name__)


# 过滤 Pydantic v2 序列化警告（LangChain 内部问题）
import warnings
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

load_dotenv()

# 全局Redis客户端
redis_client: Optional[redis.Redis] = None
# 全局会话管理器
session_manager: Optional[SessionManager] = None
# 全局后台任务
compact_task: Optional[asyncio.Task] = None
# 活跃的生成任务 {session_id: asyncio.Task}
active_generators: Dict[str, asyncio.Task] = {}

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """应用生命周期管理"""
    global redis_client, session_manager, compact_task

    # 启动时执行
    try:
        db_manager = get_db_manager()
        await db_manager.init_db()
        db_type = "PostgreSQL" if "postgresql" in db_manager.database_url else "SQLite"
        logger.info(f"数据库初始化成功 ({db_type}: {db_manager.database_url.split('@')[-1] if '@' in db_manager.database_url else 'local'})")
    except Exception as e:
        logger.warning(f"数据库初始化失败: {e}，记忆功能将不可用")

    # 初始化Redis连接
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"Redis连接成功: {redis_url}")
    except Exception as e:
        logger.warning(f"Redis连接失败: {e}，对话历史持久化将不可用")
        redis_client = None

    # 初始化会话管理器
    session_manager = SessionManager(session_timeout=3600, redis_client=redis_client)

    # 启动 Redis compact 后台任务
    if redis_client:
        compact_task = asyncio.create_task(run_compact_scheduler())
        logger.info("Redis compact 定时任务已启动（每10分钟执行）")

    yield

    # 关闭时执行
    logger.info("关闭应用...")

    # 停止后台任务
    if compact_task:
        compact_task.cancel()
        try:
            await compact_task
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        logger.info("Compact任务已停止")

    try:
        db_manager = get_db_manager()
        await db_manager.close()
        logger.info("数据库连接已关闭")
    except Exception as e:
        logger.error(f"关闭数据库连接失败: {e}")

    # 关闭Redis连接
    if redis_client:
        try:
            await redis_client.close()
            logger.info("Redis连接已关闭")
        except Exception as e:
            logger.error(f"关闭Redis连接失败: {e}")

app = FastAPI(lifespan=lifespan)

import os

# CORS 配置：生产环境应该限制具体域名
cors_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if cors_origins == ["*"]:
    # 开发环境允许所有域名
    logger.warning("CORS 允许所有域名，生产环境请设置 ALLOWED_ORIGINS 环境变量")
else:
    logger.info(f"CORS 允许的域名: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.get("/")
async def root():
    """健康检查端点"""
    return {"status": "ok", "message": "Book recommendation API is running"}


@app.get("/health")
async def health_check():
    """
    详细健康检查端点
    用于监控系统状态和并发能力评估
    """
    import psutil
    
    health_data = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {}
    }
    
    # 数据库状态检查
    try:
        db_manager = get_db_manager()
        # 简单检查连接是否正常
        db_type = "PostgreSQL" if "postgresql" in db_manager.database_url else "SQLite"
        health_data["services"]["database"] = {
            "status": "ok",
            "type": db_type
        }
    except Exception as e:
        health_data["services"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_data["status"] = "degraded"
    
    # Redis 状态检查
    if redis_client:
        try:
            await redis_client.ping()
            # 获取 Redis 信息
            info = await redis_client.info()
            health_data["services"]["redis"] = {
                "status": "ok",
                "connected_clients": info.get("connected_clients", "N/A"),
                "used_memory_human": info.get("used_memory_human", "N/A")
            }
        except Exception as e:
            health_data["services"]["redis"] = {
                "status": "error",
                "error": str(e)
            }
            health_data["status"] = "degraded"
    else:
        health_data["services"]["redis"] = {
            "status": "disabled"
        }
    
    # 会话状态
    if session_manager:
        health_data["services"]["session"] = {
            "active_sessions": session_manager.get_session_count(),
            "max_sessions": session_manager.max_sessions
        }
    
    # 系统资源
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        health_data["system"] = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
    except Exception as e:
        health_data["system"] = {
            "error": str(e)
        }
    
    return health_data

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
            logger.info("Milvus用户记忆向量数据库连接成功")
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
            logger.info("Milvus知识库向量数据库连接成功")
        except Exception as e:
            logger.warning(f"⚠ Milvus 知识库连接失败: {e}")
            logger.warning("RAG 客服功能将不可用，将使用默认客服模式")
            kb_vectorstore = None
    return kb_vectorstore

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None  # 用户ID,支持多用户记忆

class StopChatRequest(BaseModel):
    session_id: str
    user_id: Optional[str] = None

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """流式响应的聊天接口（使用 LangGraph 增强流式工作流）"""

    async def generate():
        # 检查该会话是否已有活跃任务
        if request.session_id in active_generators:
            existing_task = active_generators[request.session_id]
            if existing_task and not existing_task.done():
                yield f"data: {json.dumps({'type': 'busy', 'content': '当前有正在进行的对话，请稍后再试'}, ensure_ascii=False)}\n\n"
                return

        # 注册当前任务
        current_task = asyncio.current_task()
        if current_task:
            active_generators[request.session_id] = current_task

        try:
            # 获取或创建会话
            session = await session_manager.get_or_create_session(
                session_id=request.session_id,
                user_id=request.user_id,
                db=db
            )

            # 使用增强版流式工作流（支持 token 级别流式输出）
            async for event in stream_recommendation_workflow_enhanced(
                user_query=request.message,
                session_id=session.session_id,
                user_id=session.user_id,
                session=session
            ):
                # 将事件转换为 SSE 格式并发送
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            logger.info(f"生成任务被取消: session_id={request.session_id}")
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
            return
        finally:
            # 清理活跃任务记录
            active_generators.pop(request.session_id, None)

    return StreamingResponse(generate(), media_type="text/event-stream")

@app.post("/chat/stop")
async def chat_stop(request: StopChatRequest):
    """停止指定会话的生成任务"""
    session_id = request.session_id

    task = active_generators.pop(session_id, None)
    if task and not task.done():
        task.cancel()
        logger.info(f"已取消生成任务: session_id={session_id}")
        return {"success": True, "message": "已停止生成"}

    return {"success": False, "message": "没有正在进行的生成任务"}

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


class PurchaseRecommendationRequest(BaseModel):
    """荐购表单请求"""
    user_id: str
    book_title: str
    author: Optional[str] = None
    notes: Optional[str] = None
    contact: Optional[str] = None


@app.post("/purchase-recommendation")
async def submit_purchase_recommendation(
    request: PurchaseRecommendationRequest,
    db: AsyncSession = Depends(get_db)
):
    """提交荐购表单"""
    try:
        from utils.models import PurchaseRecommendation, User

        # 确保用户存在
        user = await db.get(User, request.user_id)
        if not user:
            user = User(user_id=request.user_id)
            db.add(user)
            await db.flush()

        # 创建荐购记录
        recommendation = PurchaseRecommendation(
            user_id=request.user_id,
            book_title=request.book_title,
            author=request.author,
            notes=request.notes,
            contact=request.contact,
            status="pending"
        )

        db.add(recommendation)
        await db.commit()
        await db.refresh(recommendation)

        logger.info(f"用户 {request.user_id} 提交荐购: {request.book_title}")

        return {
            "success": True,
            "message": "荐购提交成功",
            "id": recommendation.id
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"提交荐购失败: {e}")
        return {
            "success": False,
            "message": f"提交失败: {str(e)}"
        }


class SaveMessageRequest(BaseModel):
    """保存消息请求"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@app.post("/save-message")
async def save_message(
    request: SaveMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """保存单条用户消息到会话历史和Redis"""
    try:
        # 获取或创建会话
        session = await session_manager.get_or_create_session(
            session_id=request.session_id,
            user_id=request.user_id,
            db=db
        )

        # 保存消息到会话
        from langchain_core.messages import HumanMessage
        session.conversation_messages.append(HumanMessage(content=request.message))

        # 异步保存到 Redis
        if session.redis_client:
            human_msg = json.dumps({"type": "human", "content": request.message}, ensure_ascii=False)
            asyncio.create_task(session.bg_write(human_msg, ""))

        logger.info(f"消息已保存: {request.session_id}")

        return {
            "success": True,
            "session_id": session.session_id,
            "user_id": session.user_id
        }

    except Exception as e:
        logger.error(f"保存消息失败: {e}")
        return {
            "success": False,
            "message": f"保存失败: {str(e)}"
        }
