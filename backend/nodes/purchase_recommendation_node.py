"""
荐购图书节点 - 处理用户荐购请求，返回荐购表单卡片
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def handle_purchase_recommendation(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 处理荐购图书请求

    接收槽位中的书名和作者信息，返回触发前端荐购表单的消息
    """
    logger.debug("[节点] handle_purchase_recommendation")

    # 从槽位对象中获取书名和作者
    slots_obj = state.get("slots")
    if slots_obj and hasattr(slots_obj, 'book_title'):
        book_title = slots_obj.book_title or ""
        author = getattr(slots_obj, 'author', None) or ""
    else:
        book_title = ""
        author = ""

    logger.info(f"荐购请求: 书名={book_title}, 作者={author}")

    # 构造响应文本
    if book_title:
        if author:
            dialogue_response = f"好的，我将为您荐购《{book_title}》（{author}著）。请填写以下表单提交荐购申请："
        else:
            dialogue_response = f"好的，我将为您荐购《{book_title}》。请填写以下表单提交荐购申请："
    else:
        dialogue_response = "好的，请填写以下表单提交您的荐购申请："

    # 保存到状态
    state["dialogue_response"] = dialogue_response
    state["final_response"] = dialogue_response

    # 存储荐购信息供前端使用
    # 通过 recommended_books 字段传递，前端可以识别并显示 purchase_form
    state["recommended_books"] = [{
        "title": book_title or "未知",
        "author": author or "未知",
        "reason": "荐购申请",
        "is_purchase_recommendation": True,  # 标记为荐购类型
        "purchase_title": book_title,
        "purchase_author": author
    }]

    logger.debug(f"荐购节点完成: title={book_title}, author={author}")

    return state
