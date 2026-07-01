from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from typing import Any

from app.core.ids import new_id
from app.ingestion.pipeline import split_paragraphs


DEFAULT_INTENT_NODES: list[dict[str, Any]] = [
    {
        "id": "intent-chat-general",
        "intentCode": "chat.general",
        "name": "闲聊",
        "level": 1,
        "parentCode": None,
        "description": "问候、感谢、身份询问、寒暄和其他不需要检索业务知识或订单数据的问题。",
        "examples": "你好；谢谢；你是谁；再见；哈哈",
        "kind": "system",
        "sortOrder": 10,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce",
        "intentCode": "kb.ecommerce",
        "name": "电商领域知识库查询",
        "level": 1,
        "parentCode": None,
        "description": "电商平台规则、政策、商品服务说明和售后流程类问题，需要通过知识库回答。",
        "examples": "退货规则是什么；运费险怎么赔；发票怎么开；会员权益有哪些",
        "kind": "kb",
        "sortOrder": 20,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce-refund-policy",
        "intentCode": "kb.ecommerce.refund_policy",
        "name": "退换货与退款规则",
        "level": 2,
        "parentCode": "kb.ecommerce",
        "description": "退货、换货、仅退款、退货退款、七天无理由、退款时效、售后条件等规则说明。",
        "examples": "退货规则是什么；支持七天无理由吗；退款多久到账；什么情况不能退货",
        "kind": "kb",
        "sortOrder": 21,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce-shipping-policy",
        "intentCode": "kb.ecommerce.shipping_policy",
        "name": "发货物流规则",
        "level": 2,
        "parentCode": "kb.ecommerce",
        "description": "发货时效、配送范围、快递方式、运费、包邮门槛、物流异常规则等说明。",
        "examples": "多久发货；包邮吗；配送范围有哪些；物流异常怎么办",
        "kind": "kb",
        "sortOrder": 22,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce-invoice-policy",
        "intentCode": "kb.ecommerce.invoice_policy",
        "name": "发票规则",
        "level": 2,
        "parentCode": "kb.ecommerce",
        "description": "电子发票、纸质发票、发票抬头、开票时间、补开发票、发票修改等规则。",
        "examples": "发票怎么开；能补开发票吗；发票抬头怎么改；电子发票在哪里下载",
        "kind": "kb",
        "sortOrder": 23,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce-product-service",
        "intentCode": "kb.ecommerce.product_service",
        "name": "商品与服务说明",
        "level": 2,
        "parentCode": "kb.ecommerce",
        "description": "商品规格、尺码、保修、安装、赠品、库存、适用场景、服务承诺等说明。",
        "examples": "这个商品保修多久；尺码怎么选；有没有赠品；商品支持安装吗",
        "kind": "kb",
        "sortOrder": 24,
        "enabled": 1,
    },
    {
        "id": "intent-kb-ecommerce-payment-promotion",
        "intentCode": "kb.ecommerce.payment_promotion",
        "name": "支付与优惠规则",
        "level": 2,
        "parentCode": "kb.ecommerce",
        "description": "支付方式、优惠券、满减、积分、会员权益、活动规则、价格保护等说明。",
        "examples": "优惠券怎么用；支持哪些支付方式；会员权益有哪些；保价规则是什么",
        "kind": "kb",
        "sortOrder": 25,
        "enabled": 1,
    },
    {
        "id": "intent-order-query",
        "intentCode": "order.query",
        "name": "订单信息查询",
        "level": 1,
        "parentCode": None,
        "description": "查询用户具体订单、物流、发货、退款、售后进度和订单地址等结构化业务数据。",
        "examples": "我的订单到哪了；帮我查退款进度；订单为什么还没发货；这个订单能不能改地址",
        "kind": "mcp",
        "mcpToolId": "order_query",
        "sortOrder": 30,
        "enabled": 1,
    },
    {
        "id": "intent-order-query-logistics",
        "intentCode": "order.query.logistics",
        "name": "物流状态查询",
        "level": 2,
        "parentCode": "order.query",
        "description": "查询具体订单物流轨迹、快递单号、预计送达、签收状态和配送异常。",
        "examples": "我的订单到哪了；物流怎么不更新；快递单号是多少；什么时候送到",
        "kind": "mcp",
        "mcpToolId": "order_query",
        "sortOrder": 31,
        "enabled": 1,
    },
    {
        "id": "intent-order-query-refund-status",
        "intentCode": "order.query.refund_status",
        "name": "退款售后进度查询",
        "level": 2,
        "parentCode": "order.query",
        "description": "查询具体订单的退款进度、退货退款状态、售后审核结果和平台介入进度。",
        "examples": "我的退款进度到哪了；售后审核通过了吗；退货退款处理到哪了；平台介入有结果吗",
        "kind": "mcp",
        "mcpToolId": "order_query",
        "sortOrder": 32,
        "enabled": 1,
    },
    {
        "id": "intent-order-query-fulfillment",
        "intentCode": "order.query.fulfillment",
        "name": "发货与订单状态查询",
        "level": 2,
        "parentCode": "order.query",
        "description": "查询订单是否付款、是否发货、发货延迟原因、订单取消和订单明细状态。",
        "examples": "订单为什么还没发货；我这个订单状态是什么；订单取消了吗；付款成功了吗",
        "kind": "mcp",
        "mcpToolId": "order_query",
        "sortOrder": 33,
        "enabled": 1,
    },
    {
        "id": "intent-order-query-address-change",
        "intentCode": "order.query.address_change",
        "name": "订单地址修改查询",
        "level": 2,
        "parentCode": "order.query",
        "description": "查询具体订单是否还能修改收货地址、联系电话或配送信息。",
        "examples": "这个订单能不能改地址；收货手机号能改吗；地址填错了怎么办",
        "kind": "mcp",
        "mcpToolId": "order_query",
        "sortOrder": 34,
        "enabled": 1,
    },
]


def now_text() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.knowledge_bases: dict[str, dict[str, Any]] = {}
        self.documents: dict[str, dict[str, Any]] = {}
        self.chunks: dict[str, dict[str, Any]] = {}
        self.sample_questions: dict[str, dict[str, Any]] = {}
        self.intent_nodes: dict[str, dict[str, Any]] = {}
        self.mappings: dict[str, dict[str, Any]] = {}
        self.feedbacks: dict[str, dict[str, Any]] = {}
        self.vectors: dict[str, dict[str, Any]] = {}
        self.pipelines: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}
        self.ingestion_task_nodes: dict[str, list[dict[str, Any]]] = {}
        self.document_chunk_logs: dict[str, list[dict[str, Any]]] = {}
        self.traces: dict[str, dict[str, Any]] = {}
        self.trace_nodes: dict[str, list[dict[str, Any]]] = {}
        self.conversation_summaries: dict[str, dict[str, Any]] = {}
        self._seed()

    def _seed(self) -> None:
        admin_id = "1"
        self.users[admin_id] = {
            "id": admin_id,
            "username": "admin",
            "password": "admin",
            "role": "admin",
            "avatar": None,
            "createTime": now_text(),
            "updateTime": now_text(),
        }
        qid = new_id()
        self.sample_questions[qid] = {
            "id": qid,
            "title": "Ragent",
            "description": "默认示例问题",
            "question": "Ragent AI 可以做什么？",
            "createTime": now_text(),
            "updateTime": now_text(),
        }

        for node in DEFAULT_INTENT_NODES:
            self.intent_nodes[node["id"]] = {
                **node,
                "createTime": now_text(),
                "updateTime": now_text(),
            }
        self._seed_ecommerce_knowledge()

    def _seed_ecommerce_knowledge(self) -> None:
        kb_id = "kb-ecommerce-demo"
        collection_name = "kb_ecommerce_demo"
        demo_dir = Path(__file__).resolve().parents[2] / "resources" / "demo" / "ecommerce"
        if not demo_dir.exists():
            return

        self.knowledge_bases[kb_id] = {
            "id": kb_id,
            "name": "电商客服知识库",
            "embeddingModel": "fallback-hash-embedding",
            "collectionName": collection_name,
            "createdBy": "system",
            "documentCount": 0,
            "createTime": now_text(),
            "updateTime": now_text(),
        }

        document_count = 0
        for doc_index, path in enumerate(sorted(demo_dir.glob("*.md"))):
            if path.name.lower() == "readme.md":
                continue
            content = path.read_text(encoding="utf-8").strip()
            if not content:
                continue
            doc_id = f"doc-ecommerce-{path.stem}"
            chunk_texts = split_paragraphs(content, target_chars=700, max_chars=1000, min_chars=250)
            chunks = [text for text in chunk_texts if text.strip()]
            self.documents[doc_id] = {
                "id": doc_id,
                "kbId": kb_id,
                "docName": path.name,
                "sourceType": "file",
                "sourceLocation": str(path.as_posix()),
                "fileUrl": str(path.as_posix()),
                "fileType": "md",
                "fileSize": len(content.encode("utf-8")),
                "status": "completed" if chunks else "failed",
                "chunkCount": len(chunks),
                "enabled": 1,
                "createdBy": "system",
                "processMode": "chunk",
                "chunkStrategy": "paragraph",
                "chunkConfig": '{"targetChars":700,"maxChars":1000,"minChars":250}',
                "createTime": now_text(),
                "updateTime": now_text(),
            }
            document_count += 1

            self.document_chunk_logs[doc_id] = [
                {
                    "id": f"log-{doc_id}",
                    "docId": doc_id,
                    "status": "completed" if chunks else "failed",
                    "processMode": "chunk",
                    "chunkStrategy": "paragraph",
                    "chunkConfig": '{"targetChars":700,"maxChars":1000,"minChars":250}',
                    "chunkCount": len(chunks),
                    "message": "Seed document chunking completed" if chunks else "No readable content found",
                    "createTime": now_text(),
                }
            ]

            for chunk_index, chunk_text in enumerate(chunks):
                chunk_id = f"chunk-ecommerce-{doc_index:02d}-{chunk_index:03d}"
                embedding = self._hash_embedding(chunk_text)
                chunk = {
                    "id": chunk_id,
                    "kbId": kb_id,
                    "docId": doc_id,
                    "chunkIndex": chunk_index,
                    "content": chunk_text,
                    "contentHash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                    "charCount": len(chunk_text),
                    "tokenCount": max(1, len(chunk_text) // 4),
                    "enabled": 1,
                    "createdBy": "system",
                    "embedding": embedding,
                    "createTime": now_text(),
                    "updateTime": now_text(),
                }
                self.chunks[chunk_id] = chunk
                self.vectors[chunk_id] = {
                    "id": chunk_id,
                    "content": chunk_text,
                    "metadata": {
                        "collection_name": collection_name,
                        "doc_id": doc_id,
                        "chunk_index": chunk_index,
                        "kb_id": kb_id,
                    },
                    "embedding": embedding,
                    "score": 1.0,
                }

        self.knowledge_bases[kb_id]["documentCount"] = document_count

    def _hash_embedding(self, text: str, dimension: int = 1536) -> list[float]:
        vector = [0.0] * dimension
        for idx, char in enumerate(text):
            bucket = (ord(char) + idx * 31) % dimension
            vector[bucket] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]

    def list_values(self, name: str) -> list[dict[str, Any]]:
        return [deepcopy(item) for item in getattr(self, name).values()]

    def get(self, name: str, item_id: str) -> dict[str, Any] | None:
        item = getattr(self, name).get(item_id)
        return deepcopy(item) if item else None

    def create(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        item_id = str(payload.get("id") or new_id())
        item = {"id": item_id, **payload, "createTime": now_text(), "updateTime": now_text()}
        getattr(self, name)[item_id] = item
        return deepcopy(item)

    def update(self, name: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        collection = getattr(self, name)
        item = collection.setdefault(item_id, {"id": item_id, "createTime": now_text()})
        item.update({k: v for k, v in payload.items() if v is not None})
        item["updateTime"] = now_text()
        return deepcopy(item)

    def delete(self, name: str, item_id: str) -> None:
        getattr(self, name).pop(item_id, None)


store = MemoryStore()
