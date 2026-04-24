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
    logger.debug("[节点] handle_default_query")

    # 从槽位对象中获取查询上下文
    slots_obj = state.get("slots")
    if slots_obj and hasattr(slots_obj, 'query_context'):
        query_context = slots_obj.query_context
    else:
        query_context = ""

    # 使用槽位中的上下文，如果没有则降级到原始查询
    query_input = query_context if query_context else state["user_query"]

    logger.debug(f"上下文: {query_context[:50] if query_context else '(空)'}")

    try:
        # 导入系统提示词
        from prompts.system_prompts import DEFAULT_QUERY_SYSTEM_PROMPT

        logger.info(f"开始生成回复: {query_input[:50]}...")

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
            result_format="message",
            stream=True,
            incremental_output=True
        )

        full_response = ""
        async for resp in responses:
            if resp.status_code == 200:
                # 提取正文内容
                content = resp.output.choices[0].message.content
                if content:
                    full_response += content
                    # 发送自定义事件供外层捕获
                    dispatch_custom_event(
                        "on_tongyi_chat",
                        {"chunk": content}
                    )
            else:
                # 处理错误
                error_msg = f"API错误: {resp.code} - {resp.message}"
                logger.error(error_msg)
                state["error"] = error_msg

                # 检查是否是内容审核失败
                if "DataInspectionFailed" in error_msg or "inappropriate content" in error_msg:
                    state["dialogue_response"] = ""
                    state["final_response"] = ""
                    dispatch_custom_event(
                        "on_content_blocked",
                        {"message": "抱歉，生成的内容可能不符合相关法律政策规定，试试别的问题吧"}
                    )
                else:
                    state["final_response"] = "抱歉，服务暂时不可用，请稍后再试。"
                return state

        # 保存完整响应
        state["dialogue_response"] = full_response
        state["final_response"] = full_response
        logger.info(f"默认回复完成，长度: {len(full_response)}")

        # 保存到会话历史
        session = state.get("session")
        if session:
            from langchain_core.messages import AIMessage
            session.conversation_messages.append(AIMessage(content=full_response))

    except Exception as e:
        error_msg = str(e)
        logger.error(f"默认回复生成失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["dialogue_response"] = "抱歉，内容触发了审核。"
            state["final_response"] = "抱歉，内容触发了审核。"
        else:
            state["error"] = f"生成失败: {error_msg}"
            state["dialogue_response"] = "抱歉，处理您的请求时出现错误。"
            state["final_response"] = "抱歉，处理您的请求时出现错误。"

    return state
