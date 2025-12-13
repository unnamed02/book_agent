# 图书推荐助手 - 部署检查清单

使用此清单确保部署过程顺利完成。

## 📋 部署前检查

### 系统环境
- [ ] Python 3.10+ 已安装 (`python --version`)
- [ ] Node.js 18+ 已安装 (`node --version`)
- [ ] npm 已安装 (`npm --version`)
- [ ] Git 已安装（如需版本控制）

### 必需配置
- [ ] 获取了 OpenAI API Key
- [ ] （可选）获取了豆瓣 API Key
- [ ] （生产环境）准备了数据库（PostgreSQL 推荐）

## 🚀 开发环境部署步骤

### 1. 项目准备
- [ ] 项目代码已下载/克隆
- [ ] 进入项目目录

### 2. 后端配置
- [ ] 进入 `backend/` 目录
- [ ] 创建 Python 虚拟环境 (`python -m venv venv`)
- [ ] 激活虚拟环境
- [ ] 安装依赖 (`pip install -r requirements.txt`)
- [ ] 复制 `.env.example` 为 `.env`
- [ ] 编辑 `.env` 文件，设置 `OPENAI_API_KEY`
- [ ] 验证数据库路径 (`python verify_db_path.py`)

### 3. 前端配置
- [ ] 进入 `frontend/` 目录
- [ ] 安装依赖 (`npm install`)

### 4. 启动服务
- [ ] 启动后端服务 (端口 8000)
- [ ] 启动前端服务 (端口 5173)
- [ ] 访问 http://localhost:8000/docs 验证后端
- [ ] 访问 http://localhost:5173 验证前端

### 5. 功能测试
- [ ] 在前端输入测试查询（如"推荐几本 Python 的书"）
- [ ] 验证流式响应正常显示
- [ ] 验证书籍详情正常加载
- [ ] 检查数据库是否正常保存推荐记录 (`python query_recommendations.py stats`)

## 🏭 生产环境部署步骤

### 1. 服务器准备
- [ ] 服务器已配置（云服务器/VPS）
- [ ] 域名已解析（如需要）
- [ ] 防火墙规则已配置（开放必要端口）
- [ ] SSL 证书已准备（推荐使用 Let's Encrypt）

### 2. 数据库配置
- [ ] PostgreSQL 已安装并运行
- [ ] 创建数据库用户和数据库
- [ ] 配置数据库连接字符串
- [ ] 测试数据库连接

### 3. 后端部署
- [ ] 代码已上传到服务器
- [ ] Python 虚拟环境已创建
- [ ] 依赖已安装
- [ ] `.env.production` 已配置
- [ ] 数据库已初始化
- [ ] 进程管理器已配置（systemd/PM2）
- [ ] 后端服务已启动并设置自动重启
- [ ] 日志已配置

### 4. 前端部署
- [ ] 前端代码已构建 (`npm run build`)
- [ ] 构建产物已上传到服务器
- [ ] Nginx/Apache 已配置
- [ ] 静态文件路径已正确配置
- [ ] API 反向代理已配置

### 5. Nginx 配置
- [ ] 已配置虚拟主机
- [ ] API 反向代理已配置
- [ ] 静态文件服务已配置
- [ ] HTTPS 已启用
- [ ] Gzip 压缩已启用
- [ ] 安全头已配置

### 6. 安全配置
- [ ] `.env` 文件权限已限制 (chmod 600)
- [ ] 数据库密码已使用强密码
- [ ] SESSION_SECRET_KEY 已生成随机值
- [ ] ALLOWED_ORIGINS 已正确配置
- [ ] 防火墙规则已配置（仅开放必要端口）
- [ ] SSH 密钥登录已配置（禁用密码登录）

### 7. 监控和备份
- [ ] 数据库备份计划已配置
- [ ] 日志轮转已配置
- [ ] 磁盘空间监控已配置
- [ ] 错误告警已配置（可选：Sentry）
- [ ] 性能监控已配置（可选）

## ✅ 部署后验证

### 功能验证
- [ ] 前端页面可正常访问
- [ ] API 接口响应正常
- [ ] 用户可以发送消息
- [ ] 书籍推荐功能正常
- [ ] 流式响应正常显示
- [ ] 书籍详情正常加载
- [ ] 新会话功能正常
- [ ] 会话保持功能正常

### 性能验证
- [ ] 页面加载速度 < 3秒
- [ ] API 响应时间 < 1秒（首次请求）
- [ ] 流式响应延迟 < 500ms
- [ ] 并发用户测试通过

### 安全验证
- [ ] HTTPS 证书有效
- [ ] API Key 未泄露
- [ ] 数据库访问受限
- [ ] CORS 配置正确
- [ ] SQL 注入防护有效
- [ ] XSS 防护有效

### 数据验证
- [ ] 推荐记录正常保存
- [ ] 用户偏好正常更新
- [ ] 向量数据库正常工作
- [ ] 会话数据正常保存

## 🔧 快捷命令

### 启动服务
```bash
# 开发环境 - 一键启动
./start.sh              # Linux/macOS
start.bat               # Windows

# 生产环境
systemctl start book-agent
# 或
pm2 start book-agent-backend
```

### 停止服务
```bash
./stop.sh               # Linux/macOS
# Windows: 关闭命令窗口或 Ctrl+C

systemctl stop book-agent
# 或
pm2 stop book-agent-backend
```

### 查看日志
```bash
# 开发环境
tail -f logs/backend.log
tail -f logs/frontend.log

# 生产环境
journalctl -u book-agent -f
# 或
pm2 logs book-agent-backend
```

### 数据库操作
```bash
cd backend
python query_recommendations.py stats          # 查看统计
python query_recommendations.py users          # 列出用户
python query_recommendations.py profile <id>   # 查看用户画像
```

### 备份
```bash
# 备份 SQLite 数据库
cp backend/book_agent.db backend/book_agent.db.backup

# 备份 PostgreSQL
pg_dump -U bookagent_user bookagent > backup_$(date +%Y%m%d).sql
```

## 📞 故障排查

### 问题：服务无法启动
1. 检查端口是否被占用 (`lsof -i:8000`)
2. 检查依赖是否完整安装
3. 查看日志文件获取错误信息
4. 验证配置文件格式正确

### 问题：API 调用失败
1. 检查 OPENAI_API_KEY 是否有效
2. 检查 API 配额是否充足
3. 检查网络连接（国内可能需要代理）
4. 查看后端日志获取详细错误

### 问题：数据库连接失败
1. 检查数据库服务是否运行
2. 验证数据库连接字符串
3. 检查数据库用户权限
4. 验证防火墙规则

### 问题：前端无法连接后端
1. 检查 CORS 配置
2. 验证 API 地址配置
3. 检查防火墙规则
4. 验证反向代理配置

## 📚 参考文档

- [DEPLOYMENT.md](DEPLOYMENT.md) - 详细部署指南
- [QUICKSTART.md](QUICKSTART.md) - 快速开始指南
- [ENV_SETUP.md](ENV_SETUP.md) - 环境配置说明
- [README.md](README.md) - 项目说明

---

**部署完成后请保存此清单作为参考**

最后更新：2025-12-10
