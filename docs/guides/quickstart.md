# 

30 

## 1  ()

###  1: 
```bash
cd book_agent/backend
cp .env.example .env
#  .env OPENAI_API_KEY
```

###  2: 
```bash
cd book_agent/backend

#  ()
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 
pip install -r requirements.txt

#  ()
python service/init_knowledge_base.py

# 
uvicorn api:app --reload --port 8000
```


```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

###  3: 
```bash
cd book_agent/frontend

# 
npm install

# 
npm run dev
```


```
Local:   http://localhost:5173
```

###  4: 
 **http://localhost:5173**

---

## 2 



###  1: 
```
 Python 
```
****:  Python 

###  2:  (RAG)
```

```
****: 

###  3: 
```

```
****: 

###  4: 
****

---

## 3 API 

### Swagger UI ()
 **http://localhost:8000/docs**

### 

#### 
```
POST /api/chat
```

- ****: `{"message": ""}`
- ****: Server-Sent Events (SSE) 

#### 
```
GET /api/sessions/{session_id}
POST /api/sessions
```


---

## 4 

### 
 `backend/service/knowledge_base_data.py`
```bash
python backend/service/init_knowledge_base.py
```

### 
 `backend/graph_workflow.py` LangGraph 

### 
 `frontend/src/App.tsx`  `frontend/src/index.css`

###  LLM 
 `backend/api.py`  (System Prompt)

---

## 5 

###  
```bash
#  .env  OPENAI_API_KEY
cat backend/.env | grep OPENAI_API_KEY

# 
pip install --upgrade -r requirements.txt
```

###  
```bash
# 
curl http://localhost:8000/health

#  CORS  (backend/.env)
ALLOWED_ORIGINS=http://localhost:5173
```

###  
- WeChat DevTools      ""
- 

###  LLM API 
```
Error: invalid_api_key / invalid_request_error
```
-  `OPENAI_API_KEY` 
-  `OPENAI_API_BASE`  (: https://api.openai.com/v1)
-  API 

###  
```bash
# 
python backend/service/init_knowledge_base.py

#  Milvus 
ls -la backend/milvus_kb.db
```

---

## 6  WeChat 

### 
1.  WeChat DevTools
2. ""
3.  `wechat` 
4.  AppID
5. ""

###  API 
 `wechat/miniprogram/utils/config.ts`:
```typescript
// 
export const API_BASE_URL = 'http://localhost:8000'

// 
export const API_BASE_URL = 'https://your-domain.com'
```

### 
- WeChat DevTools    
- "TLS  HTTPS "
- ""

---

## 7 



1. **[](../overview/architecture.md)** - 
2. **[](./setup.md)** - 
3. **[API ](../api/endpoints.md)** - 
4. **[](../backend/workflow.md)** - LangGraph 
5. **[](../frontend/architecture.md)** - React 

---

##  

- ****: 
- ****:  `backend/.env` `LOG_LEVEL=DEBUG`
- ****:  Postman  `/api/chat` 
- ****:  SQLite Browser  `backend/book_agent.db`

---

: 2026-03-16
