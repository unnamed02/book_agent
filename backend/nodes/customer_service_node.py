"""
客服节点 - RAG增强的客服咨询处理
"""

import logging
import json
import asyncio
from typing import TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_customer_service(state: "BookRecommendationState") -> "BookRecommendationState":
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


async def _fallback_customer_service(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    回退的客服模式（不使用 RAG）
    """
    from prompts.system_prompts import CUSTOMER_SERVICE_SYSTEM_PROMPT

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
