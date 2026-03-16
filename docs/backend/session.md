# 会话管理系统

## 概述

Book Agent 采用三层会话存储架构，在性能和可靠性之间取得平衡：

1. **LRU 内存缓存**: 快速访问活跃会话
2. **Redis 缓存**: 高性能持久化存储对话历史
3. **PostgreSQL**: 长期数据库持久化

这种设计为活跃会话提供 O(1) 的访问速度，同时保证数据的持久性。

---

## 架构设计

### 三层存储流程

```
用户请求
    |
    v
[LRU 内存缓存] --命中--> 返回会话 (1微秒)
    |
    +--未命中
    |
    v
[Redis 缓存] --命中--> 加载到内存 (1毫秒)
    |
    +--未命中
    |
    v
[PostgreSQL] --命中--> 从数据库恢复 (10毫秒)
    |
    +--未命中
    |
    v
创建新会话
```

### 各层详细说明

| 层级 | 技术 | 延迟 | 用途 |
|------|------|------|------|
| L1 | OrderedDict (内存) | ~1微秒 | 活跃会话快速访问 |
| L2 | Redis | ~1毫秒 | 对话历史和元数据存储 |
| L3 | PostgreSQL | ~10毫秒 | 长期存储和数据恢复 |

---

## 会话生命周期

### 1. 创建新会话

```
用户开始聊天
    |
    v
生成 session_id (UUID)
    |
    v
在 PostgreSQL 创建 User 记录
    |
    v
在 PostgreSQL 创建 UserSession 记录
    |
    v
添加到 LRU 内存缓存
    |
    v
返回 Session 实例
```

### 2. 活跃会话使用

```
用户发送消息
    |
    v
SessionManager.get_or_create_session(session_id)
    |
    v
检查 LRU 缓存 --> 命中！
    |
    v
更新访问时间
    |
    v
返回会话 (瞬间完成)
```

### 3. 会话恢复

```
用户在另一个标签页打开旧会话
    |
    v
会话不在 LRU 缓存中
    |
    v
检查 PostgreSQL 数据库 --> 找到！
    |
    v
从 Redis 加载对话历史
    |
    v
创建 Session 实例
    |
    v
添加到 LRU 缓存
    |
    v
返回会话
```

### 4. 会话过期

```
会话闲置 1 小时（默认）
    |
    v
_cleanup_expired_sessions() 执行
    |
    v
从 LRU 缓存移除
    |
    v
数据保留在 Redis 和 PostgreSQL
```

---

## Redis 数据结构

### 对话历史列表

```
Key: conversation:{session_id}
Type: List

示例：
[
  {"role": "user", "content": "推荐 Python 的书", "timestamp": "..."},
  {"role": "assistant", "content": "以下是我的推荐...", "timestamp": "..."},
  ...
]
```

**用途**: 存储单个会话的所有对话消息

### 合并归档队列

```
Key: merge_archive_list
Type: Set

用途: 用户创建新会话时，将旧会话加入合并队列

示例值:
conversation:session-old-1
conversation:session-old-2
conversation:session-old-3
```

**用途**: 后台任务定期合并旧会话数据到用户总对话记录

---

## 数据库模型

### User 表（用户表）

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  user_id VARCHAR UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

| 字段 | 说明 |
|------|------|
| id | 主键 |
| user_id | 用户唯一标识 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### UserSession 表（用户会话表）

```sql
CREATE TABLE user_sessions (
  id INTEGER PRIMARY KEY,
  user_id VARCHAR NOT NULL FOREIGN KEY REFERENCES users(user_id),
  session_id VARCHAR UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  last_active_at TIMESTAMP DEFAULT NOW()
);
```

| 字段 | 说明 |
|------|------|
| id | 主键 |
| user_id | 用户 ID（外键） |
| session_id | 会话唯一标识 |
| created_at | 创建时间 |
| last_active_at | 最后活跃时间 |

---

## 配置说明

### SessionManager 初始化

```python
from session.session_manager import SessionManager
import redis.asyncio as redis

# 创建 Redis 客户端
redis_client = await redis.from_url("redis://localhost:6379")

# 创建会话管理器
session_manager = SessionManager(
    session_timeout=3600,      # 1小时（秒）
    max_sessions=1000,         # LRU 缓存最大会话数
    redis_client=redis_client
)
```

### 环境变量配置

```env
# Redis 连接
REDIS_URL=redis://localhost:6379

# 数据库连接
DATABASE_URL=postgresql://user:password@localhost/book_agent

# 会话配置
SESSION_TIMEOUT=3600
MAX_SESSIONS=1000
```

---

## 性能特征

### 各层访问时间

- **L1 (LRU 缓存)**: < 1 微秒
- **L2 (Redis)**: < 1 毫秒
- **L3 (PostgreSQL)**: < 10 毫秒

### 缓存命中率

- **LRU 缓存命中率**: 80-90% (活跃用户)
- **Redis 命中率**: 95%+ (如果可用)
- **数据库可用率**: 100% (总是可用)

---

## 故障处理

### Redis 不可用

系统自动降级：

```
用户请求
    |
    v
LRU 缓存 --命中--> 正常工作
    |
    +--未命中
    |
    v
Redis 不可用 --> 跳过
    |
    v
从 PostgreSQL 加载会话
```

影响: 首次加载较慢，但系统仍可正常运行

### PostgreSQL 不可用

系统部分功能不可用：

```
用户请求
    |
    v
LRU 缓存 --命中--> 正常工作
    |
    +--未命中
    |
    v
从 Redis 加载 (如果可用)
    |
    +--Redis 也不可用
    |
    v
创建新会话 (可能丢失历史数据)
```

影响: 新会话可以创建，但无法恢复旧会话

---

## 最佳实践

### 推荐做法

1. 使用异步驱动（asyncpg, redis.asyncio）
2. 定期监控缓存命中率
3. 实现数据库连接池
4. 定期备份 PostgreSQL 数据库
5. 配置 Redis 持久化

### 避免的做法

1. 不要绕过 SessionManager 直接访问会话
2. 不要手动删除 Redis 键
3. 不要在 SessionManager 外修改会话状态
4. 不要忽视缓存一致性

---

## 监控指标

### 关键指标

#### 1. 缓存命中率

```python
hit_rate = hits / (hits + misses) * 100
# 目标: > 80%
```

告警值: < 70% 时需要优化

#### 2. Redis 延迟

```python
redis_latency = end_time - start_time
# 目标: < 5ms
```

告警值: > 10ms 时需要检查

#### 3. LRU 缓存大小

```python
lru_size = len(session_manager.sessions)
# 告警: > max_sessions * 0.9
```

#### 4. 活跃会话数

```python
active = session_manager.get_session_count()
# 监控趋势变化
```

#### 5. 过期会话清理频率

```python
cleanup_frequency = expired_sessions_per_hour
# 监控清理是否正常工作
```

---

## 配置示例

### 开发环境配置

```python
SessionManager(
    session_timeout=1800,  # 30 分钟
    max_sessions=100,
    redis_client=None      # 开发可选
)
```

### 生产环境配置

```python
SessionManager(
    session_timeout=3600,  # 1 小时
    max_sessions=10000,
    redis_client=redis_client  # 必需
)
```

---

## 相关文件

- [SessionManager 源码](../../backend/session/session_manager.py)
- [Session 类](../../backend/session/session.py)
- [Compact 后台任务](../../backend/session/compact.py)

---

最后更新: 2026-03-16
