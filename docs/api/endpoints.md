# API 

## 

- ** URL**: `http://localhost:8000`
- ****: Session-based (Cookie)
- ****: JSON
- ****:  SSE 

---

## 

### 1. 

#### 
```
POST /api/chat
Content-Type: application/json

{
  "message": " Python ",
  "session_id": "optional-session-id"
}
```

####  (SSE )
```
event: message
data: {"type": "content", "data": ""}

event: message
data: {"type": "content", "data": ""}

event: done
data: {"type": "done"}
```

#### 
|  |  |  |  |
|------|------|------|------|
| `message` | string |  |  |
| `session_id` | string |  |  ID |

#### 
- `200`:  SSE 
- `400`: 
- `401`: 
- `500`: 

####  (cURL)
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Python"}'
```

####  (Python)
```python
import requests

response = requests.post(
    'http://localhost:8000/api/chat',
    json={'message': 'Python'},
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode())
```

---

## 

### 2. 

#### 
```
GET /api/sessions
```

#### 
```json
{
  "sessions": [
    {
      "id": "session-123",
      "created_at": "2026-03-16T10:30:00Z",
      "updated_at": "2026-03-16T11:45:00Z",
      "message_count": 5,
      "preview": "..."
    }
  ]
}
```

### 3. 

#### 
```
POST /api/sessions
Content-Type: application/json

{
  "title": ""
}
```

#### 
```json
{
  "id": "session-123",
  "title": "",
  "created_at": "2026-03-16T10:30:00Z"
}
```

### 4. 

#### 
```
GET /api/sessions/{session_id}
```

#### 
```json
{
  "id": "session-123",
  "title": "",
  "created_at": "2026-03-16T10:30:00Z",
  "messages": [
    {
      "id": "msg-1",
      "role": "user",
      "content": "Python",
      "timestamp": "2026-03-16T10:31:00Z"
    },
    {
      "id": "msg-2",
      "role": "assistant",
      "content": "...",
      "timestamp": "2026-03-16T10:31:05Z"
    }
  ]
}
```

### 5. 

#### 
```
DELETE /api/sessions/{session_id}
```

#### 
```json
{
  "success": true,
  "message": ""
}
```

---

## 

### 6. 

#### 
```
GET /api/user/profile
```

#### 
```json
{
  "id": "user-123",
  "username": "user@example.com",
  "preferences": {
    "favorite_genres": ["", ""],
    "reading_level": "intermediate"
  }
}
```

### 7. 

#### 
```
PUT /api/user/preferences
Content-Type: application/json

{
  "favorite_genres": ["", ""],
  "reading_level": "advanced"
}
```

#### 
```json
{
  "success": true,
  "preferences": { ... }
}
```

---

## 

### 8. 

#### 
```
GET /api/recommendations
?session_id=optional&limit=10&offset=0
```

#### 
```json
{
  "total": 25,
  "items": [
    {
      "id": "rec-1",
      "title": "Python ",
      "author": "",
      "source": "douban",
      "douban_url": "https://book.douban.com/subject/...",
      "score": 8.5,
      "reason": ""
    }
  ]
}
```

---

## 

### 9. 

#### 
```
GET /health
```

#### 
```json
{
  "status": "healthy",
  "timestamp": "2026-03-16T10:30:00Z"
}
```

### 10. API 

- **Swagger UI**: GET `/docs`
- **ReDoc**: GET `/redoc`
- **OpenAPI Schema**: GET `/openapi.json`

---

## 

### 
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

### 

|  | HTTP |  |
|--------|------|------|
| `INVALID_REQUEST` | 400 |  |
| `NOT_FOUND` | 404 |  |
| `UNAUTHORIZED` | 401 |  |
| `FORBIDDEN` | 403 |  |
| `RATE_LIMIT` | 429 |  |
| `SERVER_ERROR` | 500 |  |

---

## 

- ****: 10 / ()
- **LLM **: 3 5 QPS ()
- ****:  `X-RateLimit-*` 

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 8
X-RateLimit-Reset: 1710569400
```

---

## 

### Cookie 
 Cookie
```
Set-Cookie: session_id=...; HttpOnly; SameSite=Lax
```

 Cookie

---

## 

```javascript
// 1. 
const sessionResponse = await fetch('http://localhost:8000/api/sessions', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: '' })
});
const { id: sessionId } = await sessionResponse.json();

// 2.  (SSE)
const chatResponse = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: '',
    session_id: sessionId
  })
});

// 3. 
const reader = chatResponse.body.getReader();
const decoder = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}

// 4. 
const historyResponse = await fetch(
  `http://localhost:8000/api/sessions/${sessionId}`
);
const history = await historyResponse.json();
console.log(history.messages);
```

---

: [](./authentication.md) | [](./error-handling.md)

: 2026-03-16
