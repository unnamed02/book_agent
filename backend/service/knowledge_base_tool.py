"""
知识库工具 - 为客服节点提供 RAG 支持
支持向量检索和智能问答
"""

import logging
from typing import List, Dict, Optional
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_milvus import Milvus
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import asyncio

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    知识库管理器 - 基于 Milvus 的向量检索

    功能:
    1. 存储系统文档、FAQ、使用指南等
    2. 基于向量相似度检索相关知识
    3. 支持动态添加和更新知识
    """

    def __init__(
        self,
        collection_name: str = "customer_service_kb",
        embeddings: Optional[OpenAIEmbeddings] = None,
        vectorstore: Optional[Milvus] = None
    ):
        """
        初始化知识库

        Args:
            collection_name: Milvus 集合名称
            embeddings: 嵌入模型
            vectorstore: Milvus 向量存储
        """
        self.collection_name = collection_name
        self.embeddings = embeddings or OpenAIEmbeddings()
        self.vectorstore = vectorstore

        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "?", ".", "!", "?"]
        )

        logger.info(f"知识库初始化完成: {collection_name}")

    async def initialize_kb(self, knowledge_docs: List[Dict]):
        """
        初始化知识库（首次使用）

        Args:
            knowledge_docs: 知识文档列表
                [{"title": "...", "content": "...", "category": "..."}]
        """
        try:
            if not self.vectorstore:
                logger.warning("向量存储未配置，跳过知识库初始化")
                return

            # 准备文档
            documents = []
            for doc in knowledge_docs:
                # 分块
                chunks = self.text_splitter.split_text(doc["content"])

                for i, chunk in enumerate(chunks):
                    documents.append(Document(
                        page_content=chunk,
                        metadata={
                            "title": doc["title"],
                            "category": doc.get("category", "general"),
                            "chunk_id": i,
                            "source": "knowledge_base"
                        }
                    ))

            # 添加到向量库
            if documents:
                await asyncio.to_thread(
                    self.vectorstore.add_documents,
                    documents
                )
                logger.info(f"✓ 知识库初始化完成: {len(documents)} 个文档块")

        except Exception as e:
            logger.error(f"初始化知识库失败: {e}")

    async def search(
        self,
        query: str,
        top_k: int = 3,
        category_filter: Optional[str] = None
    ) -> List[Document]:
        """
        检索相关知识

        Args:
            query: 用户查询
            top_k: 返回结果数量
            category_filter: 分类过滤 (可选)

        Returns:
            相关文档列表
        """
        try:
            if not self.vectorstore:
                logger.warning("向量存储未配置")
                return []

            # 构建过滤条件
            search_kwargs = {"k": top_k}
            if category_filter:
                search_kwargs["expr"] = f'category == "{category_filter}"'

            # 向量检索
            docs = await asyncio.to_thread(
                self.vectorstore.similarity_search,
                query,
                **search_kwargs
            )

            logger.info(f"检索到 {len(docs)} 个相关知识片段")
            return docs

        except Exception as e:
            logger.error(f"知识检索失败: {e}")
            return []

    async def add_knowledge(
        self,
        title: str,
        content: str,
        category: str = "general"
    ):
        """
        添加新知识到知识库

        Args:
            title: 知识标题
            content: 知识内容
            category: 分类
        """
        try:
            if not self.vectorstore:
                logger.warning("向量存储未配置")
                return

            # 分块
            chunks = self.text_splitter.split_text(content)

            documents = []
            for i, chunk in enumerate(chunks):
                documents.append(Document(
                    page_content=chunk,
                    metadata={
                        "title": title,
                        "category": category,
                        "chunk_id": i,
                        "source": "knowledge_base"
                    }
                ))

            # 添加到向量库
            await asyncio.to_thread(
                self.vectorstore.add_documents,
                documents
            )

            logger.info(f"✓ 添加知识: {title}")

        except Exception as e:
            logger.error(f"添加知识失败: {e}")


class RAGCustomerService:
    """
    RAG 增强的客户服务

    结合知识库检索和 LLM 生成，提供准确的客服回答
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        llm: Optional[ChatOpenAI] = None
    ):
        """
        初始化 RAG 客服

        Args:
            knowledge_base: 知识库实例
            llm: 语言模型
        """
        self.kb = knowledge_base
        self.llm = llm or ChatOpenAI(model="qwen-flash", temperature=0.3)

    async def answer_question(
        self,
        user_query: str,
        conversation_history: Optional[List] = None
    ) -> Dict:
        """
        基于 RAG 回答用户问题

        Args:
            user_query: 用户问题
            conversation_history: 对话历史

        Returns:
            {
                "answer": "回答内容",
                "sources": ["来源1", "来源2"],
                "confidence": 0.85
            }
        """
        try:
            # 1. 检索相关知识
            relevant_docs = await self.kb.search(user_query, top_k=3)

            if not relevant_docs:
                # 没有找到相关知识，使用默认回答
                return await self._default_answer(user_query)

            # 2. 构建上下文
            context = self._build_context(relevant_docs)
            sources = self._extract_sources(relevant_docs)

            # 3. 生成回答
            prompt = self._build_prompt(user_query, context, conversation_history)

            response = await asyncio.to_thread(
                self.llm.invoke,
                prompt
            )

            answer = response.content

            # 4. 评估置信度（简单启发式）
            confidence = self._estimate_confidence(relevant_docs)

            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence
            }

        except Exception as e:
            logger.error(f"RAG 问答失败: {e}")
            return await self._default_answer(user_query)

    def _build_context(self, docs: List[Document]) -> str:
        """构建检索上下文"""
        context_parts = []
        for i, doc in enumerate(docs, 1):
            title = doc.metadata.get("title", "未知")
            content = doc.page_content
            context_parts.append(f"【知识 {i}: {title}】\n{content}")

        return "\n\n".join(context_parts)

    def _extract_sources(self, docs: List[Document]) -> List[str]:
        """提取知识来源"""
        sources = set()
        for doc in docs:
            title = doc.metadata.get("title", "系统文档")
            category = doc.metadata.get("category", "")
            sources.add(f"{title} ({category})" if category else title)

        return list(sources)

    def _build_prompt(
        self,
        user_query: str,
        context: str,
        conversation_history: Optional[List] = None
    ) -> str:
        """构建 RAG prompt"""

        # 对话历史
        history_text = ""
        if conversation_history:
            history_text = "\n## 对话历史\n" + "\n".join([
                f"- 用户: {h.get('user', '')}\n  助手: {h.get('assistant', '')}"
                for h in conversation_history[-3:]  # 只保留最近3轮
            ])

        prompt = f"""你是图书推荐系统的专业客服助手。请基于提供的知识库内容回答用户问题。

## 知识库内容
{context}
{history_text}

## 用户问题
{user_query}

## 回答要求
1. 优先使用知识库中的信息回答
2. 如果知识库没有直接答案，基于相关信息合理推断
3. 保持友好、专业的语气
4. 回答要简洁明了，重点突出
5. 如果确实无法回答，诚实告知并建议联系人工客服

请直接给出回答："""

        return prompt

    def _estimate_confidence(self, docs: List[Document]) -> float:
        """
        估计回答置信度

        简单启发式：
        - 有3个以上相关文档: 0.9
        - 有2个相关文档: 0.7
        - 只有1个相关文档: 0.5
        """
        if len(docs) >= 3:
            return 0.9
        elif len(docs) == 2:
            return 0.7
        elif len(docs) == 1:
            return 0.5
        else:
            return 0.3

    async def _default_answer(self, user_query: str) -> Dict:
        """
        知识库未找到时的默认回答
        """
        default_prompt = f"""你是图书推荐系统的客服助手。用户问了一个问题，但知识库中没有相关信息。

用户问题：{user_query}

请：
1. 简要说明你无法在知识库中找到相关信息
2. 基于常识尝试给出建议（如果适用）
3. 引导用户联系人工客服或提供更多细节

保持友好、专业的语气。"""

        response = await asyncio.to_thread(
            self.llm.invoke,
            default_prompt
        )

        return {
            "answer": response.content,
            "sources": [],
            "confidence": 0.3
        }


# ========== 预定义知识库内容 ==========

DEFAULT_KNOWLEDGE_BASE = [
    {
        "title": "系统功能介绍",
        "category": "feature",
        "content": """图书推荐系统是一个智能化的个性化图书推荐平台，具有以下核心功能：

1. 智能图书推荐
   - 基于用户需求和描述，推荐相关书籍
   - 支持按主题、类型、作者等多维度推荐
   - 提供豆瓣评分、书籍简介、推荐理由等详细信息

2. 个性化学习
   - 系统会记住你的阅读偏好
   - 根据你的历史浏览和反馈优化推荐
   - 避免重复推荐已看过的书籍

3. 多源信息整合
   - 豆瓣书籍评分和详情
   - 图书馆馆藏信息（索书号、位置、可借情况）
   - 电子资源链接（PDF、EPUB等）
   - 购买链接（当当、京东等）

4. 智能交互
   - 支持自然语言对话
   - 需求不明确时会主动提问澄清
   - 区分图书推荐和客服咨询
"""
    },
    {
        "title": "如何使用系统",
        "category": "usage",
        "content": """使用图书推荐系统非常简单：

## 基础使用
1. 直接描述你想读的书籍类型或主题
   - 例如："推荐Python编程的书"
   - 例如："我想学习机器学习"
   - 例如："有什么好看的科幻小说"

2. 指定具体书名查询
   - 例如："找红楼梦"
   - 例如："三体有馆藏吗"

3. 模糊需求也可以
   - 如果你的需求不够明确，系统会主动询问
   - 例如："推荐几本书" → 系统会问你感兴趣的领域

## 高级使用
1. 查看详细信息
   - 系统会自动提供豆瓣评分、简介、购买链接等

2. 个性化推荐
   - 持续使用系统，它会学习你的偏好
   - 越用越精准

3. 避免重复
   - 系统会记住已推荐的书籍
   - 不会重复推荐同一本书
"""
    },
    {
        "title": "常见问题FAQ",
        "category": "faq",
        "content": """## 推荐相关

Q: 推荐不准确怎么办？
A: 请提供更详细的需求描述，比如具体领域、难度级别、偏好风格等。系统会根据更详细的信息提供更精准的推荐。

Q: 可以推荐某个作者的书吗？
A: 可以！直接说"推荐刘慈欣的书"或"鲁迅写的书"即可。

Q: 能否查看历史推荐？
A: 可以！提供你的用户ID，系统会查询你的历史推荐记录。

## 馆藏相关

Q: 如何知道书在图书馆的位置？
A: 系统会自动显示馆藏信息，包括索书号、楼层、位置、可借数量等。

Q: 显示"暂无馆藏"怎么办？
A: 可以点击"荐购此书"链接，向图书馆推荐采购该书。

## 资源相关

Q: 有电子版资源吗？
A: 系统会自动搜索并提供电子资源链接（如果有的话）。

Q: 可以直接购买吗？
A: 系统会提供购买链接（当当、京东等），点击即可购买。


## 技术问题

Q: 系统响应慢怎么办？
A: 系统需要查询多个数据源（豆瓣、图书馆等），可能需要几秒钟时间，请耐心等待。

Q: 找不到某本书？
A: 可能是书名输入不完整或有误，尝试输入完整书名或作者名。
"""
    },
    {
        "title": "推荐策略说明",
        "category": "algorithm",
        "content": """系统的推荐策略：

## 推荐逻辑
1. 意图识别
   - 识别你是想要图书推荐还是咨询问题
   - 判断需求是否明确

2. 需求分析
   - 提取关键词（主题、类型、作者等）
   - 分析难度级别和阅读目的

3. 个性化匹配
   - 结合你的历史偏好
   - 考虑你已看过的书籍
   - 匹配最相关的书籍

4. 多维度评分
   - 内容相关性
   - 权威性（豆瓣评分）
   - 个性化匹配度
   - 时效性

## 避免重复
- 系统会记住最近30天内推荐过的书籍
- 不会重复推荐

## 持续学习
- 根据你的反馈调整推荐
- 学习你的阅读偏好
- 优化推荐权重
"""
    },
    {
        "title": "数据来源说明",
        "category": "data_source",
        "content": """系统的数据来源：

## 豆瓣书籍库
- 书籍基本信息（书名、作者、出版社、ISBN）
- 用户评分和评论
- 书籍简介和标签
- 封面图片

## 图书馆系统
- 馆藏信息（是否有藏书）
- 索书号和位置
- 可借状态和数量
- 借阅记录（用于推荐）

## 电子资源库
- PDF、EPUB等格式
- 来源包括各大电子图书馆
- 实时检索可用资源

## 电商平台
- 购买链接（当当、京东等）
- 价格信息
- 实时更新
"""
    }
]


def get_default_knowledge_base() -> List[Dict]:
    """获取默认知识库内容"""
    return DEFAULT_KNOWLEDGE_BASE
