# 🚀 试用发布部署指南

## 快速开始（5 分钟部署）

### 1. 环境准备

```bash
# 克隆代码
git clone <your-repo>
cd book_agent

# 创建日志目录
mkdir -p logs
```

### 2. 配置环境变量

```bash
cd backend
cp .env.example .env

# 编辑 .env 文件，填入真实配置
nano .env
```

**必须修改的配置：**
- `OPENAI_API_KEY` - LLM API 密钥
- `DASHSCOPE_API_KEY` - 阿里云 DashScope 密钥
- `DATABASE_URL` - 数据库连接（默认 SQLite 可直接使用）

### 3. 启动依赖服务（Docker）

```bash
# 在项目根目录执行
docker-compose up -d

# 等待服务启动（约 30 秒）
docker-compose ps
```

### 4. 初始化知识库

```bash
cd backend
python service/init_knowledge_base.py
```

### 5. 启动后端服务

#### 方案 A：PM2 部署（推荐生产环境）

```bash
# 安装 PM2
npm install -g pm2

# 部署
bash deploy_pm2.sh

# 查看状态
pm2 list
pm2 logs
```

#### 方案 B：直接启动（开发/测试）

```bash
cd backend
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. 健康检查

```bash
# 检查服务状态
curl http://localhost:8000/health

# 或使用检查脚本
python scripts/check_health.py --url http://localhost:8000

# 并发测试
python scripts/check_health.py -c 50
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `OPENAI_API_KEY` | ✅ | LLM API 密钥 |
| `DASHSCOPE_API_KEY` | ✅ | 阿里云 DashScope 密钥 |
| `DATABASE_URL` | - | 数据库 URL（默认 SQLite） |
| `REDIS_URL` | - | Redis 地址（默认 localhost） |
| `DEBUG_MODE` | - | 调试模式（生产设为 false） |
| `ALLOWED_ORIGINS` | - | CORS 白名单（生产必须设置） |

### 并发配置

当前配置支持 **100-200 并发**：

```javascript
// ecosystem.config.js
args: 'api:app --host 0.0.0.0 --port 8000 --workers 4'
```

如需提升并发：
1. 增加 workers 数量（建议 = CPU 核心数）
2. 调整 PostgreSQL 连接池大小
3. 使用独立 Milvus 服务替代 SQLite 模式

---

## 🔒 生产环境检查清单

- [ ] `.env` 文件已配置且未提交到 Git
- [ ] `DEBUG_MODE=false`
- [ ] `ALLOWED_ORIGINS` 已设置为具体域名
- [ ] 已配置 HTTPS 证书
- [ ] 小程序服务器域名白名单已添加
- [ ] 知识库已初始化
- [ ] PM2 已配置开机自启 (`pm2 startup`)

---

## 📊 监控与维护

### 查看日志

```bash
# PM2 日志
pm2 logs

# 查看特定进程
pm2 logs book-backend

# 清空日志
pm2 flush
```

### 重启服务

```bash
# 重启所有
pm2 restart all

# 重启后端
pm2 restart book-backend
```

### 性能监控

```bash
# PM2 监控面板
pm2 monit

# 查看详细信息
pm2 show book-backend
```

---

## 🐛 常见问题

### 1. 端口被占用

```bash
# 查找占用 8000 端口的进程
lsof -i :8000

# 终止进程
kill -9 <PID>
```

### 2. 数据库连接失败

```bash
# 检查 PostgreSQL 是否运行
docker-compose ps

# 查看 PostgreSQL 日志
docker-compose logs postgres
```

### 3. 内存不足

```bash
# 查看内存使用
free -h

# 调整 PM2 内存限制
# ecosystem.config.js 中修改 max_memory_restart
```

---

## 📞 获取帮助

- 查看详细文档：`docs/` 目录
- 检查健康状态：`curl /health`
- 查看日志：`pm2 logs`
