# API Reference

Base URL: `http://localhost:8000/api/v1`

All authenticated endpoints expect:
```
Authorization: Bearer <access_token>
```

Error envelope:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Video not found",
    "request_id": "..."
  }
}
```

## Auth

### POST `/auth/register`
```json
{ "email": "a@b.com", "username": "alice", "password": "Min8Chars!", "full_name": "Alice" }
```
Returns `201 UserRead`.

### POST `/auth/login`
```json
{ "email": "a@b.com", "password": "Min8Chars!" }
```
Returns:
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 3600 }
```

### POST `/auth/refresh`
```json
{ "refresh_token": "..." }
```
Returns a fresh token pair.

### GET `/auth/me`
Returns the current `UserRead`.

## Videos

### POST `/videos/upload`  (multipart)
Fields: `file` (binary), `title` (string), `description` (string, optional)

Returns `201 VideoRead` and kicks off background processing.

### GET `/videos`
Returns `VideoListItem[]`.

### GET `/videos/{id}`
Returns full `VideoRead` (includes status + error if any).

### POST `/videos/{id}/reprocess`
Returns `{ "status": "ok", "message": "Reprocessing started" }`.

### POST `/videos/{id}/summary`
Returns `VideoSummary` (LLM-generated overview + bullets).

### DELETE `/videos/{id}`
Soft deletes + removes vectors. Returns `{ status: "ok" }`.

## Chat

### POST `/chat` (non-streaming)
```json
{
  "message": "What did the speaker say about caching?",
  "conversation_id": null,
  "video_id": "uuid-or-null",
  "stream": false,
  "top_k": 8
}
```
Returns `ChatResponse { conversation_id, message: MessageRead, citations: Citation[] }`.

### POST `/chat/stream` (SSE)
Same payload. The response is a `text/event-stream` with events:

| Event   | Data shape |
|---------|------------|
| `start` | `{ conversation_id, user_message_id, citations[] }` |
| `delta` | `{ text: "..." }` (zero or more) |
| `done`  | `{ message_id, conversation_id, citations[], latency_ms }` |
| `error` | `{ message }` |

Each event is delivered as:
```
event: <event>
data: <json>

```

### GET `/chat/conversations`
List `Conversation[]` for the current user.

### GET `/chat/conversations/{id}`
Returns `ConversationDetail` with full `messages[]` (each containing `citations`).

### DELETE `/chat/conversations/{id}`
Deletes the conversation + all messages.

## Users

### GET `/users/preferences`
### PATCH `/users/preferences`
Update theme / language / response style / notes.

### GET `/users/memory`
Returns the long-term memory facts the LLM uses for personalization.

### GET `/users/recommendations`
Returns `recent_videos[]` + `topics_of_interest[]`.

## Admin (requires `is_admin`)

### GET `/admin/stats`
System-wide counts plus vector store size.

### GET `/admin/users`
First 200 users with status flags.

### GET `/admin/failed-videos`
Recent processing failures with error messages.

## Health / Meta

* `GET /api/v1/health/live` — liveness
* `GET /api/v1/health/ready` — DB + embedder check
* `GET /metrics` — Prometheus
* `GET /docs` — Swagger UI
* `GET /redoc` — Redoc
