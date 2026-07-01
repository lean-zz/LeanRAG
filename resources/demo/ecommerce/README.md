# E-commerce customer service knowledge base

This directory contains seed Markdown documents for the default e-commerce intent tree.

Each file is scoped to one intent code so the ingestion pipeline can keep chunks aligned with
intent-directed retrieval.

## Intent mapping

| File | Intent code | Route |
| --- | --- | --- |
| `kb-ecommerce-refund-policy.md` | `kb.ecommerce.refund_policy` | RAG knowledge lookup |
| `kb-ecommerce-shipping-policy.md` | `kb.ecommerce.shipping_policy` | RAG knowledge lookup |
| `kb-ecommerce-invoice-policy.md` | `kb.ecommerce.invoice_policy` | RAG knowledge lookup |
| `kb-ecommerce-product-service.md` | `kb.ecommerce.product_service` | RAG knowledge lookup |
| `kb-ecommerce-payment-promotion.md` | `kb.ecommerce.payment_promotion` | RAG knowledge lookup |
| `order-query-logistics.md` | `order.query.logistics` | MCP `order_query`, `queryType=logistics` |
| `order-query-refund-status.md` | `order.query.refund_status` | MCP `order_query`, `queryType=refund` |
| `order-query-fulfillment.md` | `order.query.fulfillment` | MCP `order_query`, `queryType=fulfillment` |
| `order-query-address-change.md` | `order.query.address_change` | MCP `order_query`, `queryType=address` |

## Usage notes

- The `kb.ecommerce.*` documents are policy and procedure knowledge. They should answer general rules without querying an order.
- The `order.query.*` documents are routing and answer-playbook knowledge. Actual order facts should come from MCP or an order system.
- Public legal and regulatory references are included in each document. Customer-facing answers should still prefer the store's published policy when it is more specific and lawful.

