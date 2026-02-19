# 图书推荐智能体

基于 LangChain 的图书推荐智能体

## 环境依赖

### 1. PostgreSQL

使用 Docker 启动 PostgreSQL：

```bash
docker run -d \
  --name my-alpine-pg \
  -e POSTGRES_PASSWORD=123456 \
  -p 5432:5432 \
  postgres:alpine
```

创建数据库：

```bash
docker exec my-alpine-pg psql -U postgres -c "CREATE DATABASE book_agent;"
```

### 2. Redis

使用 Docker 启动 Redis（带 AOF 持久化）：

```bash
docker run -d \
  --name redis-book-agent \
  -p 6379:6379 \
  -v redis_data:/data \
  --memory="512m" \
  --restart always \
  redis:8.2.4-alpine3.22 \
  redis-server \
    --appendonly yes \
    --appendfsync everysec \
    --maxmemory 400mb \
    --maxmemory-policy allkeys-lru
```

Redis 配置说明：
- `--appendonly yes`: 启用 AOF 持久化
- `--appendfsync everysec`: 每秒同步一次到磁盘
- `--maxmemory 400mb`: 最大内存限制 400MB
- `--maxmemory-policy allkeys-lru`: 内存满时使用 LRU 算法淘汰键
- `-v redis_data:/data`: 数据持久化到 Docker 卷
- `--memory="512m"`: Docker 容器内存限制 512MB
- `--restart always`: 容器自动重启

注意：AOF 重写由应用程序在每次 compact 任务后自动触发

## 安装

```bash
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入配置信息

```bash
cp .env.example .env
```

`.env` 配置示例：

```env
# OpenAI API 配置
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# 数据库配置
DATABASE_URL=postgresql+asyncpg://postgres:123456@localhost:5432/book_agent

# Redis 配置
REDIS_URL=redis://localhost:6379

# 豆瓣 API 配置
DOUBAN_API_KEY=your_douban_key

# 搜索 API 配置
TAVILY_API_KEY=your_tavily_key

# DEBUG 配置
DEBUG_MODE=true
```

## 运行

启动后端服务：

```bash
uvicorn api:app --reload --port 8000
```

## 功能

- 根据类型推荐图书（科幻、悬疑、文学、历史）
- 查询可用的图书类型
- 智能理解用户需求并调用相应工具
- Redis 会话持久化
- PostgreSQL 对话历史归档
- 自动 Compact 机制（超过150条消息自动归档）

## 数据持久化

### PostgreSQL 归档
- **触发条件**: 会话消息超过 150 条
- **执行频率**: 每 10 分钟检查一次
- **归档策略**: 保留最近 10 条消息在 Redis，其余归档到 PostgreSQL JSONB 字段
- **数据格式**: JSON 格式存储，支持查询和索引
