# LeanRAG

LeanRAG 是一个轻量级 RAG 应用，包含 FastAPI 后端、MCP 兼容服务，以及 React 管理与聊天前端。项目保留了与原 Ragent 前端兼容的公开 API，同时将 Python 实现按聊天、知识库、检索、管理后台和基础设施适配器等产品边界拆分。

> [!NOTE]
> 当前本地实现内置了内存兼容存储和模型 fallback，便于在接入生产数据库、向量库、对象存储和模型服务前快速验证 API 与前端流程。

## 功能特性

- 基于 Server-Sent Events 的流式 RAG 对话接口：`/api/ragent/rag/v3/chat`。
- 支持会话历史、停止生成、消息反馈，以及可选的深度思考与链路追踪事件。
- 知识库管理：文档上传、URL 摄取、切分、预览、Chunk 编辑等 API。
- RAG 运维控制台：示例问题、查询词映射、意图树、系统设置、评估状态和 Trace 查看。
- 管理后台：仪表盘、用户管理、基于 token 的登录认证。
- 独立 FastAPI 应用提供 MCP 兼容服务。
- 基础设施适配：Ollama、百炼/DashScope 兼容接口、AIHubMix、SiliconFlow、pgvector/Milvus 配置、Redis、RustFS/S3 兼容对象存储和 RocketMQ。

## 项目结构

```text
app/
  api/          认证、聊天、知识库、摄取、RAG 管理和仪表盘 API
  core/         配置、认证、响应封装、ID 和异常处理
  db/           SQLAlchemy 模型与兼容仓储
  infra/        LLM、向量、消息、对象存储和任务状态适配器
  ingestion/    摄取流水线编排
  knowledge/    知识文档摄取服务
  rag/          查询改写、意图识别、检索、Prompt 组装和流式生成
  services/     本地共享存储辅助逻辑
frontend/
  src/          React、Vite、Tailwind、UI 组件、聊天页和管理后台页面
mcp_server/     MCP 兼容 FastAPI 服务
resources/      RAG 流程使用的 Prompt 模板
tests/          后端 API、RAG、MCP、管理接口和基础设施 fallback 测试
```

## 环境要求

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- 现有前端脚本使用 npm；新增依赖时优先使用 pnpm
- 生产化运行可选依赖：PostgreSQL、Redis、Milvus、RustFS/S3 兼容对象存储、RocketMQ，以及已配置的 LLM Provider

## 配置

复制 `.env.example` 并按本地环境调整：

```powershell
Copy-Item .env.example .env
```

关键默认值：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RAGENT_PORT` | `9090` | 主 API 服务端口 |
| `RAGENT_CONTEXT_PATH` | `/api/ragent` | API 上下文路径 |
| `MCP_SERVER_URL` | `http://localhost:9099` | 主应用访问 MCP 服务的地址 |
| `DATABASE_URL` | 本地 PostgreSQL 地址 | SQLAlchemy 数据库连接 |
| `REDIS_URL` | 本地 Redis 地址 | Redis 连接 |
| `RAGENT_CHAT_PROVIDER` | 空 | 配置后启用 `ollama`、`bailian`、`aihubmix` 或 `siliconflow` 聊天模型 |
| `RAGENT_EMBEDDING_PROVIDER` | 空 | 配置后启用模型向量化；未配置时使用 hash fallback |
| `RAGENT_RERANK_PROVIDER` | 空 | 配置后启用模型重排 |

未配置模型 Provider 时，LeanRAG 会使用本地确定性 fallback，方便开发和测试。

## 本地启动

创建 Python 虚拟环境并安装后端依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

启动主 API：

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 9090
```

另开一个终端启动 MCP 兼容服务：

```powershell
python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 9099
```

安装并启动前端：

```powershell
cd frontend
npm install
npm run dev
```

前端默认运行在 `http://localhost:5173`，并将 `/api` 请求代理到 `http://localhost:9090`。

## 测试

在仓库根目录运行后端测试：

```powershell
pytest
```

在 `frontend/` 目录运行前端构建验证：

```powershell
npm run build
```

仓库约定要求修改 JavaScript 文件后运行 `npm test`。当前前端 `package.json` 尚未定义 `test` 脚本，正式依赖该流程前需要先补充测试脚本。

## API 约定

- 主 API 前缀：`/api/ragent`
- 主服务默认端口：`9090`
- MCP 服务默认端口：`9099`
- 标准响应格式：

```json
{
  "code": "0",
  "message": null,
  "data": {},
  "requestId": "..."
}
```

- 流式聊天接口：`GET /api/ragent/rag/v3/chat`
- 流式响应类型：`text/event-stream;charset=UTF-8`

## 文档

- 英文版：[README.md](README.md)
- 中文版：[README.zh-CN.md](README.zh-CN.md)
