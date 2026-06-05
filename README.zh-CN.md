# LeanRAG

LeanRAG 是一个轻量级 RAG 应用，包含 FastAPI 后端、MCP 兼容服务，以及 React 管理与聊天前端。项目目标不是只提供一个问答接口，而是把知识接入、切分、索引、检索、重排、提示词组装、流式回答、追踪评估和管理后台串成一条可调试、可替换、可演进的 RAG 链路。

> [!NOTE]
> 本地开发默认提供内存存储和确定性模型降级行为，便于在未接入生产数据库、向量库、对象存储和模型服务前，先验证接口、前端流程和 RAG 编排逻辑。

## RAG 链路流程

```text
文档 / URL
  -> 采集与解析
  -> 清洗、切分、预览
  -> 向量化与索引
  -> 用户问题
  -> 查询改写与意图识别
  -> 多路召回
  -> 重排与上下文压缩
  -> 提示词组装
  -> 流式生成
  -> 追踪、反馈、评估
```

1. **知识接入**：支持文件上传和 URL 摄取。接入层负责保存原始资料、记录任务状态，并把不同来源统一成后续流水线可处理的文档对象。
2. **切分与预览**：文档进入清洗、分块和元数据整理流程。管理端可以预览 chunk，并在需要时人工编辑，避免低质量切分直接影响召回。
3. **向量化与索引**：每个 chunk 生成 embedding 后写入向量检索层，同时保留文档、知识库和 chunk 的结构化信息，方便后续按知识库、标签或业务范围过滤。
4. **查询理解**：用户问题先经过查询改写、关键词映射和意图识别。设计重点是把口语化问题转换成更稳定的检索表达，同时保留原问题用于回答风格和上下文对齐。
5. **召回与重排**：检索层按向量相似度召回候选内容，并可接入 rerank 模型进行二次排序。这样既保留向量检索的宽召回能力，也提高最终上下文的相关性。
6. **上下文组装**：系统会把问题、意图、候选片段和提示词模板合并成模型输入，并控制上下文长度，减少无关内容挤占窗口。
7. **流式回答**：聊天接口以 SSE 方式返回模型输出，前端可以实时展示回答、停止生成、展示推理或链路事件。
8. **追踪与评估**：运维控制台提供示例问题、查询词映射、意图树、系统设置、评估状态和 trace 查看，用于定位召回不足、重排偏差或提示词问题。

## 功能设计

- **模块化后端**：按聊天、知识库、采集、RAG 编排、管理后台和基础设施适配拆分，避免业务逻辑和外部服务 SDK 混在一起。
- **可替换基础设施**：LLM、embedding、rerank、向量库、Redis、对象存储和消息队列都通过适配器接入；本地 fallback 保证开发和测试可以独立运行。
- **知识库可运营**：上传、URL 摄取、任务状态、chunk 预览、chunk 编辑和知识库管理都暴露为产品能力，而不是隐藏在离线脚本里。
- **RAG 可观测**：查询改写、意图、召回、重排、提示词和生成过程尽量留痕，方便从一次回答反推链路里的具体问题。
- **前后端分离**：React 前端提供聊天、知识库和后台管理页面；FastAPI 后端提供统一 API；MCP 兼容服务独立运行，便于工具侧集成。
- **面向生产扩展**：默认配置适合本地快速启动，生产环境可以逐步替换为 PostgreSQL、Redis、Milvus、S3 兼容对象存储、消息队列和真实模型服务。

## 项目结构

```text
app/
  api/          认证、聊天、知识库、采集、RAG 管理和仪表盘 API
  core/         配置、认证、响应封装、ID 和异常处理
  db/           SQLAlchemy 模型与兼容仓储
  infra/        LLM、向量、消息、对象存储和任务状态适配器
  ingestion/    采集流水线编排
  knowledge/    知识文档采集服务
  rag/          查询改写、意图识别、检索、提示词组装和流式生成
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
- 生产化运行可选依赖：PostgreSQL、Redis、Milvus、S3 兼容对象存储、消息队列，以及已配置的 LLM Provider

## 配置

复制 `.env.example` 并按本地环境调整：

```powershell
Copy-Item .env.example .env
```

关键配置包括主 API 监听地址与端口、API 上下文路径、数据库连接、Redis 连接、MCP 服务地址、聊天模型、向量化模型和重排模型。未配置模型 Provider 时，LeanRAG 会使用本地确定性 fallback，方便开发和测试。

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

仓库约定要求修改 JavaScript 文件后运行 `npm test`。当前变更只涉及 Markdown 文档，因此不需要运行该命令。

## 文档

- 中文版：[README.md](README.md)
