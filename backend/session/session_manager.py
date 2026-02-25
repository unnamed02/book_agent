"""
会话管理器
管理所有会话的生命周期，使用 LRU 缓存策略
"""

from typing import Optional
from collections import OrderedDict
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import logging
import uuid
from utils.models import User, UserSession
from sqlalchemy import select

from .session import Session

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器 - 使用 LRU 缓存策略管理所有会话
    """

    def __init__(
        self,
        session_timeout: int = 3600,
        max_sessions: int = 1000,
        redis_client: Optional[redis.Redis] = None
    ):
        """
        初始化会话管理器

        Args:
            session_timeout: 会话超时时间（秒，默认1小时）
            max_sessions: 最大会话数量（默认1000，超过后淘汰最久未使用的）
            redis_client: Redis客户端（可选）
        """
        self.sessions: OrderedDict[str, Session] = OrderedDict()
        self.session_timeout = session_timeout
        self.max_sessions = max_sessions
        self.redis_client = redis_client
        logger.info(f"✓ 会话管理器已初始化 (最大会话数: {max_sessions})")

    async def get_or_create_session(
        self,
        session_id: Optional[str],
        user_id: Optional[str],
        db: Optional[AsyncSession] = None
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
        # 生成默认ID
        session_id = session_id or str(uuid.uuid4())
        user_id = user_id or f"user_{session_id}"

        # 清理过期会话
        self._cleanup_expired_sessions()

        # 获取或创建会话
        if session_id in self.sessions:
            # 情况1: LRU 缓存中存在，直接返回
            session = self.sessions[session_id]
            session.update_access_time()
            self.sessions.move_to_end(session_id)
            return session

        # 情况2和3: LRU 中没有，检查数据库
        existing_session = None
        if db is not None:
            try:
                result = await db.execute(
                    select(UserSession).where(UserSession.session_id == session_id)
                )
                existing_session = result.scalar_one_or_none()
            except Exception as e:
                logger.error(f"查询会话失败: {e}")

        if existing_session:
            # 情况2: 数据库中存在，从 Redis 恢复
            logger.info(f"从数据库恢复会话: {session_id}")

            # 检查是否超过最大会话数
            if len(self.sessions) >= self.max_sessions:
                oldest_sid, _ = self.sessions.popitem(last=False)
                logger.info(f"🗑️ LRU 淘汰会话: {oldest_sid}")

            # 创建会话实例
            session = Session(
                session_id=session_id,
                user_id=existing_session.user_id,
                system_context="你是专业的图书推荐助手。",
                max_history_rounds=10,
                redis_client=self.redis_client
            )

            # 从 Redis 加载历史对话
            if self.redis_client:
                await session.load_from_redis()

            self.sessions[session_id] = session

        else:
            # 情况3: 数据库中也没有，创建新会话
            logger.info(f"创建新会话: {session_id}")

            # 检查是否超过最大会话数
            if len(self.sessions) >= self.max_sessions:
                oldest_sid, _ = self.sessions.popitem(last=False)
                logger.info(f"🗑️ LRU 淘汰会话: {oldest_sid}")

            # 检查该用户是否有旧会话，如果有则归档最近的一个
            if self.redis_client and db is not None:
                try:
                    result = await db.execute(
                        select(UserSession)
                        .where(UserSession.user_id == user_id)
                        .order_by(UserSession.last_active_at.desc())
                        .limit(1)
                    )
                    latest_old_session = result.scalar_one_or_none()

                    # 将最近的旧会话加入合并归档队列
                    if latest_old_session:
                        old_session_id = latest_old_session.session_id
                        old_key = f"conversation:{old_session_id}"
                        list_len = await self.redis_client.llen(old_key)
                        if list_len > 0:
                            await self.redis_client.sadd("merge_archive_list", old_key)
                            logger.info(f"用户 {user_id} 创建新会话，旧会话 {old_session_id} 已加入合并归档队列 ({list_len} 条消息)")

                        # 从 LRU 缓存中删除旧会话
                        if old_session_id in self.sessions:
                            del self.sessions[old_session_id]
                            logger.info(f"从 LRU 缓存中删除旧会话: {old_session_id}")
                except Exception as e:
                    logger.error(f"归档旧会话失败: {e}")

            # 创建新会话实例
            session = Session(
                session_id=session_id,
                user_id=user_id,
                system_context="你是专业的图书推荐助手。",
                max_history_rounds=10,
                redis_client=self.redis_client
            )
            self.sessions[session_id] = session

            # 保存到数据库
            if db is not None:
                try:
                    # 确保用户存在
                    result = await db.execute(select(User).where(User.user_id == user_id))
                    user = result.scalar_one_or_none()
                    if not user:
                        user = User(user_id=user_id)
                        db.add(user)
                        await db.flush()
                        logger.info(f"✓ 创建新用户: {user_id}")

                    # 创建会话记录
                    user_session = UserSession(
                        user_id=user_id,
                        session_id=session_id
                    )
                    db.add(user_session)
                    await db.commit()
                except Exception as e:
                    await db.rollback()

        return session

    def _cleanup_expired_sessions(self):
        """清理过期会话（基于时间的清理，配合 LRU 使用）"""
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout)
        ]

        for sid in expired:
            del self.sessions[sid]
            logger.info(f"🗑️ 清理过期会话: {sid}")

        if expired:
            logger.info(f"✓ 清理了 {len(expired)} 个过期会话")

    def get_session_count(self) -> int:
        """获取当前会话数量"""
        return len(self.sessions)

    def get_session(self, session_id: str) -> Optional[Session]:
        """根据ID获取会话"""
        return self.sessions.get(session_id)
