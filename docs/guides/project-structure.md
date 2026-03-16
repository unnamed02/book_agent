# 

Book Agent 

##  

```
book_agent/
 backend/                    #  (FastAPI)
    api.py                 # 
    graph_workflow.py       # LangGraph 
    graph_workflow_streaming.py  # 
    requirements.txt        # Python 
    .env.example           # 
   
    nodes/                 # LangGraph 
       intent_recognition_node.py
       book_info_node.py
       recommendation_node.py
       customer_service_node.py
       ...
   
    tools/                 # 
       douban_tool.py      # 
       library_tool.py     # 
       resource_tool.py    # 
       ...
   
    service/               # 
       knowledge_base_tool.py      # RAG 
       init_knowledge_base.py      # 
       knowledge_base_data.py      # 
   
    session/               # 
       session.py         # Session 
       session_manager.py # SessionManager 
       compact.py         # 
       ...
   
    utils/                 # 
       models.py          # 
       init_db.py         # 
       ...
   
    prompts/               # 
        system_prompts.py   # 

 frontend/                   # React 
    src/
       App.tsx            # 
       App.css            # 
       index.css          # CSS 
      
       components/        # React 
          ChatBox.tsx
          Message.tsx
          Sidebar.tsx
          ...
      
       pages/             # 
          Home.tsx
          ...
      
       utils/             # 
          api.ts         # API 
          config.ts      # 
          ...
      
       styles/            # 
           index.css
   
    index.html             # HTML 
    vite.config.ts         # Vite 
    package.json
    tsconfig.json

 wechat/                     # WeChat 
    miniprogram/
       pages/
          index/         # 
             index.wxml
             index.wxss
             index.ts
          ...
      
       components/        # 
          markdown-renderer/
             markdown-renderer.wxml
             markdown-renderer.wxss
             markdown-renderer.ts
             markdown-renderer.json
          ...
      
       utils/
          api.ts         # API 
          config.ts      # 
          storage.ts     # 
          ...
      
       app.ts            # 
   
    project.config.json    # 

 docs/                       #  Markdown 
    README.md
    guides/
    backend/
    api/
    overview/
    ...

 docs-vuepress/             # VuePress 2   
    .vuepress/
       config.ts          # VuePress 
       styles/            # 
    README.md              # 
    guides/
    backend/
    api/
    ...

 README.md                   #  README
 CLAUDE.md                   # Claude 
 DOCS_SETUP.md              # 
 README_DOCS.md             # 
 .gitignore
 ecosystem.config.js        # PM2 
```

##  

### Backend (`backend/`)
|  |  |
|------|------|
| `nodes/` | LangGraph  |
| `tools/` | API  |
| `service/` | RAG |
| `session/` | Redis + PostgreSQL |
| `utils/` |  |
| `prompts/` | LLM  |

### Frontend (`frontend/src/`)
|  |  |
|------|------|
| `components/` |  React  |
| `pages/` |  |
| `utils/` | API  |
| `styles/` |  |

### WeChat (`wechat/miniprogram/`)
|  |  |
|------|------|
| `pages/` | WXML + WXSS + TS |
| `components/` |  Markdown  |
| `utils/` | API |

### Docs (`docs/`  `docs-vuepress/`)
|  |  |
|------|------|
| `docs/` |  Markdown  |
| `docs-vuepress/` | VuePress 2  |

##  

```
User Request (Web/)
    
API Gateway (FastAPI)
    
LangGraph Workflow
     Intent Node
     Tools (Douban, Library, etc)
     Service Layer (RAG)
     LLM Call
    
Session Manager (Redis + PostgreSQL)
     LRU Cache ()
     Redis Cache ()
     PostgreSQL ()
    
Response (SSE Stream)
    
Frontend Rendering
```

##  

### 
- **api.py**: FastAPI  HTTP 
- **graph_workflow.py**: LangGraph 
- **session_manager.py**: LRU + Redis + PG
- **knowledge_base_tool.py**: RAG 

### 
- **App.tsx**: 
- **api.ts**: API SSE 
- **config.ts**: API 

### 
- **pages/index/index.ts**: 
- **components/markdown-renderer**:  Markdown 
- **utils/api.ts**:  API 

##  

### 
```bash
cd backend
#  (nodes/*)
#  (tools/*)
#  (prompts/*)
python -m uvicorn api:app --reload
```

### 
```bash
cd frontend
#  (src/components/*)
#  (src/styles/*)
npm run dev
```

### 
```bash
#  WeChat DevTools  wechat 
#  (miniprogram/pages/*)
#  (miniprogram/components/*)
#  DevTools 
```

### 
```bash
cd docs
#  Markdown 
#  docs-vuepress 
cd ../docs-vuepress
npm run docs:dev
```

##  

```bash
# 
wc -l backend/**/*.py frontend/src/**/*.tsx wechat/miniprogram/**/*.ts

# 
wc -l docs/**/*.md docs-vuepress/**/*.md
```

---

: 2026-03-16
