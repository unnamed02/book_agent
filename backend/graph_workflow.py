"""
LangGraph 图书推荐工作流 (适配 LangGraph 1.0.4)
使用 StateGraph 实现可视化、可控的推荐流程
"""

from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import logging
import json
import asyncio
import os
from openai import AsyncOpenAI
import dashscope


from tools.douban_tool import search_douban_book
from tools.resource_tool import search_digital_resource
from tools.library_tool import search_library_collection
from session.session import Session
from service.knowledge_base_tool import RAGCustomerService, KnowledgeBase
from prompts.system_prompts import (
    ROUTE_QUERY_SYSTEM_PROMPT,
    REWRITE_QUERY_SYSTEM_PROMPT,
    CUSTOMER_SERVICE_SYSTEM_PROMPT,
    FIND_BOOK_SYSTEM_PROMPT,
    BOOK_RECOMMENDATION_SYSTEM_PROMPT,
    DEFAULT_QUERY_SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

# ========== Pydantic 模型定义 ==========

class BookInfo(BaseModel):
    """书籍信息"""
    title: str = Field(description="书名（主标题，不含版本号）")
    author: str = Field(description="作者姓名，如果不确定则为空字符串")

class ExtractBooksResponse(BaseModel):
    """提取书籍响应结构"""
    books: List[BookInfo] = Field(
        description="提取的书籍列表。重要：如果用户查询的是丛书或系列（如'丁丁历险记'、'三体三部曲'、'哈利波特系列'），且该系列每册有独立书名，必须将每一册作为独立的BookInfo条目返回，不要只返回系列名"
    )

class BookRecommendation(BaseModel):
    """单本书籍推荐"""
    title: str = Field(description="书名")
    author: str = Field(description="作者")
    reason: str = Field(description="推荐理由")

class RecommendationResponse(BaseModel):
    """推荐响应结构"""
    dialogue: str = Field(description="对话响应，向用户解释推荐的书籍")
    books: List[BookRecommendation] = Field(description="推荐书单列表")

class RewriteQueryResponse(BaseModel):
    """查询重写响应结构"""
    rewritten_query: str = Field(description="重写后的查询文本")
    query_type: str = Field(description="查询类型：find_book/book_recommendation/customer_service/default")

# ========== 状态定义 ==========

class BookRecommendationState(TypedDict):
    """图书推荐工作流状态"""
    # 输入
    user_query: str
    session_id: str
    user_id: str

    # 会话管理器
    session: Optional[Session]
    rag_service: Optional[RAGCustomerService]  # RAG 客服服务

    # 路由结果
    query_type: str  # "book_recommendation" | "customer_service" | "find_book"

    # 推荐结果
    recommended_books: List[Dict]  # [{"title": "", "author": "", "reason": ""}]

    # 卡片数据（推荐和找书共用）
    book_cards: List[Dict]  # 书籍卡片数据
    books_without_resources: List[Dict]  # 没有馆藏和电子资源的书籍

    # 输出
    dialogue_response: str  # 对话响应
    final_response: str  # 最终完整响应

    # 元数据
    recent_recommendations: List[str]

    # 错误处理
    error: Optional[str]


# ========== 节点函数 ==========

async def route_query(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点0: 智能路由 - 分析用户查询类型

    判断:
    1. 是否需要上下文解析（rewrite）
    2. 是图书推荐、找书还是客服咨询
    """
    logger.info("📍 节点: route_query")

    session = state["session"]
    user_query = state["user_query"]

    # 设置路由系统提示词
    session.set_system_context(ROUTE_QUERY_SYSTEM_PROMPT)

    route_prompt = f"用户查询：{user_query}"

    # 使用普通 ainvoke，不包含历史上下文
    try:
        route_result = await session.ainvoke(
            route_prompt,
            model="qwen-flash",
            temperature=0,
            need_save=False,
            include_history=False  # 路由判断不需要历史上下文
        )

        # 清理结果
        clean_result = route_result.strip()

        # 验证返回的查询类型是否有效
        valid_types = ["rewrite", "find_book", "book_recommendation", "customer_service", "default"]

        if clean_result in valid_types:
            state["query_type"] = clean_result
        else:
            logger.warning(f"无效的查询类型: {clean_result}, 使用默认值")
            state["query_type"] = "default"

        logger.info(f"✓ 路由结果: type={state['query_type']}")

    except Exception as e:
        logger.error(f"路由解析失败: {e}, 使用默认值")
        # 默认当作无法分类的问题
        state["query_type"] = "default"

    return state


async def rewrite_query(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 查询重写和路由 - 将含有指代词的查询重写为明确查询，并判断路由类型

    根据对话历史，将"最后一本"、"换一本"等指代词替换为具体内容，同时确定应该路由到哪个节点
    """
    logger.info("📍 节点: rewrite_query")

    session = state["session"]
    user_query = state["user_query"]

    # 设置查询重写系统提示词
    session.set_system_context(REWRITE_QUERY_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        result = await session.ainvoke_structured(
            user_query,
            response_model=RewriteQueryResponse,
            model="qwen3-max-2026-01-23",
            temperature=0
        )

        # 更新状态
        state["user_query"] = result.rewritten_query
        state["query_type"] = result.query_type

        logger.info(f"✓ 查询重写: {user_query} → {result.rewritten_query}")
        logger.info(f"✓ 路由类型: {result.query_type}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"查询重写失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            logger.warning("查询重写触发内容审核，使用默认路由")

        # 失败时使用默认路由
        state["query_type"] = "default"

    return state


async def handle_customer_service(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: RAG 增强的客服节点 - 处理非图书推荐的客服咨询

    使用知识库检索 + LLM 生成，提供更准确的回答
    """
    logger.info("📍 节点: handle_customer_service (RAG)")

    user_query = state["user_query"]
    rag_service = state.get("rag_service")

    # 如果有 RAG 服务，使用 RAG 增强回答
    if rag_service:
        try:
            # 获取对话历史（用于上下文）
            session_obj = state.get("session")
            conversation_history = []
            if session_obj:
                # 简化历史格式供 RAG 使用
                messages = session_obj.messages[-6:]  # 最近3轮
                for i in range(0, len(messages), 2):
                    if i + 1 < len(messages):
                        conversation_history.append({
                            "user": messages[i].content if hasattr(messages[i], 'content') else str(messages[i]),
                            "assistant": messages[i+1].content if hasattr(messages[i+1], 'content') else str(messages[i+1])
                        })

            # 使用 RAG 生成回答
            rag_result = await rag_service.answer_question(
                user_query,
                conversation_history=conversation_history
            )

            answer = rag_result["answer"]
            sources = rag_result.get("sources", [])
            confidence = rag_result.get("confidence", 0.5)

            # 如果置信度较低，添加提示
            if confidence < 0.5 and sources:
                answer += "\n\n💡 *以上回答基于系统知识库，如需更多帮助请提供更多细节。*"
            elif not sources:
                answer += "\n\n💡 *如需更详细的帮助，欢迎联系人工客服。*"

            # 添加知识来源（如果有）
            if sources:
                source_text = "\n\n📚 **参考来源**: " + "、".join(sources)
                answer += source_text

            state["final_response"] = answer
            state["dialogue_response"] = answer

            logger.info(f"✓ RAG 客服响应生成完成 (置信度: {confidence:.2f})")

        except Exception as e:
            logger.error(f"RAG 客服失败，回退到默认模式: {e}")
            # 回退到默认客服模式
            state = await _fallback_customer_service(state)

    else:
        # 没有 RAG 服务，使用默认客服模式
        logger.warning("RAG 服务未配置，使用默认客服模式")
        state = await _fallback_customer_service(state)

    return state


async def _fallback_customer_service(state: BookRecommendationState) -> BookRecommendationState:
    """
    回退的客服模式（不使用 RAG）
    """
    session = state["session"]
    user_query = state["user_query"]

    # 设置客服系统提示词
    session.set_system_context(CUSTOMER_SERVICE_SYSTEM_PROMPT)

    cs_response = await session.ainvoke(
        user_query,
        model="qwen-flash",
        temperature=0.7,
        need_save=True,
        include_history=False,
    )

    state["final_response"] = cs_response
    state["dialogue_response"] = cs_response

    logger.info("✓ 默认客服响应生成完成")
    return state


async def handle_find_book(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 提取书名（找书流程第一步）

    直接查询图书馆馆藏并格式化输出
    """
    logger.info("📍 节点: handle_find_book")

    session = state["session"]
    user_query = state["user_query"]

    # 设置提取书名系统提示词
    session.set_system_context(FIND_BOOK_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        response = await session.ainvoke_structured(
            user_input=user_query,
            response_model=ExtractBooksResponse,
            model="qwen3-max-2026-01-23",
            temperature=0,
            need_save=True  # 提取书名不需要保存到历史
        )

        books = [book.model_dump() for book in response.books]
        logger.info(f"提取到 {len(books)} 本书")

        if not books:
            state["error"] = "无法提取书名"
            state["recommended_books"] = []
            state["book_cards"] = []
            state["final_response"] = "抱歉，我没有理解您要找的书名，请提供更明确的书名信息。"
            state["dialogue_response"] = state["final_response"]
            return state

        # 保存提取的书籍列表
        state["recommended_books"] = books
        logger.info(f"✓ 提取 {len(books)} 本书籍")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"找书提取失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["final_response"] = "抱歉，查询内容触发了内容审核。请尝试换一个话题。"
        else:
            state["error"] = error_msg
            state["final_response"] = "抱歉，查找时出现错误，请稍后重试。"

        state["dialogue_response"] = state["final_response"]

    return state


async def generate_recommendations(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 生成推荐书单

    1. 使用LLM结构化输出生成推荐书单和对话响应
    """
    logger.info("📍 节点: generate_recommendations")

    session = state["session"]
    user_query = state["user_query"]

    # 更新系统上下文
    # 设置图书推荐系统提示词
    session.set_system_context(BOOK_RECOMMENDATION_SYSTEM_PROMPT)

    try:
        # 使用 session 的结构化输出方法
        response = await session.ainvoke_structured(
            user_input=user_query,
            response_model=RecommendationResponse,
            model="qwen3-max-2026-01-23",
            temperature=0.7,
            need_save=True
        )

        # 直接使用结构化响应
        dialogue_part = response.dialogue
        books = [book.model_dump() for book in response.books]

        if not books:
            state["error"] = "无法生成推荐书单"
            state["recommended_books"] = []
            state["book_cards"] = []
            state["final_response"] = "抱歉，我暂时无法为您生成推荐书单。请尝试更具体地描述您的需求。"
            state["dialogue_response"] = state["final_response"]
            return state

        state["dialogue_response"] = dialogue_part
        state["recommended_books"] = books
        logger.info(f"✓ 生成 {len(books)} 本推荐书籍")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"生成推荐失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["final_response"] = "抱歉，推荐内容触发了内容审核。请尝试换一个话题或更具体地描述您的需求。"
        else:
            state["error"] = f"生成推荐失败: {error_msg}"
            state["final_response"] = "抱歉，生成推荐时出现错误。请稍后重试或尝试更换查询内容。"

        state["recommended_books"] = []
        state["book_cards"] = []
        state["dialogue_response"] = state["final_response"]

    return state


async def fetch_book_details(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 获取书籍详情并构建卡片

    1. 并行获取所有书籍的详细信息（豆瓣、馆藏、电子资源）
    2. 构建书籍卡片数据
    3. 格式化最终响应用于保存到记忆
    """
    logger.info("📍 节点: fetch_book_details")

    books = state.get("recommended_books", [])
    dialogue_part = state.get("dialogue_response", "")

    if not books:
        state["book_cards"] = []
        state["final_response"] = dialogue_part
        return state

    # 并行获取所有书籍的详细信息并构建卡片
    # 超过5本书时不获取豆瓣信息以提升性能
    fetch_douban = len(books) <= 5
    tasks = [_fetch_single_book_detail(book, fetch_douban) for book in books]
    all_books_detail = await asyncio.gather(*tasks)

    # 过滤有效结果并去重，同时构建书籍卡片
    book_cards = []
    books_without_resources = []
    seen_books = set()
    book_titles = []

    for i, detail in enumerate(all_books_detail):
        original_book = books[i]

        # 如果没有获取到详情，记录为未找到
        if not detail or not detail.get("title"):
            books_without_resources.append({
                "title": original_book.get("title", ""),
                "author": original_book.get("author", "")
            })
            continue

        book_key = (detail["title"], detail["author"])
        if book_key in seen_books:
            continue

        seen_books.add(book_key)
        book_titles.append(f"《{detail.get('title', '')}》")

        # 解析电子资源并按平台分组
        resources = _group_resources_by_source(detail.get("digital_resources", "[]"))

        # 解析馆藏信息
        library_items = _format_library_info(detail.get("library_info", "[]"))

        has_library = library_items is not None and len(library_items) > 0
        has_resources = len(resources) > 0

        # 如果既没有馆藏也没有电子资源，放入无资源列表
        if not has_library and not has_resources:
            books_without_resources.append({
                "title": detail.get("title", ""),
                "author": detail.get("author", "")
            })
        else:
            # 构建卡片数据
            book_cards.append({
                **detail,  # 直接展开所有字段
                "hasLibrary": has_library,
                "libraryItems": library_items or [],
                "hasResources": has_resources,
                "resources": resources
            })

    state["book_cards"] = book_cards
    state["books_without_resources"] = books_without_resources
    logger.info(f"✓ 获取 {len(book_cards)} 本书籍的详细信息")

    # 格式化最终响应（用于保存到记忆）
    books_text = "、".join(book_titles) if book_titles else ""

    if dialogue_part and books_text:
        final_response = f"{dialogue_part}\n\n推荐书籍：{books_text}"
    elif dialogue_part:
        final_response = dialogue_part
    elif books_text:
        final_response = f"推荐书籍：{books_text}"
    else:
        final_response = ""

    state["final_response"] = final_response
    logger.info("✓ 书籍详情获取完成")

    return state


# ========== 条件路由 ==========

async def handle_default_query(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 处理无法分类的问题 - 使用百炼原生 API 配合联网搜索

    对于无法归类到图书推荐、找书、客服的问题，使用增强的 LLM 回答
    特别适合需要查询 ISBN、出版社、版本信息等需要准确性的问题
    """
    logger.info("📍 节点: handle_default_query")

    session = state["session"]
    user_query = state["user_query"]

    try:

        # 设置系统提示词
        session.set_system_context(DEFAULT_QUERY_SYSTEM_PROMPT)

        # 构建消息列表（包含系统消息和历史对话）
        messages = []
        for msg in session.messages:
            if isinstance(msg, SystemMessage):
                messages.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                messages.append({"role": "assistant", "content": msg.content})

        # 添加当前查询
        messages.append({"role": "user", "content": user_query})

        # 使用百炼原生 API，启用联网搜索
        response = dashscope.Generation.call(
            api_key=os.getenv("OPENAI_API_KEY"),  # 使用 OPENAI_API_KEY 环境变量
            model="qwen-flash",
            messages=messages,
            enable_search=True,  # 开启联网搜索
            search_options={
                "search_strategy": "max",  # 配置搜索策略为高性能模式
                "enable_source": True,
                "forced_search": True 
            },
            result_format="message"
        )

        # 检查响应状态
        if response.status_code != 200:
            raise Exception(f"API 调用失败: {response.code} - {response.message}")
    
        # 提取回复内容
        answer = response.output.choices[0].message.content
        logger.info(response)

        # 保存到会话历史
        session.conversation_messages.append(HumanMessage(content=user_query))
        session.conversation_messages.append(AIMessage(content=answer))

        # 异步保存到 Redis
        if session.redis_client:
            human_msg = json.dumps({"type": "human", "content": user_query}, ensure_ascii=False)
            ai_msg = json.dumps({"type": "ai", "content": answer}, ensure_ascii=False)
            asyncio.create_task(session.bg_write(human_msg, ai_msg))

        state["dialogue_response"] = answer
        state["final_response"] = answer

        logger.info(f"默认回复生成完成，长度: {len(answer)}")

    except Exception as e:
        logger.error(f"默认回复生成失败: {e}")
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
        state["final_response"] = state["dialogue_response"]

    return state


def route_by_type(state: BookRecommendationState) -> str:
    """
    条件边: 根据查询类型路由

    Returns:
        "rewrite" | "customer_service" | "recommend" | "find_book" | "default"
    """
    query_type = state.get("query_type", "book_recommendation")

    # 如果需要重写查询，路由到重写节点
    if query_type == "rewrite":
        return "rewrite"

    # 如果是客服咨询，直接路由到客服节点
    if query_type == "customer_service":
        return "customer_service"

    # 如果是找书，直接路由到找书节点
    if query_type == "find_book":
        return "find_book"

    # 如果是无法分类的问题，路由到默认处理节点
    if query_type == "default":
        return "default"

    # 图书推荐需求，进入推荐流程
    return "recommend"


def has_error(state: BookRecommendationState) -> str:
    """
    条件边: 判断是否有错误

    Returns:
        "error" 或 "continue"
    """
    if state.get("error"):
        return "error"
    else:
        return "continue"


# ========== 辅助函数 ==========


async def _fetch_single_book_detail(book: Dict, fetch_douban: bool = True) -> Dict:
    """

    包括：豆瓣详情、馆藏、电子资源、购买链接
    """
    title = book["title"]
    author = book["author"]
    reason = book.get("reason", "")

    try:
        logger.info(f"开始获取《{title}》的详细信息")

        # 并行获取电子资源、馆藏信息
        tasks = [
            asyncio.to_thread(
                search_digital_resource.invoke,
                {"title": title, "author": author}
            ),
            asyncio.to_thread(
                search_library_collection.invoke,
                {"title": title, "author": author}
            )
        ]

        # 只有在需要时才获取豆瓣信息
        if fetch_douban:
            tasks.insert(0, asyncio.to_thread(
                search_douban_book.invoke,
                {"title": title, "author": author}
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理豆瓣结果
        cover_url = ""
        digital_idx = 0
        library_idx = 1

        if fetch_douban:
            digital_idx = 1
            library_idx = 2
            if not isinstance(results[0], Exception):
                try:
                    data = json.loads(results[0])
                    books_found = data.get("books", [])
                    if books_found:
                        first_book = books_found[0]
                        cover_url = first_book.get("cover_url", "")
                    else:
                        logger.warning(f"豆瓣未找到《{title}》")
                except Exception as e:
                    logger.warning(f"豆瓣结果解析失败: {e}")
            else:
                logger.warning(f"豆瓣查询失败: {results[0]}")

        # 组装完整信息
        return {
            "title": title,
            "author": author,
            "publisher": "",
            "isbn": "",
            "rating": "",
            "summary": "",
            "image": cover_url,
            "reason": reason,
            "digital_resources": results[digital_idx] if not isinstance(results[digital_idx], Exception) else "[]",
            "library_info": results[library_idx] if not isinstance(results[library_idx], Exception) else "[]"
        }

    except Exception as e:
        logger.error(f"获取《{title}》详细信息失败: {e}")
        return {}


def _format_library_info(library_json: str):
    """格式化馆藏信息为结构化数组"""
    try:
        libraries = json.loads(library_json)
        if libraries:
            lib_items = []
            for lib in libraries:
                # 新格式：包含 title, pub_info, call_number, location, status, total, available
                title = lib.get('title', '')
                pub_info = lib.get('pub_info', '')
                library = lib.get('library', '')
                call_number = lib.get('call_number', '')
                location = lib.get('location', '')
                status = lib.get('status', '')
                total = lib.get('total', 0)
                available = lib.get('available', 0)

                lib_items.append({
                    'title': title,
                    'pub_info': pub_info,
                    'library': library,
                    'call_number': call_number,
                    'location': location,
                    'status': status,
                    'total': total,
                    'available': available
                })
            return lib_items
        else:
            return None
    except Exception as e:
        logger.error(f"格式化馆藏信息失败: {e}")
        return None


def _group_resources_by_source(digital_resources_json: str) -> List[Dict]:
    """将电子资源按平台分组"""
    resources_by_source = {}
    try:
        resource_list = json.loads(digital_resources_json)
        for r in resource_list:
            source = r.get("source", "")
            if source:
                if source not in resources_by_source:
                    resources_by_source[source] = []
                resources_by_source[source].append({
                    "title": r.get("title", ""),
                    "link": r.get("link", ""),
                    "author": r.get("author", ""),
                    "publisher": r.get("publisher", "")
                })
    except Exception as e:
        logger.error(f"解析电子资源失败: {e}")

    # 转换为数组格式
    return [
        {"source": source, "books": books_list}
        for source, books_list in resources_by_source.items()
    ]


# ========== 构建 StateGraph ==========

def create_recommendation_graph() -> StateGraph:
    """
    创建图书推荐工作流图

    工作流程：
    0. route_query（智能路由）
       ├─ 需要重写 → rewrite_query → route_query（循环）
       ├─ 客服咨询 → customer_service → END
       ├─ 找书 → find_book → fetch_book_details → END
       ├─ 图书推荐 → generate_recommendations → fetch_book_details → END
       └─ 无法分类 → default → END

    图书推荐路径：
    1. generate_recommendations（生成推荐书单和对话）
    2. fetch_book_details（获取书籍详情并构建卡片）

    节点说明：
    - route_query: 智能路由，判断查询类型（rewrite/find_book/book_recommendation/customer_service/default）
    - rewrite_query: 查询重写，将指代词替换为具体内容后返回 route_query
    - customer_service: 处理客服咨询（使用 RAG）
    - find_book: 提取书名（找书流程第一步）
    - generate_recommendations: 生成推荐书单和对话响应
    - fetch_book_details: 获取书籍详情并构建卡片（找书和推荐共用）
    - default: 处理无法分类的问题，直接调用 LLM 原始输出
    """
    workflow = StateGraph(BookRecommendationState)

    # 添加节点
    workflow.add_node("route", route_query)
    workflow.add_node("rewrite", rewrite_query)
    workflow.add_node("customer_service", handle_customer_service)
    workflow.add_node("find_book", handle_find_book)
    workflow.add_node("generate_recommendations", generate_recommendations)
    workflow.add_node("fetch_book_details", fetch_book_details)
    workflow.add_node("default", handle_default_query)

    # 设置入口点
    workflow.set_entry_point("route")

    # 智能路由条件边
    workflow.add_conditional_edges(
        "route",
        route_by_type,
        {
            "rewrite": "rewrite",
            "customer_service": "customer_service",
            "find_book": "find_book",
            "recommend": "generate_recommendations",
            "default": "default"
        }
    )

    # 重写后直接路由到对应节点（不再回到 route）
    workflow.add_conditional_edges(
        "rewrite",
        route_by_type,
        {
            "customer_service": "customer_service",
            "find_book": "find_book",
            "recommend": "generate_recommendations",
            "default": "default"
        }
    )

    # 客服分支直接结束
    workflow.add_edge("customer_service", END)

    # 默认处理分支直接结束
    workflow.add_edge("default", END)

    # 找书分支：提取书名 → 获取详情 → 结束
    workflow.add_edge("find_book", "fetch_book_details")

    # 推荐分支：生成推荐 → 获取详情 → 结束
    workflow.add_edge("generate_recommendations", "fetch_book_details")

    # 获取详情后结束
    workflow.add_edge("fetch_book_details", END)

    return workflow.compile()


# ========== 流式执行 ==========

async def stream_recommendation_workflow(
    user_query: str,
    session_id: str,
    user_id: str,
    session: Session,
    rag_service: Optional[RAGCustomerService] = None
):
    """
    流式执行推荐工作流，逐步返回结果

    Args:
        user_query: 用户查询
        session_id: 会话ID
        user_id: 用户ID
        session: 会话管理器
        rag_service: RAG 客服服务（可选）

    Yields:
        Dict: 各阶段的事件
            - type: "session" | "status" | "dialogue" | "books" | "book_cards" | "append_message" | "done" | "error"
            - content: 内容
    """
    logger.info(f"🚀 启动推荐工作流 - 用户查询: {user_query[:50]}...")

    # 创建图
    graph = create_recommendation_graph()

    # 初始化状态
    initial_state = BookRecommendationState(
        user_query=user_query,
        session_id=session_id,
        user_id=user_id,
        session=session,
        rag_service=rag_service,
        query_type="book_recommendation",
        recommended_books=[],
        book_cards=[],
        books_without_resources=[],
        dialogue_response="",
        final_response="",
        recent_recommendations=[],
        error=None
    )

    # 返回会话信息
    yield {
        "type": "session",
        "session_id": session_id,
        "user_id": user_id
    }

    try:
        # 流式执行图（LangGraph 支持 astream）
        async for event in graph.astream(initial_state):
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            logger.info(f"🔄 节点完成: {node_name}")

            # 根据节点发送不同事件
            if node_name == "customer_service":
                # 客服响应
                yield {
                    "type": "message",
                    "content": node_state["final_response"]
                }
                yield {"type": "done"}
                return

            elif node_name == "default":
                # 默认处理响应
                yield {
                    "type": "message",
                    "content": node_state["final_response"]
                }
                yield {"type": "done"}
                return

            elif node_name == "find_book":
                # 找书第一步：提取书名完成
                if node_state.get("error"):
                    yield {
                        "type": "error",
                        "content": node_state.get("final_response", "抱歉，查找时出现错误。")
                    }
                    yield {"type": "done"}
                    return

                # 发送找到的书籍信息
                books = node_state.get("recommended_books", [])
                if books:
                    if len(books) > 5:
                        # 超过5本显示前5本
                        book_list = "\n".join([
                            f"《{b['title']}》 - {b['author']}" if b.get('author') else f"《{b['title']}》"
                            for b in books[:5]
                        ])
                        yield {
                            "type": "message",
                            "content": f"相关书籍有：\n{book_list}\n等 {len(books)} 本"
                        }
                    else:
                        # 5本及以下显示详细列表
                        book_list = "\n".join([
                            f"《{b['title']}》 - {b['author']}" if b.get('author') else f"《{b['title']}》"
                            for b in books
                        ])
                        yield {
                            "type": "message",
                            "content": f"相关书籍有：\n{book_list}"
                        }

           # 发送状态提示
                yield {
                    "type": "status",
                    "content": "正在为您查询这些书籍的详细信息..."
                }

            elif node_name == "generate_recommendations":
                # 生成推荐书单完成
                if node_state.get("error"):
                    yield {
                        "type": "error",
                        "content": "抱歉，我无法为您生成推荐书单。请尝试更具体地描述您的需求。"
                    }
                    yield {"type": "done"}
                    return

                # 发送对话部分
                dialogue_response = node_state.get("dialogue_response")
                if dialogue_response:
                    yield {
                        "type": "message",
                        "content": dialogue_response
                    }

                # 发送初步书单（简单格式）
                books = node_state.get("recommended_books", [])
                if books:
                    book_list_text = "\n\n".join([
                        f"**{i}. {b['title']}** - {b['author']}"
                        for i, b in enumerate(books, 1)
                    ])
                    yield {
                        "type": "books",
                        "content": book_list_text
                    }

                # 发送状态提示
                yield {
                    "type": "status",
                    "content": "正在为您查询这些书籍的详细信息..."
                }

            elif node_name == "fetch_book_details":
                # 获取书籍详情完成（找书和推荐共用）
                book_cards = node_state.get("book_cards", [])
                books_without_resources = node_state.get("books_without_resources", [])

                if book_cards:
                    yield {
                        "type": "book_cards",
                        "content": book_cards
                    }

                # 如果有无资源的书籍，发送提示
                if books_without_resources:
                    yield {
                        "type": "books_not_found",
                        "content": books_without_resources
                    }

        # 最终完成标记
        yield {"type": "done"}

    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        yield {
            "type": "error",
            "content": f"处理您的请求时出错: {str(e)}"
        }
        yield {"type": "done"}
