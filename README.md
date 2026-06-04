# LeanRAG

LeanRAG is a lightweight RAG application with a FastAPI backend, an MCP-compatible service, and a React admin/chat frontend. The project keeps the public API surface compatible with the original Ragent frontend while separating the Python implementation into clear product modules for chat, knowledge ingestion, retrieval, administration, and infrastructure adapters.

> [!NOTE]
> The local implementation includes in-memory compatibility storage and fallback model behavior so the API and UI can be validated quickly before wiring production databases, vector stores, object storage, and model providers.

## Features

- Streaming RAG chat over server-sent events at `/api/ragent/rag/v3/chat`.
- Conversation history, stop controls, message feedback, and optional deep-thinking trace events.
- Knowledge base management with document upload, URL ingestion, chunking, preview, and chunk editing APIs.
- RAG operations console for sample questions, query-term mappings, intent trees, settings, evaluation status, and trace inspection.
- Admin dashboard and user management APIs with token-based authentication.
- MCP compatibility service on a separate FastAPI app.
- Provider adapters for Ollama, Bailian/DashScope-compatible chat and rerank, AIHubMix, SiliconFlow, pgvector/Milvus-style vector configuration, Redis, RustFS/S3-compatible object storage, and RocketMQ.

## Project Structure

```text
app/
  api/          FastAPI route modules for auth, chat, knowledge, ingestion, RAG admin, and dashboard APIs
  core/         Configuration, auth, response envelopes, IDs, and error handling
  db/           SQLAlchemy models plus the compatibility repository
  infra/        LLM, vector, messaging, object storage, and task-state adapters
  ingestion/    Ingestion pipeline orchestration
  knowledge/    Knowledge document ingestion services
  rag/          Query rewrite, intent resolution, retrieval, prompt assembly, and streaming pipeline
  services/     Shared local store helpers
frontend/
  src/          React, Vite, Tailwind, shadcn-style UI, chat pages, and admin pages
mcp_server/     MCP-compatible FastAPI service
resources/      Prompt templates used by the RAG pipeline
tests/          Backend API, RAG, MCP, management, and infrastructure fallback tests
```

## Requirements

- Python 3.11 or newer
- Node.js 18 or newer
- npm for existing frontend scripts, or pnpm when installing new dependencies
- Optional services for production-like runs: PostgreSQL, Redis, Milvus, RustFS/S3-compatible storage, RocketMQ, and a configured LLM provider

## Configuration

Copy `.env.example` and adjust values for your environment:

```powershell
Copy-Item .env.example .env
```

Important defaults:

| Variable | Default | Purpose |
| --- | --- | --- |
| `RAGENT_PORT` | `9090` | Main API service port |
| `RAGENT_CONTEXT_PATH` | `/api/ragent` | API context path |
| `MCP_SERVER_URL` | `http://localhost:9099` | MCP service URL used by the main app |
| `DATABASE_URL` | local PostgreSQL URL | SQLAlchemy database connection |
| `REDIS_URL` | local Redis URL | Redis connection |
| `RAGENT_CHAT_PROVIDER` | empty | Enables `ollama`, `bailian`, `aihubmix`, or `siliconflow` chat provider |
| `RAGENT_EMBEDDING_PROVIDER` | empty | Enables provider-backed embeddings; otherwise hash fallback is used |
| `RAGENT_RERANK_PROVIDER` | empty | Enables provider-backed reranking |

When providers are not configured, LeanRAG falls back to local deterministic behavior for development and tests.

## Run Locally

Create the Python environment and install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

Start the main API:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 9090
```

Start the MCP compatibility service in another terminal:

```powershell
python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 9099
```

Install and start the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and proxies `/api` requests to `http://localhost:9090`.

## Test

Run backend tests from the repository root:

```powershell
pytest
```

Run frontend build validation from `frontend/`:

```powershell
npm run build
```

The repository agreement requires `npm test` after modifying JavaScript files. The current frontend package does not define a `test` script, so add one before relying on that workflow.

## API Conventions

- Main API prefix: `/api/ragent`
- Default main port: `9090`
- Default MCP port: `9099`
- Standard response envelope:

```json
{
  "code": "0",
  "message": null,
  "data": {},
  "requestId": "..."
}
```

- Streaming chat route: `GET /api/ragent/rag/v3/chat`
- Streaming media type: `text/event-stream;charset=UTF-8`

## Documentation

- English: [README.md](README.md)
- Chinese: [README.zh-CN.md](README.zh-CN.md)
