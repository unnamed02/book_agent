"""
数据库模型定义 - 支持记忆系统
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class UserPreference(Base):
    """用户偏好表"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)

    # 偏好类型
    preference_type = Column(String(50), nullable=False)  # genre, author, topic, format
    preference_value = Column(Text, nullable=False)

    # 权重和置信度
    weight = Column(Float, default=1.0)  # 偏好权重 0-1
    confidence = Column(Float, default=0.5)  # 置信度

    # 来源
    source = Column(String(50))  # explicit(明确), implicit(隐式), inferred(推断)

    # 时间戳
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_reinforced_at = Column(DateTime)

    # 衰减
    decay_rate = Column(Float, default=0.95)  # 时间衰减率

    # 唯一约束
    __table_args__ = (
        Index('idx_user_pref_type_value', 'user_id', 'preference_type', 'preference_value', unique=True),
        Index('idx_user_weight', 'user_id', 'weight'),
    )

    def __repr__(self):
        return f"<UserPreference(user={self.user_id}, type={self.preference_type}, value={self.preference_value}, weight={self.weight})>"


class RecommendationHistory(Base):
    """推荐历史表"""
    __tablename__ = "recommendation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    session_id = Column(String(36))

    # 推荐内容
    title = Column(String(255), nullable=False)
    book_author = Column(String(255))
    book_isbn = Column(String(20), index=True)
    book_genre = Column(String(100))

    # 推荐原因
    recommendation_reason = Column(Text)
    confidence_score = Column(Float)  # 推荐置信度

    # 用户查询
    user_query = Column(Text)
    query_intent = Column(String(100))  # search, explore, learn

    # 时间戳
    recommended_at = Column(DateTime, default=datetime.now)

    # 关系
    feedbacks = relationship("FeedbackRecord", back_populates="recommendation", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_user_time', 'user_id', 'recommended_at'),
        Index('idx_isbn', 'book_isbn'),
        Index('idx_session', 'session_id'),
    )

    def __repr__(self):
        return f"<RecommendationHistory(user={self.user_id}, book={self.title}, at={self.recommended_at})>"


class FeedbackRecord(Base):
    """反馈记录表"""
    __tablename__ = "feedback_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    recommendation_id = Column(Integer, ForeignKey('recommendation_history.id', ondelete='CASCADE'))

    # 反馈类型
    feedback_type = Column(String(50), nullable=False)  # clicked, interested, not_interested, read

    # 评分
    rating = Column(Integer, CheckConstraint('rating >= 1 AND rating <= 5'))

    # 文字反馈
    comment = Column(Text)

    # 隐式反馈
    dwell_time = Column(Integer)  # 停留时间(秒)

    created_at = Column(DateTime, default=datetime.now)

    # 关系
    recommendation = relationship("RecommendationHistory", back_populates="feedbacks")

    # 索引
    __table_args__ = (
        Index('idx_user_feedback', 'user_id', 'feedback_type'),
        Index('idx_rating', 'rating'),
    )

    def __repr__(self):
        return f"<FeedbackRecord(user={self.user_id}, type={self.feedback_type}, rating={self.rating})>"


class ReadingProgress(Base):
    """阅读进度表"""
    __tablename__ = "reading_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)
    book_isbn = Column(String(20), nullable=False)

    # 进度
    status = Column(String(50), nullable=False)  # reading, completed, abandoned, want_to_read
    progress_percent = Column(Integer, default=0, nullable=False)

    # 时间
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 笔记
    notes = Column(Text)

    # 约束
    __table_args__ = (
        CheckConstraint('progress_percent >= 0 AND progress_percent <= 100', name='check_progress_range'),
        Index('idx_user_isbn', 'user_id', 'book_isbn', unique=True),
        Index('idx_status', 'status'),
        Index('idx_last_updated', 'last_updated'),
    )

    def __repr__(self):
        return f"<ReadingProgress(user={self.user_id}, isbn={self.book_isbn}, status={self.status}, progress={self.progress_percent}%)>"


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
