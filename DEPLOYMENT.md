# 图书推荐助手 - 部署指南

## 系统要求

### 硬件要求
- CPU: 2核心及以上
- 内存: 4GB 及以上（推荐 8GB）
- 磁盘: 10GB 可用空间

### 软件要求
- **Python**: 3.10 或更高版本
- **Node.js**: 18.x 或更高版本
- **npm**: 9.x 或更高版本
- **操作系统**: Windows 10/11, Linux, macOS

## 快速部署步骤

### 1. 克隆或解压项目

如果从 Git 克隆：
```bash
git clone <repository-url>
cd book_agent
```

如果已经有项目文件，直接进入项目目录：
```bash
cd d:\work2\book_agent
```

### 2. 后端部署

#### 2.1 创建 Python 虚拟环境

**Windows**:
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
```

**Linux/macOS**:
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
```

#### 2.2 安装 Python 依赖

```bash
pip install -r requirements.txt
```

#### 2.3 配置环境变量

复制环境变量模板：
```bash
copy .env.example .env   # Windows
cp .env.example .env     # Linux/macOS
```

编辑 `.env` 文件，配置以下必需项：

```env
# OpenAI API 配置（必需）
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_API_BASE=https://api.openai.com/v1

# 数据库配置（可选，默认使用 SQLite）
# DATABASE_URL=sqlite+aiosqlite:///D:/work2/book_agent/backend/book_agent.db

# 如果使用 PostgreSQL（生产环境推荐）
# DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/bookagent
```

**重要说明**：
- `OPENAI_API_KEY` 是必需的，请从 OpenAI 官网获取
- 默认使用 SQLite 数据库，数据文件位于 `backend/book_agent.db`
- 生产环境建议使用 PostgreSQL 数据库

#### 2.4 初始化数据库

数据库会在首次启动时自动初始化。如需手动初始化：

```bash
python init_db.py
```

验证数据库：
```bash
python verify_db_path.py
```

#### 2.5 启动后端服务

**开发模式**（带热重载）:
```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

**生产模式**:
```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
```

后端服务将在 `http://localhost:8000` 启动

### 3. 前端部署

打开新的终端窗口：

#### 3.1 安装前端依赖

```bash
cd frontend
npm install
```

#### 3.2 配置 API 地址（可选）

如果后端不在 `localhost:8000`，需要修改 `src/App.jsx` 中的 API 地址：

```javascript
// 第 58 行
const response = await fetch('http://your-backend-host:8000/chat/stream', {
```

#### 3.3 启动前端开发服务器

```bash
npm run dev
```

前端将在 `http://localhost:5173` 启动（默认端口）

#### 3.4 构建生产版本（可选）

```bash
npm run build
```

构建产物位于 `dist/` 目录，可以使用任何静态文件服务器部署。

## 验证部署

### 1. 检查后端健康状态

访问：`http://localhost:8000/docs`

应该能看到 FastAPI 自动生成的 API 文档。

### 2. 检查前端

访问：`http://localhost:5173`

应该能看到图书推荐助手的界面。

### 3. 测试功能

在前端输入：`推荐几本 Python 编程的书`

应该能看到：
1. 立即显示简短回应和书单
2. 显示"正在为您查询这些书籍的详细信息..."
3. 逐本显示详细书籍信息

## 生产环境部署建议

### 1. 使用进程管理器

**使用 systemd（Linux）**:

创建 `/etc/systemd/system/book-agent.service`：
```ini
[Unit]
Description=Book Agent Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/book_agent/backend
Environment="PATH=/path/to/book_agent/backend/venv/bin"
ExecStart=/path/to/book_agent/backend/venv/bin/uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl enable book-agent
sudo systemctl start book-agent
```

**使用 PM2（跨平台）**:
```bash
# 安装 PM2
npm install -g pm2

# 启动后端
pm2 start "uvicorn api:app --host 0.0.0.0 --port 8000 --workers 4" --name book-agent-backend

# 启动前端（开发服务器）
pm2 start "npm run dev" --name book-agent-frontend --cwd /path/to/frontend
```

### 2. 使用 Nginx 反向代理

安装 Nginx 后，配置 `/etc/nginx/sites-available/book-agent`：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    location / {
        root /path/to/book_agent/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

启用配置：
```bash
sudo ln -s /etc/nginx/sites-available/book-agent /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. 配置 HTTPS（推荐）

使用 Let's Encrypt 免费证书：
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 4. 数据库迁移到 PostgreSQL

```bash
# 安装 PostgreSQL
sudo apt install postgresql postgresql-contrib

# 创建数据库和用户
sudo -u postgres psql
CREATE DATABASE bookagent;
CREATE USER bookagent_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE bookagent TO bookagent_user;
\q

# 更新 .env 文件
DATABASE_URL=postgresql+asyncpg://bookagent_user:your_secure_password@localhost:5432/bookagent
```

## 常见问题排查

### 问题 1: 后端启动失败，提示 "No module named 'xxx'"

**解决方案**：
```bash
# 确保在虚拟环境中
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows

# 重新安装依赖
pip install -r requirements.txt
```

### 问题 2: 前端连接后端失败，提示 CORS 错误

**解决方案**：检查 `backend/api.py` 的 CORS 配置：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://your-frontend-domain"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 问题 3: 数据库文件找不到

**解决方案**：
```bash
cd backend
python verify_db_path.py
```

如果路径不正确，在 `.env` 中显式设置：
```env
DATABASE_URL=sqlite+aiosqlite:///D:/work2/book_agent/backend/book_agent.db
```

### 问题 4: OpenAI API 调用失败

**检查项**：
1. API Key 是否正确设置在 `.env` 文件中
2. API Base URL 是否正确（国内用户可能需要代理）
3. 账户是否有余额

### 问题 5: 流式响应中断或不显示

**解决方案**：
1. 检查浏览器控制台是否有 JavaScript 错误
2. 确认后端返回的 SSE 格式正确
3. 检查网络代理或防火墙设置

## 监控和维护

### 查看推荐历史

```bash
cd backend
python query_recommendations.py stats      # 查看统计
python query_recommendations.py recent 7   # 查看最近7天记录
python query_recommendations.py users      # 列出所有用户
```

### 查看用户画像

```bash
python query_recommendations.py profile <user_id>
```

### 数据库备份

**SQLite**:
```bash
cp backend/book_agent.db backend/book_agent.db.backup
```

**PostgreSQL**:
```bash
pg_dump -U bookagent_user bookagent > backup.sql
```

### 日志管理

后端日志默认输出到控制台。生产环境建议配置日志文件：

修改 `backend/api.py`：
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
```

## 性能优化建议

1. **使用 Redis 缓存**：缓存书籍详情和推荐结果
2. **数据库索引**：为常用查询字段添加索引
3. **CDN 加速**：将前端静态资源部署到 CDN
4. **负载均衡**：使用多个 worker 进程和负载均衡器
5. **向量数据库优化**：定期清理 Chroma 数据库

## 安全建议

1. **不要将 `.env` 文件提交到 Git**：已在 `.gitignore` 中配置
2. **使用强密码**：数据库密码、API Key 等应使用强密码
3. **定期更新依赖**：`pip list --outdated` 检查过期包
4. **启用 HTTPS**：生产环境必须使用 HTTPS
5. **限制 API 访问**：配置速率限制和访问控制

## 升级指南

### 更新后端代码

```bash
cd backend
git pull  # 如果使用 Git
pip install -r requirements.txt --upgrade
```

### 更新前端代码

```bash
cd frontend
git pull
npm install
npm run build
```

## 支持与反馈

如遇到问题或有改进建议，请通过以下方式联系：
- GitHub Issues
- 邮件联系
- 项目文档

---

**版本**: 1.0
**最后更新**: 2025-12-10
