# 图书推荐助手 - 快速开始指南

## 最简单的启动方式

### Windows 用户

1. **双击运行** `start.bat`
   - 首次运行会自动安装所有依赖
   - 会自动打开浏览器访问应用
   - 需要在首次运行时配置 `.env` 文件中的 API Key

2. **或者分别启动**：
   - 双击 `start_backend.bat` 启动后端
   - 双击 `start_frontend.bat` 启动前端

### Linux/macOS 用户

1. **运行一键启动脚本**：
```bash
chmod +x start.sh
./start.sh
```

2. **停止服务**：
```bash
./stop.sh
```

3. **或者分别启动**：
```bash
chmod +x start_backend.sh start_frontend.sh
./start_backend.sh    # 在一个终端启动后端
./start_frontend.sh   # 在另一个终端启动前端
```

## 首次运行前的准备

### 1. 获取 OpenAI API Key

访问 https://platform.openai.com/api-keys 获取 API Key

### 2. 配置环境变量

编辑 `backend/.env` 文件（首次运行时会自动创建）：

```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### 3. 安装必要软件

- **Python 3.10+**: https://www.python.org/downloads/
- **Node.js 18+**: https://nodejs.org/

## 访问应用

启动后，在浏览器中访问：
- **前端界面**: http://localhost:5173
- **后端 API 文档**: http://localhost:8000/docs

## 使用示例

在聊天框中输入以下内容测试：

```
推荐几本 Python 编程的书
我想学习机器学习
找一些科幻小说
```

## 常见问题

### 问题：后端启动失败

**解决方案**：
1. 检查是否已安装 Python 3.10+
2. 确认 `.env` 文件中的 `OPENAI_API_KEY` 已正确配置
3. 查看终端错误信息

### 问题：前端无法连接后端

**解决方案**：
1. 确保后端服务已启动（访问 http://localhost:8000/docs 验证）
2. 检查防火墙设置
3. 确认端口 8000 和 5173 未被占用

### 问题：依赖安装失败

**Windows**：以管理员身份运行命令提示符
**Linux/macOS**：使用 `sudo` 或检查权限

## 进阶功能

### 查看推荐历史

```bash
cd backend
python query_recommendations.py stats      # 查看统计
python query_recommendations.py users      # 列出所有用户
```

### 查看用户画像

```bash
python query_recommendations.py profile <user_id>
```

### 数据库管理

数据库文件位于：`backend/book_agent.db`

备份数据库：
```bash
copy backend\book_agent.db backend\book_agent.db.backup  # Windows
cp backend/book_agent.db backend/book_agent.db.backup    # Linux/macOS
```

## 获取帮助

详细部署说明请参考：[DEPLOYMENT.md](DEPLOYMENT.md)

---

**祝使用愉快！**
