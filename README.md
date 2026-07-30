# AI Knowledge Base

Upload PDF, DOCX, or TXT documents and ask an LLM questions answered from their
contents. Answers are grounded in retrieved passages and cite the exact chunks
they came from, so you can verify every claim.

## Deployment

| | URL |
|---|---|
| **Frontend** | https://ai-knowledge-base-one-mu.vercel.app |
| **Backend** | https://ai-knowledge-base-api.vercel.app |
| **API docs** | https://ai-knowledge-base-api.vercel.app/docs |
| **Health** | https://ai-knowledge-base-api.vercel.app/health |

Both are live and publicly accessible. Sign up with any email and an
8+ character password containing a letter and a number.

Stack in production: **Vercel** (React SPA) → **Vercel Python function**
(FastAPI) → **Neon Postgres + pgvector**, with **Gemini** for embeddings and
generation.

---

## Table of contents

- [What it does](#what-it-does)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [Database design](#database-design)
- [API reference](#api-reference)
- [Folder structure](#folder-structure)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Testing](#testing)
- [Deployment guide](#deployment-guide)
- [Assumptions](#assumptions)
- [Trade-offs](#trade-offs)
- [If I had more time](#if-i-had-more-time)

---

## What it does

1. **Sign up / log in** — JWT-authenticated accounts.
2. **Upload a document** — validated, then processed in the background. The
   dashboard shows live status (`Queued → Processing → Ready`).
3. **Ask questions** — e.g. _"Summarize this document"_, _"What are the key
   points?"_, _"List all important dates"_, _"What is the refund policy?"_
4. **Read the answer with its sources** — each answer expands to show the
   passages that produced it, with a similarity score.
5. **Chat history persists** — reload the page and the conversation is still
   there, filterable per document.

Every user sees only their own documents, chunks, and history.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.13) | Async, Pydantic validation, free interactive OpenAPI docs |
| Frontend | **React 19 + Vite + TypeScript** | Fast builds, typed API boundary |
| Styling | **Tailwind CSS v4** | Consistent responsive UI without hand-written CSS |
| Database | **PostgreSQL + pgvector** | Relational data *and* vector search in one store — no separate vector DB to run |
| LLM | **Google Gemini** (`gemini-2.5-flash`) | Genuine free tier, so cost never blocks the demo |
| Embeddings | **`gemini-embedding-001`** @ 768 dims | Same vendor; supports asymmetric task types |
| Auth | **PyJWT + bcrypt** | Standard, stateless, no session store needed |

### Why `gemini-embedding-001` and not `gemini-embedding-2`

The newer model returns a **single aggregated vector** when given multiple
inputs, which is wrong for indexing chunks independently, and it dropped the
`task_type` parameter. `gemini-embedding-001` embeds each chunk separately in
one batched call and supports asymmetric embedding — documents are embedded as
`RETRIEVAL_DOCUMENT`, questions as `RETRIEVAL_QUERY`, which measurably improves
retrieval over embedding both the same way.

## Architecture

```
┌──────────────────┐   HTTPS + JWT   ┌──────────────────┐
│  React SPA       │ ───────────────▶│  FastAPI         │
│  (Vercel)        │◀─────────────── │  (Render/Docker) │
└──────────────────┘                 └────────┬─────────┘
                                              │
                          ┌───────────────────┼───────────────────┐
                          ▼                                       ▼
                 ┌──────────────────┐                   ┌──────────────────┐
                 │ Postgres+pgvector│                   │  Gemini API      │
                 │ (Neon)           │                   │  embed + generate│
                 └──────────────────┘                   └──────────────────┘
```

The backend is **layered**, and each layer only talks to the one below it:

```
api/        HTTP concerns only — parse, validate, status codes
   ↓
services/   business logic — extraction, chunking, embedding, RAG
   ↓
crud/       database queries, always scoped by user_id
   ↓
models/     SQLAlchemy ORM
```

Routes never touch the database or the LLM directly. This is what makes the LLM
swappable and the whole pipeline testable without a network call.

### Ingestion pipeline

Ingestion is deliberately **two-phase**, split at the HTTP boundary:

| Phase | Endpoint | Work | Measured |
|---|---|---|---|
| 1 | `POST /upload` | validate (ext + MIME + magic bytes) → extract text → store as `pending` | ~0.8 s, no network call |
| 2 | `POST /documents/{id}/process` | chunk (~1000 chars, 150 overlap, on paragraph/sentence seams) → embed in batches (`RETRIEVAL_DOCUMENT`) → INSERT pgvector rows → `ready` | ~1.2 s, calls the LLM |

Three things fall out of that split:

- **Upload never blocks on the LLM.** The response returns as soon as the text is
  extracted, so the dashboard has a genuine `pending → ready` transition to
  display rather than a status that was already final on arrival.
- **A failed embed is retryable.** The extracted text is persisted on the
  document, so re-processing needs no re-upload — a failed card gets a retry
  button, and `POST .../process` is idempotent (it replaces chunks rather than
  appending).
- **It behaves the same on either host.** Serverless platforms freeze the process
  once a response is sent, so a `BackgroundTask` would never finish; splitting
  the work across two requests sidesteps that entirely. On a long-running server
  `DEFER_EMBEDDING=true` hands phase 2 to a background task instead.

Extraction runs *before* the document row is created, so an unreadable file (a
scanned, image-only PDF) is rejected with `400` rather than stored as a document
that could never be indexed.

### Retrieval pipeline

`POST /ask`:

```
question → embed (RETRIEVAL_QUERY)
         → SELECT ... ORDER BY embedding <=> :query LIMIT 6
              WHERE documents.user_id = <caller>   ← tenant isolation in SQL
                AND documents.status  = 'ready'
         → drop hits below 0.30 similarity (noise)
         → build a numbered-context prompt
         → gemini-2.5-flash with a strict grounding system prompt
         → persist question + answer + citations in one transaction
```

The system prompt requires the model to answer **only** from the supplied
passages, to cite them by number, and to say so when the answer isn't there.
Verified behaviour on a real document:

> **Q: What is the CEO's home address?**
> A: "The provided documents don't cover that."

### Why RAG rather than stuffing the whole document in the prompt

Stuffing is simpler but breaks on documents larger than the context window, gets
more expensive per question, and dilutes the model's attention. Chunk-and-retrieve
scales to large documents, keeps each request cheap, and — most usefully — makes
answers **auditable**, because you know exactly which passages were used.

## Database design

```
users                                  documents
─────────────────────                  ────────────────────────────────
id            uuid PK                  id            uuid PK
email         text UNIQUE, indexed     user_id       → users.id  CASCADE
hashed_password text                   filename      text
created_at    timestamptz              file_type     text
                                       size_bytes    int
                                       status        enum(pending|processing|
                                                          ready|failed)
                                       error_message text NULL
                                       raw_text      text NULL
                                       char_count    int
                                       chunk_count   int
                                       created_at    timestamptz

document_chunks                        messages
─────────────────────────────          ──────────────────────────────
id            uuid PK                  id          uuid PK
document_id   → documents.id CASCADE   user_id     → users.id  CASCADE
chunk_index   int                      document_id → documents.id NULL
content       text                     role        enum(user|assistant)
embedding     vector(768)              content     text
                                       sources     jsonb NULL
                                       created_at  timestamptz
```

Design notes:

- **`messages.document_id` is nullable** — null means the question was asked
  across *all* of the user's documents rather than one.
- **`messages.sources` is JSONB** — the cited chunks are snapshotted onto the
  answer, so history renders citations without re-running retrieval, and
  citations survive the source document being deleted.
- **Cascades everywhere** — deleting a user or document removes its chunks and
  messages, with no orphan rows.
- **Status is a real enum**, not a boolean, so a failed document can carry a
  reason the UI can display.
- No ANN index on `embedding`: at this scale an exact scan is faster than
  building HNSW. See [Trade-offs](#trade-offs).

## API reference

Paths match the assignment spec exactly. Full interactive docs are generated at
**`/docs`** — that is the authoritative reference, including every schema.

| Method | Path | Auth | Description |
|---|---|:---:|---|
| `POST` | `/signup` | – | Create an account → `201` + token |
| `POST` | `/login` | – | Exchange credentials → `200` + token |
| `GET` | `/me` | ✓ | Current user (used to restore a session) |
| `POST` | `/upload` | ✓ | Upload + extract text → `202`, `status="pending"` |
| `POST` | `/documents/{id}/process` | ✓ | Chunk + embed → `status="ready"`. Idempotent; retries a failure |
| `GET` | `/documents` | ✓ | List own documents, newest first |
| `GET` | `/documents/{id}` | ✓ | One document — poll this for status |
| `DELETE` | `/documents/{id}` | ✓ | Delete a document and its chunks |
| `POST` | `/ask` | ✓ | Ask a question → answer + sources |
| `GET` | `/history` | ✓ | Chat history, optionally per document |
| `GET` | `/health` | – | Liveness + whether the LLM is configured |

Authenticate with `Authorization: Bearer <access_token>`.

<details>
<summary><strong>Example: signup → upload → ask</strong></summary>

```bash
API=http://localhost:8000

# 1. Create an account
TOKEN=$(curl -s -X POST $API/signup \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"Password123"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. Upload — validates and extracts text, returns 202 "pending"
DOC=$(curl -s -X POST $API/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@handbook.pdf" \
  | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 3. Index it — chunks and embeds, returns "ready"
curl -s -X POST $API/documents/$DOC/process -H "Authorization: Bearer $TOKEN"

# 4. Ask a question
curl -s -X POST $API/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"question\":\"List all important dates.\",\"document_id\":\"$DOC\"}"
```

</details>

### Error handling

Every failure returns `{"detail": "<human-readable message>"}` with a correct
status code:

| Code | When |
|---|---|
| `400` | Empty file, unreadable text, or asking before any document is ready |
| `401` | Missing, malformed, expired, or wrongly-signed token |
| `404` | Unknown id — **also** another user's id, so ownership isn't leaked |
| `409` | Email already registered |
| `413` | File over `MAX_UPLOAD_MB` (rejected from `Content-Length`, before buffering) |
| `415` | Unsupported extension, mismatched MIME type, or wrong magic bytes |
| `422` | Request body/query failed validation |
| `503` | Gemini unreachable, rate-limited, or `GEMINI_API_KEY` unset |

Uploads are checked three ways — extension, declared content type, **and magic
bytes** — so an `.exe` renamed to `.pdf` is rejected rather than parsed.
Unexpected exceptions are logged server-side and returned as a generic `500`,
never leaking internals.

## Folder structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py               app factory, CORS, routers, lifespan
│   │   ├── core/                 config, security (JWT/bcrypt), exceptions
│   │   ├── db/                   engine, session, declarative base
│   │   ├── models/               User, Document, DocumentChunk, Message
│   │   ├── schemas/              Pydantic request/response models
│   │   ├── crud/                 queries, all scoped by user_id
│   │   ├── api/
│   │   │   ├── deps.py           get_db, get_current_user, LLM factory
│   │   │   └── routes/           auth.py, documents.py, chat.py
│   │   └── services/
│   │       ├── extraction.py     validation + PDF/DOCX/TXT text extraction
│   │       ├── chunking.py       overlapping, boundary-aware splitter
│   │       ├── ingestion.py      background pipeline orchestration
│   │       ├── rag.py            retrieve → prompt → generate → persist
│   │       └── llm/
│   │           ├── base.py       LLMProvider Protocol
│   │           └── gemini.py     Gemini implementation
│   ├── tests/                    73 tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/                  axios client + auth/documents/chat modules
│       ├── context/              AuthContext
│       ├── components/           ui.tsx, Layout, ProtectedRoute,
│       │                         FileDropzone, ChatMessage
│       ├── pages/                Login, Signup, Dashboard, Chat
│       └── types/                shared API types
├── docker-compose.yml            local Postgres with pgvector
└── render.yaml                   backend deployment blueprint
```

## Local setup

**Prerequisites:** Python 3.13+, Node 20+, Docker (for Postgres), and a free
Gemini API key from <https://aistudio.google.com/apikey>.

### 1. Database

```bash
docker compose up -d          # Postgres 17 + pgvector on :5432
```

Prefer a hosted database? Skip this and point `DATABASE_URL` at Neon.

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash
# source .venv/bin/activate        # macOS / Linux

pip install -r requirements.txt
cp .env.example .env
# then edit .env: set GEMINI_API_KEY, and a random JWT_SECRET:
#   python -c "import secrets; print(secrets.token_urlsafe(48))"

uvicorn app.main:app --reload
```

API on <http://localhost:8000>, docs on <http://localhost:8000/docs>. Tables and
the `vector` extension are created automatically on startup.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL=http://localhost:8000
npm run dev
```

App on <http://localhost:5173>.

## Environment variables

### Backend (`backend/.env`)

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | local docker | Must use the `postgresql+psycopg://` scheme |
| `JWT_SECRET` | — | **Required.** Long random string |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 24 hours |
| `GEMINI_API_KEY` | — | **Required** for upload and ask |
| `GEMINI_CHAT_MODEL` | `gemini-2.5-flash` | |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | |
| `EMBEDDING_DIMENSIONS` | `768` | Fixed at table creation; changing it needs a migration |
| `DEFER_EMBEDDING` | `false` | Background-task phase 2. Only safe on a long-running host |
| `AUTO_INIT_DB` | `true` | Set `false` on serverless; run `scripts/init_db.py` once |
| `MAX_UPLOAD_MB` | `10` | |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `150` | Characters |
| `RETRIEVAL_TOP_K` | `6` | Passages sent to the model |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated |

### Frontend (`frontend/.env`)

| Variable | Notes |
|---|---|
| `VITE_API_URL` | Backend base URL. Baked in at build time |

## Testing

```bash
cd backend
pytest              # 73 tests
pytest -v           # see individual names
```

Tests run against a `knowledge_base_test` database that is created and dropped
automatically, and the LLM is replaced with a deterministic stub — so the suite
needs **no API key, costs nothing, and makes no network calls**. The stub derives
embeddings from token histograms, so similarity search still behaves realistically.

Coverage highlights:

- **Auth** — duplicate emails, weak passwords, case normalisation, expired
  tokens, tokens forged with another secret, and that a wrong password is
  indistinguishable from an unknown email
- **Uploads** — all three real formats end to end (a genuine PDF, DOCX with a
  table, and TXT), plus `.exe` rejection, magic-byte mismatch, oversized, and
  empty files
- **RAG** — that retrieved passages actually reach the prompt, that citations
  are returned and persisted, and that an unprocessable document errors clearly
- **Tenant isolation** — user B cannot read, delete, or *retrieve chunks from*
  user A's documents, and histories are private
- **Chunking** — size limits, overlap correctness, blank input, and words longer
  than a whole chunk

Frontend typecheck and production build:

```bash
cd frontend && npx tsc --noEmit && npm run build
```

## Deployment guide

The live deployment runs entirely on Vercel (frontend + backend function) with
Neon provisioned through the Vercel Marketplace. The repo also keeps a
Docker/Render path, which is the better architecture — see
[Serverless vs. a long-running server](#serverless-vs-a-long-running-server).

### Option A — the deployed setup (all Vercel)

```bash
# Backend
cd backend
vercel link --project ai-knowledge-base-api
vercel integration add neon          # provisions Postgres, injects DATABASE_URL

vercel env add JWT_SECRET production   # python -c "import secrets;print(secrets.token_urlsafe(48))"
vercel env add GEMINI_API_KEY production
vercel env add AUTO_INIT_DB production # false — schema is created once, below
vercel env add CORS_ORIGINS production # your frontend URL

# Create the schema once (pgvector + 4 tables)
vercel env pull .env.local
DATABASE_URL="$(grep '^DATABASE_URL=' .env.local | cut -d= -f2- | tr -d '\"')" \
  python scripts/init_db.py

vercel deploy --prod

# Frontend
cd ../frontend
vercel env add VITE_API_URL production          # the backend URL from above
vercel deploy --prod
```

`VITE_API_URL` is baked in at build time, so changing it needs a **redeploy**,
not a restart.

### Serverless vs. a long-running server

On Vercel the process is frozen the moment a response is sent, so a FastAPI
`BackgroundTask` would never run. The two-phase ingestion split solves that
structurally rather than by configuration — phase 2 is its own HTTP request, so
nothing needs to survive past a response. Two settings remain host-specific:

| Setting | Serverless (deployed) | Long-running (Docker/Render) |
|---|---|---|
| `DEFER_EMBEDDING` | `false` (default) — phase 2 runs inline in its own request | `true` — phase 2 is handed to a background task |
| `AUTO_INIT_DB` | `false` — schema created once via `scripts/init_db.py` | `true` — created on startup |
| Connection pool | `NullPool`, auto-detected from `$VERCEL`; Neon's pooler handles it | SQLAlchemy pool with `pool_pre_ping` |

`DEFER_EMBEDDING` defaults to `false` deliberately: inline is correct on every
host, so the unsafe value is never the default.

`api/index.py` exposes the same FastAPI app as an ASGI function, so both hosts
run identical application code.

**Remaining trade-off:** phase 2 is bounded by Vercel's 60 s function limit, so a
very large document could time out mid-embed. It would be left `failed` with the
retry button available, and the extracted text is already stored — but a truly
large corpus wants either the Render path or incremental batch processing (see
[If I had more time](#if-i-had-more-time)).

### Option B — Render + Neon (the non-blocking architecture)

### 1. Database — Neon

1. Create a project at <https://neon.tech> (free tier).
2. In the SQL editor: `CREATE EXTENSION IF NOT EXISTS vector;`
   (the app also does this on startup).
3. Copy the **pooled** connection string and change the scheme to
   `postgresql+psycopg://`, keeping `?sslmode=require`.

### 2. Backend — Render

1. **New → Web Service**, connect this repo.
2. Root directory `backend`, runtime **Docker**, health check path `/health`.
3. Environment variables:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Neon pooled URL |
   | `GEMINI_API_KEY` | your key |
   | `JWT_SECRET` | generate a random value |
   | `CORS_ORIGINS` | your Vercel URL (set after step 3) |

   `render.yaml` declares all of this if you deploy via **Blueprint** instead.
4. Deploy, then confirm `https://<service>.onrender.com/health` returns
   `{"status":"ok","llm_configured":true}`.

### 3. Frontend — Vercel

1. **Add New → Project**, import this repo.
2. Root directory `frontend`, framework **Vite** (auto-detected).
3. Environment variable `VITE_API_URL` = your Render URL (no trailing slash).
4. Deploy.

### 4. Connect them

Set `CORS_ORIGINS` on Render to the Vercel domain and redeploy. `VITE_API_URL` is
baked in at build time, so **changing it requires a Vercel redeploy**, not just a
restart.

Then walk the full flow on the live URLs: sign up → upload → wait for Ready →
ask a question → reload and confirm history persisted.

## Assumptions

- **Text-based documents only.** Scanned or image-only PDFs have no extractable
  text and fail with an explanatory message rather than silently producing an
  empty knowledge base. OCR was out of scope.
- **English-language content**, though Gemini's embeddings are multilingual and
  will mostly work otherwise.
- **Single-user documents.** No sharing, teams, or roles — each document belongs
  to exactly one account.
- **10 MB / document** is enough for the target use case (handbooks, policies,
  contracts, reports).
- **Modest concurrency.** Free-tier hosting with one instance; the design notes
  below say what would change under real load.
- **Legacy `.doc` is not supported** — only the modern zip-based `.docx`.

## Trade-offs

**Extracted text in the database, original files discarded.**
Serverless and Render filesystems are both ephemeral, so anything written to disk
vanishes on redeploy, and object storage was avoidable complexity. Storing the
extracted text (`documents.raw_text`) rather than the upload is what makes phase 2
retryable without a re-upload. The cost is roughly doubled row size and the fact
that a document can't be re-downloaded or re-extracted with a better parser later.

**Client-triggered phase 2 instead of a job queue.**
A real queue (Celery/RQ) needs a Redis broker and a worker process — neither is
free to host, and both add moving parts to a take-home. Splitting ingestion into
two endpoints gets the important properties (fast upload, observable status,
retryable failure) with no extra infrastructure, at the cost of the client having
to make the second call. If that call is never made, the document simply stays
`pending` and visibly un-indexed rather than silently broken. A production version
would use a real queue with automatic retries and a sweep for stale rows.

**JWT in `localStorage`, no refresh tokens.**
Simplest thing that works for a SPA on a different origin from the API. It is
readable by injected scripts, so a genuine XSS would expose the token; the
mitigation is httpOnly, `SameSite` cookies plus CSRF protection, which needs
cookie-domain coordination. Access tokens are short-lived (24 h) with no rotation.

**No ANN index on the vector column.**
pgvector's exact search is a sequential scan — at hundreds or a few thousand
chunks that's single-digit milliseconds and *more* accurate than an approximate
index. HNSW would only start paying off in the 100k+ chunk range, and building it
early would cost recall for no gain. One `CREATE INDEX` when that day comes.

**`create_all()` on startup instead of Alembic.**
The schema was designed once and shipped once, so there is no migration history
to replay. This does mean a schema change needs a manual migration — the first
real change to a deployed database should introduce Alembic.

**Fixed-size chunking rather than semantic chunking.**
The splitter respects paragraph and sentence boundaries, which captures most of
the benefit cheaply. Semantic chunking (embedding candidate splits to find
topic shifts) is better but costs an extra embedding pass per document.

**Similarity floor of 0.30, with a fallback.**
Passages below the floor are dropped as noise. But if *everything* scores low the
single best hit is kept anyway, so the model can judge relevance itself rather
than being handed an empty context and inventing an answer.

## If I had more time

- **Streaming answers** via SSE, so text appears token by token instead of after
  a pause.
- **Multi-turn context** — follow-ups like "and what about sick leave?" currently
  don't see the previous exchange. Would need query rewriting from history.
- **A real job queue** (Celery + Redis) with automatic retries, plus a sweep that
  re-queues documents stuck in `processing`, replacing the client-triggered
  process call.
- **Incremental batch embedding** — process N chunks per request and let the
  client drive to completion, which would lift the 60 s serverless ceiling for
  very large documents entirely.
- **Hybrid search** — combine vector similarity with Postgres full-text search
  and rerank, which fixes the classic RAG weakness on exact keywords and IDs.
- **Reranking** with a cross-encoder over the top ~20 candidates to improve
  precision before the generation step.
- **Frontend tests** — Vitest + React Testing Library for the auth flow and
  chat, and Playwright for one end-to-end pass. The backend is well covered; the
  frontend is verified manually and by typecheck.
- **Per-user rate limiting** so one account can't exhaust the shared Gemini quota.
- **Observability** — structured JSON logs, request tracing, and metrics on
  retrieval quality (similarity distributions, "not found" rate).
- **Page/section numbers in citations** so a source links to *where* in the
  original document it came from, not just which chunk.
