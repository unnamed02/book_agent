# 解析书单节点 (Parse Book List Node)

## 功能说明

解析书单节点使用 LLM 从推荐文本中提取结构化的书籍信息，转换为标准的书籍数据结构。

## 主要职责

1. **文本解析** - 使用 LLM 理解推荐文本

2. **信息提取** - 从推荐文本中提取书名、作者、推荐理由

3. **JSON 转换** - 将提取的信息转换为结构化 JSON 格式

4. **数据验证** - 确保提取的数据完整有效

## 输入

从推荐节点获取：
```python
state = {
  "book_list_text": "推荐思路：...\n\n推荐书单：\n《Python高效编程》- 作者：张三 - ...",
  "session": Session对象
}
```

## 工作流程

```
接收推荐文本
    |
    v
检查文本是否为空
    |
    +-- 为空 --> 返回空书单
    |
    v
设置书单解析提示词
    |
    v
调用 LLM 解析文本
    |
    v
提取响应中的 JSON
    |
    v
解析 JSON 数据
    |
    v
转换为标准格式
    |
    v
返回结构化书籍列表
```

## 解析流程详解

### 1. LLM 调用

使用快速、轻量的模型进行解析：

```python
response = await session.ainvoke(
    user_input=book_list_text,
    model="qwen-flash",  # 快速模型
    temperature=0,        # 确定性输出
    need_save=False,
    include_history=False
)
```

### 2. JSON 提取

处理多种 JSON 包装方式：

```
LLM 响应可能的格式：
1. 原始 JSON 对象
2. ```json { ... } ``` 代码块
3. ``` { ... } ``` 代码块
4. 其他文本中嵌入 JSON
```

节点自动处理这些格式，使用括号计数找到完整的 JSON 对象。

### 3. 数据转换

从 LLM 输出转换为标准格式：

```python
# LLM 返回的 JSON
{
  "books": [
    {
      "title": "Python高效编程",
      "author": "张三",
      "reason": "这是Python编程的必读经典"
    }
  ]
}

# 转换为标准格式
books = [
  {
    "title": "Python高效编程",
    "author": "张三",
    "reason": "这是Python编程的必读经典"
  }
]
```

## 返回格式

```python
state = {
  "recommended_books": [
    {
      "title": "Python高效编程",
      "author": "张三",
      "reason": "这是Python编程的必读经典"
    },
    {
      "title": "Fluent Python",
      "author": "Luciano Ramalho",
      "reason": "深入讲解Python特性和最佳实践"
    },
    ...
  ]
}
```

## 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | qwen-flash | 轻量快速模型，适合解析任务 |
| 温度 | 0 | 确定性输出，确保一致的解析 |
| 流式 | 否 | 返回完整响应后再处理 |

## 错误处理

| 错误类型 | 原因 | 处理 |
|---------|------|------|
| 文本为空 | 上游未生成推荐文本 | 返回空书单列表 |
| JSON 解析失败 | LLM 输出格式错误 | 记录错误，返回空列表 |
| 缺少关键字段 | 提取的数据不完整 | 跳过该条目或填充默认值 |

### 常见问题处理

```python
# 处理不同的 JSON 包装
if "```json" in json_text:
    json_text = json_text.split("```json")[1].split("```")[0].strip()
elif "```" in json_text:
    json_text = json_text.split("```")[1].split("```")[0].strip()

# 处理文本中的 JSON 对象
if "{" in json_text:
    start = json_text.index("{")
    json_text = json_text[start:]
    # 使用括号计数找到完整的 JSON
```

## 与下游节点的关系

解析完成后，节点将控制权传给：

1. **获取详情节点** - 获取每本书的豆瓣、馆藏、电子资源信息

工作流的路由规则：
- 如果成功提取书籍 → 继续到获取详情节点
- 如果提取失败或为空 → 返回错误响应

## 相关文件

- 源码: [parse_book_list_node.py](../../../backend/nodes/parse_book_list_node.py)
- 系统提示词: [system_prompts.py](../../../backend/prompts/system_prompts.py)
- 会话管理: [session.py](../../../backend/session/session.py)

---

最后更新: 2026-03-16
