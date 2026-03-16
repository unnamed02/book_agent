# 查找书籍节点 (Find Book Node)

## 功能说明

查找书籍节点负责根据用户提供的书籍名称，使用 LLM 生成结构化的查找结果文本，然后由下游节点解析并获取详细信息。

**注意**：此节点与推荐书籍节点非常相似 - 都是生成文本，然后由解析书单节点提取结构化信息。

## 主要职责

1. **流式生成查找结果** - 使用 LLM 生成用户友好的查找列表文本

2. **实时反馈** - 流式输出让用户看到正在查找的书籍

3. **文本存储** - 将生成的文本保存供解析节点使用

## 输入

从意图识别节点获取：
```python
state = {
  "user_query": "帮我找《Python高效编程》和《Fluent Python》",
  "slots": FindBookSlots(
    book_titles=["Python高效编程", "Fluent Python"]
  ),
  "session": Session对象
}
```

## 工作流程

```
接收书名列表（从意图识别节点）
    |
    v
构建查询输入
    |
    +-- 如果有书名：「查找以下书籍：...」
    |
    +-- 如果没有：使用原始用户查询
    |
    v
设置查找系统提示词
    |
    v
流式调用 LLM 生成查找结果
    |
    v
实时推送生成的文本给前端
    |
    v
保存生成的书单文本 (book_list_text)
    |
    v
继续流程：解析书单 -> 获取详情
```

**工作流特点**：
- 使用 LLM 生成文本（而不是直接调用 API）
- 支持流式输出，用户可实时看到查找进度
- 输出格式与推荐节点相同，由相同的后续节点处理
- 温度为 0，确保确定性输出

## 返回的结果格式

```python
state = {
  "book_list_text": "正在查找以下书籍：\n《Python高效编程》 - 作者：张三\n《Fluent Python》 - 作者：Luciano Ramalho\n\n已找到 2 本书籍的详细信息...",
  "dialogue_response": "正在查找以下书籍：...",
  "streaming_tokens": ["正在", "查找", "..."]  # 流式令牌
}
```

## 状态更新

| 字段 | 说明 |
|------|------|
| `book_list_text` | 生成的查找结果文本 |
| `dialogue_response` | 对话响应（与 book_list_text 相同） |
| `streaming_tokens` | 流式生成的令牌数组 |
| `error` | 如果发生错误 |

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | qwen3-max-2026-01-23 | 最新千问模型 |
| 温度 | 0 | 确定性输出 |
| 流式 | 是 | 实时推送生成结果 |
| 保存 | 是 | 将结果保存到用户记忆 |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| LLM 生成失败 | 记录错误，返回错误消息 |
| 内容审核失败 | 返回"内容触发了审核" |
| 没有提取到书名 | 降级到使用原始查询 |

## 与下游节点的关系

查找书籍节点的输出被直接传递给解析书单节点：

```
查找书籍节点
    |
    v
生成 search_results（书籍列表）
    |
    v
状态中的 search_results 被解析书单节点使用
    |
    v
后续步骤：获取详情节点构建完整卡片
```

注意：此节点与推荐书籍流程在解析之后合并，使用相同的获取详情机制。

## 相关文件

- 源码: [find_book_node.py](../../../backend/nodes/find_book_node.py)
- 豆瓣工具: [douban_tool.py](../../../backend/tools/douban_tool.py)
- 图书馆工具: [library_tool.py](../../../backend/tools/library_tool.py)
- 解析书单: [parse_book_list_node.py](../../../backend/nodes/parse_book_list_node.py)
- 获取详情: [fetch_details_node.py](../../../backend/nodes/fetch_details_node.py)

---

最后更新: 2026-03-16
