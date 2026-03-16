# 

## 

Book Agent  AI 

```
       
  WeChat             React Web App   
       
                                  
          HTTPS/SSE                HTTPS/SSE
         
                     

     FastAPI  ()              
   LangGraph                 
    (LRU  + Redis)      
   RAG                       
                               

                           
                           
 Redis        Milvus    PostgreSQL
()    (DB)   ()
                           
                           

                           
    &             
    &             
                
    &                 


       

  OpenAI  API (LLM)             
  Douban /  /         
                      

```

## 

### 1. 
- **React **:  SPA  Ant Design 6 + Vite
- **WeChat **: WXML + TypeScript
-  FastAPI 

### 2.  (LangGraph)
 LangGraph 

```python

    
[]  
    
  []    LLM  
            []  RAG   LLM  
            []    LLM  
```

### 3. 

** & **:
- **Redis**: 
  -  (Key: `conversation:{session_id}`)
  - 
  - 

****:
- **Milvus**: 
  - 
  - RAG 

****:
- **PostgreSQL**: 
  - 
  - 
  - 
- **SQLite**: 

### 4. 

```

    
[]
    
 LRU   ?  
   ()             
                  [Redis ]
                    
  ?   Redis   
                      
                  [PG ]
                     
                   ?    
                      
                  
```

### 5. 
- **LLM**: OpenAI  API ( DeepSeekGPT )
- ****: Douban API
- ****: 

## 

### SSE 
 Server-Sent Events (SSE) 

```
 POST /chat
    
 (LangGraph )
    
SSE 
    

```

## 

|  |  |  |
|------|------|------|
| LLM  | LangGraph |  |
|  | Milvus Lite |  |
|  | React 19 |  |
|  |  |  |
| API  | RESTful + SSE |  |

## 

- ****: FastAPI  PM2  K8s 
- ****: LangGraph 
- ****: Milvus 
- **LLM **:  LLM 

---

[](./tech-stack.md) | [](./features.md)
