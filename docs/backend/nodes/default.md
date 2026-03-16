# 默认节点 (Default Node)

## 功能说明

默认节点处理无法分类为图书推荐、查找、或客服的通用查询，使用通义千问 API 直接回答各类问题。

## 主要职责

1. **通用回答** - 处理与图书无关的闲聊和问题

2. **网络搜索** - 启用搜索功能获取实时信息

3. **流式推理** - 显示 LLM 的思考过程（reasoning）

4. **流式输出** - 实时推送生成的文本给前端

## 输入

从意图识别节点获取：
```python
state = {
  "user_query": "今天天气怎么样？",
  "slots": DefaultQuerySlots(query_context="今天天气怎么样？"),
  "session": Session对象
}
```

## 工作流程

```
接收通用查询
    |
    v
从槽位提取查询上下文
    |
    v
设置默认系统提示词
    |
    v
启用网络搜索（enable_search=true）
    |
    v
流式调用千问大模型
    |
    v
处理推理内容
    |
    +-- 有推理 --> 推送思考内容
    |
    v
处理正文内容
    |
    +-- 实时推送回答文本
    |
    v
保存完整响应
    |
    v
返回最终回答
```

## 关键特性

### 1. 网络搜索集成

启用实时搜索获取最新信息：

```python
responses = await AioGeneration.call(
    model="qwen3-max-2026-01-23",
    enable_search=True,  # 启用搜索
    ...
)
```

这允许回答时间相关的问题：
- "今天天气怎么样？"
- "最新的技术新闻？"
- "最近的体育赛事？"

### 2. 推理思考显示

通义千问支持显示思考过程（Chain-of-Thought）：

```python
async for resp in responses:
    # 提取推理内容
    reasoning_content_chunk = resp.output.choices[0].message.get("reasoning_content")
    if reasoning_content_chunk:
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
```

### 3. 流式处理

通过增量输出实时推送文本：

```python
stream=True,              # 启用流式
incremental_output=True   # 增量输出
```

前端可以订阅 `on_tongyi_thinking` 和 `on_tongyi_chat` 事件获取实时内容。

## 返回格式

```python
state = {
  "dialogue_response": "完整的回答文本",
  "final_response": "完整的回答文本",
  "streaming_tokens": ["token1", "token2", ...],  # 流式令牌列表
  "error": None
}
```

## API 调用参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | qwen3-max-2026-01-23 | 最新的千问大模型 |
| 搜索 | 启用 | enable_search=True |
| 格式 | message | result_format="message" |
| 流式 | 启用 | stream=True |
| 增量 | 启用 | incremental_output=True |

## 错误处理

### 状态码检查

```python
async for resp in responses:
    if resp.status_code == 200:
        # 处理响应
    else:
        raise Exception(f"DashScope Error: {resp.message}")
```

### 异常捕获

```python
try:
    # API 调用
except Exception as e:
    logger.error(f"默认回复生成失败: {e}")
    state["error"] = str(e)
    state["dialogue_response"] = "抱歉，我暂时无法回答您的问题。"
    state["final_response"] = state["dialogue_response"]
```

## 适用场景

默认节点用于回答：

- 闲聊和问候 ("你好", "最近怎么样？")
- 常识问题 ("地球绕太阳一圈需要多久？")
- 新闻和时事 ("今天的新闻？", "最新的科技动向？")
- 天气查询 ("明天下雨吗？")
- 其他通用查询

## 与其他节点的关系

默认节点是意图识别的 fallback：

```
用户问题
    |
    v
意图识别节点
    |
    +-- find_book --> 查找节点
    +-- book_recommendation --> 推荐节点
    +-- book_info --> 书籍信息节点
    +-- customer_service --> 客服节点
    +-- default --> 默认节点 <-- 你在这里
```

## 前端事件监听

前端可以通过 EventSource 监听两个事件：

### 思考事件 (on_tongyi_thinking)
```javascript
eventSource.addEventListener('on_tongyi_thinking', (event) => {
  const data = JSON.parse(event.data);
  console.log('LLM 思考:', data.chunk);
  // 显示思考过程
});
```

### 回答事件 (on_tongyi_chat)
```javascript
eventSource.addEventListener('on_tongyi_chat', (event) => {
  const data = JSON.parse(event.data);
  console.log('LLM 回答:', data.chunk);
  // 显示回答文本
});
```

## 成本考虑

使用通义千问 API 的成本：
- 启用搜索：可能增加调用成本
- 推理显示：使用思考令牌
- 流式输出：计费标准与非流式相同

## 相关文件

- 源码: [default_node.py](../../../backend/nodes/default_node.py)
- 系统提示词: [system_prompts.py](../../../backend/prompts/system_prompts.py)
- 会话管理: [session.py](../../../backend/session/session.py)
- DashScope 文档: [https://dashscope.aliyun.com/](https://dashscope.aliyun.com/)

---

最后更新: 2026-03-16
