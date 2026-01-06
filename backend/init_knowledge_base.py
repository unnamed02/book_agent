"""
知识库初始化脚本
用于首次创建和更新知识库
"""

import asyncio
import logging
from langchain_openai import OpenAIEmbeddings
from langchain_milvus import Milvus
from knowledge_base_tool import (
    KnowledgeBase,
    RAGCustomerService,
    get_default_knowledge_base
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def initialize_knowledge_base(
    milvus_uri: str = "./milvus_kb.db",
    collection_name: str = "customer_service_kb"
):
    """
    初始化知识库

    Args:
        milvus_uri: Milvus 连接URI（本地文件或远程服务）
        collection_name: 集合名称
    """
    try:
        logger.info("开始初始化知识库...")

        # 初始化 Embeddings
        embeddings = OpenAIEmbeddings()

        # 初始化 Milvus 向量存储
        vectorstore = Milvus(
            embedding_function=embeddings,
            connection_args={"uri": milvus_uri},
            collection_name=collection_name,
            drop_old=True,  # 删除旧集合，重新创建
        )

        # 创建知识库
        kb = KnowledgeBase(
            collection_name=collection_name,
            embeddings=embeddings,
            vectorstore=vectorstore
        )

        # 加载默认知识
        default_knowledge = get_default_knowledge_base()
        logger.info(f"加载 {len(default_knowledge)} 个默认知识文档")

        # 初始化知识库
        await kb.initialize_kb(default_knowledge)

        logger.info("✅ 知识库初始化完成！")
        logger.info(f"  - Milvus URI: {milvus_uri}")
        logger.info(f"  - 集合名称: {collection_name}")
        logger.info(f"  - 文档数量: {len(default_knowledge)}")

        return kb

    except Exception as e:
        logger.error(f"❌ 知识库初始化失败: {e}")
        raise


async def test_knowledge_base(kb: KnowledgeBase):
    """
    测试知识库检索
    """
    logger.info("\n" + "="*50)
    logger.info("测试知识库检索功能")
    logger.info("="*50)

    test_queries = [
        "如何使用这个系统？",
        "推荐不准确怎么办？",
        "有电子资源吗？",
        "如何查看历史推荐？",
        "系统有什么功能？"
    ]

    for query in test_queries:
        logger.info(f"\n查询: {query}")
        docs = await kb.search(query, top_k=2)

        if docs:
            for i, doc in enumerate(docs, 1):
                logger.info(f"  结果 {i}: {doc.metadata.get('title', '未知')}")
                logger.info(f"    内容: {doc.page_content[:100]}...")
        else:
            logger.info("  未找到相关结果")


async def test_rag_service(kb: KnowledgeBase):
    """
    测试 RAG 客服服务
    """
    logger.info("\n" + "="*50)
    logger.info("测试 RAG 客服服务")
    logger.info("="*50)

    rag_service = RAGCustomerService(knowledge_base=kb)

    test_questions = [
        "这个系统有什么功能？",
        "怎么使用推荐系统？",
        "如果推荐的书不准确怎么办？",
        "可以查看我的历史推荐吗？"
    ]

    for question in test_questions:
        logger.info(f"\n问题: {question}")
        result = await rag_service.answer_question(question)

        logger.info(f"回答: {result['answer'][:200]}...")
        logger.info(f"置信度: {result['confidence']:.2f}")
        if result['sources']:
            logger.info(f"来源: {', '.join(result['sources'])}")


async def add_custom_knowledge(kb: KnowledgeBase):
    """
    添加自定义知识示例
    """
    logger.info("\n" + "="*50)
    logger.info("添加自定义知识")
    logger.info("="*50)

    custom_knowledge = {
        "title": "图书馆开放时间",
        "category": "library_info",
        "content": """图书馆开放时间安排：

周一至周五: 8:00 - 22:00
周六周日: 9:00 - 18:00
法定节假日: 10:00 - 16:00

特别提醒：
- 考试周期间，开放时间会延长至晚上24:00
- 寒暑假期间，开放时间会有所调整，请关注图书馆官网通知
- 自习区域24小时开放（需刷卡进入）

联系方式：
- 咨询电话: 123-4567-8900
- 电子邮件: library@example.edu
"""
    }

    await kb.add_knowledge(
        title=custom_knowledge["title"],
        content=custom_knowledge["content"],
        category=custom_knowledge["category"]
    )

    logger.info(f"✅ 成功添加知识: {custom_knowledge['title']}")


async def main():
    """
    主函数
    """
    try:
        # 1. 初始化知识库
        kb = await initialize_knowledge_base()

        # 2. 测试检索
        await test_knowledge_base(kb)

        # 3. 测试 RAG 服务
        await test_rag_service(kb)

        # 4. 添加自定义知识（示例）
        await add_custom_knowledge(kb)

        # 5. 再次测试检索自定义知识
        logger.info("\n" + "="*50)
        logger.info("测试自定义知识检索")
        logger.info("="*50)
        docs = await kb.search("图书馆开放时间", top_k=1)
        if docs:
            logger.info(f"找到: {docs[0].metadata.get('title')}")
            logger.info(f"内容: {docs[0].page_content}")

        logger.info("\n🎉 所有测试完成！")

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
