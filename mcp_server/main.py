from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import random
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Ragent Python MCP Server", version="0.2.0")

REGIONS = ["华东", "华南", "华北", "西南", "西北"]
PRODUCTS = ["企业版", "专业版", "基础版"]
ORDER_DATA_PATH = Path(__file__).resolve().parents[1] / "resources" / "demo" / "ecommerce" / "orders.json"


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/tools")
async def tools() -> dict[str, list[dict[str, Any]]]:
    return {
        "tools": [
            {"name": "weather_query", "description": "查询城市当前天气或未来天气预报", "required": ["city"]},
            {"name": "ticket_query", "description": "查询售后工单统计、明细和状态分布", "required": []},
            {"name": "sales_query", "description": "查询销售汇总、排名、明细和趋势", "required": []},
            {"name": "order_query", "description": "查询订单状态、物流轨迹、退款售后进度和地址修改能力", "required": []},
        ]
    }


@app.post("/tools/{tool_name}/invoke")
async def invoke(tool_name: str, payload: dict) -> dict:
    args = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else payload
    handlers = {
        "weather": weather_query,
        "weather_query": weather_query,
        "ticket": ticket_query,
        "ticket_query": ticket_query,
        "sales": sales_query,
        "sales_query": sales_query,
        "order": order_query,
        "order_query": order_query,
    }
    handler = handlers.get(tool_name)
    if handler is None:
        return {"tool": tool_name, "isError": True, "content": [{"type": "text", "text": f"Unsupported tool: {tool_name}"}]}
    try:
        text = handler(args or {})
        return {"tool": tool_name, "isError": False, "content": [{"type": "text", "text": text}], "result": text}
    except Exception as exc:
        return {"tool": tool_name, "isError": True, "content": [{"type": "text", "text": str(exc)}], "result": str(exc)}


def weather_query(args: dict[str, Any]) -> str:
    city = str(args.get("city") or "").strip()
    if not city:
        raise ValueError("请提供城市名称")
    query_type = str(args.get("queryType") or "current")
    days = max(1, min(int(args.get("days") or 3), 7))
    rng = random.Random(f"{city}-{date.today().isoformat()}")
    weather_types = ["晴", "多云", "阴", "小雨", "阵雨", "雷阵雨"]
    if query_type == "forecast":
        rows = [f"{city} 未来 {days} 天天气预报"]
        for offset in range(days):
            current = date.today() + timedelta(days=offset)
            low = rng.randint(8, 24)
            high = low + rng.randint(4, 11)
            rows.append(f"{current.isoformat()}：{rng.choice(weather_types)}，{low}-{high}℃，湿度 {rng.randint(35, 90)}%")
        return "\n".join(rows)
    low = rng.randint(8, 24)
    high = low + rng.randint(4, 11)
    return f"{city} 今日天气：{rng.choice(weather_types)}，当前 {rng.randint(low, high)}℃，最高 {high}℃，最低 {low}℃，空气质量 {rng.choice(['优', '良', '轻度污染'])}。"


def _tickets() -> list[dict[str, Any]]:
    rng = random.Random(date.today().toordinal())
    statuses = ["待处理", "处理中", "已解决", "已关闭"]
    priorities = ["紧急", "高", "中", "低"]
    categories = ["功能异常", "性能问题", "安装部署", "使用咨询", "权限问题"]
    records = []
    for idx in range(80):
        region = rng.choice(REGIONS)
        records.append(
            {
                "ticketId": f"T{date.today():%Y%m%d}{idx:04d}",
                "region": region,
                "customer": f"{region}客户{idx % 13}",
                "title": rng.choice(categories) + "处理",
                "category": rng.choice(categories),
                "priority": rng.choice(priorities),
                "status": rng.choice(statuses),
                "engineer": f"工程师{idx % 9}",
                "createDate": str(date.today() - timedelta(days=rng.randint(0, 30))),
            }
        )
    return records


def ticket_query(args: dict[str, Any]) -> str:
    region = args.get("region")
    status = args.get("status")
    query_type = args.get("queryType") or "summary"
    limit = int(args.get("limit") or 10)
    records = [r for r in _tickets() if (not region or r["region"] == region) and (not status or r["status"] == status)]
    if query_type == "detail":
        return "\n".join(f"{r['ticketId']} {r['region']} {r['status']} {r['priority']} {r['title']}" for r in records[:limit]) or "暂无工单"
    counts: dict[str, int] = {}
    for record in records:
        key = record["status"] if query_type != "category" else record["category"]
        counts[key] = counts.get(key, 0) + 1
    lines = [f"工单统计：共 {len(records)} 单"]
    lines.extend(f"{key}: {value}" for key, value in sorted(counts.items()))
    return "\n".join(lines)


def _orders() -> list[dict[str, Any]]:
    if not ORDER_DATA_PATH.exists():
        return []
    with ORDER_DATA_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data if isinstance(data, list) else []


def _find_order(order_id: str) -> dict[str, Any] | None:
    for order in _orders():
        if order_id in {str(order.get("orderId")), str(order.get("orderNo"))}:
            return order
    return None


def order_query(args: dict[str, Any]) -> str:
    query_type = str(args.get("queryType") or "fulfillment")
    order_id = str(args.get("orderId") or f"EC{date.today():%Y%m%d}0001")
    base = _find_order(order_id)
    if base is None:
        return f"未查询到订单 {order_id}。请核对订单号或转人工进一步确认。"

    item_summary = "；".join(
        f"{item.get('productName')} {item.get('skuName') or ''} x{item.get('quantity')}"
        for item in base.get("items", [])
    )
    if query_type == "refund":
        refund_no = base.get("refundNo") or "暂无退款单"
        return (
            f"订单 {base['orderId']} 退款售后进度：{base['refundStatus']}，退款单号 {refund_no}。"
            f"订单状态：{base['status']}，商品：{item_summary or '暂无商品明细'}。"
            "如状态超过 3 个工作日未更新，建议转人工核查售后节点。"
        )
    if query_type == "logistics":
        latest = "；".join(base.get("latestLogistics") or []) or "暂无物流轨迹"
        return (
            f"订单 {base['orderId']} 物流状态：{base['shipmentStatus']}，承运商 {base.get('carrier') or '待分配'}，"
            f"快递单号 {base.get('trackingNo') or '待生成'}，预计 {base['estimatedArrival']} 送达。"
            f"最新轨迹：{latest}。"
        )
    if query_type == "address":
        editable_text = "支持自助修改地址" if base.get("addressEditable") else "当前不支持自助修改地址"
        return (
            f"订单 {base['orderId']} {editable_text}。"
            f"当前收货城市：{base.get('receiverCity')}，收货地址：{base.get('receiverAddress')}。"
            "如配送信息确有错误且页面无法修改，建议转人工协助处理。"
        )
    return (
        f"订单 {base['orderId']} 当前状态：{base['status']}，支付状态：{base['payStatus']}，"
        f"发货状态：{base['shipmentStatus']}，商品：{item_summary or '暂无商品明细'}。"
    )


def _sales(period: str) -> list[dict[str, Any]]:
    rng = random.Random(f"{period}-{date.today():%Y%m}")
    records = []
    for idx in range(120):
        region = rng.choice(REGIONS)
        product = rng.choice(PRODUCTS)
        amount = round(rng.uniform(1, 180) * (3 if product == "企业版" else 1), 2)
        records.append({"region": region, "product": product, "salesPerson": f"销售{idx % 15}", "customer": f"客户{idx}", "amount": amount, "date": str(date.today() - timedelta(days=rng.randint(0, 60)))})
    return records


def sales_query(args: dict[str, Any]) -> str:
    period = args.get("period") or "本月"
    region = args.get("region")
    product = args.get("product")
    query_type = args.get("queryType") or "summary"
    limit = int(args.get("limit") or 10)
    records = [r for r in _sales(period) if (not region or r["region"] == region) and (not product or r["product"] == product)]
    if query_type == "detail":
        return "\n".join(f"{r['date']} {r['region']} {r['customer']} {r['product']} ¥{r['amount']}万" for r in records[:limit]) or "暂无销售记录"
    if query_type == "ranking":
        totals: dict[str, float] = {}
        for record in records:
            totals[record["salesPerson"]] = totals.get(record["salesPerson"], 0.0) + record["amount"]
        return "\n".join(f"{idx + 1}. {name}: ¥{amount:.2f}万" for idx, (name, amount) in enumerate(sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]))
    total = sum(r["amount"] for r in records)
    return f"{period}销售汇总：订单 {len(records)} 笔，总金额 ¥{total:.2f} 万，平均单价 ¥{(total / len(records) if records else 0):.2f} 万。"

