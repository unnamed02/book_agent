# 📚 AI图书推荐助手

基于 React + FastAPI + LangChain 的智能图书推荐系统

## 功能演示

[![功能演示](https://img.shields.io/badge/B站-功能演示-ff69b4)](https://www.bilibili.com/video/BV1bSwizkEdS/?spm_id_from=333.1365.list.card_archive.click&vd_source=531309240069252bb300dc8ae876c5b3)

## 功能特点

### 核心功能
- **智能图书推荐**：基于 LangGraph 工作流，自动理解用户需求并推荐相关书籍
- **RAG 智能客服**：基于知识库的问答系统，自动处理系统使用、功能咨询等问题
- **个性化学习**：记住用户阅读偏好，避免重复推荐
- **多源信息整合**：提供馆藏信息、电子资源、购买链接

### 交互体验
- 现代化聊天界面
- 流式响应，实时反馈
- Markdown 格式展示
- 智能澄清问题引导

## 技术栈

### 前端
- React 19
- Ant Design 6
- Tailwind CSS 4
- Vite

### 后端
- **FastAPI**：高性能异步 Web 框架
- **LangChain & LangGraph**：智能工作流编排
- **OpenAI API**：大语言模型（支持 DeepSeek、GPT 等）
- **Milvus Lite**：向量数据库，支持记忆存储和 RAG 检索
- **SQLAlchemy**：数据持久化（用户偏好、推荐历史）

## 安装运行

### 1. 后端设置

```bash
cd backend

# 安装依赖
pip install fastapi uvicorn langchain langchain-openai langchain-milvus sqlalchemy aiosqlite

# 初始化知识库（首次运行）
python init_knowledge_base.py

# 启动服务
uvicorn api:app --reload --port 8000
```

### 2. 前端设置

```bash
cd frontend
npm install
npm run dev
```

### 3. 访问应用

打开浏览器访问: http://localhost:5173

## 环境变量

在 `backend/.env` 文件中配置:

```env
# OpenAI API 配置（支持 DeepSeek 等兼容服务）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url

# 数据库配置（可选，默认使用 SQLite）
DATABASE_URL=sqlite+aiosqlite:///./book_agent.db

# Milvus 配置（可选，默认使用 Milvus Lite）
MILVUS_URI=./milvus_memory.db
MILVUS_KB_URI=./milvus_kb.db
```

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

### 3. 个性化推荐
- **用户画像**：自动学习用户阅读偏好
- **记忆系统**：记住历史推荐，避免重复
- **向量检索**：基于语义相似度匹配相关书籍

### 4. 多源信息整合
每本推荐书籍都包含：
- 📊 豆瓣评分和详细简介
- 📍 图书馆馆藏信息（索书号、位置、可借状态）
- 📥 电子资源链接（PDF、EPUB 等）
- 🛒 购买链接（当当、京东等电商平台）

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
├── backend/
│   ├── api.py                    # FastAPI 主应用
│   ├── graph_workflow.py         # LangGraph 工作流
│   ├── knowledge_base_tool.py    # RAG 客服系统
│   ├── init_knowledge_base.py    # 知识库初始化
│   ├── memory_manager.py         # 用户记忆管理
│   ├── conversation_manager.py   # 对话管理
│   ├── session.py                # 会话管理
│   ├── models.py                 # 数据模型
│   ├── douban_tool.py            # 豆瓣 API
│   ├── resource_tool.py          # 电子资源搜索
│   ├── shop_tool.py              # 购买链接
│   └── library_tool.py           # 馆藏查询
└── frontend/
    ├── src/
    │   ├── App.tsx               # 主组件
    │   └── ...
    └── ...
```

## 技术亮点

1. **LangGraph 工作流编排**：使用状态图实现复杂的推荐流程
2. **RAG 增强客服**：向量检索 + LLM 生成，提供准确的客服回答
3. **流式响应**：实时反馈，提升用户体验
4. **向量数据库**：Milvus Lite 支持记忆存储和语义检索
5. **异步架构**：FastAPI + async/await 实现高性能


## 许可证

MIT License
