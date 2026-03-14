"""
LangGraph 增强流式输出实现
使用 astream_events() 实现 token 级别的流式输出

改造要点:
1. 使用 astream_events(version="v2") 替代 astream()
2. 监听 on_chat_model_stream 事件实现 token 流式
3. 监听 on_chain_start/end 事件显示节点状态

注意: 这是真正的实时流式输出，token 在生成时立即发送
"""

from typing import AsyncIterator, Dict, Any, Optional, TypedDict, List, Union
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
import logging

# 导入节点函数
from nodes import (
    recognize_intent,
    handle_customer_service,
    handle_find_book,
    handle_recommendation,
    parse_book_list,
    fetch_book_details,
    handle_default_query,
    handle_book_info
)
from nodes.intent_recognition_node import IntentSlots
from session.session import Session
from service.knowledge_base_tool import RAGCustomerService

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
    slots: Optional[IntentSlots]  # 槽位信息（IntentSlots 对象）

    # 推荐结果
    recommended_books: List[Dict]  # [{"title": "", "author": "", "reason": ""}]
    book_list_text: str  # 人类可读的书单文本（用于解析）

    # 卡片数据（推荐和找书共用）
    book_cards: List[Dict]  # 书籍卡片数据
    books_without_resources: List[Dict]  # 没有馆藏和电子资源的书籍

    # 输出
    dialogue_response: str  # 对话响应
    final_response: str  # 最终完整响应

    # 流式输出相关
    enable_streaming: bool  # 是否启用流式输出
    streaming_tokens: Optional[List[str]]  # 流式输出的 token 列表

    # 元数据
    recent_recommendations: List[str]

    # 错误处理
    error: Optional[str]


# ========== 工作流图构建 ==========

def route_by_type(state: BookRecommendationState) -> str:
    """
    条件边: 根据查询类型路由

    Returns:
        "clarify" | "customer_service" | "recommend" | "find_book" | "book_info" | "default"
    """
    query_type = state.get("query_type", "book_recommendation")

    # 如果需要反问，直接结束
    if query_type == "clarify":
        return "clarify"

    # 如果是客服咨询，直接路由到客服节点
    if query_type == "customer_service":
        return "customer_service"

    # 如果是找书，直接路由到找书节点
    if query_type == "find_book":
        return "find_book"

    # 如果是书籍信息查询，直接路由到书籍信息节点
    if query_type == "book_info":
        return "book_info"

    # 如果是无法分类的问题，路由到默认处理节点
    if query_type == "default":
        return "default"

    # 图书推荐需求，进入推荐流程
    return "recommend"


def create_recommendation_graph() -> StateGraph:
    """
    创建图书推荐工作流图

    工作流程：
    0. recognize_intent（统一意图识别）
       ├─ 客服咨询 → customer_service → END
       ├─ 找书 → find_book → parse_book_list → fetch_book_details → END
       ├─ 图书推荐 → generate_recommendations → parse_book_list → fetch_book_details → END
       ├─ 书籍信息查询 → book_info → END
       └─ 无法分类 → default → END

    图书推荐路径：
    1. generate_recommendations（生成人类可读书单，流式输出）
    2. parse_book_list（解析书单，提取书籍信息）
    3. fetch_book_details（获取书籍详情并构建卡片）

    节点说明：
    - recognize_intent: 统一意图识别，判断查询类型并在需要时重写查询
    - customer_service: 处理客服咨询（使用 RAG）
    - find_book: 提取书名（找书流程第一步）
    - generate_recommendations: 生成人类可读书单（流式输出）
    - parse_book_list: 解析书单文本，提取书籍信息
    - fetch_book_details: 获取书籍详情并构建卡片（找书和推荐共用）
    - default: 处理无法分类的问题，直接调用 LLM 原始输出
    """
    workflow = StateGraph(BookRecommendationState)

    # 添加节点
    workflow.add_node("intent", recognize_intent)
    workflow.add_node("customer_service", handle_customer_service)
    workflow.add_node("find_book", handle_find_book)
    workflow.add_node("generate_recommendations", handle_recommendation)
    workflow.add_node("parse_book_list", parse_book_list)
    workflow.add_node("fetch_book_details", fetch_book_details)
    workflow.add_node("default", handle_default_query)
    workflow.add_node("book_info", handle_book_info)

    # 设置入口点
    workflow.set_entry_point("intent")

    # 智能路由条件边
    workflow.add_conditional_edges(
        "intent",
        route_by_type,
        {
            "clarify": END,
            "customer_service": "customer_service",
            "find_book": "find_book",
            "recommend": "generate_recommendations",
            "book_info": "book_info",
            "default": "default"
        }
    )


    # 客服分支直接结束
    workflow.add_edge("customer_service", END)

    # 默认处理分支直接结束
    workflow.add_edge("default", END)

    # 书籍信息查询分支直接结束
    workflow.add_edge("book_info", END)

    # 找书分支：生成书单 → 解析书单 → 获取详情 → 结束
    workflow.add_edge("find_book", "parse_book_list")

    # 推荐分支：生成人类可读书单 → 解析书单 → 获取详情 → 结束
    workflow.add_edge("generate_recommendations", "parse_book_list")
    workflow.add_edge("parse_book_list", "fetch_book_details")

    # 获取详情后结束
    workflow.add_edge("fetch_book_details", END)

    return workflow.compile()


# ========== 流式执行 ==========


async def stream_recommendation_workflow_enhanced(
    user_query: str,
    session_id: str,
    user_id: str,
    session: Session,
    rag_service: Optional[RAGCustomerService] = None
) -> AsyncIterator[Dict[str, Any]]:
    """
    增强版流式工作流 - 支持 token 级别流式输出

    使用 astream_events() 替代 astream()，提供更细粒度的流式控制
    """

    logger.info(f"🚀 启动增强流式工作流 - 查询: {user_query[:50]}...")

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
        book_list_text="",
        book_cards=[],
        books_without_resources=[],
        dialogue_response="",
        final_response="",
        recent_recommendations=[],
        error=None,
        enable_streaming=True,
        streaming_tokens=[]
    )

    # 返回会话信息
    yield {
        "type": "session",
        "session_id": session_id,
        "user_id": user_id
    }

    current_node = None

    try:
        # 使用 astream_events 获取细粒度事件
        async for event in graph.astream_events(initial_state, version="v2"):
            event_type = event["event"]

            # 1. 节点开始执行
            if event_type == "on_chain_start":
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")

                if node_name:
                    current_node = node_name
                    yield {
                        "type": "node_start",
                        "node": node_name,
                        "content": get_node_description(node_name)
                    }
                    logger.info(f"📍 节点开始: {node_name}")

            # 2. LLM Token 流式输出
            elif event_type == "on_chat_model_stream":
                chunk = event["data"]["chunk"]

                # 在 generate_recommendations、find_book、default 和 book_info 节点输出 token
                # parse_book_list 节点不输出 token（后台解析）
                if hasattr(chunk, "content") and chunk.content and current_node in ["generate_recommendations", "find_book", "default", "book_info"]:
                    token = chunk.content
                    yield {
                        "type": "token",
                        "content": token,
                        "node": current_node
                    }
            
            elif event_type == "on_custom_event" and event["name"] == "on_tongyi_chat":
                token = event["data"]["chunk"]

                if token:
                    yield {
                        "type": "token",
                        "content": token,
                        "node": current_node
                    }

            # 3. 通义思考过程流式输出
            elif event_type == "on_custom_event" and event["name"] == "on_tongyi_thinking":
                chunk = event["data"]["chunk"]

                if chunk:
                    yield {
                        "type": "thinking",
                        "content": chunk,
                        "node": current_node
                    }

            # 4. 搜索结果
            elif event_type == "on_custom_event" and event["name"] == "on_search_results":
                search_results = event["data"]["search_results"]

                if search_results:
                    yield {
                        "type": "search_results",
                        "content": search_results,
                        "node": current_node
                    }


            # 5. 节点执行完成
            elif event_type == "on_chain_end":
                metadata = event.get("metadata", {})
                node_name = metadata.get("langgraph_node")

                if node_name:
                    output = event["data"].get("output", {})

                    yield {
                        "type": "node_end",
                        "node": node_name,
                        "content": f"✓ {node_name} 完成"
                    }

                    # 处理特定节点的输出
                    if node_name == "fetch_book_details":
                        book_cards = output.get("book_cards", [])
                        if book_cards:
                            yield {
                                "type": "book_cards",
                                "content": book_cards
                            }
                        
                        books_without_resources = output.get("books_without_resources", [])
                        if books_without_resources:
                            yield {
                                "type": "books_not_found",
                                "content": books_without_resources
                            }

                    # customer_service 节点输出对话响应
                    elif node_name == "customer_service":
                        dialogue_response = output.get("dialogue_response", "")
                        if dialogue_response:
                            yield {
                                "type": "message",
                                "content": dialogue_response
                            }

                    # default 节点已通过 token 流式输出，不需要再次发送完整响应

                    logger.info(f"✓ 节点完成: {node_name}")

        # 流程结束
        yield {"type": "done"}
        logger.info("✓ 工作流执行完成")

    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        yield {
            "type": "error",
            "content": f"抱歉，处理过程中出现错误: {str(e)}"
        }
        yield {"type": "done"}


def get_node_description(node_name: str) -> str:
    """获取节点的用户友好描述"""
    descriptions = {
        "route": "🧭 正在分析您的需求...",
        "rewrite": "✏️ 正在理解上下文...",
        "customer_service": "💬 正在查询知识库...",
        "find_book": "🔍 正在查找书籍...",
        "generate_recommendations": "📚 正在生成推荐...",
        "parse_book_list": "📋 正在解析书单...",
        "fetch_book_details": "📖 正在获取书籍详情...",
        "book_info": "📊 正在查询书籍信息...",
        "default": "💭 正在思考..."
    }
    return descriptions.get(node_name, f"正在执行 {node_name}...")
