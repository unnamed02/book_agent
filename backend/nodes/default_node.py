"""
默认处理节点 - 处理无法分类的问题
"""

import logging
import json
import asyncio
import os
import dashscope
from typing import TYPE_CHECKING
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_default_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理无法分类的问题 - 使用百炼 API 配合联网搜索

    对于无法归类到图书推荐、找书、客服的问题，使用增强的 LLM 回答
    特别适合需要查询 ISBN、出版社、版本信息等需要准确性的问题
    """
    logger.info("📍 节点: handle_default_query")

    session = state["session"]
    user_query = state["user_query"]

    try:
        # 导入系统提示词
        from prompts.system_prompts import DEFAULT_QUERY_SYSTEM_PROMPT

        # 设置系统提示词
        session.set_system_context(DEFAULT_QUERY_SYSTEM_PROMPT)

        logger.info(f"🚀 开始生成默认回复（联网搜索），查询: {user_query[:50]}...")

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

        # 使用百炼原生 API，启用联网搜索（非流式）
        response = dashscope.Generation.call(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="qwen-flash",
            messages=messages,
            enable_search=True,  # 开启联网搜索
            search_options={
                "search_strategy": "max",
                "enable_source": True,
                "forced_search": True
            },
            result_format="message"
        )

        if response.status_code == 200:
            full_response = response.output.choices[0].message.content
            logger.info(f"✓ 默认回复生成完成，长度: {len(full_response)}")

            # 保存到会话历史
            session.conversation_messages.append(HumanMessage(content=user_query))
            session.conversation_messages.append(AIMessage(content=full_response))

            # 异步保存到 Redis
            if session.redis_client:
                human_msg = json.dumps({"type": "human", "content": user_query}, ensure_ascii=False)
                ai_msg = json.dumps({"type": "ai", "content": full_response}, ensure_ascii=False)
                asyncio.create_task(session.bg_write(human_msg, ai_msg))

            state["dialogue_response"] = full_response
            state["final_response"] = full_response
        else:
            logger.error(f"Dashscope 调用失败: {response.code} - {response.message}")
            state["error"] = f"API 调用失败: {response.message}"
            state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
            state["final_response"] = state["dialogue_response"]

    except Exception as e:
        logger.error(f"默认回复生成失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
        state["final_response"] = state["dialogue_response"]

    return state
