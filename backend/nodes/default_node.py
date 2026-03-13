"""
默认处理节点 - 处理无法分类的问题
"""

import logging
import os
from typing import TYPE_CHECKING
from dashscope import AioGeneration
from langchain_core.callbacks.manager import dispatch_custom_event

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_default_query(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理无法分类的问题 - 使用通义千问直接回答

    对于无法归类到图书推荐、找书、客服的问题，使用 LLM 直接回答
    """
    logger.info("📍 节点: handle_default_query")

    # 从槽位对象中获取查询上下文
    slots_obj = state.get("slots")
    if slots_obj and hasattr(slots_obj, 'query_context'):
        query_context = slots_obj.query_context
    else:
        query_context = ""

    # 使用槽位中的上下文，如果没有则降级到原始查询
    query_input = query_context if query_context else state["user_query"]

    logger.info(f"📚 从槽位提取的上下文: {query_context[:50] if query_context else '(空)'}")

    try:
        # 导入系统提示词
        from prompts.system_prompts import DEFAULT_QUERY_SYSTEM_PROMPT

        logger.info(f"🚀 开始生成默认回复，查询: {query_input[:50]}...")

        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        # 使用原生 DashScope API 进行流式调用
        responses = await AioGeneration.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen3-max-2026-01-23",
            messages=[
                {"role": "system", "content": DEFAULT_QUERY_SYSTEM_PROMPT},
                {"role": "user", "content": query_input}
            ],
            enable_search=True,
            result_format="message",
            stream=True,
            incremental_output=True
        )

        full_response = ""

        # 流式处理响应
        async for resp in responses:
            if resp.status_code == 200:
                # 提取思考内容
                reasoning_content_chunk = resp.output.choices[0].message.get("reasoning_content", None)
                if reasoning_content_chunk is not None:
                    dispatch_custom_event(
                        "on_tongyi_thinking",
                        {"chunk": reasoning_content_chunk}
                    )

                # 提取正文内容
                content = resp.output.choices[0].message.content
                if content:
                    dispatch_custom_event(
                        "on_tongyi_chat",
                        {"chunk": content}
                    )
                    state["streaming_tokens"].append(content)
                    full_response += content
            else:
                raise Exception(f"DashScope Error: {resp.message}")

        logger.info(f"✓ 默认回复生成完成，长度: {len(full_response)}")

        state["dialogue_response"] = full_response
        state["final_response"] = full_response

    except Exception as e:
        logger.error(f"默认回复生成失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
        state["final_response"] = state["dialogue_response"]

    return state
