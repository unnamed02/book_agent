# 

## 

### 
- ****: Windows / macOS / Linux
- **Python**: 3.10+ ()
- **Node.js**: 18+ ()
- **Git**: 

### 
- **VSCode** + Python 
- **WeChat DevTools** ()
- **Postman**  **Thunder Client** (API )

---

## 

### 1. 
```bash
git clone <repository-url>
cd book_agent/backend
```

### 2. 
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python -m venv venv
source venv/bin/activate
```

### 3. 
```bash
pip install -r requirements.txt
```

### 4.  Redis ()

**Windows**:
```bash
#  Docker ()
docker run -d --name redis -p 6379:6379 redis:latest

#  Windows Subsystem for Linux (WSL)
#  WSL :
sudo apt-get install redis-server
```

**macOS**:
```bash
#  Homebrew
brew install redis

#  Redis
redis-server
```

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

#  Docker
docker run -d --name redis -p 6379:6379 redis:latest
```

 Redis:
```bash
redis-cli ping
# : PONG
```

### 5. 
```bash
# 
cp .env.example .env

#  .env 
```

#### 
```env
# OpenAI  API ()
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1
```

#### 
```env
#  ()
# 
DATABASE_URL=sqlite:///./book_agent.db

# 
DATABASE_URL=postgresql://user:password@localhost:5432/book_agent

# Redis  ()
REDIS_URL=redis://localhost:6379

# 
MILVUS_URI=http://localhost:19530
```

#### 
```env
# Douban API
DOUBAN_API_KEY=your-douban-key

# CORS 
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174

# 
LOG_LEVEL=INFO
ENV=development
```

### 6. 
```bash
python service/init_knowledge_base.py
```


### 7. 
```bash
uvicorn api:app --reload --port 8000
```

  `http://localhost:8000` 
 API  `http://localhost:8000/docs` (Swagger UI)

---

## 

### 1. 
```bash
cd book_agent/frontend
```

### 2. 
```bash
npm install
```

### 3.  API 
 `src/config.ts`  `.env.local`:
```typescript
// src/config.ts
export const API_BASE_URL = 'http://localhost:8000'
```


```env
VITE_API_BASE_URL=http://localhost:8000
```

### 4. 
```bash
npm run dev
```

  `http://localhost:5173` 

### 5.  ()
```bash
npm run build
npm run preview  # 
```

---

## 

### 1. 
```bash
cd book_agent/wechat
```

### 2. 
```bash
npm install
```

### 3.  API 
 `miniprogram/utils/config.ts`:
```typescript
export const API_BASE_URL = 'http://localhost:8000'
// 
export const API_BASE_URL = 'https://your-domain.com'
```

### 4.  WeChat DevTools 
-  WeChat DevTools
-  ""
-  `wechat` 
-  AppID
-  ""

### 5. 
 WeChat DevTools 
-  ""  ""
-  "TLS  HTTPS " ()
-  ""

---

## 

### 
```bash
#  API 
curl http://localhost:8000/docs

# 
curl http://localhost:8000/health
```

### 
 `http://localhost:5173`

### 
1.  http://localhost:8000
2.  http://localhost:5173
3. 
4. 
5. 

---

## 

### :  -  `.env` 
****:  `.env.example`  `.env`
```bash
cp backend/.env.example backend/.env
```

### :  `OPENAI_API_KEY`
****:  `.env`  API 

### : 
****:
1.  http://localhost:8000
2.  CORS 
3.  `ALLOWED_ORIGINS` 

### :  SSE 
****:
1.  ""
2. 

---

## 

:
- [](./quickstart.md) - 
- [](./project-structure.md) - 
- [](../guides/development.md) - 

: 2026-03-16
