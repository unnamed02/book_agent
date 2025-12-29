from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from douban_tool import search_douban_book, get_douban_book_detail
from resource_tool import search_digital_resource
from shop_tool import search_shop_by_isbn
from library_tool import search_library_collection
import logging
import json
import asyncio
from langchain_openai import ChatOpenAI
    
logger = logging.getLogger(__name__)


def filter_info_with_llm(raw_result: str, book_name: str, author: str) -> int:
    """使用 LLM 过滤搜索结果，只保留相关的"""

    if "未找到" in raw_result or "搜索失败" in raw_result:
        return raw_result

    logger.info(f"\n{raw_result} {book_name} {author} ***\n")
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    prompt = f"""从以下搜索结果中，筛选出与书名: {book_name} 作者：{author} 最相关的资源。

选择标准（按优先级）：
1. 作者最接近 (模糊匹配)
2. 标题最接近 
3. 如果标题相似度接近，优先选择有评分的版本
4. 如果有多个版本且标题完全相同，选择出版时间最新的

如果没有相关的，返回"暂无相关资源"

搜索结果：
{raw_result}

这是一个数组，返回最合适的下标,纯数字"""

    try:
        select = llm.invoke(prompt).content
        return int(select)
    except:
        return 0


def create_book_info_chain():
    """创建图书信息收集 LCEL 链"""

    # Step 1: 搜索豆瓣获取 URI
    def get_uri(x):
        result = search_douban_book.invoke({"book_name": x["book_name"], "author": x["author"]})
        try:
            data = json.loads(result)
            books = data.get("books", [])
            return books[filter_info_with_llm(result,x["book_name"],x["author"])]["uri"] if books else ""
        except:
            return ""

    uri_chain = RunnablePassthrough.assign(uri=RunnableLambda(get_uri))

    # Step 2: 获取详情
    def get_detail(x):
        if not x["uri"]:
            return {}
        result = get_douban_book_detail.invoke({"uri": x["uri"]})
        try:
            return json.loads(result)
        except:
            return {}

    detail_chain = uri_chain.assign(detail=RunnableLambda(get_detail))

    # Step 3: 并行调用资源、商城和图书馆工具
    async def get_resources(x):
        detail = x.get("detail", {})

        publisher = detail.get("publisher", "")
        author = detail.get("author", "")
        title = detail.get("title", x["book_name"])
        isbn = detail.get("isbn", "")

        tasks = []
        tasks.append(asyncio.to_thread(
            search_digital_resource.invoke,
            {"publisher": publisher, "book_name": title, "author": author, "isbn": isbn}
        ))
        if isbn:
            tasks.append(asyncio.to_thread(
                search_shop_by_isbn.invoke,
                {"isbn": isbn}
            ))
            tasks.append(asyncio.to_thread(
                search_library_collection.invoke,
                {"isbn": isbn, "book_name": title}
            ))
        else:
            tasks.append(asyncio.sleep(0, result="无购买信息"))
            tasks.append(asyncio.sleep(0, result="[]"))

        results = await asyncio.gather(*tasks)
        return {"resource": results[0], "shop": results[1], "library": results[2]}

    final_chain = detail_chain.assign(tools_result=RunnableLambda(get_resources))

    # Step 4: 格式化输出为 markdown
    def format_output(x):
        detail = x.get("detail", {})
        tools = x.get("tools_result", {})

        # 从 JSON 中提取详情信息
        title = detail.get("title", "未知")
        author = detail.get("author", "未知")
        publisher = detail.get("publisher", "未知")
        isbn = detail.get("isbn", "未知")
        raw_summary = detail.get("summary", "暂无简介")
        image = detail.get("image", "")

        # 使用 LLM 生成评价
        if raw_summary and raw_summary != "暂无简介":
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
            prompt = f"""根据以下信息生成一段简洁的推荐理由（100-150字）：

书名：{title}
作者：{author}
简介：{raw_summary}

要求：突出书籍特点和内容梗概，语言简洁有吸引力。"""
            try:
                summary = llm.invoke(prompt).content
            except:
                summary = raw_summary
        else:
            summary = raw_summary

        # 如果书籍信息无效，返回空字符串
        if not detail or title == "未知" or not title:
            return ""

        # 格式化电子资源
        resource_text = tools.get('resource', '[]')
        try:
            resources = json.loads(resource_text)
            if resources:
                formatted = []
                for r in resources:
                    title_with_author = f"{r['title']} - {r['author']}" if r.get('author') else r['title']
                    formatted.append(f"\n[{r['source']}] [{title_with_author}]({r['link']})")
                resource_text = '\n'.join(formatted)
            else:
                resource_text = '暂无资源'
        except:
            resource_text = '暂无资源'

        # 格式化购买链接
        shop_text = tools.get('shop', '[]')
        try:
            shops = json.loads(shop_text)
            if shops:
                shop_text = '\n'.join([f"\n[{s['source']}] [{s['title']}]({s['link']})  {s['price']}" for s in shops])
            else:
                shop_text = '暂无购买链接'
        except:
            shop_text = '暂无购买链接'

        # 格式化馆藏信息
        library_text = tools.get('library', '[]')
        try:
            libraries = json.loads(library_text)
            if libraries:
                lib_lines = []
                for lib in libraries:
                    lib_lines.append(f"\n索书号: {lib['call_number']} | {lib['floor']} {lib['location']} | {lib['status']} (馆藏{lib['total']}册，可借{lib['available']}册)")
                library_text = '\n'.join(lib_lines)
            else:
                library_text = '暂无馆藏\n\n[荐购此书](https://library.example.com/recommend)'
        except:
            library_text = '暂无馆藏\n\n[荐购此书](https://library.example.com/recommend)'

        from urllib.parse import quote
        proxy_image = f"http://localhost:8000/proxy-image?url={quote(image)}" if image else ""
        image_markdown = f"![{title}]({proxy_image})\n\n" if proxy_image else ""

        markdown = f"""{image_markdown}###  {title}
**作者**：{author} \n
**出版社**：{publisher} \n
**ISBN**：{isbn}  \n

**推荐理由**：
{summary}

**📍 馆藏信息**：
{library_text}

**📥 电子资源**：
{resource_text}

**🛒 购买链接**：
{shop_text}


---"""
        return markdown

    return final_chain | RunnableLambda(format_output)

async def process_book_with_chain(book_name: str, author: str) -> str:
    """使用 LCEL 链处理单本书"""

    try:
        logger.info(f"开始处理: {book_name} {author}")
        chain = create_book_info_chain()
        result = await chain.ainvoke({"book_name": book_name,"author": author})
        logger.info(f"完成处理: {book_name}, 结果长度: {len(result)}")
        return result
    except Exception as e:
        logger.error(f"处理《{book_name}》失败: {e}", exc_info=True)
        return f"处理《{book_name}》时出错: {str(e)}"
