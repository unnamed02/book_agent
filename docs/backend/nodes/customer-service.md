# 客服节点 (Customer Service Node)

## 功能说明

客服节点处理非图书推荐相关的用户咨询，提供两种模式：RAG 增强回答和纯 LLM 回答。

## 主要职责

1. **RAG 知识库检索** - 从知识库中找到相关的文档片段

2. **上下文准备** - 提供用户历史对话作为上下文

3. **响应生成** - 基于知识库内容和 LLM 生成准确回答

4. **置信度评估** - 评估回答的置信度，添加适当的提示

## 输入

从意图识别节点获取：
```python
state = {
  "user_query": "这个系统有什么功能？",
  "session": Session对象,
  "rag_service": RAGService对象  # 可选
}
```

## 工作流程

### 启用 RAG 的流程

```
接收用户问题
    |
    v
检查 RAG 服务是否可用
    |
    +-- 否 --> 降级到纯 LLM 模式
    |
    v
获取对话历史（最近 3 轮）
    |
    v
调用 RAG 服务检索相关文档
    |
    v
LLM 基于检索结果生成回答
    |
    v
评估回答的置信度
    |
    v
根据置信度添加提示信息
    |
    v
返回最终回答
```

### 降级为纯 LLM 模式

```
检查到 RAG 服务不可用
    |
    v
使用客服系统提示词
    |
    v
直接调用 LLM
    |
    v
生成回答
    |
    v
返回结果
```

## 两种模式对比

| 特性 | RAG 模式 | 纯 LLM 模式 |
|------|---------|----------|
| 数据来源 | 知识库 + LLM | 仅 LLM 训练数据 |
| 准确性 | 更高（基于真实数据） | 中等（可能出现幻觉） |
| 置信度 | 可计算 | 不可用 |
| 参考来源 | 可提供 | 无 |
| 响应时间 | 稍慢 | 快 |
| 后备方案 | 纯 LLM | 仅此一种 |

## RAG 回答流程

### 1. 历史对话提取

从会话中获取最近 3 轮对话作为上下文：

```python
# 获取最近 6 条消息（3 轮对话）
messages = session_obj.messages[-6:]

# 转换为简化格式
conversation_history = [
  {
    "user": "用户问题 1",
    "assistant": "助手回答 1"
  },
  {
    "user": "用户问题 2",
    "assistant": "助手回答 2"
  }
]
```

### 2. 知识库检索

```python
rag_result = await rag_service.answer_question(
    user_query,  # 当前问题
    conversation_history=conversation_history  # 上下文
)

# 返回格式
{
  "answer": "回答文本",
  "sources": ["来源1", "来源2"],
  "confidence": 0.85  # 置信度 0-1
}
```

### 3. 置信度处理

根据置信度添加适当的提示：

```python
if confidence < 0.5 and sources:
    # 置信度较低，但有来源
    answer += "\n💡 以上回答基于系统知识库，如需更多帮助请提供更多细节。"
elif not sources:
    # 没有找到相关来源
    answer += "\n💡 如需更详细的帮助，欢迎联系人工客服。"
```

### 4. 参考来源添加

```python
if sources:
    source_text = "\n📚 **参考来源**: " + "、".join(sources)
    answer += source_text
```

## 返回格式

### RAG 成功的返回

```python
state = {
  "final_response": "关于系统功能的详细回答...\n\n💡 以上回答基于系统知识库\n\n📚 参考来源: FAQ文档、功能介绍",
  "dialogue_response": "同上"
}
```

### RAG 失败降级到纯 LLM

```python
state = {
  "final_response": "基于 LLM 生成的回答",
  "dialogue_response": "同上"
}
```

## 关键参数

### RAG 模式

| 参数 | 值 | 说明 |
|------|-----|------|
| 历史长度 | 6 消息 | 3 轮对话 |
| 检索库 | 知识库 | Milvus 向量数据库 |
| 融合 | RAG + LLM | 检索 + 生成 |

### 纯 LLM 模式

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | qwen-flash | 轻量模型 |
| 温度 | 0.7 | 增加多样性 |
| 历史 | 否 | 不需要历史 |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| RAG 服务异常 | 自动降级到纯 LLM，记录错误 |
| 知识库无相关文档 | 添加"欢迎联系人工客服"提示 |
| LLM 调用失败 | 返回通用错误消息 |

## 适用场景

客服节点用于回答：

- 系统功能和使用方法
- 常见问题解答 (FAQ)
- 账户相关问题
- 技术支持问题
- 反馈和建议

## 与其他节点的关系

客服节点在意图识别为 `customer_service` 时被调用：

```
用户问题
    |
    v
意图识别节点
    |
    v
识别为 customer_service
    |
    v
客服节点处理 <-- 你在这里
    |
    v
返回回答给用户
```

## 相关文件

- 源码: [customer_service_node.py](../../../backend/nodes/customer_service_node.py)
- RAG 服务: [knowledge_base_tool.py](../../../backend/service/knowledge_base_tool.py)
- 知识库初始化: [init_knowledge_base.py](../../../backend/service/init_knowledge_base.py)
- 系统提示词: [system_prompts.py](../../../backend/prompts/system_prompts.py)

---

最后更新: 2026-03-16
