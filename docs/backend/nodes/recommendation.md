# 推荐节点 (Recommendation Node)

## 功能说明

推荐节点使用 LLM 生成人类可读的书籍推荐书单，生成格式为：推荐思路 + 书籍列表，并支持流式输出。

## 主要职责

1. **提取推荐主题** - 从槽位中获取用户想要的书籍类型

2. **LLM 生成** - 使用大模型生成自然语言推荐理由

3. **流式输出** - 实时将生成的文本发送给前端

4. **内容审核** - 处理不当内容的检测

## 输入

从意图识别节点获取：
```python
state = {
  "user_query": "推荐关于编程的书",
  "slots": RecommendBookSlots(topic="编程"),
  "session": Session对象
}
```

## 工作流程

```
接收推荐请求
    |
    v
从槽位提取推荐主题
    |
    v
构建查询输入（如：推荐关于编程的书籍）
    |
    v
设置推荐系统提示词
    |
    v
流式调用 LLM（温度0.7，增加多样性）
    |
    v
实时收集生成的文本
    |
    v
保存完整书单文本
    |
    v
返回推荐结果
```

## 生成格式

推荐节点生成的文本格式为：

```
【推荐思路】
以2-3句话说明为什么推荐这些书籍

【推荐书单】
《Python高效编程》 - 作者：张三 - 这是Python编程的经典之作
《Fluent Python》 - 作者：Luciano Ramalho - 深入讲解Python特性
《Python Cookbook》 - 作者：David Beazley - 实用编程技巧集合
```

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | qwen3-max-2026-01-23 | 最新的千问大模型 |
| 温度 | 0.7 | 增加生成的多样性（0.7 > 0 > 1.0） |
| 流式 | 是 | 实时返回文本流 |
| 保存记忆 | 是 | 将推荐结果保存到用户记忆 |
| 包含历史 | 否 | 不需要用户的历史对话 |

## 状态更新

| 字段 | 说明 | 类型 |
|------|------|------|
| `book_list_text` | 完整的推荐文本 | string |
| `dialogue_response` | 推荐的原始文本 | string |
| `streaming_tokens` | 流式生成的令牌数组 | list[string] |
| `error` | 如果发生错误 | string |

## 流式输出处理

节点支持实时推送生成的文本：

```python
# 初始化流式令牌列表
state["streaming_tokens"] = []

# 异步生成器逐个推送令牌
async for token in session.astream(...):
    full_response += token
    state["streaming_tokens"].append(token)  # 实时收集
```

前端可以监听 SSE 事件实时接收这些令牌并显示。

## 错误处理

| 错误类型 | 原因 | 响应 |
|---------|------|------|
| 内容审核失败 | 内容触发了安全审核 | 返回"内容审核失败" |
| 模型超时 | 生成时间过长 | 返回已生成的部分文本 |
| API 错误 | 模型 API 不可用 | 返回"生成推荐时出现错误" |

### 审核失败处理

如果检测到 `data_inspection_failed` 或 `inappropriate_content`：

```python
state["error"] = "内容审核失败"
state["dialogue_response"] = "抱歉，内容触发了审核。"
state["book_list_text"] = ""
```

## 与下游节点的关系

推荐节点生成文本后，流程继续到下游节点构建完整卡片：

```
推荐节点
    |
    v
生成推荐文本 (book_list_text)
    |
    v
解析书单节点
    |
    +-- 使用 LLM 从文本提取书籍信息
    |
    v
获取详情节点
    |
    +-- 并行查询豆瓣、馆藏、电子资源
    |
    v
返回完整卡片数据给前端
```

**与查找书籍的关系**：
- 推荐节点生成推荐文本，然后进行解析
- 查找书籍节点直接获得结构化数据，也需要解析处理
- 两条路径都通过相同的获取详情节点来丰富数据

## 相关文件

- 源码: [recommendation_node.py](../../../backend/nodes/recommendation_node.py)
- 系统提示词: [system_prompts.py](../../../backend/prompts/system_prompts.py)
- 会话管理: [session.py](../../../backend/session/session.py)

---

最后更新: 2026-03-16
