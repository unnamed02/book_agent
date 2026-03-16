# 获取详情节点 (Fetch Details Node)

## 功能说明

获取详情节点负责并行获取书籍的多源信息，包括豆瓣评分、图书馆馆藏、电子资源等详细数据，并构建完整的书籍卡片。

## 主要职责

1. **并行数据获取** - 同时调用多个数据源
   - 豆瓣 API（评分、封面、出版信息等）
   - 图书馆检索系统（馆藏信息）
   - 电子资源库（数字版本）

2. **数据聚合** - 整合来自多个来源的信息

3. **卡片构建** - 生成用于前端展示的书籍卡片数据

4. **质量过滤** - 去除没有有效资源的书籍

## 输入

从推荐节点或查找节点获取：
```python
state = {
  "recommended_books": [
    {
      "title": "Python高效编程",
      "author": "张三",
      "reason": "这是Python编程的必读经典"
    },
    ...
  ],
  "dialogue_response": "为您推荐以下书籍..."
}
```

## 工作流程

```
接收书籍列表
    |
    v
判断书籍数量（≤5本则获取豆瓣，>5本跳过豆瓣）
    |
    v
并行获取每本书的详情
    |
    +-- 查询电子资源库
    |
    +-- 查询图书馆系统
    |
    +-- 查询豆瓣 API (条件)
    |
    v
聚合结果并构建卡片
    |
    v
过滤无资源书籍
    |
    v
返回完整卡片数据
```

## 关键操作

### 并行获取单本书详情

为提高性能，系统使用 `asyncio.gather()` 并行调用三个信息源：

```python
tasks = [
  asyncio.to_thread(search_digital_resource, title, author),
  asyncio.to_thread(search_library_collection, title, author),
  asyncio.to_thread(search_douban_book, title, author)  # 条件
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 资源分组

电子资源按平台分组，便于前端展示：

```python
resources_by_source = {
  "微信读书": [book1, book2],
  "掌阅": [book3],
  "豆瓣阅读": [book4]
}
```

### 数据有效性检查

只有同时满足以下条件之一的书籍才会保留：
- 拥有图书馆馆藏
- 拥有电子资源

## 返回格式

```python
state = {
  "book_cards": [
    {
      "title": "Python高效编程",
      "author": "张三",
      "reason": "这是Python编程的必读经典",
      "rating": "8.5",
      "image": "https://book.douban.com/...",
      "publisher": "机械工业出版社",
      "pubdate": "2020-01",
      "isbn": "978-7-111-xxxxx",
      "summary": "本书详细讲述...",
      "hasLibrary": true,
      "libraryItems": [
        {
          "name": "市中心图书馆",
          "location": "第3楼编程类书籍区",
          "availability": "可借"
        }
      ],
      "hasResources": true,
      "resources": [
        {
          "source": "微信读书",
          "books": [
            {
              "title": "Python高效编程",
              "link": "https://...",
              "author": "张三",
              "publisher": "机械工业出版社"
            }
          ]
        }
      ]
    },
    ...
  ],
  "books_without_resources": [
    {
      "title": "某本书",
      "author": "某作者"
    }
  ],
  "final_response": "推荐书籍：《Python高效编程》、《Fluent Python》..."
}
```

## 性能优化

### 条件性豆瓣查询

为了平衡数据完整性和响应速度：

| 书籍数量 | 豆瓣查询 | 理由 |
|---------|---------|------|
| ≤ 5 本 | 是 | 用户查看少量书籍，需要完整信息 |
| > 5 本 | 否 | 列表较长，豆瓣查询可能导致超时 |

### 异步并行处理

- 每本书的三个查询同时进行
- 使用 `asyncio.gather()` 管理并发
- 返回异常时不中断整体流程

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 豆瓣查询失败 | 继续返回其他数据，仅缺少评分和封面 |
| 馆藏查询失败 | 继续返回，仅显示电子资源 |
| 电子资源查询失败 | 继续返回，仅显示馆藏 |
| 三个都失败 | 书籍加入 `books_without_resources` 列表 |

## 状态更新

| 字段 | 说明 |
|------|------|
| `book_cards` | 完整的书籍卡片数组 |
| `books_without_resources` | 没有任何资源的书籍列表 |
| `final_response` | 格式化的最终响应文本 |

## 相关文件

- 源码: [fetch_details_node.py](../../../backend/nodes/fetch_details_node.py)
- 豆瓣工具: [douban_tool.py](../../../backend/tools/douban_tool.py)
- 图书馆工具: [library_tool.py](../../../backend/tools/library_tool.py)
- 资源工具: [resource_tool.py](../../../backend/tools/resource_tool.py)

---

最后更新: 2026-03-16
