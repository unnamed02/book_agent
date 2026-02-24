"""
数据库模型定义
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    """用户表"""
    __tablename__ = "users"

    user_id = Column(String(100), primary_key=True, comment="用户ID（微信openid）")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


class UserSession(Base):
    """用户会话表"""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True, comment="用户ID")
    session_id = Column(String(100), unique=True, nullable=False, index=True, comment="会话ID")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    last_active_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="最后活跃时间")


class ConversationArchive(Base):
    """对话历史归档表"""
    __tablename__ = "conversation_archives"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False, index=True, comment="会话ID")
    messages = Column(JSONB, nullable=False, comment="消息列表（JSONB）")
    archived_at = Column(DateTime, default=func.now(), comment="归档时间")


class PurchaseRecommendation(Base):
    """荐购表单表"""
    __tablename__ = "purchase_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False, index=True, comment="用户ID")
    book_title = Column(String(500), nullable=False, comment="书名")
    author = Column(String(200), nullable=True, comment="作者")
    notes = Column(Text, nullable=True, comment="备注")
    contact = Column(String(100), nullable=True, comment="联系方式")
    status = Column(String(20), default="pending", comment="状态: pending/approved/rejected")
    created_at = Column(DateTime, default=func.now(), comment="提交时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")


# 数据库连接和会话管理
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, database_url: str = None):
        """
        初始化数据库连接

        Args:
            database_url: 数据库连接URL,如果不提供则从环境变量读取
                         格式: postgresql+asyncpg://user:password@host:port/database
        """
        # 默认数据库路径：使用绝对路径避免工作目录问题
        default_db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "book_agent.db"
        )
        default_url = f"sqlite+aiosqlite:///{default_db_path}"

        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            default_url
        )

        # 创建异步引擎
        self.engine = create_async_engine(
            self.database_url,
            echo=False,  # 生产环境设为False
            poolclass=NullPool if "sqlite" in self.database_url else None,
            pool_pre_ping=True,  # 连接健康检查
        )

        # 创建会话工厂
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        """初始化数据库表"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        """获取数据库会话"""
        async with self.async_session_maker() as session:
            yield session

    async def close(self):
        """关闭数据库连接"""
        await self.engine.dispose()


# 全局数据库管理器实例
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """获取全局数据库管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_db() -> AsyncSession:
    """依赖注入: 获取数据库会话"""
    db_manager = get_db_manager()
    async with db_manager.async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
