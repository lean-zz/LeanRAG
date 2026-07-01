from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "t_user"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    username: Mapped[str] = mapped_column(String(64))
    password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))
    avatar: Mapped[str | None] = mapped_column(String(128))
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class KnowledgeBase(Base):
    __tablename__ = "t_knowledge_base"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    embedding_model: Mapped[str] = mapped_column(String(64))
    collection_name: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(20))
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class KnowledgeDocument(Base):
    __tablename__ = "t_knowledge_document"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(20))
    doc_name: Mapped[str] = mapped_column(String(256))
    file_url: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(16))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    chunk_config: Mapped[dict | None] = mapped_column(JSONB)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class KnowledgeChunk(Base):
    __tablename__ = "t_knowledge_chunk"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str] = mapped_column(String(20))
    doc_id: Mapped[str] = mapped_column(String(20))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class KnowledgeVector(Base):
    __tablename__ = "t_knowledge_vector"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    content: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)


class Conversation(Base):
    __tablename__ = "t_conversation"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(128))
    last_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class Message(Base):
    __tablename__ = "t_message"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    thinking_content: Mapped[str | None] = mapped_column(Text)
    thinking_duration: Mapped[int | None] = mapped_column(Integer)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class IntentNode(Base):
    __tablename__ = "t_intent_node"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    kb_id: Mapped[str | None] = mapped_column(String(20))
    intent_code: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(128))
    level: Mapped[int | None] = mapped_column(Integer)
    parent_code: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    examples: Mapped[str | None] = mapped_column(Text)
    collection_name: Mapped[str | None] = mapped_column(String(64))
    top_k: Mapped[int | None] = mapped_column(Integer)
    mcp_tool_id: Mapped[str | None] = mapped_column(String(64))
    kind: Mapped[str | None] = mapped_column(String(32))
    prompt_snippet: Mapped[str | None] = mapped_column(Text)
    prompt_template: Mapped[str | None] = mapped_column(Text)
    param_prompt_template: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class QueryTermMapping(Base):
    __tablename__ = "t_query_term_mapping"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    domain: Mapped[str | None] = mapped_column(String(64))
    source_term: Mapped[str | None] = mapped_column(String(128))
    target_term: Mapped[str | None] = mapped_column(String(128))
    match_type: Mapped[str | None] = mapped_column(String(32))
    priority: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)
    remark: Mapped[str | None] = mapped_column(String(512))
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class SampleQuestion(Base):
    __tablename__ = "t_sample_question"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))
    question: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class IngestionPipeline(Base):
    __tablename__ = "t_ingestion_pipeline"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(512))
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class IngestionPipelineNode(Base):
    __tablename__ = "t_ingestion_pipeline_node"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    pipeline_id: Mapped[str] = mapped_column(String(20))
    node_id: Mapped[str | None] = mapped_column(String(64))
    node_type: Mapped[str | None] = mapped_column(String(64))
    next_node_id: Mapped[str | None] = mapped_column(String(64))
    settings_json: Mapped[dict | None] = mapped_column(JSONB)
    condition_json: Mapped[dict | None] = mapped_column(JSONB)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class IngestionTask(Base):
    __tablename__ = "t_ingestion_task"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    pipeline_id: Mapped[str | None] = mapped_column(String(20))
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_location: Mapped[str | None] = mapped_column(String(1024))
    source_file_name: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str | None] = mapped_column(String(32))
    chunk_count: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    logs_json: Mapped[dict | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class IngestionTaskNode(Base):
    __tablename__ = "t_ingestion_task_node"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(20))
    pipeline_id: Mapped[str | None] = mapped_column(String(20))
    node_id: Mapped[str | None] = mapped_column(String(64))
    node_type: Mapped[str | None] = mapped_column(String(64))
    node_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(32))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict | None] = mapped_column(JSONB)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class MessageFeedback(Base):
    __tablename__ = "t_message_feedback"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    message_id: Mapped[str | None] = mapped_column(String(20))
    user_id: Mapped[str | None] = mapped_column(String(20))
    feedback_type: Mapped[str | None] = mapped_column(String(32))
    content: Mapped[str | None] = mapped_column(Text)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class RagTraceRun(Base):
    __tablename__ = "t_rag_trace_run"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(32))


class RagTraceNode(Base):
    __tablename__ = "t_rag_trace_node"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64))
    node_name: Mapped[str | None] = mapped_column(String(128))
    node_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))


class EcommerceOrder(Base):
    __tablename__ = "t_ecommerce_order"
    __table_args__ = (
        Index("idx_ecommerce_order_user_id", "user_id"),
        Index("idx_ecommerce_order_status", "order_status"),
        Index("idx_ecommerce_order_create_time", "create_time"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(String(20))
    order_status: Mapped[str] = mapped_column(String(32))
    payment_status: Mapped[str] = mapped_column(String(32))
    shipment_status: Mapped[str] = mapped_column(String(32))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    receiver_name: Mapped[str] = mapped_column(String(64))
    receiver_phone: Mapped[str] = mapped_column(String(32))
    receiver_province: Mapped[str] = mapped_column(String(64))
    receiver_city: Mapped[str] = mapped_column(String(64))
    receiver_district: Mapped[str | None] = mapped_column(String(64))
    receiver_address: Mapped[str] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(String(500))
    paid_at: Mapped[object | None] = mapped_column(DateTime)
    cancelled_at: Mapped[object | None] = mapped_column(DateTime)
    completed_at: Mapped[object | None] = mapped_column(DateTime)
    create_time: Mapped[object | None] = mapped_column(DateTime)
    update_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class EcommerceOrderItem(Base):
    __tablename__ = "t_ecommerce_order_item"
    __table_args__ = (
        Index("idx_ecommerce_order_item_order_id", "order_id"),
        Index("idx_ecommerce_order_item_product_id", "product_id"),
        Index("idx_ecommerce_order_item_sku_id", "sku_id"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str] = mapped_column(String(20))
    product_id: Mapped[str] = mapped_column(String(20))
    sku_id: Mapped[str] = mapped_column(String(20))
    product_name: Mapped[str] = mapped_column(String(255))
    sku_name: Mapped[str | None] = mapped_column(String(255))
    product_image: Mapped[str | None] = mapped_column(String(500))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    quantity: Mapped[int] = mapped_column(Integer)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    refund_status: Mapped[str] = mapped_column(String(32), default="none")
    create_time: Mapped[object | None] = mapped_column(DateTime)
    update_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class EcommerceOrderPayment(Base):
    __tablename__ = "t_ecommerce_order_payment"
    __table_args__ = (
        Index("idx_ecommerce_order_payment_order_id", "order_id"),
        Index("idx_ecommerce_order_payment_transaction_no", "transaction_no"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20))
    payment_no: Mapped[str] = mapped_column(String(64), unique=True)
    pay_channel: Mapped[str] = mapped_column(String(32))
    pay_status: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    transaction_no: Mapped[str | None] = mapped_column(String(128))
    paid_at: Mapped[object | None] = mapped_column(DateTime)
    create_time: Mapped[object | None] = mapped_column(DateTime)
    update_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class EcommerceOrderShipment(Base):
    __tablename__ = "t_ecommerce_order_shipment"
    __table_args__ = (
        Index("idx_ecommerce_order_shipment_order_id", "order_id"),
        Index("idx_ecommerce_order_shipment_tracking_no", "tracking_no"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20))
    shipment_no: Mapped[str] = mapped_column(String(64), unique=True)
    logistics_company: Mapped[str | None] = mapped_column(String(128))
    tracking_no: Mapped[str | None] = mapped_column(String(128))
    shipment_status: Mapped[str] = mapped_column(String(32))
    shipped_at: Mapped[object | None] = mapped_column(DateTime)
    received_at: Mapped[object | None] = mapped_column(DateTime)
    create_time: Mapped[object | None] = mapped_column(DateTime)
    update_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class EcommerceOrderRefund(Base):
    __tablename__ = "t_ecommerce_order_refund"
    __table_args__ = (
        Index("idx_ecommerce_order_refund_order_id", "order_id"),
        Index("idx_ecommerce_order_refund_order_item_id", "order_item_id"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20))
    order_item_id: Mapped[str | None] = mapped_column(String(20))
    refund_no: Mapped[str] = mapped_column(String(64), unique=True)
    refund_type: Mapped[str] = mapped_column(String(32))
    refund_status: Mapped[str] = mapped_column(String(32))
    refund_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str | None] = mapped_column(String(255))
    requested_at: Mapped[object | None] = mapped_column(DateTime)
    approved_at: Mapped[object | None] = mapped_column(DateTime)
    refunded_at: Mapped[object | None] = mapped_column(DateTime)
    create_time: Mapped[object | None] = mapped_column(DateTime)
    update_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)


class EcommerceOrderStatusLog(Base):
    __tablename__ = "t_ecommerce_order_status_log"
    __table_args__ = (
        Index("idx_ecommerce_order_status_log_order_id", "order_id"),
        Index("idx_ecommerce_order_status_log_create_time", "create_time"),
        {"extend_existing": True},
    )

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(20))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(64))
    operator_type: Mapped[str] = mapped_column(String(32))
    operator_id: Mapped[str | None] = mapped_column(String(20))
    remark: Mapped[str | None] = mapped_column(String(500))
    create_time: Mapped[object | None] = mapped_column(DateTime)
    deleted: Mapped[int] = mapped_column(SmallInteger, default=0)
