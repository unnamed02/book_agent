# 意图识别节点 (Intent Recognition Node)

## 功能说明

意图识别节点是工作流的入口节点，负责分析用户查询并识别其意图类型。

## 主要职责

1. **识别查询类型** - 判断用户想要什么
   - `find_book`: 查找特定书籍
   - `book_recommendation`: 获取书籍推荐
   - `book_info`: 查询书籍信息（梗概、版本比较等）
   - `customer_service`: 客服咨询
   - `default`: 闲聊或其他

2. **提取槽位信息** - 根据意图类型提取关键信息
   - 书名、作者、主题等

3. **反问处理** - 当信息不足时生成反问
   - 例如：用户说"推荐一本书"但没说想要什么类型
   - 节点会反问"请问您想看什么类型的书呢？"

## 槽位定义

### FindBookSlots (查找书籍)
```python
{
  "book_titles": ["书名1", "书名2"]  # 用户提到的书籍名称列表
}
```

### RecommendBookSlots (推荐书籍)
```python
{
  "topic": "编程书籍"  # 推荐主题或类型
}
```

### BookInfoSlots (书籍信息查询)
```python
{
  "query": "版本比较",  # 查询类型: 梗概、版本比较、导读等
  "book_title": "Python高效编程",  # 可选：书名
  "author": "张三",  # 可选：作者
  "pub_info": ["机械工业出版社", "中文版"]  # 可选：版本信息
}
```

### CustomerServiceSlots (客服咨询)
```python
{
  "question": "这个系统有什么功能？"  # 用户的问题
}
```

### DefaultQuerySlots (默认/闲聊)
```python
{
  "query_context": "你好"  # 查询内容
}
```

## 工作流程

```
用户输入
    |
    v
调用 LLM 识别意图
    |
    v
信息完整？
    |
    +-- 否 --> 生成反问 --> 结束 (query_type: clarify)
    |
    +-- 是 --> 提取槽位 --> 继续工作流
```

## 返回的状态更新

| 字段 | 说明 | 示例 |
|------|------|------|
| `query_type` | 查询类型 | "book_recommendation" |
| `slots` | 提取的槽位信息 | RecommendBookSlots(...) |
| `dialogue_response` | 如果需要反问的响应 | "请问您想看什么类型的书？" |
| `final_response` | 如果直接回复的最终响应 | (同上) |

## 配置参数

```python
model="qwen3-max-2026-01-23"  # 使用的 LLM 模型
temperature=0  # 温度为 0 保证结果确定性
```

## 错误处理

- 如果识别失败，自动降级为 `default` 类型
- 如果触发内容审核，记录日志并使用默认路由

## 相关文件

- 源码: [intent_recognition_node.py](../../../backend/nodes/intent_recognition_node.py)
- 系统提示词: [prompts/system_prompts.py](../../../backend/prompts/system_prompts.py)

---

最后更新: 2026-03-16
