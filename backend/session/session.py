"""
会话管理类
封装会话相关的所有状态和管理器，包括对话上下文管理和记忆管理
"""

from typing import Optional, List, Dict
from datetime import datetime
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_milvus import Milvus
from backend.session.memory_manager import UserMemoryManager
from backend.session.conversation_manager import ConversationManager, create_conversation_manager
from backend.service.knowledge_base_tool import RAGCustomerService, KnowledgeBase
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


class Session:
    """
    会话类 - 封装单个用户会话的所有状态

    属性:
        - session_id: 会话ID
        - user_id: 用户ID
        - conversation_manager: 对话管理器（管理上下文）
        - memory_manager: 记忆管理器（管理长期记忆）
        - rag_service: RAG 客服服务（处理知识库问答）
        - history: 对话历史（简单备份）
        - last_access: 最后访问时间
    """

    def __init__(
        self,
        session_id: str,
        user_id: str,
        system_context: str = "你是专业的图书推荐助手。",
        max_history_rounds: int = 10
    ):
        """
        初始化会话

        Args:
            session_id: 会话ID
            user_id: 用户ID
            system_context: 系统上下文
            max_history_rounds: 最大保留对话轮数
        """
        self.session_id = session_id
        self.user_id = user_id
        self.last_access = datetime.now()

        # 创建对话管理器（每个会话一个）
        self.conversation_manager = create_conversation_manager(
            user_id=user_id,
            system_context=system_context,
            max_history_rounds=max_history_rounds
        )

        # 记忆管理器（懒加载）
        self.memory_manager: Optional[UserMemoryManager] = None

        # RAG 客服服务（懒加载）
        self.rag_service: Optional[RAGCustomerService] = None

        # 对话历史（备份用）
        self.history: List[Dict] = []

        logger.info(f"✓ 创建会话: {session_id} (用户: {user_id})")

    def update_access_time(self):
        """更新最后访问时间"""
        self.last_access = datetime.now()

    def is_expired(self, timeout_seconds: int = 3600) -> bool:
        """
        检查会话是否过期

        Args:
            timeout_seconds: 超时时间（秒）

        Returns:
            是否过期
        """
        elapsed = (datetime.now() - self.last_access).total_seconds()
        return elapsed > timeout_seconds

    async def initialize_memory_manager(
        self,
        db_session: AsyncSession,
        vectorstore: Milvus
    ):
        """
        初始化记忆管理器（懒加载）

        Args:
            db_session: 数据库会话
            vectorstore: 向量数据库
        """
        if self.memory_manager is not None:
            # 如果已存在，只更新数据库会话
            self.memory_manager.db_session = db_session
            self.memory_manager.longterm_memory.db_session = db_session
            logger.debug(f"更新会话 {self.session_id} 的数据库会话")
            return

        try:
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            embeddings = OpenAIEmbeddings()

            self.memory_manager = UserMemoryManager(
                user_id=self.user_id,
                db_session=db_session,
                llm=llm,
                embeddings=embeddings,
                vectorstore=vectorstore
            )

            # 首次加载长期记忆（用户画像、历史推荐等）
            # 这些数据相对稳定，只在 session 创建时加载一次
            await self.memory_manager.load_all_memories("")

            logger.info(f"✓ 为会话 {self.session_id} 创建记忆管理器并加载长期记忆")
        except Exception as e:
            logger.warning(f"创建记忆管理器失败: {e}，将使用无记忆模式")
            self.memory_manager = None

    async def initialize_rag_service(
        self,
        kb_vectorstore: Optional[Milvus] = None
    ):
        """
        初始化 RAG 客服服务（懒加载）

        Args:
            kb_vectorstore: 知识库向量数据库
        """
        if self.rag_service is not None:
            logger.debug(f"会话 {self.session_id} 的 RAG 服务已存在")
            return

        try:
            if kb_vectorstore is None:
                logger.warning("知识库向量数据库未提供，RAG 服务不可用")
                return

            embeddings = OpenAIEmbeddings()
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

            # 创建知识库
            kb = KnowledgeBase(
                collection_name="customer_service_kb",
                embeddings=embeddings,
                vectorstore=kb_vectorstore
            )

            # 创建 RAG 服务
            self.rag_service = RAGCustomerService(
                knowledge_base=kb,
                llm=llm
            )

            logger.info(f"✓ 为会话 {self.session_id} 创建 RAG 客服服务")

        except Exception as e:
            logger.warning(f"创建 RAG 服务失败: {e}，将使用默认客服模式")
            self.rag_service = None

    def add_to_history(self, user_msg: str, assistant_msg: str):
        """
        添加对话到历史记录（简单备份）

        Args:
            user_msg: 用户消息
            assistant_msg: 助手消息
        """
        self.history.append({
            "user": user_msg,
            "assistant": assistant_msg
        })

        # 只保留最近5轮对话
        if len(self.history) > 5:
            self.history = self.history[-5:]

    async def update_preferences(self, user_query: str):
        """
        根据用户查询增量更新偏好（不重新加载所有记忆）

        Args:
            user_query: 用户查询
        """
        if not self.memory_manager:
            return

        try:
            # 只提取并更新用户偏好，不重新加载所有记忆
            await self.memory_manager.update_preferences_from_query(user_query)
            logger.debug(f"✓ 会话 {self.session_id} 更新偏好成功")
        except Exception as e:
            logger.error(f"✗ 会话 {self.session_id} 更新偏好失败: {e}")

    def get_conversation_rounds(self) -> int:
        """获取对话轮数"""
        return self.conversation_manager.get_conversation_rounds()

    def __repr__(self) -> str:
        return f"Session(id={self.session_id}, user={self.user_id}, rounds={self.get_conversation_rounds()})"


class SessionManager:
    """
    会话管理器 - 管理所有会话
    """

    def __init__(self, session_timeout: int = 3600):
        """
        初始化会话管理器

        Args:
            session_timeout: 会话超时时间（秒，默认1小时）
        """
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
        logger.info("✓ 会话管理器已初始化")

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        db: Optional[AsyncSession] = None,
        vectorstore: Optional[Milvus] = None
    ) -> Session:
        """
        获取或创建会话

        Args:
            session_id: 会话ID（可选）
            user_id: 用户ID（可选）
            db: 数据库会话
            vectorstore: 向量数据库

        Returns:
            Session 实例
        """
        import uuid

        # 生成默认ID
        if not session_id:
            session_id = str(uuid.uuid4())
        if not user_id:
            user_id = f"user_{session_id}"

        # 清理过期会话
        self._cleanup_expired_sessions()

        # 获取或创建会话
        if session_id not in self.sessions:
            # 创建新会话
            session = Session(
                session_id=session_id,
                user_id=user_id,
                system_context="你是专业的图书推荐助手。",
                max_history_rounds=10
            )
            self.sessions[session_id] = session
        else:
            # 更新访问时间
            session = self.sessions[session_id]
            session.update_access_time()

        # 懒加载记忆管理器
        if db is not None and vectorstore is not None:
            await session.initialize_memory_manager(db, vectorstore)

        return session

    def _cleanup_expired_sessions(self):
        """清理过期会话"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]
    
        for sid in expired:
            del self.sessions[sid]
            logger.info(f"🗑️ 清理过期会话: {sid}")

    def get_session_count(self) -> int:
        """获取当前会话数量"""
        return len(self.sessions)

    def get_session(self, session_id: str) -> Optional[Session]:
        """根据ID获取会话"""
        return self.sessions.get(session_id)
