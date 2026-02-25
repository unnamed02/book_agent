
---

# 会话管理系统技术文档

## 1. 概述

该系统旨在管理多用户环境下的对话状态，结合了 **LRU（最近最少使用）缓存策略**、**Redis 持久化** 以及 **SQL 数据库记录**。为了应对长时间对话带来的存储压力，系统还包含了一个 **Compact（压缩/归档）机制**。

---

## 2. 核心组件详细说明

### 2.1 Session 类 (`session.py`)

`Session` 是对话状态的最小单位，负责管理单个用户的内存历史和 LLM 交互。

* **内存管理**：使用 `deque` 存储对话，通过 `max_history_rounds` 限制内存中的上下文长度（默认 10 轮）。
* **LLM 交互**：封装了 `ainvoke` 异步方法，支持动态切换模型（默认 `qwen-flash`）和温度参数。
* **Redis 同步**：
* 每条新消息都会实时追加到 Redis List (`conversation:{session_id}`)。
* **触发压缩**：当 Redis 列表长度超过 **220 条** 时，会自动将该会话 ID 加入 `needs_compact_list` 队列。



### 2.2 SessionManager 类 (`session_manager.py`)

负责全局会话的生命周期管理和资源调度。

* **LRU 策略**：通过 `OrderedDict` 管理内存会话。当达到 `max_sessions`（默认 1000）时，自动淘汰最久未使用的会话。
* **多级加载机制**：
1. **内存层**：首先检查 `self.sessions` 字典。
2. **数据库层**：若内存无命中，则查询 SQL 数据库（`UserSession` 表）确认会话是否存在。
3. **持久化层**：若数据库存在记录，则从 Redis 恢复该会话的所有历史消息。


* **归档逻辑**：当用户创建新会话时，系统会自动检测旧会话。若旧会话有内容，将其加入 `merge_archive_list` 归档队列。

### 2.3 Compact/归档机制 (`compact.py`)

为了防止 Redis 列表无限增长导致性能下降，系统设计了异步压缩机制。

* **会话压缩 (`compact_session_list`)**：
* 从 Redis 列表获取所有消息。
* 保留最新的 20 条消息作为“活跃上下文”。
* 将旧的消息（20条以后）转换成总结（Summary）或直接存入长期归档，以减小 List 体积。


* **自动处理队列**：
* `needs_compact_list`：存储达到长度阈值、需要压缩的活跃会话。
* `merge_archive_list`：存储用户已切换、可以被完全归档的旧会话。



---

## 3. 数据流转示意

1. **用户输入** -> `SessionManager.get_or_create_session()`。
2. **执行对话** -> `Session.ainvoke()`。
* 存入内存 `deque`。
* 存入 Redis List。


3. **触发阈值** -> 若 Redis List > 220 条 -> 加入 `needs_compact_list`。
4. **后台清理** -> `compact.py` 定期轮询队列，执行压缩并释放 Redis 空间。

---

## 4. 关键配置参数

| 参数 | 默认值 | 所在位置 | 说明 |
| --- | --- | --- | --- |
| `max_history_rounds` | 10 | `Session` | 内存中保留的对话轮数 |
| `max_sessions` | 1000 | `SessionManager` | 内存中最多维护的活跃会话数 |
| `session_timeout` | 3600s | `SessionManager` | 会话非活动过期时间 |
| `Compact Threshold` | 220 | `Session` | 触发 Redis 列表压缩的消息条数阈值 |

---

## 5. 异常处理

* **Redis 连接失败**：系统会记录错误日志，但仍会尝试依赖内存完成当前对话。
* **数据库回滚**：在 `SessionManager` 创建新用户或会话失败时，会自动执行 `db.rollback()` 确保事务一致性。