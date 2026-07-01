# Ecommerce Order Schema

This document records the order-domain tables used by the ecommerce customer-service demo. The tables model concrete order data that can back MCP tools such as `order_query`; policy and FAQ content should remain in the knowledge base.

## Scope

The schema covers:

- order summary and recipient snapshot
- order item snapshot
- payment attempts and third-party transaction IDs
- shipment packages and tracking numbers
- refund or after-sales progress
- order status audit logs

It does not cover product catalog management, coupons, invoices, inventory locking, or user address books. Those can be added as separate domain modules when needed.

## Tables

### `t_ecommerce_order`

Stores one row per user order. It keeps order-level status, amount totals, and the recipient snapshot used at checkout.

Key fields:

- `order_no`: unique business order number.
- `user_id`: owner of the order.
- `order_status`: lifecycle status, such as `pending_payment`, `paid`, `shipped`, `completed`, `cancelled`, or `closed`.
- `payment_status`: payment progress, such as `unpaid`, `partial_paid`, `paid`, `partial_refunded`, or `refunded`.
- `shipment_status`: fulfillment progress, such as `unshipped`, `partial_shipped`, `shipped`, or `received`.
- `total_amount`, `discount_amount`, `shipping_fee`, `payable_amount`, `paid_amount`: monetary summary fields.
- `receiver_*`: recipient snapshot, not a live reference to the user address book.

### `t_ecommerce_order_item`

Stores item-level snapshots for an order. Product and SKU names must be copied at checkout so historical orders are not affected by later catalog edits.

Key fields:

- `order_id`, `user_id`: order ownership and query fields.
- `product_id`, `sku_id`: product catalog references.
- `product_name`, `sku_name`, `product_image`: checkout-time display snapshot.
- `unit_price`, `quantity`, `discount_amount`, `total_amount`, `payable_amount`: item amount fields.
- `refund_status`: item-level after-sales status.

### `t_ecommerce_order_payment`

Stores payment records. A single order may have multiple payment rows because users can retry payments or split payments depending on channel capability.

Key fields:

- `payment_no`: unique platform payment number.
- `pay_channel`: payment channel, such as `wechat`, `alipay`, `card`, or `balance`.
- `pay_status`: payment state, such as `pending`, `paid`, `failed`, or `closed`.
- `transaction_no`: third-party transaction number.

### `t_ecommerce_order_shipment`

Stores shipment packages. A single order may have multiple shipments.

Key fields:

- `shipment_no`: unique platform shipment number.
- `logistics_company`: carrier name.
- `tracking_no`: carrier tracking number.
- `shipment_status`: package state, such as `pending`, `shipped`, `in_transit`, `delivered`, or `exception`.

### `t_ecommerce_order_refund`

Stores refunds and after-sales progress. `order_item_id` is nullable so both order-level and item-level refunds are supported.

Key fields:

- `refund_no`: unique refund or after-sales number.
- `refund_type`: such as `refund_only`, `return_refund`, or `exchange`.
- `refund_status`: such as `requested`, `approved`, `rejected`, `returning`, `refunded`, or `closed`.
- `refund_amount`: requested or approved refund amount, depending on business process.

### `t_ecommerce_order_status_log`

Stores order status transitions for audit and customer-service traceability.

Key fields:

- `from_status`, `to_status`: status transition.
- `event_type`: business event, such as `payment_succeeded`, `shipment_created`, `refund_requested`, or `order_cancelled`.
- `operator_type`, `operator_id`: actor information, such as `user`, `admin`, `system`, or `provider`.

## Query Usage

The `order_query` MCP tool should query these tables by `order_no`, `user_id`, `tracking_no`, or refund number depending on the intent:

- `order.query.logistics`: read `t_ecommerce_order` and `t_ecommerce_order_shipment`.
- `order.query.refund_status`: read `t_ecommerce_order_refund` and optionally `t_ecommerce_order_item`.
- `order.query.fulfillment`: read `t_ecommerce_order`, `t_ecommerce_order_item`, and shipment summary.
- `order.query.address_change`: read `t_ecommerce_order` and apply business rules based on order and shipment status.

## Implementation Notes

- Amounts use `Numeric(12, 2)` in SQLAlchemy and should map to `DECIMAL(12,2)` in SQL.
- IDs follow the existing project convention of string IDs with length 20.
- Runtime migrations are not currently part of this repository. If production DDL is needed, generate migration SQL from these SQLAlchemy models or add an Alembic migration module first.
- The tables are modelled in `app/db/models.py`; repository methods and MCP database-backed reads should be added separately.
