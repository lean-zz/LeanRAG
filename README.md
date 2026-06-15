# LeanRAG

LeanRAG 是一个面向真实业务问答场景的轻量级 RAG 应用。它不是只封装一次大模型调用，而是把知识接入、文本切分、向量索引、查询改写、意图识别、多通道召回、重排、Prompt 编排、SSE 流式回答、链路追踪和后台运营串成一条可调试、可替换、可演进的 RAG 工程链路。

这个项目适合作为面试中的工程型 AI 项目案例：既能讲清楚 RAG 的核心算法链路，也能展开后端架构、前端管理台、基础设施适配、降级策略、可观测性和测试保障。

## 项目价值

多数 RAG Demo 只覆盖“上传文档 -> 提问 -> 返回答案”的最短路径。LeanRAG 关注的是更接近生产环境的问题：

- 文档来源不一致时，如何统一进入可追踪的知识摄取流程。
- 用户问题口语化、范围模糊时，如何先做查询改写、问题拆分和意图识别。
- 只靠向量相似度不稳定时，如何引入多通道召回、去重、重排和上下文组装。
- 模型、向量库、对象存储、Redis、消息队列暂未就绪时，如何通过本地 fallback 保持开发和测试可运行。
- 回答质量异常时，如何通过 trace 定位问题出在改写、意图、召回、Prompt 还是模型生成。

## 核心能力

### 完整 RAG 问答链路

```text
用户问题
  -> 会话记忆加载
  -> 查询改写与问题拆分
  -> 意图识别
  -> 知识库 / MCP 多通道召回
  -> 候选 chunk 去重与重排
  -> Prompt 模板组装
  -> LLM 流式生成
  -> 消息落库与 Trace 记录
```

后端通过 `app/rag/` 拆分 RAG 编排能力，避免把检索、Prompt、模型调用和会话状态混在一个接口里。聊天接口使用 SSE 返回流式结果，前端可以实时展示回答、思考提示和结束事件。

### 可运营的知识库摄取

```text
文件 / URL
  -> 原始内容保存
  -> 文本解码
  -> 固定长度 / 段落 / 结构感知切分
  -> embedding 生成
  -> 向量索引
  -> chunk 预览与管理
```

知识库不是离线脚本，而是产品能力。项目提供知识库、文档、chunk、摄取任务状态和后台管理接口，方便在管理台查看文档处理结果，并对 chunk 质量进行检查。

### 多通道召回与重排

检索层支持基于意图的定向召回和全局向量召回，并在后处理阶段完成：

- 多通道结果合并。
- chunk 去重。
- 按通道优先级和分数排序。
- 可选 rerank 模型二次排序。
- 知识库上下文与 MCP 工具上下文分区组装。

这部分是面试中很适合展开的设计点：单纯向量召回容易受 query 表达影响，LeanRAG 通过“意图约束 + 全局补召 + rerank”的方式，在召回宽度和上下文相关性之间做平衡。

### MCP 工具融合

LeanRAG 支持把 MCP 工具结果纳入回答上下文。意图节点可以指向 MCP 工具，检索层会抽取参数、调用工具服务，并把工具返回结果与知识库片段一起交给 Prompt 层。

这让系统不只回答静态知识库问题，也可以接入天气、销售、工单等结构化业务工具，形成“知识库 + 工具调用”的混合问答能力。

### 可替换基础设施

项目对外部依赖做了适配层隔离：

- LLM：支持 Ollama、百炼、AIHubMix、SiliconFlow 等 OpenAI 风格接口。
- Embedding：支持远程 embedding，也提供确定性 hash embedding fallback。
- Rerank：支持外部 rerank，也可降级为原始顺序。
- Vector Store：支持 Milvus；不可用时回退到本地仓储检索。
- Object Storage：支持 S3 兼容对象存储；不可用时保持主流程可继续。
- Task State / Store：支持本地内存态，便于开发和测试。

这种设计让项目可以先在本地完整跑通，再逐步替换为 PostgreSQL、Redis、Milvus、S3 兼容存储和真实模型服务。

### RAG 可观测性

系统会记录 RAG 运行过程中的关键节点，包括：

- 查询改写与问题拆分。
- 意图识别。
- 多通道召回。
- MCP 工具调用。
- Prompt 渲染。
- LLM 生成。

管理端可以查看 trace run 和 trace node，用于定位“为什么这次回答不好”。这比只看最终答案更适合做质量分析，也更能体现工程深度。

## 架构概览

```text
                    React + Vite 管理台 / 聊天前端
                                |
                                v
                         FastAPI 主服务
                                |
        -------------------------------------------------
        |              |                |               |
      Auth           Chat          Knowledge        Admin / Trace
        |              |                |               |
        |              v                v               v
        |        RAG Pipeline     Ingestion Pipeline   Ops APIs
        |              |                |
        |              v                v
        |       LLM / Embedding   Object Storage
        |       Rerank Adapter    Vector Store
        |              |
        v              v
   Repository     MCP Compatible Service
        |
        v
 Local Store / SQLAlchemy-compatible Repository
```

## 技术栈

### 后端

- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- httpx
- pytest

### 前端

- React 18
- TypeScript
- Vite
- Tailwind CSS
- Radix UI
- Zustand
- React Router
- Recharts

### AI 与基础设施

- OpenAI-style Chat Completion / Embedding API
- Ollama / 百炼 / AIHubMix / SiliconFlow Provider 适配
- Milvus 向量检索适配
- S3 兼容对象存储适配
- MCP 兼容工具服务

## 目录结构

```text
app/
  api/          认证、聊天、知识库、摄取、RAG 管理、仪表盘和 Trace API
  core/         配置、认证、响应封装、ID、异常处理
  db/           SQLAlchemy 模型与兼容仓储
  infra/        LLM、embedding、rerank、向量库、对象存储、任务状态适配
  ingestion/    文档摄取流水线
  knowledge/    知识文档摄取服务
  rag/          查询改写、意图识别、检索、Prompt、会话记忆、流式编排
  services/     本地共享存储辅助逻辑

frontend/
  src/          React 页面、组件、状态管理、API service、后台管理台

mcp_server/     MCP 兼容 FastAPI 服务
resources/      RAG Prompt 模板
tests/          API、RAG、MCP、管理接口和基础设施 fallback 测试
```

## 面试可讲点

### 1. 为什么不是简单 RAG Demo

LeanRAG 把 RAG 拆成可观察、可替换的多个阶段。面试时可以重点讲“从用户问题到最终答案，每一步如何影响回答质量”，以及 trace 如何帮助定位问题。

### 2. 如何处理召回不稳定

项目没有只依赖单一路径召回，而是做了意图定向召回、全局向量补召、去重和 rerank。可以展开讲 query 改写、意图置信度、topK 策略和上下文质量之间的关系。

### 3. 如何保证本地开发可运行

真实 RAG 项目依赖很多外部服务。LeanRAG 通过模型 fallback、hash embedding、本地向量仓储和对象存储降级，让核心接口、测试和前端流程不依赖完整生产环境。

### 4. 如何把 RAG 做成产品能力

知识库管理、文档摄取、chunk 预览、意图树、查询词映射、示例问题、系统设置、Trace 页面都进入管理台。可以说明你考虑的不只是算法效果，还有运营和排障。

### 5. 如何设计可扩展边界

模型 Provider、向量库、对象存储、MCP 工具都通过适配器接入。后续替换外部服务时，不需要重写业务 API 和前端流程。

## 本地启动

### 1. 准备环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

```powershell
cd frontend
npm install
```

新增前端依赖时优先使用 `pnpm`。

### 2. 配置环境变量

复制 `.env.example`：

```powershell
Copy-Item .env.example .env
```

关键配置包括：

- 主 API 地址与端口。
- 数据库连接。
- Redis 连接。
- MCP 服务地址。
- Chat / Embedding / Rerank Provider。
- Milvus 与对象存储配置。

未配置远程模型 Provider 时，系统会使用本地 fallback，便于先验证接口、前端流程和 RAG 编排逻辑。

### 3. 启动后端 API

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 9090
```

### 4. 启动 MCP 服务

另开一个终端：

```powershell
python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 9099
```

### 5. 启动前端

```powershell
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:5173`，并将 `/api` 请求代理到 `http://localhost:9090`。

## 测试

后端测试：

```powershell
pytest
```

前端构建：

```powershell
cd frontend
npm run build
```

仓库约定：修改 JavaScript 文件后需要运行 `npm test`。当前 README 更新只涉及 Markdown 文档，不需要运行该命令。

## 项目边界

LeanRAG 当前重点是 RAG 工程链路和可运营后台，不追求把所有生产基础设施都内置到本仓库。生产部署时建议替换或补齐：

- 持久化数据库。
- 分布式任务队列。
- 稳定的向量数据库。
- 对象存储。
- 真实模型 Provider。
- 权限、审计、限流和监控体系。

这个边界也是项目设计的一部分：核心业务流程先保持清晰，外部基础设施通过适配层逐步增强。
