"""
版本比较节点 - 比较图书的不同版本
"""

import logging
import os
from typing import TYPE_CHECKING
import dashscope
from prompts.system_prompts import VERSION_COMPARE_SYSTEM_PROMPT
from dashscope import AioGeneration
from langchain_core.callbacks.manager import dispatch_custom_event

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_version_compare(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 比较图书版本

    使用联网搜索功能，比较不同出版社、译者的版本差异，给出推荐意见
    """
    logger.info("📍 节点: handle_version_compare")

    # 调试：打印完整的 slots 对象
    slots_obj = state.get("slots")
    logger.info(f"🔍 slots 对象类型: {type(slots_obj)}")
    logger.info(f"🔍 slots 对象内容: {slots_obj}")

    # 从槽位对象中获取书名、作者和版本信息
    if slots_obj and hasattr(slots_obj, 'book_title'):
        book_title = slots_obj.book_title
        author = getattr(slots_obj, 'author', None)
        pub_info = getattr(slots_obj, 'pub_info', None) or []
    else:
        book_title = ""
        author = None
        pub_info = []

    # 构建查询输入
    if book_title:
        query_parts = [book_title]
        if author:
            query_parts.append(f"作者：{author}")

        if pub_info:
            query_input = f"{''.join(query_parts)}的版本比较，已知版本：{', '.join(pub_info)}"
        else:
            query_input = f"{''.join(query_parts)}哪个版本好？"
    else:
        # 降级到使用原始查询
        query_input = state["user_query"]

    logger.info(f"📚 从槽位提取的书名: {book_title}")
    logger.info(f"👤 作者: {author}")
    logger.info(f"📝 版本信息: {pub_info}")

    try:
        # 初始化 streaming_tokens 列表
        if state.get("streaming_tokens") is None:
            state["streaming_tokens"] = []

        logger.info(f"🚀 开始版本比较，查询: {query_input[:50]}...")

        # 使用原生 DashScope API 进行流式调用
        responses = await AioGeneration.call(
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            model="qwen3-max-2026-01-23",
            messages=[
                {"role": "system", "content": VERSION_COMPARE_SYSTEM_PROMPT},
                {"role": "user", "content": query_input}
            ],
            enable_search=True,
            search_options={
                "enable_source": True,
                "prepend_search_result": True,  # 首包只返回搜索来源
                "search_strategy": "turbo",
                "forced_search": True,
                "assigned_site_list": ["douban.com"]  # 仅从豆瓣检索
            },
            result_format="message",
            stream=True,
            incremental_output=True
        )

        full_response = ""
        first_chunk = True

        # 流式处理响应
        async for resp in responses:
            if resp.status_code == 200:
                # 1. 提取搜索来源（首包）
                if first_chunk:
                    search_info = resp.output.get("search_info", {})
                    if search_info and "search_results" in search_info:
                        search_results = search_info["search_results"]
                        logger.info(f"🔍 已阅读 {len(search_results)} 个页面")
                        for web in search_results:
                            logger.info(f"  [{web['index']}]: [{web['title']}]({web['url']})")
                    first_chunk = False

                # 2. 提取正文内容
                
                content = resp.output.choices[0].message.content
                if content:
                    dispatch_custom_event(
                    "on_chat_model_stream_manual", 
                    {"chunk": content}
                    )
                    state["streaming_tokens"].append(content)
            else:
                raise Exception(f"DashScope Error: {resp.message}")

        logger.info(f"✓ 版本比较完成，长度: {len(full_response)}")

        state["dialogue_response"] = full_response
        state["final_response"] = full_response

    except Exception as e:
        logger.error(f"版本比较失败: {e}", exc_info=True)
        state["error"] = str(e)
        state["dialogue_response"] = "抱歉，版本比较时出现错误。"
        state["final_response"] = state["dialogue_response"]

    return state
