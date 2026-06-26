# After-Sales Customer Support RAG Implementation Plan

> **For AI agents:** Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to execute this plan. Track progress with checkbox syntax (`- [ ]`). This document is a planning artifact only; it does not modify application code.

**Goal:** Transform LeanRAG from a general-purpose RAG demo into an enterprise after-sales and customer-support knowledge assistant.

**Architecture:** Preserve the existing FastAPI + React + RAG pipeline architecture. Domain specialization should happen through prompts, seeded support data, intent-tree configuration, MCP-style business tools, UI wording, and focused trace/quality views before adding new infrastructure.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, React 18, TypeScript, Vite, Tailwind CSS, Zustand, OpenAI-style LLM/embedding adapters, MCP-compatible service adapters.

---

## Product Direction

The target product is an enterprise after-sales support assistant for customer-service representatives, support engineers, and support-operation managers.

It should answer questions from product manuals, FAQ documents, warranty policies, return policies, troubleshooting SOPs, service-center rules, and ticket/system data. The assistant should not only return a natural-language answer; it should explain the basis, suggest the next support action, and leave a trace that operators can inspect when answer quality is poor.

Recommended product name for the first iteration: **AfterSales Copilot**.

## Version Roadmap

### V0: Domain Planning And Demo Dataset

**Purpose:** Make the target domain concrete before touching runtime behavior.

**Outcome:** The project has a clear after-sales support domain model, demo dataset, sample questions, and acceptance criteria.

**Scope:**
- Define after-sales personas and workflows.
- Define domain vocabulary.
- Prepare demo knowledge documents.
- Prepare representative sample questions.
- Define answer-quality rules.

**Not in scope:**
- Runtime code changes.
- New database tables.
- Production integrations.

**Exit criteria:**
- A support-domain specification exists.
- Demo documents are realistic enough to exercise FAQ, policy, troubleshooting, and ticket-style queries.
- Each sample question maps to an expected route: knowledge-only, tool-only, mixed knowledge + tool, or clarification.

### V1: Customer-Support RAG Shell

**Purpose:** Rebrand and configure the existing application as a customer-support assistant without changing the core RAG architecture.

**Outcome:** Users experience the system as an after-sales support assistant instead of a generic RAG application.

**Scope:**
- Update frontend labels and navigation wording.
- Add support-specific welcome text and sample questions.
- Add support-specific system prompts.
- Seed initial support intent tree.
- Seed support terminology mappings.
- Use existing trace pages as answer-debugging views.

**Not in scope:**
- Real ticket-system integration.
- Complex case management.
- Agent handoff workflow.

**Exit criteria:**
- A user can open the chat page and see support-focused prompts.
- A support FAQ question returns a structured support answer.
- A warranty-policy question retrieves relevant policy content.
- Trace shows rewrite, intent, retrieval, prompt, and generation nodes for support questions.

### V2: Mock Business Tools Through MCP

**Purpose:** Demonstrate business-system integration using mock MCP tools.

**Outcome:** The assistant can answer questions that require structured business data, not just static documents.

**Scope:**
- Add mock tools for ticket status, warranty status, service-center lookup, and product lookup.
- Configure intent nodes to route suitable questions to mock tools.
- Teach prompts to distinguish tool results from knowledge-base content.
- Expand trace details for tool calls.

**Not in scope:**
- Authentication against real CRM, ERP, or ticket systems.
- Durable ticket creation.
- Real PII handling beyond demo-safe mock data.

**Exit criteria:**
- "What is the status of ticket T-10001?" calls a mock ticket tool.
- "Is serial number SN-X100-2026-0001 still under warranty?" calls a warranty tool.
- "Where can I repair product X100 in Shanghai?" calls a service-center tool.
- Mixed questions combine policy documents and tool results in one answer.

### V3: Support Operations Console

**Purpose:** Turn the admin area into a support-operations console.

**Outcome:** Support leads can inspect, tune, and improve customer-support answers using existing knowledge, intent, sample question, terminology, and trace features.

**Scope:**
- Rename admin sections to support-domain terms.
- Add support-specific filters to trace and knowledge views.
- Add answer-quality review fields if the current feedback model is insufficient.
- Add operational dashboards for common intents, no-answer rate, tool-call rate, and low-confidence retrieval.
- Document a knowledge-maintenance workflow.

**Not in scope:**
- Full analytics warehouse.
- Role-specific permission model beyond the existing auth pattern.
- Human-agent ticket queue.

**Exit criteria:**
- Operators can find failed or low-quality support answers.
- Operators can identify whether the issue came from intent classification, retrieval, prompt rendering, tool output, or generation.
- Operators can map a poor answer to a concrete remediation: add document, edit chunk, add term mapping, adjust intent examples, or improve prompt.

### V4: Production Readiness

**Purpose:** Prepare the after-sales assistant for a real enterprise pilot.

**Outcome:** The system has stronger safety, compliance, integration, and operational controls.

**Scope:**
- Add source citation and answer-grounding rules.
- Add sensitive-data handling rules.
- Add escalation and refusal policies.
- Integrate real CRM/ticket/warranty systems through replaceable adapters.
- Add audit logs for tool calls and support decisions.
- Add regression evaluation sets for support questions.

**Not in scope:**
- Replacing the entire current repository architecture.
- Building a full CRM.
- Building a full contact-center platform.

**Exit criteria:**
- A support manager can run a regression suite before updating prompts or knowledge.
- Tool calls are auditable.
- Answers clearly state when they are based on policy, tool data, or missing information.
- The assistant has a defined escalation policy for ambiguous, high-risk, or customer-sensitive cases.

---

## Target Domain Model

### Core Concepts

- **Customer:** The person asking for support.
- **Support Agent:** The internal user using the assistant to answer customers.
- **Product:** A sellable or serviceable item.
- **Product Model:** A product family or model, such as `X100`.
- **Serial Number:** A unique identifier used for warranty and batch lookup.
- **Warranty:** Coverage status, start/end dates, and exclusion rules.
- **Ticket:** A support request tracked in a business system.
- **Fault Code:** A structured error code from a product.
- **Troubleshooting SOP:** A step-by-step diagnostic process.
- **Service Center:** A repair or service location.
- **Escalation:** Transfer to human expert, field engineer, or higher support tier.

### Supported Question Types

- Product usage questions.
- Fault-code explanation.
- Troubleshooting guidance.
- Warranty and return-policy questions.
- Ticket-status questions.
- Service-center lookup.
- Product compatibility questions.
- Accessory and spare-part questions.
- Escalation and handoff questions.

### Answer Categories

- **Knowledge-only:** Answer from manuals, FAQs, policies, or SOPs.
- **Tool-only:** Answer from a business system, such as ticket status.
- **Mixed:** Combine policy documents with tool results.
- **Clarification required:** Ask for serial number, product model, ticket ID, fault code, city, or purchase date.
- **Escalation required:** Advise human handling due to safety, legal, payment, privacy, or severe product failure.

---

## Answer Contract

The assistant should produce predictable support answers. For most questions, use this structure:

```text
Conclusion:
Give the direct answer.

Basis:
List the document, policy, SOP, or tool result used.

Steps:
Give actionable steps for the customer or support agent.

Need To Confirm:
List missing information, if any.

Escalation:
State whether human escalation is recommended and why.
```

For troubleshooting questions, use this structure:

```text
Likely Causes:
List the most probable causes.

Customer Checks:
Steps the customer can safely perform.

Support-Agent Checks:
Steps intended for internal support or field engineers.

Escalation Conditions:
When the case must be escalated.

Basis:
List matched SOPs, fault-code documents, or tool results.
```

The final Chinese UI/output can localize these headings as:

- `结论`
- `依据`
- `处理步骤`
- `需要确认`
- `是否建议转人工`
- `可能原因`
- `客户可自行操作`
- `客服/工程师排查`
- `升级工单条件`

---

## Proposed File Responsibilities

This plan intentionally separates domain configuration from core RAG behavior where possible.

### Planning And Documentation

- `docs/superpowers/plans/2026-06-26-after-sales-customer-support-rag.md`
  - Owns this roadmap and execution plan.

- `docs/after-sales/domain-model.md`
  - Defines support-domain objects, terms, question types, and answer rules.

- `docs/after-sales/demo-script.md`
  - Defines demo user flows and expected outputs for each version.

- `docs/after-sales/ops-playbook.md`
  - Explains how support operators maintain documents, chunks, intents, terms, sample questions, and answer traces.

### Demo Data

- `resources/demo/after-sales/faq.md`
  - Product FAQ document for ingestion.

- `resources/demo/after-sales/warranty-policy.md`
  - Warranty and repair policy document for ingestion.

- `resources/demo/after-sales/return-policy.md`
  - Return and exchange policy document for ingestion.

- `resources/demo/after-sales/troubleshooting-x100.md`
  - Fault-code and troubleshooting SOP document for ingestion.

- `resources/demo/after-sales/service-center-policy.md`
  - Service-center rules and appointment policy document for ingestion.

- `resources/demo/after-sales/sample-questions.json`
  - Seed data for support-focused sample questions.

- `resources/demo/after-sales/intent-tree.json`
  - Seed data for support intent nodes.

- `resources/demo/after-sales/query-term-mappings.json`
  - Seed data for support synonym and terminology mappings.

### Prompt Templates

- `resources/prompt/after-sales-answer-chat-system.st`
  - Support-specific answer policy and response contract.

- `resources/prompt/after-sales-guidance-prompt.st`
  - Clarification prompt for ambiguous support questions.

- `resources/prompt/after-sales-mcp-parameter-extract.st`
  - Parameter extraction rules for ticket ID, serial number, city, product model, and fault code.

### Backend

- `app/rag/prompt.py`
  - Selects support-domain prompt templates when after-sales mode is enabled.

- `app/rag/intent.py`
  - Uses support intent examples and node configuration without changing the resolver contract.

- `app/rag/retrieval.py`
  - Preserves current retrieval engine; only adjust support-specific metadata handling if required.

- `mcp_server/main.py`
  - Adds mock after-sales tool endpoints for V2.

- `app/db/repository.py`
  - Adds seed helpers only if existing CRUD APIs cannot load demo data conveniently.

### Frontend

- `frontend/src/components/chat/WelcomeScreen.tsx`
  - Shows support-specific examples and positioning.

- `frontend/src/components/chat/MessageItem.tsx`
  - Keeps answer rendering stable for structured support headings.

- `frontend/src/pages/admin/AdminLayout.tsx`
  - Renames generic admin sections to support-operations language.

- `frontend/src/pages/admin/traces/RagTracePage.tsx`
  - Presents RAG trace as support answer diagnostics.

- `frontend/src/pages/admin/intent-tree/IntentTreePage.tsx`
  - Keeps current intent-tree management; update labels only where needed.

### Tests

- `tests/test_after_sales_prompts.py`
  - Verifies support prompt rendering and required answer rules.

- `tests/test_after_sales_intent_seed.py`
  - Verifies support intent-tree seed shape and required nodes.

- `tests/test_after_sales_mcp_tools.py`
  - Verifies mock tool behavior.

- `tests/test_after_sales_rag_flow.py`
  - Verifies knowledge-only, tool-only, mixed, clarification, and escalation flows.

- `frontend/src/**`
  - If JavaScript or TypeScript files are modified, run `npm test` as required by the project working agreement. If no `npm test` script exists at execution time, add or clarify the test script before claiming frontend test completion.

---

## V0 Tasks: Domain Planning And Demo Dataset

### Task 0.1: Create Domain Documentation

**Files:**
- Create: `docs/after-sales/domain-model.md`
- Create: `docs/after-sales/demo-script.md`
- Create: `docs/after-sales/ops-playbook.md`

- [x] Write `domain-model.md` with personas, domain terms, question categories, answer categories, and escalation rules.
- [x] Write `demo-script.md` with at least 12 end-to-end demo questions:
  - 3 FAQ questions.
  - 2 warranty-policy questions.
  - 2 troubleshooting questions.
  - 2 ticket-status questions.
  - 1 service-center question.
  - 1 ambiguous question requiring clarification.
  - 1 escalation-required question.
- [x] Write `ops-playbook.md` explaining how operators should improve a poor answer using knowledge documents, chunks, intent nodes, term mappings, sample questions, and trace.
- [x] Review the documents and remove vague placeholders. Use concrete example product names, serial numbers, ticket IDs, and cities.

**Validation:**
- Run: `rg "placeholder|fill-me" docs/after-sales`
- Expected: no matches.

### Task 0.2: Prepare Demo Knowledge Documents

**Files:**
- Create: `resources/demo/after-sales/faq.md`
- Create: `resources/demo/after-sales/warranty-policy.md`
- Create: `resources/demo/after-sales/return-policy.md`
- Create: `resources/demo/after-sales/troubleshooting-x100.md`
- Create: `resources/demo/after-sales/service-center-policy.md`

- [x] Write a product FAQ for product model `X100`.
- [x] Write a warranty policy with coverage periods, exclusions, and required proof.
- [x] Write a return policy with return window, non-returnable cases, and inspection flow.
- [x] Write troubleshooting SOPs for at least four fault codes: `E01`, `E17`, `E37`, and `N04`.
- [x] Write service-center policy with city lookup assumptions, appointment rules, and repair lead time.
- [x] Ensure each document contains headings that chunking can preserve.

**Validation:**
- Run: `rg "X100|E01|E17|E37|N04|warranty|return|service center" resources/demo/after-sales`
- Expected: all required terms appear in relevant files.

### Task 0.3: Define Seed Data Contracts

**Files:**
- Create: `resources/demo/after-sales/sample-questions.json`
- Create: `resources/demo/after-sales/intent-tree.json`
- Create: `resources/demo/after-sales/query-term-mappings.json`

- [x] Add sample questions with title, description, question text, and enabled state.
- [x] Add intent-tree seed nodes using existing fields:
  - `intentCode`
  - `name`
  - `level`
  - `parentCode`
  - `description`
  - `examples`
  - `kind`
  - `mcpToolId`
  - `promptSnippet`
  - `topK`
  - `sortOrder`
  - `enabled`
- [x] Add query-term mappings for colloquial support language:
  - `打不开` -> `无法启动`
  - `坏了` -> `故障`
  - `黑屏` -> `显示异常`
  - `退货` -> `退换货政策`
  - `修一下` -> `维修服务`
  - `保不保` -> `保修状态`
- [x] Validate JSON syntax.

**Validation:**
- Run: `python -m json.tool resources/demo/after-sales/sample-questions.json`
- Run: `python -m json.tool resources/demo/after-sales/intent-tree.json`
- Run: `python -m json.tool resources/demo/after-sales/query-term-mappings.json`
- Expected: each command exits successfully.

---

## V1 Tasks: Customer-Support RAG Shell

### Task 1.1: Add Support Prompt Templates

**Files:**
- Create: `resources/prompt/after-sales-answer-chat-system.st`
- Create: `resources/prompt/after-sales-guidance-prompt.st`
- Create: `resources/prompt/after-sales-mcp-parameter-extract.st`
- Modify: `app/rag/prompt.py`
- Test: `tests/test_after_sales_prompts.py`

- [x] Write a failing test that renders the support answer prompt and asserts it contains required sections:
  - conclusion
  - basis
  - steps
  - missing information
  - escalation
- [x] Add support prompt templates.
- [x] Update prompt selection so after-sales mode can use the support prompt without removing the generic prompt.
- [x] Run the prompt test and confirm it passes.

**Validation:**
- Run: `pytest tests/test_after_sales_prompts.py -v`
- Expected: pass.

### Task 1.2: Seed Support Intents And Terms

**Files:**
- Modify: `app/db/repository.py` only if a seed helper is needed.
- Test: `tests/test_after_sales_intent_seed.py`
- Data: `resources/demo/after-sales/intent-tree.json`
- Data: `resources/demo/after-sales/query-term-mappings.json`

- [x] Write tests that load seed JSON and verify required root intents:
  - `after_sales.product_usage`
  - `after_sales.troubleshooting`
  - `after_sales.warranty`
  - `after_sales.return_exchange`
  - `after_sales.service_center`
  - `after_sales.ticket_status`
  - `after_sales.escalation`
- [x] Verify troubleshooting child intents include fault-code lookup and cannot-start flow.
- [x] Verify tool-backed intents include a non-empty `mcpToolId`.
- [x] Add seed-loading documentation or helper if existing admin APIs are insufficient for loading the JSON.

**Validation:**
- Run: `pytest tests/test_after_sales_intent_seed.py -v`
- Expected: pass.

### Task 1.3: Rebrand Frontend Shell

**Files:**
- Modify: `frontend/src/components/chat/WelcomeScreen.tsx`
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Modify: `frontend/src/pages/admin/AdminLayout.tsx`
- Modify: `frontend/src/pages/admin/dashboard/DashboardPage.tsx`

- [x] Replace generic RAG copy with support-assistant copy.
- [x] Use sample questions from support seed data where the current UI supports samples.
- [x] Rename admin sections:
  - `知识库` -> `售后知识库`
  - `意图树` -> `问题分类`
  - `术语映射` -> `客服术语映射`
  - `链路追踪` -> `回答诊断`
  - `样例问题` -> `客服示例问题`
- [x] Preserve existing routes unless there is a strong reason to migrate paths.

**Validation:**
- Run: `cd frontend; npm run build`
- Run after JavaScript/TypeScript modifications: `cd frontend; npm test`
- Expected: build succeeds; `npm test` succeeds or the executor explicitly documents that no test script existed before adding one.

### Task 1.4: Validate Knowledge-Only Support Flow

**Files:**
- Test: `tests/test_after_sales_rag_flow.py`
- Data: `resources/demo/after-sales/*.md`

- [x] Add a test or scripted validation for a FAQ question.
- [x] Add a test or scripted validation for a warranty-policy question.
- [x] Add a test or scripted validation for a troubleshooting question.
- [x] Assert that each answer includes support-style sections and a trace record.

**Validation:**
- Run: `pytest tests/test_after_sales_rag_flow.py -v`
- Expected: pass.

---

## V2 Tasks: Mock Business Tools Through MCP

### Task 2.1: Add Mock Tool Contracts

**Files:**
- Modify: `mcp_server/main.py`
- Create: `docs/after-sales/mock-tool-contracts.md`
- Test: `tests/test_after_sales_mcp_tools.py`

- [x] Document mock tool contracts:
  - `get_ticket_status(ticket_id)`
  - `get_warranty_status(serial_number)`
  - `find_service_center(city, product_model)`
  - `get_product_by_serial(serial_number)`
- [x] Add deterministic mock responses using demo IDs:
  - `T-10001`
  - `T-10002`
  - `SN-X100-2026-0001`
  - `SN-X100-2024-0099`
- [x] Add tests for success and not-found cases.

**Validation:**
- Run: `pytest tests/test_after_sales_mcp_tools.py -v`
- Expected: pass.

### Task 2.2: Configure Tool-Backed Intent Nodes

**Files:**
- Modify: `resources/demo/after-sales/intent-tree.json`
- Modify: `resources/prompt/after-sales-mcp-parameter-extract.st`
- Test: `tests/test_after_sales_intent_seed.py`
- Test: `tests/test_after_sales_rag_flow.py`

- [x] Ensure ticket-status intent routes to `get_ticket_status`.
- [x] Ensure warranty-status intent routes to `get_warranty_status`.
- [x] Ensure service-center intent routes to `find_service_center`.
- [x] Ensure serial-number product lookup routes to `get_product_by_serial`.
- [x] Add parameter-extraction examples for ticket ID, serial number, city, and product model.

**Validation:**
- Run: `pytest tests/test_after_sales_intent_seed.py tests/test_after_sales_rag_flow.py -v`
- Expected: pass.

### Task 2.3: Validate Tool-Only And Mixed Flows

**Files:**
- Test: `tests/test_after_sales_rag_flow.py`
- Modify: `app/rag/pipeline.py` only if the current pipeline cannot preserve required tool context in answers.
- Modify: `app/rag/retrieval.py` only if tool results are not exposed cleanly to prompt rendering.

- [x] Add a test for ticket-status tool-only flow.
- [x] Add a test for warranty-status tool-only flow.
- [x] Add a test for mixed flow: "SN-X100-2024-0099 is already out of warranty. Can it still be repaired?"
- [x] Assert the mixed answer cites both tool result and policy content.
- [x] Assert trace includes a tool-call node.

**Validation:**
- Run: `pytest tests/test_after_sales_rag_flow.py -v`
- Expected: pass.

---

## V3 Tasks: Support Operations Console

### Task 3.1: Convert Trace To Answer Diagnostics

**Files:**
- Modify: `frontend/src/pages/admin/traces/RagTracePage.tsx`
- Modify: `frontend/src/pages/admin/traces/RagTraceDetailPage.tsx`
- Modify: `frontend/src/pages/admin/traces/components/RunsTable.tsx`
- Modify: `frontend/src/pages/admin/traces/traceUtils.ts`

- [x] Rename trace list terminology to support answer diagnostics.
- [x] Highlight diagnostic stages:
  - question rewrite
  - intent classification
  - knowledge retrieval
  - tool call
  - prompt rendering
  - model generation
- [x] Add empty states and failure hints using support-operations language.
- [x] Keep existing API contracts unless backend data is insufficient.

**Validation:**
- Run: `cd frontend; npm run build`
- Run after JavaScript/TypeScript modifications: `cd frontend; npm test`
- Expected: build succeeds; frontend tests pass or missing test script is handled.

### Task 3.2: Add Support Quality Metrics

**Files:**
- Modify: `app/db/repository.py`
- Modify: `app/api/rag_admin.py` or existing trace/admin endpoint file that owns trace reporting.
- Modify: `frontend/src/pages/admin/dashboard/DashboardPage.tsx`
- Test: `tests/test_management_api.py`

- [x] Add API-level aggregation for:
  - total support questions
  - no-answer count
  - tool-call count
  - escalation count
  - top intents
  - recent low-quality feedback
- [x] Render metrics in the dashboard using existing chart/card patterns.
- [x] Keep metric calculations simple and derived from existing repository data first.

**Validation:**
- Run: `pytest tests/test_management_api.py -v`
- Run: `cd frontend; npm run build`
- Run after JavaScript/TypeScript modifications: `cd frontend; npm test`
- Expected: pass.

### Task 3.3: Document Operations Workflow

**Files:**
- Modify: `docs/after-sales/ops-playbook.md`

- [x] Add a workflow for fixing wrong answers caused by missing documents.
- [x] Add a workflow for fixing wrong answers caused by bad chunks.
- [x] Add a workflow for fixing wrong answers caused by wrong intent classification.
- [x] Add a workflow for fixing wrong answers caused by missing term mappings.
- [x] Add a workflow for fixing wrong answers caused by bad tool output.

**Validation:**
- Run: `rg "missing documents|bad chunks|intent classification|term mappings|tool output" docs/after-sales/ops-playbook.md`
- Expected: all workflow topics appear.

---

## V4 Tasks: Production Readiness

### Task 4.1: Add Grounding And Citation Policy

**Files:**
- Modify: `resources/prompt/after-sales-answer-chat-system.st`
- Modify: `app/rag/prompt.py`
- Test: `tests/test_after_sales_prompts.py`
- Test: `tests/test_after_sales_rag_flow.py`

- [x] Require answers to separate document basis from tool basis.
- [x] Require "insufficient information" when neither document nor tool data supports the answer.
- [x] Require explicit escalation for safety, legal, payment, privacy, or severe-product-failure cases.
- [x] Add regression tests for unsupported claims and escalation.

**Validation:**
- Run: `pytest tests/test_after_sales_prompts.py tests/test_after_sales_rag_flow.py -v`
- Expected: pass.

### Task 4.2: Add Audit Logging For Tool Calls

**Files:**
- Modify: `app/db/models.py`
- Modify: `app/db/repository.py`
- Modify: `app/rag/retrieval.py`
- Test: `tests/test_after_sales_mcp_tools.py`
- Test: `tests/test_after_sales_rag_flow.py`

- [x] Add a minimal tool-call audit model only if existing trace nodes cannot satisfy audit needs.
- [x] Record tool ID, sanitized parameters, response status, duration, user ID, conversation ID, and trace ID.
- [x] Avoid storing sensitive raw customer data unless explicitly required.
- [x] Expose audit data through trace detail where appropriate.

**Validation:**
- Run: `pytest tests/test_after_sales_mcp_tools.py tests/test_after_sales_rag_flow.py -v`
- Expected: pass.

### Task 4.3: Add Regression Evaluation Set

**Files:**
- Create: `resources/demo/after-sales/eval-set.json`
- Create: `tests/test_after_sales_eval_set.py`

- [x] Define at least 30 evaluation cases:
  - 8 FAQ cases.
  - 6 troubleshooting cases.
  - 5 policy cases.
  - 5 tool cases.
  - 3 mixed cases.
  - 3 refusal/escalation cases.
- [x] For each case, include expected route, required answer sections, required citations/tool basis, and forbidden claims.
- [x] Add tests that validate eval-set schema.
- [x] Add a lightweight runner or test helper that can execute the set against deterministic fallback behavior where possible.

**Validation:**
- Run: `python -m json.tool resources/demo/after-sales/eval-set.json`
- Run: `pytest tests/test_after_sales_eval_set.py -v`
- Expected: pass.

---

## Test Strategy

### Backend

Run focused tests per version, then the full backend suite:

```powershell
pytest tests/test_after_sales_prompts.py -v
pytest tests/test_after_sales_intent_seed.py -v
pytest tests/test_after_sales_mcp_tools.py -v
pytest tests/test_after_sales_rag_flow.py -v
pytest
```

### Frontend

Any change under `frontend/src` or other JavaScript/TypeScript files must respect the project agreement:

```powershell
cd frontend
npm run build
npm test
```

If `npm test` is not defined when execution begins, the implementer must either add an appropriate test script or explicitly stop and ask how the project wants frontend tests to run.

### Manual Demo Validation

Use these demo questions as smoke tests:

```text
X100 第一次使用前需要做什么？
X100 显示 E37 是什么意思？
我的 SN-X100-2026-0001 还在保修期吗？
工单 T-10001 现在处理到哪一步了？
上海哪里可以维修 X100？
我的设备坏了，能退吗？
机器冒烟了，我还能继续通电测试吗？
```

Expected behavior:
- FAQ and policy questions cite documents.
- Serial number, ticket, and service-center questions use tools.
- Ambiguous questions ask for missing information.
- Safety-sensitive questions recommend escalation and avoid risky instructions.

---

## Release Plan

### V0 Release

- Commit only documentation and demo data.
- No runtime behavior changes.
- Use this version to confirm product scope with stakeholders.

### V1 Release

- Commit prompt, seed, and UI wording changes.
- Demo knowledge-only support answers.
- Verify backend tests and frontend build/test requirements.

### V2 Release

- Commit mock MCP tools and tool-backed intent configuration.
- Demo ticket, warranty, service-center, and mixed answers.
- Verify trace includes tool-call context.

### V3 Release

- Commit support-operations console wording and quality metrics.
- Demo how an operator diagnoses and fixes a poor answer.

### V4 Release

- Commit production-readiness controls, audit logging, and regression evals.
- Use this version as the pilot-readiness baseline.

---

## Risks And Mitigations

### Risk: Scope Expands Into Full CRM

Mitigation: Keep CRM and ticket systems as external tools. The assistant should query and summarize business data; it should not become the system of record.

### Risk: Answers Overclaim Beyond Sources

Mitigation: Add grounding rules, unsupported-answer tests, citation expectations, and escalation policies in V4.

### Risk: Demo Data Feels Artificial

Mitigation: Make the demo documents internally consistent with concrete product models, serial numbers, ticket IDs, policy dates, and fault codes.

### Risk: Intent Tree Becomes Hard To Maintain

Mitigation: Keep V1 intent tree shallow. Add depth only when trace data shows a real classification need.

### Risk: Frontend Renaming Breaks Generic Reusability

Mitigation: Prefer labels and configuration over route or component rewrites. Preserve generic components where possible.

---

## Execution Recommendation

Start with V0 and V1. They provide the highest product-perception improvement with the least architectural risk.

Only start V2 after V1 can reliably answer knowledge-only support questions. Only start V3 after trace output is useful enough to diagnose at least three intentionally bad answers. Only start V4 when the project needs a real enterprise pilot rather than a polished demo.
