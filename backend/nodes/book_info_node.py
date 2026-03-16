"""
书籍信息查询节点 - 处理书籍相关的各种查询（版本比较、梗概、导读等）
"""

import logging
import os
from typing import TYPE_CHECKING
import dashscope
from prompts.system_prompts import BOOK_INFO_SYSTEM_PROMPT
from dashscope import AioGeneration
from langchain_core.callbacks.manager import dispatch_custom_event

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_book_info(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 查询书籍信息

    使用联网搜索功能，回答关于特定书籍的各种问题：
    - 版本比较：比较不同出版社、译者的版本差异，给出推荐意见
    - 梗概介绍：介绍书籍的主要内容和核心观点
    - 导读：提供阅读建议和重点章节推荐
    - 其他书籍相关问题
    """
    logger.info("📍 节点: handle_book_info")

    # 调试：打印完整的 slots 对象
    slots_obj = state.get("slots")
    logger.info(f"🔍 slots 对象类型: {type(slots_obj)}")
    logger.info(f"🔍 slots 对象内容: {slots_obj}")

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

    logger.info(f"📚 从槽位提取的书名: {book_title}")
    logger.info(f"👤 作者: {author}")
    logger.info(f"🔖 查询类型: {query}")
    logger.info(f"📝 版本信息: {pub_info}")

    try:
        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        logger.info(f"🚀 开始书籍信息查询，查询: {query_input[:50]}...")

        # 使用原生 DashScope API 进行流式调用
        responses = await AioGeneration.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen3-max-2026-01-23",
            messages=[
                {"role": "system", "content": BOOK_INFO_SYSTEM_PROMPT},
                {"role": "user", "content": query_input}
            ],
            enable_search=True,
            # enable_thinking=True,
            search_options={
                "enable_source": True,
                "prepend_search_result": True,  # 首包只返回搜索来源
                "search_strategy": "agent",
                "enable_citation": True,     # 开启角标标注
                "citation_format": "[ref_<number>]", # 设置角标样式
                "forced_search": True,
                "assigned_site_list": ["book.douban.com","search.douban.com/book/"],  # 仅从豆瓣检索
                "intention_options": {
                    "prompt_intervene": "优先去https://search.douban.com/book/subject_search?{book_title}搜书名"
                }
            },
            result_format="message",
            stream=True,
            incremental_output=True
        )

        full_response = ""
        first_chunk = True
        last_resp = None

        # 流式处理响应
        async for resp in responses:
            if resp.status_code == 200:
                last_resp = resp
                # 1. 提取搜索来源（首包）
                if first_chunk:
                    search_info = resp.output.get("search_info", {})
                    if search_info and "search_results" in search_info:
                        search_results = search_info["search_results"]

                        # 发送搜索结果事件
                        dispatch_custom_event(
                            "on_search_results",
                            {"search_results": search_results}
                        )
                    first_chunk = False

                # 2. 提取思考内容
                reasoning_content_chunk = resp.output.choices[0].message.get("reasoning_content", None)
                if reasoning_content_chunk is not None:
                    dispatch_custom_event(
                        "on_tongyi_thinking",
                        {"chunk": reasoning_content_chunk}
                    )

                # 3. 提取正文内容
                content = resp.output.choices[0].message.content
                if content:
                    dispatch_custom_event(
                    "on_tongyi_chat",
                    {"chunk": content}
                    )
                    state["streaming_tokens"].append(content)
            else:
                raise Exception(f"DashScope Error: {resp.message}")

        # 打印最后一个响应的 token 用量
        if last_resp and last_resp.usage:
            usage = last_resp.usage
            logger.info(f"📊 Token 用量 - 输入: {usage.input_tokens}, 输出: {usage.output_tokens}, 总计: {usage.total_tokens}")

        logger.info(f"✓ 书籍信息查询完成，长度: {len(full_response)}")

        state["dialogue_response"] = full_response
        state["final_response"] = full_response

    except Exception as e:
        logger.error(f"书籍信息查询失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，查询书籍信息时出现错误。"
        state["final_response"] = state["dialogue_response"]

    return state
