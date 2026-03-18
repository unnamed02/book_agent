---
home: true
heroImage: /logo.svg
heroImageDark: /logo-dark.svg
heroText: Book Agent
tagline: AI 智能推荐系统完整文档
actionText: 快速开始 →
actionLink: /guides/quickstart
features:
  - title: 快速开始
    details: 30分钟内快速启动完整系统
  - title: 系统架构
    details: 深入理解 Redis + PostgreSQL 三层存储架构
  - title: 完整 API 文档
    details: 10+ 个完整的 API 端点说明和代码示例
  - title: 详细技术文档
    details: LangGraph 工作流、会话管理等核心系统详解
  - title: 快速参考
    details: 命令速查表、环境变量、常见问题速查
  - title: 多平台支持
    details: 支持 Web、小程序、后端完整开发指南
---

欢迎

Book Agent 是一个 AI 驱动的智能书籍推荐系统，集成了三个客户端：

- React Web 应用 - 现代化网页聊天界面
- WeChat 小程序 - 微信原生小程序
- FastAPI 后端 - LangGraph 工作流引擎

---

快速导航

后端开发
- [环境配置](/guides/setup) - 完整的开发环境设置
- [会话管理系统](/backend/session) - Redis + PostgreSQL 三层架构
- [LangGraph 工作流](/backend/workflow) - 核心工作流详解
- [工作流节点](/backend/nodes/) - 8 个节点详细文档 (新增)
- [API 端点文档](/api/endpoints) - 10+ 完整 API 说明

前端开发
- [快速开始](/guides/quickstart) - 前端部分
- [API 文档](/api/endpoints) - 接口调用说明

小程序开发
- [环境配置](/guides/setup) - 小程序配置
- [API 文档](/api/endpoints) - 接口调用

系统设计
- [系统架构](/overview/architecture) - 完整系统架构
- [技术栈](/overview/tech-stack) - 技术选型说明
- [功能特性](/overview/features) - 完整功能列表

---

功能演示

<video width="100%" height="auto" controls style="border-radius: 8px; margin: 20px 0;">
  <source src="/video/2026-03-18 20-12-44.mp4" type="video/mp4">
  您的浏览器不支持视频播放
</video>

---

30秒快速开始

启动后端
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn api:app --reload --port 8000
```

启动前端
```bash
cd frontend
npm install
npm run dev
```

打开浏览器
访问 http://localhost:5173

---

项目统计

| 指标 | 数值 |
|------|------|
| 核心文档 | 20+ 个 |
| 工作流节点文档 | 8 个 |
| 代码示例 | 50+ 个 |
| 快速参考表 | 10+ 个 |
| 架构图 | 5+ 个 |
| API 端点 | 10+ 个 |

---

最新更新 (2026-03-16)

工作流节点文档 (新增)
- 8 个 LangGraph 节点的完整详解
- 意图识别、推荐、查找、信息、客服、默认等节点
- 每个节点包含工作流程、参数说明、错误处理
- 节点间数据流和状态转移详解

架构更新
- Redis 缓存：高性能对话历史存储
- PostgreSQL：长期数据持久化
- LRU 内存缓存：活跃会话快速访问
- 完整会话管理系统文档

文档改进
- 新增 15KB+ 会话管理详细文档
- 新增 20KB+ 工作流节点详细文档
- 环境配置指南更新
- Redis 安装说明（Windows/macOS/Linux）

---

相关链接

- [项目 GitHub](#)
- [问题反馈](#)
- [贡献指南](#)
- [LICENSE](#)

---

创建日期: 2026-03-16 | 更新日期: 2026-03-16 | 版本: 1.0.0
