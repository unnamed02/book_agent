"""
用户记忆管理器 - LangChain 集成版本
支持短期记忆、工作记忆和长期记忆的统一管理
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import json
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from pydantic import BaseModel, ConfigDict
from langchain_milvus import Milvus
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
import logging

logger = logging.getLogger(__name__)


class LongTermUserMemory(BaseModel):
    """长期用户记忆 - 从数据库加载用户偏好和历史"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str
    db_session: AsyncSession
    memory_key: str = "long_term_memory"

    @property
    def memory_variables(self) -> List[str]:
        """返回记忆变量列表"""
        return [self.memory_key]

    async def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """加载用户长期记忆"""
        try:
            # 1. 加载用户偏好
            preferences = await self._load_preferences()

            # 2. 加载最近推荐(避免重复)
            recent_books = await self._load_recent_recommendations(days=30)

            # 3. 加载正面反馈书籍
            liked_books = await self._load_liked_books()

            # 4. 加载阅读进度
            reading_progress = await self._load_reading_progress()

            # 5. 构建记忆上下文
            memory_context = {
                "preferences": self._format_preferences(preferences),
                "recent_recommendations": recent_books,
                "liked_books": liked_books,
                "reading_progress": reading_progress,
                "user_profile": await self._build_user_profile(preferences)
            }

            return {self.memory_key: memory_context}

        except Exception as e:
            logger.error(f"加载长期记忆失败: {str(e)}")
            return {self.memory_key: {}}

    async def _load_preferences(self) -> List[Dict]:
        """加载用户偏好"""
        from backend.utils.models import UserPreference

        result = await self.db_session.execute(
            select(UserPreference)
            .where(UserPreference.user_id == self.user_id)
            .where(UserPreference.weight > 0.1)  # 只加载权重>0.1的偏好
            .order_by(desc(UserPreference.weight))
        )

        preferences = result.scalars().all()

        # 应用时间衰减
        return self._apply_time_decay(preferences)

    async def _load_recent_recommendations(self, days: int = 30) -> List[Dict]:
        """加载最近N天的推荐书籍,避免重复推荐"""
        from backend.utils.models import RecommendationHistory

        cutoff_date = datetime.now() - timedelta(days=days)

        result = await self.db_session.execute(
            select(RecommendationHistory.book_title, RecommendationHistory.book_isbn)
            .where(
                and_(
                    RecommendationHistory.user_id == self.user_id,
                    RecommendationHistory.recommended_at >= cutoff_date
                )
            )
            .distinct()
        )

        books = []
        for row in result.all():
            title = row[0]
            isbn = row[1]
            # 如果有 ISBN，显示为 "书名 (ISBN: xxx)"，否则只显示书名
            if isbn and isbn != "":
                books.append(f"{title} (ISBN: {isbn})")
            else:
                books.append(title)

        return books

    async def _load_liked_books(self) -> List[Dict]:
        """加载用户喜欢的书籍"""
        from backend.utils.models import FeedbackRecord, RecommendationHistory

        result = await self.db_session.execute(
            select(RecommendationHistory)
            .join(FeedbackRecord)
            .where(
                and_(
                    RecommendationHistory.user_id == self.user_id,
                    FeedbackRecord.rating >= 4  # 4星及以上
                )
            )
            .order_by(desc(FeedbackRecord.created_at))
            .limit(10)
        )

        books = result.scalars().all()
        return [
            {
                "title": book.book_title,
                "author": book.book_author,
                "genre": book.book_genre,
                "isbn": book.book_isbn
            }
            for book in books
        ]

    async def _load_reading_progress(self) -> List[Dict]:
        """加载阅读进度"""
        from backend.utils.models import ReadingProgress

        result = await self.db_session.execute(
            select(ReadingProgress)
            .where(
                and_(
                    ReadingProgress.user_id == self.user_id,
                    ReadingProgress.status.in_(['reading', 'completed'])
                )
            )
            .order_by(desc(ReadingProgress.last_updated))
            .limit(5)
        )

        progress = result.scalars().all()
        return [
            {
                "isbn": p.book_isbn,
                "status": p.status,
                "progress": p.progress_percent
            }
            for p in progress
        ]

    def _apply_time_decay(self, preferences: List, decay_rate: float = 0.95) -> List[Dict]:
        """应用时间衰减"""
        now = datetime.now()
        decayed_prefs = []

        for pref in preferences:
            if pref.last_reinforced_at:
                days_passed = (now - pref.last_reinforced_at).days
                decay_periods = days_passed / 30  # 每30天一个衰减周期

                # 指数衰减
                current_weight = pref.weight * (decay_rate ** decay_periods)

                if current_weight >= 0.1:
                    decayed_prefs.append({
                        "type": pref.preference_type,
                        "value": pref.preference_value,
                        "weight": current_weight,
                        "source": pref.source
                    })

        return decayed_prefs

    def _format_preferences(self, preferences: List[Dict]) -> Dict:
        """格式化偏好数据"""
        formatted = defaultdict(list)

        for pref in preferences:
            formatted[pref["type"]].append({
                "value": pref["value"],
                "weight": pref["weight"]
            })

        # 按权重排序
        for pref_type in formatted:
            formatted[pref_type].sort(key=lambda x: x["weight"], reverse=True)

        return dict(formatted)

    async def _build_user_profile(self, preferences: List[Dict]) -> str:
        """构建用户画像摘要"""
        if not preferences:
            return "新用户,暂无阅读偏好"

        # 提取top偏好
        top_genres = []
        top_authors = []
        top_topics = []

        for pref in preferences[:10]:  # 只取前10个
            if pref["type"] == "genre":
                top_genres.append(pref["value"])
            elif pref["type"] == "author":
                top_authors.append(pref["value"])
            elif pref["type"] == "topic":
                top_topics.append(pref["value"])

        profile_parts = []
        if top_genres:
            profile_parts.append(f"喜欢 {', '.join(top_genres[:3])}")
        if top_authors:
            profile_parts.append(f"喜爱作者: {', '.join(top_authors[:3])}")
        if top_topics:
            profile_parts.append(f"关注主题: {', '.join(top_topics[:3])}")

        return "; ".join(profile_parts) if profile_parts else "无明显偏好"

    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """保存上下文(异步处理)"""
        # 长期记忆的保存通过专门的接口处理,这里不实现
        pass

    def clear(self) -> None:
        """清除记忆"""
        pass


class UserMemoryManager:
    """
    用户记忆管理器 - 整合短期、工作和长期记忆
    """

    def __init__(
        self,
        user_id: str,
        db_session: AsyncSession,
        llm: Optional[ChatOpenAI] = None,
        embeddings: Optional[OpenAIEmbeddings] = None,
        vectorstore: Optional[Milvus] = None
    ):
        self.user_id = user_id
        self.db_session = db_session
        self.llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.vectorstore = vectorstore

        # 记忆缓存
        self._memories: Dict[str, Any] = {}

        # 初始化各层记忆
        self._init_memories()

    def _init_memories(self):
        """初始化记忆组件 (使用 LangChain 1.x 推荐方式)"""

        # 1. 短期记忆 - 使用 ChatMessageHistory 存储最近对话
        self.chat_history = ChatMessageHistory()

        # 2. 长期记忆 - 用户偏好和历史
        self.longterm_memory = LongTermUserMemory(
            user_id=self.user_id,
            db_session=self.db_session
        )

        logger.info(f"用户 {self.user_id} 记忆系统初始化完成 (LangChain 1.x)")

    async def load_all_memories(self, user_input: str) -> Dict[str, Any]:
        """加载所有类型的记忆 (LangChain 1.x)"""
        inputs = {"input": user_input}
        memories = {}

        try:
            # 1. 短期记忆 - 从 ChatMessageHistory 获取
            chat_messages = self.chat_history.messages
            if chat_messages:
                memories["chat_history"] = chat_messages

            # 2. 长期记忆 (异步)
            long_term = await self.longterm_memory.load_memory_variables(inputs)
            memories.update(long_term)

            # 缓存记忆
            self._memories = memories

            logger.info(f"成功加载用户 {self.user_id} 的所有记忆")
            return memories

        except Exception as e:
            logger.error(f"加载记忆失败: {str(e)}")
            self._memories = {}
            return {}

    def get_memories(self) -> Dict[str, Any]:
        """获取已加载的记忆"""
        return self._memories

    def save_interaction(self, user_input: str, assistant_output: str):
        """保存交互到短期记忆 (LangChain 1.x)"""
        # 保存到 ChatMessageHistory
        self.chat_history.add_user_message(user_input)
        self.chat_history.add_ai_message(assistant_output)

        # 只保留最近10条消息
        if len(self.chat_history.messages) > 20:  # 10轮对话 = 20条消息
            self.chat_history.messages = self.chat_history.messages[-20:]

        logger.debug(f"保存交互到短期记忆: {user_input[:50]}...")

    async def save_to_vector_store(self, user_input: str, assistant_output: str, metadata: Dict = None):
        """保存到向量数据库"""
        if not self.vectorstore:
            return

        try:
            # 构建文档
            text = f"用户: {user_input}\n助手: {assistant_output}"
            meta = {
                "user_id": self.user_id,
                "timestamp": datetime.now().isoformat(),
                **(metadata or {})
            }

            # 添加到向量库
            await asyncio.to_thread(
                self.vectorstore.add_texts,
                texts=[text],
                metadatas=[meta]
            )

            logger.debug("保存到向量数据库成功")

        except Exception as e:
            logger.error(f"保存到向量数据库失败: {str(e)}")

    async def save_recommendation(
        self,
        book: Dict,
        user_query: str,
        session_id: str,
        confidence_score: float = None,
        auto_commit: bool = True
    ):
        """保存推荐记录到长期记忆"""
        from backend.utils.models import RecommendationHistory

        try:
            recommendation = RecommendationHistory(
                user_id=self.user_id,
                session_id=session_id,
                book_title=book.get("title", ""),
                book_author=book.get("author", ""),
                book_isbn=book.get("isbn", ""),
                book_genre=book.get("genre", ""),
                recommendation_reason=book.get("reason", ""),
                confidence_score=confidence_score,
                user_query=user_query,
                recommended_at=datetime.now()
            )

            self.db_session.add(recommendation)

            if auto_commit:
                await self.db_session.commit()
                logger.info(f"✓ 保存推荐记录: {book.get('title')}")
            else:
                logger.debug(f"添加推荐记录到会话（未提交）: {book.get('title')}")

        except Exception as e:
            logger.error(f"保存推荐记录失败: {str(e)}")
            if auto_commit:
                await self.db_session.rollback()
            raise  # 重新抛出异常，让调用者处理

    async def update_preferences_from_query(self, user_query: str):
        """基于用户现有偏好和当前查询，智能更新偏好"""

        try:
            # 1. 加载用户当前偏好
            current_preferences = await self.longterm_memory._load_preferences()

            # 2. 格式化当前偏好供 LLM 参考
            current_prefs_text = self._format_current_preferences(current_preferences)

            # 3. 使用 LLM 提取偏好，同时考虑历史偏好
            extract_prompt = f"""你是一个专业的用户偏好分析助手。请基于用户的历史偏好和当前查询，分析并更新用户的阅读偏好。

## 用户当前偏好
{current_prefs_text}

## 用户当前查询
{user_query}

## 任务
1. 从当前查询中提取新的偏好信息（类型、主题、作者等）
2. 结合用户的历史偏好，判断这些新偏好是否需要添加或强化
3. 如果查询与现有偏好相关，应该强化现有偏好的权重

## 返回格式（JSON）
{{
    "genres": ["类型1", "类型2"],
    "topics": ["主题1", "主题2"],
    "authors": ["作者1"],
    "reading_level": "beginner/intermediate/advanced",
    "purpose": "entertainment/learning/research",
    "reasoning": "简短说明你的分析"
}}

注意：
- 只提取明确提到的信息，不要过度推测
- 如果查询很模糊或只是澄清问题，返回空列表
- genres/topics/authors 应该是具体的值，如 "科幻"、"Python编程"、"刘慈欣"
"""

            response = await asyncio.to_thread(
                self.llm.invoke,
                extract_prompt
            )

            # 解析 LLM 响应
            prefs = self._parse_preferences(response.content)

            if prefs and any(prefs.get(k) for k in ["genres", "topics", "authors"]):
                # 更新数据库
                await self._upsert_preferences(prefs, source="explicit")
                logger.info(f"从查询更新偏好: {prefs}")
            else:
                logger.debug("查询中未提取到明确偏好，跳过更新")

        except Exception as e:
            logger.error(f"更新偏好失败: {str(e)}")

    def _format_current_preferences(self, preferences: List[Dict]) -> str:
        """格式化当前偏好为文本"""
        if not preferences:
            return "暂无历史偏好（新用户）"

        formatted_prefs = defaultdict(list)
        for pref in preferences[:15]:  # 只显示前15个
            formatted_prefs[pref["type"]].append(
                f"{pref['value']} (权重: {pref['weight']:.2f})"
            )

        result = []
        if formatted_prefs.get("genre"):
            result.append(f"- 喜欢的类型: {', '.join(formatted_prefs['genre'][:5])}")
        if formatted_prefs.get("topic"):
            result.append(f"- 关注的主题: {', '.join(formatted_prefs['topic'][:5])}")
        if formatted_prefs.get("author"):
            result.append(f"- 喜爱的作者: {', '.join(formatted_prefs['author'][:5])}")

        return "\n".join(result) if result else "暂无明显偏好"

    def _parse_preferences(self, llm_response: str) -> Dict:
        """解析 LLM 返回的偏好"""
        try:
            # 清理 markdown 代码块
            clean_response = llm_response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
                clean_response = clean_response.strip()

            return json.loads(clean_response)
        except Exception as e:
            logger.warning(f"解析偏好失败: {str(e)}")
            return {}

    async def _upsert_preferences(self, preferences: Dict, source: str = "explicit"):
        """插入或更新用户偏好"""
        from backend.utils.models import UserPreference

        try:
            # 处理各类偏好
            for genre in preferences.get("genres", []):
                await self._upsert_single_preference("genre", genre, source, weight=0.7)

            for topic in preferences.get("topics", []):
                await self._upsert_single_preference("topic", topic, source, weight=0.6)

            for author in preferences.get("authors", []):
                await self._upsert_single_preference("author", author, source, weight=0.8)

            await self.db_session.commit()

        except Exception as e:
            logger.error(f"更新偏好数据库失败: {str(e)}")
            await self.db_session.rollback()

    async def _upsert_single_preference(
        self,
        pref_type: str,
        pref_value: str,
        source: str,
        weight: float = 0.5
    ):
        """插入或更新单个偏好"""
        from backend.utils.models import UserPreference

        # 查询是否存在
        result = await self.db_session.execute(
            select(UserPreference).where(
                and_(
                    UserPreference.user_id == self.user_id,
                    UserPreference.preference_type == pref_type,
                    UserPreference.preference_value == pref_value
                )
            )
        )

        existing = result.scalar_one_or_none()

        if existing:
            # 更新权重 (加权平均)
            existing.weight = (existing.weight * 0.7) + (weight * 0.3)
            existing.last_reinforced_at = datetime.now()
            existing.updated_at = datetime.now()
        else:
            # 新建
            new_pref = UserPreference(
                user_id=self.user_id,
                preference_type=pref_type,
                preference_value=pref_value,
                weight=weight,
                source=source,
                last_reinforced_at=datetime.now()
            )
            self.db_session.add(new_pref)

    def build_personalized_prompt(self, user_query: str, base_prompt: str, memories: Dict) -> str:
        """构建个性化 prompt"""

        # 提取长期记忆
        long_term = memories.get("long_term_memory", {})
        user_profile = long_term.get("user_profile", "新用户")
        liked_books = long_term.get("liked_books", [])
        recent_books = long_term.get("recent_recommendations", [])

        # 构建个性化前缀
        personalization = f"""
## 用户画像
{user_profile}

## 用户喜欢的书籍
{self._format_book_list(liked_books[:5])}

## 最近已推荐(请避免重复)
{', '.join(recent_books[:10]) if recent_books else '无'}
"""

        # 整合 prompt
        enhanced_prompt = f"{personalization}\n\n{base_prompt}\n\n## 当前需求\n{user_query}"

        return enhanced_prompt

    def _format_book_list(self, books: List[Dict]) -> str:
        """格式化书籍列表"""
        if not books:
            return "暂无"

        formatted = []
        for book in books:
            formatted.append(
                f"- 《{book.get('title')}》 作者:{book.get('author')} ({book.get('genre')})"
            )

        return "\n".join(formatted)

    def get_memory_summary(self) -> Dict:
        """获取记忆系统摘要"""
        return {
            "user_id": self.user_id,
            "buffer_size": len(self.buffer_memory.buffer),
            "has_vector_memory": self.retriever_memory is not None,
            "has_longterm_memory": True
        }
