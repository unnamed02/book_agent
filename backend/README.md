# 图书推荐智能体

基于 LangChain 的简单图书推荐智能体 demo。

## 安装

```bash
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入你的 OpenAI API Key

```bash
cp .env.example .env
```

## 运行

```bash
python book_agent.py
```

## 功能

- 根据类型推荐图书（科幻、悬疑、文学、历史）
- 查询可用的图书类型
- 智能理解用户需求并调用相应工具
