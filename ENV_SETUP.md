# 图书推荐系统 - 环境配置指南

## 快速开始

### 1. 配置环境变量

复制环境变量模板文件：

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件，填入你的实际配置：

```bash
# 必须配置的项目
OPENAI_API_KEY=sk-your-actual-api-key
DOUBAN_API_KEY=your-douban-api-key
SESSION_SECRET_KEY=your-random-secret-key  # 可以用: openssl rand -hex 32 生成
```

### 2. 安装依赖

**后端:**
```bash
cd backend
pip install -r requirements.txt
```

**前端:**
```bash
cd frontend
npm install
```

### 3. 运行服务

**后端:**
```bash
cd backend
uvicorn api:app --reload --port 8000
```

**前端:**
```bash
cd frontend
npm run dev
```

## 安全注意事项

### ⚠️ 重要提醒

1. **永远不要提交 `.env` 文件到 Git**
   - `.env` 已经在 `.gitignore` 中
   - 只提交 `.env.example` 作为模板

2. **保护你的 API 密钥**
   - 不要在代码中硬编码密钥
   - 不要在日志中打印密钥
   - 定期轮换密钥

3. **使用强随机密钥**
   ```bash
   # 生成安全的 SESSION_SECRET_KEY
   openssl rand -hex 32
   ```

## Git 工作流

### 首次提交前的检查

```bash
# 确认 .env 文件不在追踪列表中
git status

# 应该看到 .env 被忽略，只显示 .env.example
```

### 提交代码

```bash
# 添加所有文件（.env 会被自动忽略）
git add .

# 提交
git commit -m "feat: 初始化项目结构"

# 推送到远程仓库
git push origin main
```

## 环境变量说明

| 变量名 | 说明 | 必需 | 默认值 |
|-------|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | ✅ | - |
| `OPENAI_API_BASE` | API Base URL | ❌ | https://api.openai.com/v1 |
| `DOUBAN_API_KEY` | 豆瓣 API 密钥 | ✅ | - |
| `SESSION_SECRET_KEY` | 会话加密密钥 | ✅ | - |
| `ALLOWED_ORIGINS` | CORS 允许的源 | ❌ | http://localhost:5173 |
| `REDIS_URL` | Redis 连接 URL | ❌ | redis://localhost:6379 |
| `DATABASE_URL` | 数据库连接 URL | ❌ | - |
| `MAX_CONCURRENT_REQUESTS` | 最大并发请求数 | ❌ | 50 |
| `MAX_LLM_CONCURRENT` | LLM 最大并发 | ❌ | 10 |
| `MAX_LLM_QPS` | LLM QPS 限制 | ❌ | 5 |
| `MAX_MEMORY_PERCENT` | 内存使用上限(%) | ❌ | 80.0 |
| `ENV` | 运行环境 | ❌ | development |
| `LOG_LEVEL` | 日志级别 | ❌ | INFO |

## 常见问题

### Q: 忘记添加 .gitignore 就提交了 .env 怎么办？

```bash
# 从 Git 历史中删除敏感文件
git rm --cached backend/.env
git commit -m "fix: 移除敏感配置文件"

# 然后立即轮换所有暴露的密钥！
```

### Q: 如何在不同环境使用不同配置？

创建多个环境文件：
- `.env.development` - 开发环境
- `.env.staging` - 测试环境
- `.env.production` - 生产环境

然后在启动时指定：
```bash
ENV_FILE=.env.production uvicorn api:app
```

### Q: 团队协作时如何同步配置？

1. 更新 `.env.example` 添加新的配置项
2. 提交 `.env.example` 到 Git
3. 团队成员拉取后手动更新自己的 `.env`


## 技术支持

如有问题，请查看项目文档或提交 Issue。
