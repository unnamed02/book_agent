# 📚 AI图书推荐助手

基于 React + FastAPI + LangChain 的智能图书推荐系统

## 功能特点

- 智能图书推荐
- 自动查找电子资源
- 现代化聊天界面
- Markdown 格式展示

## 在线试用

🎯 **[立即试用](http://101.37.238.186:5174/)**

快速体验系统功能，无需安装！支持：
- ✨ 智能图书推荐
- 💬 RAG 客服问答
- 🎯 个性化推荐
- 📚 多源信息查询

## 技术栈

### 前端
- React 19
- Ant Design 6
- Tailwind CSS 4
- Vite

### 后端
- FastAPI
- LangChain
- OpenAI API (DeepSeek)

## 安装运行

### 1. 后端设置

```bash
cd backend
pip install fastapi uvicorn
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

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=your_base_url
```
