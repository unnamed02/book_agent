"""
书籍信息查询节点 - 处理版本比较、梗概、导读等
"""

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING
from dashscope import AioGeneration
from langchain_core.callbacks.manager import dispatch_custom_event
from langchain_core.messages import AIMessage
from prompts.system_prompts import BOOK_INFO_SYSTEM_PROMPT

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_book_info(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理书籍信息查询

    使用联网搜索功能，回答关于特定书籍的各种问题：
    - 版本比较：比较不同出版社、译者的版本差异，给出推荐意见
    - 梗概介绍：介绍书籍的主要内容和核心观点
    - 导读：提供阅读建议和重点章节推荐
    - 其他书籍相关问题
    """
    logger.debug("[节点] handle_book_info")

    # 调试：打印完整的 slots 对象
    slots_obj = state.get("slots")
    logger.debug(f"slots类型: {type(slots_obj)}")
    logger.debug(f"slots内容: {slots_obj}")

    # 从槽位对象中获取书名、作者、查询类型和版本信息
    if slots_obj and hasattr(slots_obj, 'book_title'):
        book_title = slots_obj.book_title
        query = getattr(slots_obj, 'query', None)
        author = getattr(slots_obj, 'author', None)
        pub_info = getattr(slots_obj, 'pub_info', None) or []
    else:
        book_title = ""
        author = None
        query = '相关信息'
        pub_info = []

    # 构建查询输入
    if book_title:
        query_parts = [f"《{book_title}》"]
        if author:
            query_parts.append(f"作者：{author}")

        # 根据查询类型和版本信息构建查询
        if pub_info:
            query_input = f"{''.join(query_parts)}的{query}，已知版本：{', '.join(pub_info)}"
        else:
            query_input = f"{''.join(query_parts)}的{query}"
    else:
        # 降级到使用原始查询
        query_input = state["user_query"]

    logger.info(f"书名: {book_title}")
    logger.info(f"作者: {author}")
    logger.info(f"查询: {query}")
    logger.debug(f"版本信息: {pub_info}")

    try:
        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        logger.info(f"开始书籍查询: {query_input[:50]}...")

        # 使用原生 DashScope API 进行流式调用
        responses = await AioGeneration.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen3-max-2026-01-23",
            messages=[
                {"role": "system", "content": BOOK_INFO_SYSTEM_PROMPT},
                {"role": "user", "content": query_input}
            ],
            result_format="message",
            stream=True,
            incremental_output=True,
            enable_search=True,
            search_options={
                "enable_source": True,
                "enable_citation": True,
                "citation_format": "【index】"
            }
        )

        full_response = ""
        first_chunk = True
        last_resp = None

        async for resp in responses:
            if resp.status_code == 200:
                last_resp = resp
                # 提取搜索来源（首包）
                if first_chunk:
                    search_info = resp.output.get("search_info", {})
                    if search_info and "search_results" in search_info:
                        dispatch_custom_event(
                            "on_search_results",
                            {"search_results": search_info["search_results"]}
                        )
                    first_chunk = False

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
                    full_response += content
                    state["streaming_tokens"].append(content)
            else:
                error_msg = f"API错误: {resp.code} - {resp.message}"
                logger.error(error_msg)
                state["error"] = error_msg
                state["dialogue_response"] = "抱歉，服务暂时不可用，请稍后再试。"
                state["final_response"] = "抱歉，服务暂时不可用，请稍后再试。"
                return state

        # 打印最后一个响应的 token 用量
        if last_resp and last_resp.usage:
            usage = last_resp.usage
            logger.debug(f"Token: {usage.input_tokens}/{usage.output_tokens}/{usage.total_tokens}")

        logger.info(f"书籍查询完成，长度: {len(full_response)}")

        state["dialogue_response"] = full_response
        state["final_response"] = full_response

        # 持久化到 session（只保存 AI 回复）
        session = state.get("session")
        if session:
            # 保存到内存历史（只存 AI）
            session.conversation_messages.append(AIMessage(content=full_response))
            
            # 异步写入 Redis（只存 AI）
            if session.redis_client:
                ai_msg = json.dumps({"type": "ai", "content": full_response}, ensure_ascii=False)
                asyncio.create_task(session.bg_write(ai=ai_msg))

    except Exception as e:
        error_msg = str(e)
        logger.error(f"书籍信息查询失败: {error_msg}", exc_info=True)

        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            state["error"] = "内容审核失败"
            state["dialogue_response"] = "抱歉，内容触发了审核。"
            state["final_response"] = "抱歉，内容触发了审核。"
        else:
            state["error"] = f"查询失败: {error_msg}"
            state["dialogue_response"] = "抱歉，查询书籍信息时出现错误。"
            state["final_response"] = "抱歉，查询书籍信息时出现错误。"

    return state
