"""
统一意图识别节点 - 槽位填充设计
"""

import logging
from typing import TYPE_CHECKING, Optional, List, Union
from abc import ABC
from prompts.system_prompts import INTENT_RECOGNITION_SYSTEM_PROMPT
from pydantic import BaseModel, Field


# 定义槽位基类
class IntentSlots(BaseModel, ABC):
    """意图槽位的抽象基类"""
    pass


# 为每种意图类型定义独立的槽位模型
class FindBookSlots(IntentSlots):
    """找书意图的槽位"""
    book_titles: List[str] = Field(description="书名列表")


class RecommendBookSlots(IntentSlots):
    """推荐书籍意图的槽位"""
    topic: str = Field(description="推荐主题或类型")


class BookInfoSlots(IntentSlots):
    """书籍信息查询的槽位（版本比较、梗概、导读等）"""
    query: str = Field(description="查询类型描述，如：版本比较、梗概介绍、导读、书评等")
    book_title: Optional[str] = Field(default=None, description="书名")
    author: Optional[str] = Field(default=None, description="作者")
    pub_info: Optional[List[str]] = Field(default=None, description="版本信息列表（出版社、译者等）")

class DefaultQuerySlots(IntentSlots):
    """默认查询（闲聊等）的槽位"""
    query_context: str = Field(description="查询上下文")


class CustomerServiceSlots(IntentSlots):
    """客服咨询的槽位"""
    question: str = Field(description="用户问题")


class IntentRecognitionResponse(BaseModel):
    """意图识别响应结构"""
    query_type: str = Field(description="查询类型：find_book/book_recommendation/book_info/customer_service/default")

    # 使用联合类型表示槽位
    slots: Optional[Union[FindBookSlots, RecommendBookSlots, BookInfoSlots, DefaultQuerySlots, CustomerServiceSlots]] = Field(
        default=None,
        description="槽位信息，根据 query_type 自动选择对应的槽位类型"
    )

    # 是否需要反问
    missing_info: Optional[str] = Field(default=None, description="缺失的信息类型：book_title/topic/none")


if TYPE_CHECKING:
    from graph_workflow_streaming import BookRecommendationState

logger = logging.getLogger(__name__)


async def recognize_intent(state: "BookRecommendationState") -> "BookRecommendationState":
    """
    节点: 统一意图识别 - 分析查询意图并填充槽位

    功能：
    1. 判断查询类型
    2. 提取该类型所需的槽位信息
    3. 如果信息不足，生成反问
    """
    logger.info("📍 节点: recognize_intent")

    session = state["session"]
    user_query = state["user_query"]

    # 设置意图识别系统提示词
    session.set_system_context(INTENT_RECOGNITION_SYSTEM_PROMPT)

    try:
        # 使用结构化输出
        result = await session.ainvoke_structured(
            user_query,
            response_model=IntentRecognitionResponse,
            model="qwen3-max-2026-01-23",
            temperature=0
        )

        state["query_type"] = result.query_type
        logger.info(f"✓ 意图识别: type={result.query_type}")

        # 检查槽位是否完整
        if result.missing_info and result.missing_info != "none":
            # book_info 类型：title 和 author 有一个就不反问
            if result.missing_info == "book_title" and result.query_type == "book_info":
                slots = result.slots
                if slots and (getattr(slots, "book_title", None) or getattr(slots, "author", None)):
                    state["slots"] = slots
                    logger.info(f"✓ 槽位填充完成: {slots}")
                    return state

            # 信息不足，生成反问并直接结束
            if result.missing_info == "book_title":
                clarify_response = "请问您想查找哪本书呢？可以告诉我书名或作者。"
            elif result.missing_info == "topic":
                clarify_response = "请问您想看什么类型的书呢？比如：编程、小说、历史、心理学等。"
            else:
                clarify_response = "抱歉，我没有理解您的需求，能否提供更多信息？"

            state["query_type"] = "clarify"
            state["dialogue_response"] = clarify_response
            state["final_response"] = clarify_response
            logger.info(f"⚠ 信息不足，生成反问: {clarify_response}")
        else:
            # 信息完整，保存槽位对象到状态
            if result.slots:
                state["slots"] = result.slots
                logger.info(f"✓ 槽位填充完成: {result.slots}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"意图识别失败: {error_msg}", exc_info=True)

        # 判断是否是内容审核失败
        if "data_inspection_failed" in error_msg or "inappropriate content" in error_msg:
            logger.warning("意图识别触发内容审核，使用默认路由")

        # 失败时使用默认路由
        state["query_type"] = "default"
        state["slots"] = {"query_context": user_query, "book_titles": []}

    return state
