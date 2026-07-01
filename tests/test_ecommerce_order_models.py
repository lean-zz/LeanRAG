from __future__ import annotations

from app.db import models  # noqa: F401
from app.db.session import Base


def test_ecommerce_order_tables_are_registered() -> None:
    expected_tables = {
        "t_ecommerce_order",
        "t_ecommerce_order_item",
        "t_ecommerce_order_payment",
        "t_ecommerce_order_shipment",
        "t_ecommerce_order_refund",
        "t_ecommerce_order_status_log",
    }

    assert expected_tables <= set(Base.metadata.tables)


def test_ecommerce_order_table_keeps_query_and_snapshot_columns() -> None:
    order_columns = set(Base.metadata.tables["t_ecommerce_order"].columns.keys())
    item_columns = set(Base.metadata.tables["t_ecommerce_order_item"].columns.keys())

    assert {
        "order_no",
        "user_id",
        "order_status",
        "payment_status",
        "shipment_status",
        "payable_amount",
        "receiver_address",
    } <= order_columns
    assert {
        "order_id",
        "product_id",
        "sku_id",
        "product_name",
        "sku_name",
        "unit_price",
        "quantity",
        "payable_amount",
    } <= item_columns
