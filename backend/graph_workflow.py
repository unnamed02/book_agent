"""
LangGraph 图书推荐工作流 (适配 LangGraph 1.0.4)
使用 StateGraph 实现可视化、可控的推荐流程
"""

from typing import TypedDict, List, Dict, Optional
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
import logging
import json
import re
import asyncio


from backend.recommend.tools.douban_tool import search_douban_book, get_douban_book_detail
from backend.recommend.tools.resource_tool import search_digital_resource
from backend.recommend.tools.shop_tool import search_shop_by_isbn, search_and_filter_book
from backend.recommend.tools.library_tool import search_library_collection
from backend.session.memory_manager import UserMemoryManager
from backend.session.conversation_manager import ConversationManager
from backend.service.knowledge_base_tool import RAGCustomerService, KnowledgeBase

logger = logging.getLogger(__name__)


# ========== 状态定义 ==========

class BookRecommendationState(TypedDict):
    """图书推荐工作流状态"""
    # 输入
    user_query: str
    session_id: str
    user_id: str

    # 会话管理器
    conversation_manager: Optional[ConversationManager]
    memory_manager: Optional[UserMemoryManager]
    rag_service: Optional[RAGCustomerService]  # RAG 客服服务

    # 路由结果
    query_type: str  # "book_recommendation" | "customer_service" | "clarification"
    is_query_clear: bool  # 需求是否明确
    clarification_questions: List[str]  # 澄清问题列表

    # 推荐结果
    recommended_books: List[Dict]  # [{"title": "", "author": "", "reason": ""}]

    # 详细信息
    books_detail: List[Dict]  # 完整的书籍信息（包括豆瓣、馆藏、资源等）

    # 输出
    dialogue_response: str  # 对话响应
    final_response: str  # 最终完整响应

    # 元数据
    user_profile: Optional[str]
    recent_recommendations: List[str]

    # 错误处理
    error: Optional[str]


# ========== 节点函数 ==========

async def route_query(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点0: 智能路由 - 分析用户查询类型和明确性

    判断:
    1. 是图书推荐需求还是客服咨询
    """
    logger.info("📍 节点: route_query")

    conversation_manager = state["conversation_manager"]
    user_query = state["user_query"]

    route_prompt = f"""分析用户的查询意图和明确性。

用户查询：{user_query}

请判断查询类型：

1. **查询类型判断**：
   - 图书推荐（book_recommendation）：用户想要图书推荐、询问书籍、查找书籍等
   - 客服咨询（customer_service）：询问系统功能、使用方法、技术问题、投诉建议等

2. **搜索书单（search_booklist）**：用户直接提供书单，包含书名和作者的列表
   - 例如："帮我查找：1. Python编程 - Eric, 2. 红楼梦 - 曹雪芹"
   - 判断标准：用户消息中包含多本书籍信息（书名+作者），并且有明确的列表格式（数字编号、换行等）

3. **请求详细信息（request_detail）**：用户明确要求查看详细信息、馆藏、资源等
   - 明确关键词：详细信息、馆藏、资源、链接、购买、哪里买、电子版、借阅
   - **重要**：如果对话历史中助手刚刚推荐了书籍并询问"需要我帮您查找这些书籍的详细信息吗"，
     而用户回复"需要"、"要"、"好的"、"可以"、"行"、"嗯"等肯定词，应判断为 request_detail。

返回格式（JSON）：
{{
  "query_type": "book_recommendation 或 customer_service 或 search_booklist",
  "is_clear": true/false,
  "clarification_questions": ["问题1", "问题2", "问题3"]  // 仅在不明确时提供
}}

示例：
- 输入："Python编程的书" → {{"query_type": "book_recommendation", "is_clear": true}}
- 输入："推荐几本书" → {{"query_type": "book_recommendation", "is_clear": false, "clarification_questions": ["您想了解哪个领域？", "是学习还是娱乐？"]}}
- 输入："怎么使用这个系统？" → {{"query_type": "customer_service", "is_clear": true}}
- 输入："1. 《源代码》（[美]比尔·盖茨，鲁伊 译，郑纬民、韦青 审校）2. 《大道》（赵理亚 选，芒格书院 编）" ->  → {{"query_type": "search_booklist", "is_clear": true}}


只返回JSON，不要其他内容。"""

    route_result = await conversation_manager.ainvoke(
        route_prompt,
        model="gpt-4o-mini",
        temperature=0
    )

    # 解析路由结果
    try:
        # 清理可能的 markdown 代码块
        clean_result = route_result.strip()
        if clean_result.startswith("```"):
            clean_result = clean_result.split("```")[1]
            if clean_result.startswith("json"):
                clean_result = clean_result[4:]
        clean_result = clean_result.strip()

        route_data = json.loads(clean_result)

        state["query_type"] = route_data.get("query_type", "book_recommendation")
        state["is_query_clear"] = route_data.get("is_clear", True)
        state["clarification_questions"] = route_data.get("clarification_questions", [])

        logger.info(f"✓ 路由结果: type={state['query_type']}, clear={state['is_query_clear']}")

    except Exception as e:
        logger.error(f"路由解析失败: {e}, 使用默认值")
        # 默认当作图书推荐
        state["query_type"] = "book_recommendation"
        state["is_query_clear"] = True
        state["clarification_questions"] = []

    return state


async def handle_customer_service(state: BookRecommendationState) -> BookRecommendationState:
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
            conversation_manager = state.get("conversation_manager")
            conversation_history = []
            if conversation_manager:
                # 简化历史格式供 RAG 使用
                messages = conversation_manager.messages[-6:]  # 最近3轮
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


async def _fallback_customer_service(state: BookRecommendationState) -> BookRecommendationState:
    """
    回退的客服模式（不使用 RAG）
    """
    conversation_manager = state["conversation_manager"]
    user_query = state["user_query"]

    cs_prompt = f"""你是图书推荐系统的客服助手，请回答用户的问题。

用户问题：{user_query}

系统功能说明：
- 图书推荐：基于用户需求推荐合适的图书
- 个性化学习：根据用户历史偏好提供个性化推荐
- 多源信息：提供豆瓣评分、馆藏信息、电子资源、购买链接
- 记忆功能：记住用户的阅读偏好，避免重复推荐

常见问题：
- 如何使用？直接描述你想读的书籍类型或主题即可
- 推荐不准确？可以提供更详细的需求描述
- 想看历史推荐？告诉我你的用户ID即可查询

请用友好、专业的语气回答用户问题。"""

    cs_response = await conversation_manager.ainvoke(
        cs_prompt,
        model="gpt-4o-mini",
        temperature=0.7
    )

    state["final_response"] = cs_response
    state["dialogue_response"] = cs_response

    logger.info("✓ 默认客服响应生成完成")
    return state


async def generate_clarification_response(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 生成澄清问题响应

    当用户需求不明确时调用
    """
    logger.info("📍 节点: generate_clarification_response")

    questions = state["clarification_questions"]

    response_text = f"""我需要了解更多信息来为您推荐合适的书籍：

{chr(10).join([f"{i+1}. {q}" for i, q in enumerate(questions)])}

请告诉我更多详细信息，我会为您精准推荐！"""

    state["final_response"] = response_text
    state["dialogue_response"] = response_text

    logger.info("✓ 生成澄清问题完成")
    return state


async def load_user_context(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点3: 加载用户上下文（记忆、偏好）

    为个性化推荐准备数据
    """
    logger.info("📍 节点: load_user_context")

    memory_manager = state.get("memory_manager")

    if memory_manager:
        try:
            memories = memory_manager.get_memories()
            long_term = memories.get("long_term_memory", {})

            state["user_profile"] = long_term.get("user_profile", "新用户")
            state["recent_recommendations"] = long_term.get("recent_recommendations", [])

            logger.info(f"✓ 加载用户画像: {state['user_profile']}")
        except Exception as e:
            logger.warning(f"加载用户上下文失败: {e}")
            state["user_profile"] = None
            state["recent_recommendations"] = []
    else:
        state["user_profile"] = None
        state["recent_recommendations"] = []

    return state


async def update_user_preferences(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点4: 更新用户偏好

    根据当前查询增量更新偏好
    """
    logger.info("📍 节点: update_user_preferences")

    memory_manager = state.get("memory_manager")

    if memory_manager:
        try:
            await memory_manager.update_preferences_from_query(state["user_query"])
            logger.info("✓ 更新用户偏好完成")
        except Exception as e:
            logger.warning(f"更新偏好失败: {e}")

    return state


async def generate_book_recommendations(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点5: 生成详细书籍推荐列表（带推荐理由）

    使用LLM根据用户需求和画像推荐书籍，用于需要详细信息的场景
    """
    logger.info("📍 节点: generate_book_recommendations")

    conversation_manager = state["conversation_manager"]
    user_query = state["user_query"]
    user_profile = state.get("user_profile")
    recent_books = state.get("recent_recommendations", [])

    # 更新系统上下文
    if user_profile or recent_books:
        system_context = f"""你是专业的图书推荐助手。

## 用户画像
{user_profile if user_profile else "新用户"}

## 最近推荐（避免重复）
{', '.join(recent_books[:10]) if recent_books else '无'}

请基于用户画像提供个性化推荐。"""

        conversation_manager.set_system_context(system_context)

    recommend_prompt = f"""请根据用户需求进行个性化推荐。

用户需求：{user_query}

请按以下格式回答：

先自然且亲切地回应用户的需求，然后直接给出推荐书单的JSON。

JSON格式：
{{"books": [{{"title": "完整书名", "author": "作者名", "reason": "简短推荐理由(20字内)"}}, ...]}}

推荐策略：
1. 如果用户明确指定了书名，只返回名称相符或者相似的书籍
2. 如果用户描述了主题、领域或需求，推荐3-5本相关书籍
3. 考虑用户的阅读历史，避免重复推荐

选书标准：
1. 必须是真实存在的图书，有明确的作者
2. 优先推荐中文版
3. 优先选择经典、权威的书籍

格式要求：
- 对话部分用自然语言，不要加"第一部分"、"第二部分"等标记
- JSON部分不要用```包裹，直接输出
- author字段只写作者名字，不要加"著"、"编"、"译"等后缀
  * 正确：{{"author": "曹雪芹"}}
  * 错误：{{"author": "曹雪芹 著"}} 或 {{"author": "曹雪芹 著，高鹗 续"}}"""

    llm_response = await conversation_manager.ainvoke(
        recommend_prompt,
        model="DeepSeek-V3.2-Fast",
        temperature=0.7
    )
    logger.info(f"LLM原始响应: {llm_response[:200]}...")

    # 解析响应
    dialogue_part, books = _parse_recommendation_response(llm_response)

    if not books:
        state["error"] = "无法生成推荐书单"
        state["recommended_books"] = []
    else:
        state["dialogue_response"] = dialogue_part
        state["recommended_books"] = books
        logger.info(f"✓ 生成 {len(books)} 本推荐书籍")

    return state


async def fetch_books_detail(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点6: 并行获取所有书籍的详细信息

    包括豆瓣信息、馆藏、电子资源、购买链接等
    """
    logger.info("📍 节点: fetch_books_detail")

    books = state["recommended_books"]

    # 并行处理所有书籍
    tasks = [_fetch_single_book_detail(book) for book in books]
    all_books_detail = await asyncio.gather(*tasks)

    # 过滤有效结果并去重
    valid_books = []
    seen_books = set()

    for detail in all_books_detail:
        if not detail or not detail.get("title"):
            continue

        book_key = (detail["title"], detail["author"])
        if book_key not in seen_books:
            seen_books.add(book_key)
            valid_books.append(detail)

    state["books_detail"] = valid_books
    logger.info(f"✓ 获取 {len(valid_books)} 本书籍的详细信息")

    return state

async def search_booklist(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点: 搜索书单 - 解析用户提供的书单并调用 douban_tool 查找基本信息，直接输出 CSV

    用户直接提供书单（书名+作者），系统解析后使用 douban_tool 查找 ISBN，输出纯 CSV
    """
    logger.info("📍 节点: search_booklist")

    conversation_manager = state["conversation_manager"]
    user_query = state["user_query"]

    # 使用 LLM 解析用户提供的书单
    parse_prompt = f"""请从用户消息中提取书单信息，返回 JSON 格式的书籍列表。

用户消息：
{user_query}

要求：
1. 提取所有书籍的书名和作者
2. 返回格式：{{"books": [{{"title": "书名", "author": "作者"}}]}}
3. 如果无法提取，返回空列表：{{"books": []}}

只返回 JSON，不要其他内容。"""

    parse_result = await conversation_manager.ainvoke(
        parse_prompt,
        model="gpt-4o-mini",
        temperature=0
    )

    # 解析 JSON
    try:
        clean_result = parse_result.strip()
        if clean_result.startswith("```"):
            clean_result = clean_result.split("```")[1]
            if clean_result.startswith("json"):
                clean_result = clean_result[4:]
        clean_result = clean_result.strip()

        book_data = json.loads(clean_result)
        books = book_data.get("books", [])

        if not books:
            state["error"] = "无法从您的消息中提取书单信息，请提供书名和作者"
            state["final_response"] = "无法从您的消息中提取书单信息，请提供书名和作者"
            return state

        logger.info(f"✓ 解析到 {len(books)} 本书籍")

        # 使用 Markdown 表格格式
        table_lines = [
            "| 书名 | 作者 | ISBN |",
            "| --- | --- | --- |"
        ]

        for idx, book in enumerate(books):
            title = book["title"]
            author = book["author"]

            try:
                # 频率控制：每次调用前等待1秒（第一次除外）
                if idx > 0:
                    logger.info("等待1秒，避免频率限制...")
                    await asyncio.sleep(1)

                # 直接调用商城 API 搜索图书（只用书名，不加作者）
                logger.info(f"[{idx + 1}/{len(books)}] 正在搜索《{title}》...")

                import requests
                api_url = "https://fx.cnpdx.com/fxpms/commodity/pageQuery"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Content-Type": "application/json;charset=UTF-8"
                }
                payload = {
                    "searchField": "searchAll",
                    "searchContent": title,  # 只用书名搜索
                    "page": 1,
                    "rows": 10
                }

                response = requests.post(api_url, json=payload, headers=headers, timeout=10)
                raw_data = response.text

                # 提取所有搜索结果
                import re
                book_titles = re.findall(r'"bookTitle":"((?:\\"|[^"])*)"', raw_data)
                isbns = re.findall(r'"isbn":"((?:\\"|[^"])*)"', raw_data)
                authors_list = re.findall(r'"authoreditor":"((?:\\"|[^"])*)"', raw_data)

                if not book_titles:
                    # 未找到，使用原始信息
                    table_lines.append(f"| {title} | {author} | |")
                    logger.warning(f"未找到《{title}》")
                    continue

                # 构建候选书籍列表（用于 LLM 筛选）
                candidates = []
                for i in range(min(len(book_titles), len(isbns), len(authors_list))):
                    clean_title = re.sub(r'<[^>]+>', '', book_titles[i])
                    candidates.append({
                        "title": clean_title,
                        "author": authors_list[i],
                        "isbn": isbns[i]
                    })

                # 使用 LLM 筛选最匹配的书籍
                logger.info(f"使用 LLM 筛选《{title}》的最佳匹配...")
                filter_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
                filter_prompt = f"""从以下搜索结果中，选择与目标书籍最匹配的一本。

目标书籍：
- 书名：{title}
- 作者：{author}

搜索结果：
{json.dumps(candidates, ensure_ascii=False, indent=2)}

请选择最匹配的书籍，只返回该书籍的索引（0-{len(candidates)-1}）。
如果没有合适的匹配，返回 -1。

只返回数字，不要其他内容。"""

                filter_result = filter_llm.invoke(filter_prompt).content.strip()

                try:
                    selected_idx = int(filter_result)
                    if 0 <= selected_idx < len(candidates):
                        selected = candidates[selected_idx]
                        actual_title = selected["title"]
                        actual_author = selected["author"]
                        isbn = selected["isbn"]

                        table_lines.append(f"| {actual_title} | {actual_author} | {isbn} |")
                        logger.info(f"✓ 获取《{title}》信息成功")
                    else:
                        # LLM 返回 -1，没有合适的匹配
                        table_lines.append(f"| {title} | {author} | |")
                        logger.warning(f"LLM 未找到《{title}》的合适匹配")
                except ValueError:
                    # LLM 返回格式错误，使用第一个结果
                    logger.warning(f"LLM 返回格式错误，使用第一个结果")
                    selected = candidates[0]
                    table_lines.append(f"| {selected['title']} | {selected['author']} | {selected['isbn']} |")

            except Exception as e:
                logger.error(f"获取《{title}》信息失败: {e}")
                # 失败时也添加到表格，ISBN 为空
                table_lines.append(f"| {title} | {author} | |")

        # 直接设置最终响应（Markdown 表格格式）
        state["final_response"] = "\n".join(table_lines)
        logger.info(f"✓ 生成表格数据完成，共 {len(books)} 本书")

    except Exception as e:
        logger.error(f"搜索书单失败: {e}")
        state["error"] = f"搜索书单失败: {str(e)}"
        state["final_response"] = f"搜索书单失败: {str(e)}"

    return state


async def format_final_response(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点7: 格式化最终响应

    将所有信息整合成 Markdown 格式
    """
    logger.info("📍 节点: format_final_response")

    dialogue = state.get("dialogue_response", "")
    books_detail = state.get("books_detail", [])

    # 格式化每本书的详细信息
    formatted_books = []
    for detail in books_detail:
        formatted = _format_book_markdown(detail)
        if formatted:
            formatted_books.append(formatted)

    # 组合最终响应
    if dialogue:
        final_response = f"{dialogue}\n\n---\n\n" + "\n\n".join(formatted_books)
    else:
        final_response = "\n\n".join(formatted_books)

    state["final_response"] = final_response
    logger.info("✓ 格式化最终响应完成")

    return state


async def save_to_memory(state: BookRecommendationState) -> BookRecommendationState:
    """
    节点8: 保存到记忆系统

    保存推荐记录、交互历史到数据库和向量库
    """
    logger.info("📍 节点: save_to_memory")

    memory_manager = state.get("memory_manager")

    if not memory_manager:
        logger.warning("没有记忆管理器，跳过保存")
        return state

    try:
        user_query = state["user_query"]
        final_response = state["final_response"]
        books_detail = state["books_detail"]
        session_id = state["session_id"]

        # 保存到短期记忆
        memory_manager.save_interaction(user_query, final_response)

        # 保存到向量数据库
        await memory_manager.save_to_vector_store(
            user_query,
            final_response,
            metadata={"session_id": session_id}
        )

        # 批量保存推荐记录
        for book in books_detail:
            try:
                await memory_manager.save_recommendation(
                    book={
                        "title": book.get("title", ""),
                        "author": book.get("author", ""),
                        "isbn": book.get("isbn", ""),
                        "reason": book.get("reason", "")
                    },
                    user_query=user_query,
                    session_id=session_id,
                    auto_commit=False
                )
            except Exception as e:
                logger.error(f"保存推荐记录失败: {e}")

        # 统一提交
        await memory_manager.db_session.commit()
        logger.info(f"✓ 保存 {len(books_detail)} 条推荐记录到数据库")

    except Exception as e:
        logger.error(f"保存记忆失败: {e}")
        if memory_manager:
            await memory_manager.db_session.rollback()

    return state


# ========== 条件路由 ==========

def route_by_type(state: BookRecommendationState) -> str:
    """
    条件边: 根据查询类型路由

    Returns:
        "customer_service" | "clarify" | "recommend" | "search_booklist"
    """
    query_type = state.get("query_type", "book_recommendation")

    # 如果是客服咨询，直接路由到客服节点
    if query_type == "customer_service":
        return "customer_service"

    # 如果是搜索书单，直接路由到搜索书单节点
    if query_type == "search_booklist":
        return "search_booklist"

    # 如果是图书推荐，检查是否需要澄清
    if not state.get("is_query_clear", True):
        return "clarify"

    # 明确的图书推荐需求
    return "recommend"


def should_clarify(state: BookRecommendationState) -> str:
    """
    条件边: 判断是否需要澄清

    Returns:
        "clarify" 或 "proceed"
    """
    if state.get("is_query_clear", True):
        return "proceed"
    else:
        return "clarify"


def has_error(state: BookRecommendationState) -> str:
    """
    条件边: 判断是否有错误

    Returns:
        "error" 或 "continue"
    """
    if state.get("error"):
        return "error"
    else:
        return "continue"


# ========== 辅助函数 ==========

def _parse_recommendation_response(llm_response: str) -> tuple[str, List[Dict]]:
    """
    解析LLM推荐响应，提取对话部分和书籍列表

    Returns:
        (dialogue_part, books_list)
    """
    dialogue_part = ""
    books = []

    # 尝试提取JSON部分
    json_match = re.search(r'\{["\']books["\']\s*:\s*\[.*?\]\s*\}', llm_response, re.DOTALL)

    if json_match:
        json_part = json_match.group(0)
        dialogue_part = llm_response[:json_match.start()].strip()

        try:
            # 清理并解析JSON
            clean_json = re.sub(r'```json\s*|\s*```', '', json_part).strip()
            # 修复常见JSON格式问题
            clean_json = re.sub(r'("reason":\s*)([^",}\]]+)([,}\]])', r'\1"\2"\3', clean_json)

            book_data = json.loads(clean_json)
            books = book_data.get("books", [])
        except Exception as e:
            logger.error(f"解析书单JSON失败: {e}")
            # 尝试正则提取
            books = _regex_extract_books(llm_response)
    else:
        # 没有找到标准JSON，尝试正则提取
        books = _regex_extract_books(llm_response)

    return dialogue_part, books



def _regex_extract_books(text: str) -> List[Dict]:
    """使用正则表达式提取书籍信息（带 reason）"""
    books = []

    title_pattern = r'"title":\s*"([^"]+)"'
    author_pattern = r'"author":\s*"([^"]+)"'
    reason_pattern = r'"reason":\s*"?([^",}]+)"?'

    titles = re.findall(title_pattern, text)
    authors = re.findall(author_pattern, text)
    reasons = re.findall(reason_pattern, text)

    for i in range(min(len(titles), len(authors))):
        books.append({
            "title": titles[i],
            "author": authors[i],
            "reason": reasons[i] if i < len(reasons) else "推荐阅读"
        })

    logger.info(f"正则提取得到 {len(books)} 本书籍")
    return books



async def _fetch_single_book_detail(book: Dict) -> Dict:
    """
    获取单本书的完整信息

    包括：豆瓣详情、馆藏、电子资源、购买链接
    """
    title = book["title"]
    author = book["author"]
    reason = book.get("reason", "")

    try:
        logger.info(f"开始获取《{title}》的详细信息")

        # Step 1: 搜索豆瓣获取 URI
        douban_search_result = search_douban_book.invoke({
            "book_name": title,
            "author": author
        })

        data = json.loads(douban_search_result)
        books_found = data.get("books", [])

        if not books_found:
            logger.warning(f"豆瓣未找到《{title}》")
            return {}

        # 选择最相关的结果（通常第一个）
        uri = books_found[0]["uri"]

        # Step 2: 获取豆瓣详情
        detail_result = get_douban_book_detail.invoke({"uri": uri})
        detail = json.loads(detail_result)

        # Step 3: 并行获取资源、购买、馆藏信息
        isbn = detail.get("isbn", "")
        publisher = detail.get("publisher", "")

        tasks = [
            asyncio.to_thread(
                search_digital_resource.invoke,
                {"publisher": publisher, "book_name": title, "author": author, "isbn": isbn}
            )
        ]

        if isbn:
            tasks.append(asyncio.to_thread(search_shop_by_isbn.invoke, {"isbn": isbn}))
            tasks.append(asyncio.to_thread(search_library_collection.invoke, {"isbn": isbn, "book_name": title}))
        else:
            tasks.append(asyncio.sleep(0, result="[]"))
            tasks.append(asyncio.sleep(0, result="[]"))

        results = await asyncio.gather(*tasks)

        # 组装完整信息
        return {
            "title": detail.get("title", title),
            "author": detail.get("author", author),
            "publisher": detail.get("publisher", "未知"),
            "isbn": isbn,
            "rating": detail.get("rating", ""),
            "summary": detail.get("summary", ""),
            "image": detail.get("image", ""),
            "reason": reason,
            "digital_resources": results[0],
            "shop_links": results[1],
            "library_info": results[2]
        }

    except Exception as e:
        logger.error(f"获取《{title}》详细信息失败: {e}")
        return {}


def _format_book_markdown(detail: Dict) -> str:
    """
    将书籍详细信息格式化为 Markdown
    """
    if not detail or not detail.get("title"):
        return ""

    title = detail["title"]
    author = detail["author"]
    publisher = detail.get("publisher", "未知")
    isbn = detail.get("isbn", "未知")
    summary = detail.get("summary", "暂无简介")
    image = detail.get("image", "")
    rating = detail.get("rating", "")
    reason = detail.get("reason", "")

    # 构建推荐理由：优先使用 LLM 生成的 reason，其次使用豆瓣简介
    if reason:
        # 如果有推荐理由，结合简介一起展示
        recommendation = f"{reason}\n\n{summary[:200]}..." if len(summary) > 200 else f"{reason}\n\n{summary}"
    else:
        # 只使用简介
        recommendation = summary

    # 格式化电子资源
    resource_text = _format_digital_resources(detail.get("digital_resources", "[]"))

    # 格式化购买链接
    shop_text = _format_shop_links(detail.get("shop_links", "[]"))

    # 格式化馆藏信息
    library_text = _format_library_info(detail.get("library_info", "[]"))

    # 图片
    image_markdown = f"![{title}]({image})\n\n" if image else ""

    # 评分
    rating_text = f"⭐ **豆瓣评分**：{rating}\n\n" if rating else ""

    markdown = f"""{image_markdown}###  {title}
**作者**：{author}

**出版社**：{publisher}

**ISBN**：{isbn}

{rating_text}**推荐理由**：
{recommendation}

**📍 馆藏信息**：
{library_text}

**📥 电子资源**：
{resource_text}

**🛒 购买链接**：
{shop_text}


---"""

    return markdown


def _format_digital_resources(resource_json: str) -> str:
    """格式化电子资源"""
    try:
        resources = json.loads(resource_json)
        if resources:
            formatted = []
            for r in resources:
                title_with_author = f"{r['title']} - {r['author']}" if r.get('author') else r['title']
                formatted.append(f"\n[{r['source']}] [{title_with_author}]({r['link']})")
            return '\n'.join(formatted)
        else:
            return '暂无资源'
    except:
        return '暂无资源'


def _format_shop_links(shop_json: str) -> str:
    """格式化购买链接"""
    try:
        shops = json.loads(shop_json)
        if shops:
            return '\n'.join([f"\n[{s['source']}] [{s['title']}]({s['link']})  {s['price']}" for s in shops])
        else:
            return '暂无购买链接'
    except:
        return '暂无购买链接'


def _format_library_info(library_json: str) -> str:
    """格式化馆藏信息"""
    try:
        libraries = json.loads(library_json)
        if libraries:
            lib_lines = []
            for lib in libraries:
                lib_lines.append(
                    f"\n索书号: {lib['call_number']} | {lib['floor']} {lib['location']} | {lib['status']} "
                    f"(馆藏{lib['total']}册，可借{lib['available']}册)"
                )
            return '\n'.join(lib_lines)
        else:
            return '暂无馆藏\n\n[荐购此书](https://library.example.com/recommend)'
    except:
        return '暂无馆藏\n\n[荐购此书](https://library.example.com/recommend)'


# ========== 构建 StateGraph ==========

def create_recommendation_graph() -> StateGraph:
    """
    创建图书推荐工作流图

    工作流程：
    0. route_query（智能路由）
       ├─ 客服咨询 → customer_service → END
       ├─ 需求不明确 → clarify → END
       ├─ 搜索书单 → search_booklist → END
       └─ 明确的图书推荐 → load_context

    图书推荐路径：
    1. load_context（加载用户上下文）
       └→ recommend

    2. recommend（生成推荐书单）
       ├─ 有错误 → END
       └─ 无错误 → fetch_detail

    3. fetch_detail（获取书籍详细信息）
       └→ format_response

    4. format_response（格式化最终响应）
       └→ update_prefs

    5. update_prefs（更新用户偏好）
       └→ save_memory

    6. save_memory（保存到记忆系统）
       └→ END

    节点说明：
    - route_query: 智能路由，判断查询类型和明确性
    - customer_service: 处理客服咨询（使用 RAG）
    - clarify: 生成澄清问题引导用户
    - search_booklist: 搜索用户提供的书单，输出 Markdown 表格
    - load_context: 从数据库加载用户画像和历史推荐
    - recommend: 使用LLM生成个性化推荐书单（基于用户画像）
    - fetch_detail: 并行获取豆瓣、馆藏、资源、购买链接
    - format_response: 格式化为Markdown响应
    - update_prefs: 根据推荐结果增量更新用户偏好（偏好学习）
    - save_memory: 保存交互到数据库和向量库
    """
    workflow = StateGraph(BookRecommendationState)

    # 添加节点
    workflow.add_node("route", route_query)
    workflow.add_node("customer_service", handle_customer_service)
    workflow.add_node("clarify", generate_clarification_response)
    workflow.add_node("search_booklist", search_booklist)
    workflow.add_node("load_context", load_user_context)
    workflow.add_node("update_prefs", update_user_preferences)
    workflow.add_node("recommend", generate_book_recommendations)
    workflow.add_node("fetch_detail", fetch_books_detail)
    workflow.add_node("format_response", format_final_response)
    workflow.add_node("save_memory", save_to_memory)

    # 设置入口点
    workflow.set_entry_point("route")

    # 智能路由条件边
    workflow.add_conditional_edges(
        "route",
        route_by_type,
        {
            "customer_service": "customer_service",
            "clarify": "clarify",
            "recommend": "load_context",
            "search_booklist": "search_booklist"
        }
    )

    # 客服分支直接结束
    workflow.add_edge("customer_service", END)

    # 澄清分支直接结束
    workflow.add_edge("clarify", END)

    # 搜索书单分支直接结束
    workflow.add_edge("search_booklist", END)

    # load_context → recommend（直接进入详细推荐流程）
    workflow.add_edge("load_context", "recommend")

    # 详细推荐流程：recommend → fetch_detail → format_response → update_prefs → save_memory → END
    workflow.add_conditional_edges(
        "recommend",
        has_error,
        {
            "error": END,
            "continue": "fetch_detail"
        }
    )

    # 详细信息流程
    workflow.add_edge("fetch_detail", "format_response")
    workflow.add_edge("format_response", "update_prefs")
    workflow.add_edge("update_prefs", "save_memory")
    workflow.add_edge("save_memory", END)

    return workflow.compile()


# ========== 流式执行 ==========

async def stream_recommendation_workflow(
    user_query: str,
    session_id: str,
    user_id: str,
    conversation_manager: ConversationManager,
    memory_manager: Optional[UserMemoryManager] = None,
    rag_service: Optional[RAGCustomerService] = None
):
    """
    流式执行推荐工作流，逐步返回结果

    Args:
        user_query: 用户查询
        session_id: 会话ID
        user_id: 用户ID
        conversation_manager: 会话管理器
        memory_manager: 记忆管理器（可选）
        rag_service: RAG 客服服务（可选）

    Yields:
        Dict: 各阶段的事件
            - type: "session" | "status" | "dialogue" | "books" | "book_detail" | "done" | "error"
            - content: 内容
    """
    # 创建图
    graph = create_recommendation_graph()

    # 初始化状态
    initial_state = BookRecommendationState(
        user_query=user_query,
        session_id=session_id,
        user_id=user_id,
        conversation_manager=conversation_manager,
        memory_manager=memory_manager,
        rag_service=rag_service,  # 添加 RAG 服务
        query_type="book_recommendation",  # 新增
        is_query_clear=True,
        clarification_questions=[],
        recommended_books=[],
        books_detail=[],
        dialogue_response="",
        final_response="",
        user_profile=None,
        recent_recommendations=[],
        error=None
    )

    # 返回会话信息
    yield {
        "type": "session",
        "session_id": session_id,
        "user_id": user_id
    }

    try:
        # 流式执行图（LangGraph 支持 astream）
        async for event in graph.astream(initial_state):
            node_name = list(event.keys())[0]
            node_state = event[node_name]

            logger.info(f"🔄 节点完成: {node_name}")

            # 根据节点发送不同事件
            if node_name == "search_booklist":
                # 搜索书单完成，直接返回 CSV
                yield {
                    "type": "message",
                    "content": node_state["final_response"]
                }
                yield {"type": "done"}
                return

            elif node_name == "customer_service":
                # 客服响应
                yield {
                    "type": "message",
                    "content": node_state["final_response"]
                }
                yield {"type": "done"}
                return

            elif node_name == "clarify":
                # 澄清问题
                yield {
                    "type": "message",
                    "content": node_state["final_response"]
                }
                yield {"type": "done"}
                return

            elif node_name == "recommend":
                # 推荐生成完成
                if node_state.get("error"):
                    yield {
                        "type": "error",
                        "content": "抱歉，我无法为您生成推荐书单。请尝试更具体地描述您的需求。"
                    }
                    yield {"type": "done"}
                    return

                # 发送对话部分
                if node_state.get("dialogue_response"):
                    yield {
                        "type": "dialogue",
                        "content": node_state["dialogue_response"]
                    }

                # 发送初步书单（简单格式）
                books = node_state.get("recommended_books", [])
                if books:
                    book_list_text = "\n\n".join([
                        f"**{i}. {b['title']}** - {b['author']}"
                        for i, b in enumerate(books, 1)
                    ])
                    yield {
                        "type": "books",
                        "content": book_list_text
                    }

            elif node_name == "fetch_detail":
                # 开始获取详细信息
                yield {
                    "type": "status",
                    "content": "正在为您查询这些书籍的详细信息..."
                }

            elif node_name == "format_response":
                # 发送详细信息
                books_detail = node_state["books_detail"]
                for i, book in enumerate(books_detail, 1):
                    formatted = _format_book_markdown(book)
                    if formatted:
                        yield {
                            "type": "book_detail",
                            "content": formatted,
                            "index": i,
                            "total": len(books_detail)
                        }

            elif node_name == "save_memory":
                # 保存完成
                logger.info("✓ 工作流执行完成")

        # 最终完成标记
        yield {"type": "done"}

    except Exception as e:
        logger.error(f"工作流执行失败: {e}", exc_info=True)
        yield {
            "type": "error",
            "content": f"处理您的请求时出错: {str(e)}"
        }
        yield {"type": "done"}
