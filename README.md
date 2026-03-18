# 📚 AI图书推荐助手

基于 WeChat 小程序 + FastAPI + LangGraph 的智能图书推荐系统

> 前端：WeChat 小程序 | 后端：FastAPI + LangGraph | 数据库：Redis + PostgreSQL + Milvus

## 功能演示

<div style="text-align: center; margin: 30px 0;">
  <a href="https://www.bilibili.com/video/BV1bSwizkEdS/?spm_id_from=333.1365.list.card_archive.click&vd_source=531309240069252bb300dc8ae876c5b3">
    <img alt="B站功能演示" src="https://img.shields.io/badge/B站-功能演示-ff69b4?style=for-the-badge&logo=bilibili&logoColor=white&labelColor=ff69b4&color=ff69b4" width="200" height="50">
  </a>
</div>

## 功能特点

### 核心功能
- **智能图书推荐**：基于 LangGraph 工作流，自动理解用户需求并推荐相关书籍
- **RAG 智能客服**：基于知识库的问答系统，自动处理系统使用、功能咨询等问题
- **个性化学习**：记住用户阅读偏好，避免重复推荐
- **多源信息整合**：提供馆藏信息、电子资源、购买链接
- **图书荐购**：图书荐购、版本推荐

### 交互体验
- 现代化聊天界面
- 流式响应，实时反馈
- Markdown 格式展示
- 智能澄清问题引导

## 技术栈

### 前端（已停止维护 React 版本）
- **WeChat 小程序**：原生 WXML + TypeScript
- 自定义 Markdown 渲染组件
- SSE 流式响应支持

### 后端
- **FastAPI**：高性能异步 Web 框架
- **LangChain & LangGraph**：智能工作流编排
- **OpenAI API**：大语言模型（支持 DeepSeek、GPT 等）
- **SQLAlchemy**：ORM 框架

### 数据库（推荐 Docker 部署）
- **Redis**：会话缓存、对话历史存储
- **PostgreSQL**：用户数据、推荐历史持久化
- **Milvus**：向量数据库，支持记忆存储和 RAG 检索

## 快速开始

### 第一步：安装依赖服务

需要安装以下三个数据库服务。建议使用 Docker，但也可以本地安装。

#### 方案 A：Docker 安装（推荐）

```bash
# Redis（启用 AOF 和自动重写）
docker run -d --name book_agent_redis -p 6379:6379 redis:7-alpine \
  redis-server --appendonly yes --appendfsync everysec \
  --auto-aof-rewrite-percentage 100 --auto-aof-rewrite-min-size 268435456

# PostgreSQL
docker run -d --name book_agent_postgres \
  -e POSTGRES_USER=book_agent \
  -e POSTGRES_PASSWORD=book_agent_password \
  -e POSTGRES_DB=book_agent \
  -p 5432:5432 \
  -v postgres_data:/var/lib/postgresql/data \
  postgres:15-alpine

# Milvus
docker run -d --name book_agent_milvus \
  -p 19530:19530 \
  -p 9091:9091 \
  -e COMMON_STORAGETYPE=local \
  milvusdb/milvus:latest
```

#### 方案 B：本地安装

参考各服务官方文档：
- [Redis 安装](https://redis.io/docs/install/)
- [PostgreSQL 安装](https://www.postgresql.org/download/)
- [Milvus 安装](https://milvus.io/docs/install_standalone-docker.md)

### 第二步：后端设置

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制并编辑 .env 文件）
cp .env.example .env

# 初始化知识库（首次运行）
python service/init_knowledge_base.py

# 启动服务
uvicorn api:app --reload --port 8000
```

**环境变量配置** (`.env`)：
```env
# LLM 配置
OPENAI_API_KEY=your_api_key
OPENAI_API_BASE=https://api.openai.com/v1
DASHSCOPE_API_KEY=your_dashscope_key  # 必填，book_info以来通义联网搜索

# 数据库配置
DATABASE_URL=postgresql+asyncpg://book_agent:your_password@localhost:5432/book_agent
REDIS_URL=redis://localhost:6379/0
MILVUS_URI=http://localhost:19530

# 豆瓣 API 配置  
DOUBAN_API_KEY=your_douban_key

# CORS 配置
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5173


## 环境需求

- **Python**: 3.10+
- **Node.js**: 18+
- **Docker**: 最新版本
- **WeChat DevTools**: 用于小程序开发

## 数据库说明

### Redis
- 用途：会话缓存、对话历史、临时数据
- 端口：6379
- Docker 启动：已在 docker-compose 中配置

### PostgreSQL
- 用途：用户信息、推荐历史、会话记录持久化
- 端口：5432
- 用户名：book_agent
- Docker 启动：已在 docker-compose 中配置

### Milvus
- 用途：向量存储、RAG 知识库、用户记忆
- 端口：19530（grpc）、9091（http）
- 推荐：Docker 部署

## Redis 配置

启用 AOF 持久化和自动重写，确保数据安全性：

```bash
# redis.conf
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 268435456  # 256MB
```

**配置说明**：
- `appendonly yes`：启用 AOF 持久化，记录每个写入命令
- `appendfsync everysec`：每秒同步一次，平衡性能和安全性
- `auto-aof-rewrite-percentage 100`：当 AOF 文件大小增长 100% 时自动重写
- `auto-aof-rewrite-min-size 256MB`：AOF 文件至少达到 256MB 才触发重写

## 核心功能说明

### 1. 智能路由系统
系统会自动识别用户意图：
- **图书推荐**：直接推荐相关书籍
- **客服咨询**：使用 RAG 知识库回答系统相关问题
- **需求澄清**：当需求不明确时，主动提问引导用户

### 2. RAG 智能客服
基于向量数据库的知识库检索：
- 自动回答系统功能、使用方法等问题
- 提供参考来源和置信度
- 无法回答时，引导用户联系人工客服

知识库内容包括：
- 系统功能介绍
- 使用指南
- 常见问题 FAQ
- 推荐策略说明
- 数据来源说明


### 3. 多源信息整合
每本推荐书籍都包含：
- 📊 豆瓣评分和详细简介
- 📍 图书馆馆藏信息（索书号、位置、可借状态）
- 📥 电子资源链接（PDF、EPUB 等）
- 🛒 购买链接（当当、京东等电商平台）#现移除，后续有需要可以补充

## 使用示例

### 图书推荐
```
用户：推荐Python编程的书
系统：[推荐《Python编程：从入门到实践》等书籍，并提供详细信息]

用户：找红楼梦
系统：[返回《红楼梦》的馆藏、资源、购买链接等]
```

### 客服咨询
```
用户：这个系统有什么功能？
系统：[基于知识库回答系统功能]

用户：如何查看历史推荐？
系统：[提供详细的使用指南]
```

### 需求澄清
```
用户：推荐几本书
系统：我需要了解更多信息：
     1. 您想了解哪个领域？
     2. 是学习还是娱乐阅读？
     3. 有偏好的类型吗？
```

## 项目结构

```
book_agent/
├── backend/                         # FastAPI 后端
│   ├── api.py                       # 主应用、SSE 流式端点
│   ├── graph_workflow.py            # LangGraph 工作流
│   ├── service/
│   │   ├── knowledge_base_tool.py   # RAG 客服系统
│   │   ├── init_knowledge_base.py   # 知识库初始化
│   │   └── ...
│   ├── nodes/                       # 8 个工作流节点
│   │   ├── intent_recognition.py    # 意图识别
│   │   ├── find_book_node.py        # 查找书籍
│   │   ├── recommendation_node.py   # 书籍推荐
│   │   └── ...
│   ├── session/                     # Redis + PostgreSQL + LRU 三层会话管理
│   ├── tools/
│   │   ├── douban_tool.py           # 豆瓣数据源
│   │   ├── resource_tool.py         # 电子资源
│   │   ├── shop_tool.py             # 购买链接
│   │   └── library_tool.py          # 馆藏查询
│   ├── utils/
│   │   └── models.py                # SQLAlchemy 数据模型
│   ├── requirements.txt
│   └── .env.example
│
├── wechat/                          # WeChat 小程序（原生 WXML）
│   ├── miniprogram/
│   │   ├── pages/index/             # 聊天页面
│   │   ├── components/              # 自定义 Markdown 组件
│   │   ├── utils/api.ts             # API 通信
│   │   └── app.json
│   └── project.config.json
│
├── frontend/                        # React Web 版本（已停止维护）
│   └── ...
│
├── docs/                            # VuePress 2 文档
│   ├── backend/
│   │   ├── session.md               # 会话管理详解
│   │   ├── workflow.md              # 工作流说明
│   │   └── nodes/                   # 8 个节点详细文档
│   └── ...
│
├── README.md                        # 项目说明
├── LICENSE                          # GPLv3 许可证
└── CLAUDE.md                        # Claude Code 项目指南
```

## 技术亮点

1. **LangGraph 工作流**：8 个专用节点，自动意图识别和智能路由
2. **三层会话管理**：LRU 内存缓存 + Redis 高速缓存 + PostgreSQL 持久化
3. **RAG 增强客服**：向量检索 + LLM 生成，动态知识库
4. **SSE 流式响应**：真实时响应流，前端和小程序都支持
5. **微信小程序原生**：WXML 原生实现，自定义 Markdown 渲染
6. **Docker 一键部署**：Redis、PostgreSQL、Milvus 容器化
7. **异步高性能**：FastAPI + asyncio 处理并发请求


## 许可证

GPLv3 (General Public License v3.0)

本项目采用 GPLv3 许可证。根据 GPLv3，任何使用、修改或分发本项目代码的人必须：
- 保持相同的 GPLv3 许可证
- 公开源代码
- 保留原始版权声明

详见 [LICENSE](./LICENSE) 文件
