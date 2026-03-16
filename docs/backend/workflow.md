# LangGraph 

## 

Book Agent  LangGraph 

```

   
[]
   
   :   []  []  
  
   :   [RAG ]  []  
  
   :     []  
```

---

## 

### 1.  (State)

```python
@dataclass
class AgentState:
    """"""
    messages: list[dict]           # 
    current_intent: str            # 
    search_results: list[dict]     # 
    rag_results: list[dict]        # RAG 
    response: str                  # 
    metadata: dict                 # 
```

### 2.  (Nodes)



|  |  |  |  |
|--------|------|------|------|
| `classify_intent` |  | `messages` | `current_intent` |
| `search_books` |  | `messages` | `search_results` |
| `rag_retrieve` | RAG  | `messages` | `rag_results` |
| `generate_response` |  LLM  | state +  | `response` |
| `ask_clarification` |  | `messages` | `response` |

### 3.  (Edges)

- ****:  `current_intent` 
- ****: (RAG)
- ****: 

---

## 

### A. 

```python
def classify_intent(state: AgentState) -> AgentState:
    """
     LLM 

    :
    - "book_recommendation": 
    - "customer_service": ( RAG)
    - "clarification_needed": 
    """
    messages = state.messages

    #  LLM
    response = llm.invoke([
        SystemMessage("..."),
        *messages
    ])

    # 
    intent = extract_intent(response.content)

    state.current_intent = intent
    return state
```

****:
- : " Python "
- : `current_intent = "book_recommendation"`

---

### B. 

: `current_intent == "book_recommendation"`

```python
def search_books(state: AgentState) -> AgentState:
    """"""

    # 
    keywords = extract_keywords(state.messages[-1].content)

    # 
    results = []
    results.extend(douban_search(keywords))
    results.extend(library_search(keywords))
    results.extend(shopping_search(keywords))

    state.search_results = results
    return state

def generate_response(state: AgentState) -> AgentState:
    """"""

    response = llm.invoke([
        SystemMessage("..."),
        *state.messages,
        HumanMessage(f": {state.search_results}")
    ])

    state.response = response.content
    return state
```

****:
```
: " Python "
    
: book_recommendation
    
: Python, , 
    
:
  - Python( 8.9)
  - Fluent Python( 4.8)
    
LLM :
  "
   1. Python- 
   2. Fluent Python- "
```

---

### C.  RAG 

: `current_intent == "customer_service"`

```python
def rag_retrieve(state: AgentState) -> AgentState:
    """"""

    # 
    query_embedding = embedder.embed_query(state.messages[-1].content)

    #  Milvus 
    results = milvus_kb.search(
        data=query_embedding,
        limit=5,
        output_fields=["text", "source", "metadata"]
    )

    state.rag_results = results
    return state

def generate_rag_response(state: AgentState) -> AgentState:
    """ RAG """

    context = "\n".join([r['text'] for r in state.rag_results])

    response = llm.invoke([
        SystemMessage("..."),
        SystemMessage(f":\n{context}"),
        *state.messages
    ])

    state.response = response.content
    return state
```

****:
```
: ""
    
: customer_service
    
RAG 
    
:
  - ""
  - ": "
    
LLM :
  "
   1.  - ...
   2.  - ...
   3.  - ..."
```

---

### D. 

: `current_intent == "clarification_needed"`

```python
def ask_clarification(state: AgentState) -> AgentState:
    """"""

    response = llm.invoke([
        SystemMessage("..."),
        *state.messages,
        HumanMessage(" 1-2 ")
    ])

    state.response = response.content
    return state
```

****:
```
: ""
    
: clarification_needed ()
    
LLM :
  "
   1. (///...)
   2. (//)"
```

---

## 

### 

```python
from langgraph.graph import StateGraph

def create_workflow():
    """ LangGraph """

    workflow = StateGraph(AgentState)

    # 
    workflow.add_node("classify", classify_intent)
    workflow.add_node("search", search_books)
    workflow.add_node("rag", rag_retrieve)
    workflow.add_node("generate", generate_response)
    workflow.add_node("clarify", ask_clarification)

    # 
    workflow.add_conditional_edges(
        "classify",
        route_by_intent,
        {
            "book_recommendation": "search",
            "customer_service": "rag",
            "clarification_needed": "clarify"
        }
    )

    # 
    workflow.add_edge("search", "generate")
    workflow.add_edge("rag", "generate")

    # 
    workflow.set_entry_point("classify")
    workflow.add_edge("generate", END)
    workflow.add_edge("clarify", END)

    return workflow.compile()

# 
agent = create_workflow()
```

---

## 

### 

```python
result = agent.invoke({
    "messages": [
        HumanMessage(""),
    ],
    "search_results": [],
    "rag_results": [],
    "response": ""
})

print(result["response"])
```

###  ()

```python
async def stream_agent(state_dict):
    """"""
    async for output in agent.astream(state_dict):
        # output : {node_name: updated_state}
        yield json.dumps(output)
```

---

## 

### 1. 

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def classify_intent(state: AgentState) -> AgentState:
    logger.debug(f": {state.messages[-1]}")
    # ...
    logger.info(f": {state.current_intent}")
    return state
```

### 2. 

```python
# 
agent.with_config({"run_name": "debug_run"}).invoke(state)
```

### 3. 

```python
from IPython.display import Image

# 
png_data = agent.get_graph().draw_mermaid_png()
Image(png_data)
```

 Mermaid 
```
graph LR
    A[] -->|| B[]
    A -->|| C[RAG]
    A -->|| D[]
    B --> E[]
    C --> E
    D --> F[]
    E --> F
```

---

## 

### 1.  LLM 

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def cached_embedding(text):
    return embedder.embed_query(text)
```

### 2. 

```python
import asyncio

async def parallel_search(keywords):
    """"""
    douban_task = asyncio.create_task(douban_search(keywords))
    library_task = asyncio.create_task(library_search(keywords))

    return await asyncio.gather(douban_task, library_task)
```

### 3. 

 FastAPI 

---

## 

### 

```python
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def search_books_with_retry(state: AgentState):
    try:
        return search_books(state)
    except Exception as e:
        logger.error(f": {e}")
        raise
```

### 

```python
import asyncio

try:
    result = await asyncio.wait_for(
        agent.ainvoke(state),
        timeout=30.0
    )
except asyncio.TimeoutError:
    return {"response": ""}
```

---

## 

### 

1.  `classify_intent` 
2. 
3. 

```python
# 
workflow.add_node("summarize", summarize_books)

# 
workflow.add_conditional_edges(
    "classify",
    route_by_intent,
    {
        ...
        "summary_request": "summarize"
    }
)
```

---

## 

- [LangGraph ](https://langchain-ai.github.io/langgraph/)
- [](https://en.wikipedia.org/wiki/State_pattern)
- [: graph_workflow.py](../../backend/graph_workflow.py)

: 2026-03-16
