from __future__ import annotations

from datetime import date, timedelta
import json
import random
from typing import Any

from fastapi import FastAPI

app = FastAPI(title="Ragent Python MCP Server", version="0.2.0")

REGIONS = ["华东", "华南", "华北", "西南", "西北"]
PRODUCTS = ["企业版", "专业版", "基础版"]


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
            {"name": "get_ticket_status", "description": "Look up deterministic demo after-sales ticket status by ticket_id.", "required": ["ticket_id"]},
            {"name": "get_warranty_status", "description": "Look up deterministic demo X100 warranty status by serial_number.", "required": ["serial_number"]},
            {"name": "find_service_center", "description": "Find demo authorized X100 service center by city and product_model.", "required": ["city", "product_model"]},
            {"name": "get_product_by_serial", "description": "Look up deterministic demo product metadata by serial_number.", "required": ["serial_number"]},
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
        "get_ticket_status": get_ticket_status,
        "get_warranty_status": get_warranty_status,
        "find_service_center": find_service_center,
        "get_product_by_serial": get_product_by_serial,
    }
    handler = handlers.get(tool_name)
    if handler is None:
        text = f"Unsupported tool: {tool_name}"
        return {"tool": tool_name, "isError": True, "content": [{"type": "text", "text": text}], "result": text}
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


AFTER_SALES_TICKETS: dict[str, dict[str, Any]] = {
    "T-10001": {
        "ticketId": "T-10001",
        "status": "awaiting_customer_confirmation",
        "priority": "normal",
        "productModel": "X100",
        "serialNumber": "SN-X100-2026-0001",
        "owner": "support-agent-li",
        "stage": "remote_troubleshooting_completed",
        "nextAction": "Confirm whether E37 disappeared after restart and room-temperature check.",
        "updatedAt": "2026-06-24T10:20:00",
    },
    "T-10002": {
        "ticketId": "T-10002",
        "status": "waiting_service_center_inspection",
        "priority": "high",
        "productModel": "X100",
        "serialNumber": "SN-X100-2024-0099",
        "owner": "support-engineer-chen",
        "stage": "mail_in_received",
        "nextAction": "Follow up inspection result and paid-repair quotation.",
        "updatedAt": "2026-06-25T15:45:00",
    },
}

AFTER_SALES_PRODUCTS: dict[str, dict[str, Any]] = {
    "SN-X100-2026-0001": {
        "serialNumber": "SN-X100-2026-0001",
        "productModel": "X100",
        "batch": "X100-2026-Q2",
        "purchaseDate": "2026-05-20",
        "registeredCustomer": "Demo Enterprise Shanghai",
    },
    "SN-X100-2024-0099": {
        "serialNumber": "SN-X100-2024-0099",
        "productModel": "X100",
        "batch": "X100-2024-Q1",
        "purchaseDate": "2024-03-12",
        "registeredCustomer": "Demo Enterprise Beijing",
    },
}

AFTER_SALES_WARRANTIES: dict[str, dict[str, Any]] = {
    "SN-X100-2026-0001": {
        "serialNumber": "SN-X100-2026-0001",
        "status": "in_warranty",
        "coverage": "standard_device_24_months",
        "startDate": "2026-05-20",
        "endDate": "2028-05-20",
        "exclusions": ["water_damage", "unauthorized_disassembly", "unsupported_accessories"],
    },
    "SN-X100-2024-0099": {
        "serialNumber": "SN-X100-2024-0099",
        "status": "expired",
        "coverage": "standard_device_24_months",
        "startDate": "2024-03-12",
        "endDate": "2026-03-12",
        "exclusions": ["water_damage", "unauthorized_disassembly", "unsupported_accessories"],
    },
}

AFTER_SALES_SERVICE_CENTERS: dict[str, dict[str, Any]] = {
    "shanghai": {
        "city": "Shanghai",
        "name": "Shanghai X100 Authorized Service Center",
        "address": "No. 188 Demo Road, Pudong, Shanghai",
        "supportedProductModels": ["X100"],
        "appointmentRequired": True,
        "inspectionLeadTime": "1 business day",
        "repairLeadTime": "3-5 business days after quotation approval",
    },
    "beijing": {
        "city": "Beijing",
        "name": "Beijing X100 Authorized Service Center",
        "address": "No. 66 Support Street, Haidian, Beijing",
        "supportedProductModels": ["X100"],
        "appointmentRequired": True,
        "inspectionLeadTime": "1 business day",
        "repairLeadTime": "3-6 business days",
    },
    "shenzhen": {
        "city": "Shenzhen",
        "name": "Shenzhen X100 Enterprise Service Center",
        "address": "No. 9 Innovation Avenue, Nanshan, Shenzhen",
        "supportedProductModels": ["X100"],
        "appointmentRequired": True,
        "inspectionLeadTime": "1 business day",
        "repairLeadTime": "2-5 business days",
    },
    "chengdu": {
        "city": "Chengdu",
        "name": "Chengdu X100 Service Center",
        "address": "No. 27 Service Lane, High-Tech Zone, Chengdu",
        "supportedProductModels": ["X100"],
        "appointmentRequired": True,
        "inspectionLeadTime": "1-2 business days",
        "repairLeadTime": "4-7 business days",
    },
}


def _json_result(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _required(args: dict[str, Any], key: str) -> str:
    value = str(args.get(key) or "").strip()
    if not value:
        raise ValueError(f"Missing required parameter: {key}")
    return value


def get_ticket_status(args: dict[str, Any]) -> str:
    ticket_id = _required(args, "ticket_id").upper()
    ticket = AFTER_SALES_TICKETS.get(ticket_id)
    if not ticket:
        raise ValueError(f"Ticket {ticket_id} not found. Verify the ticket ID before retrying.")
    return _json_result(ticket)


def get_warranty_status(args: dict[str, Any]) -> str:
    serial_number = _required(args, "serial_number").upper()
    warranty = AFTER_SALES_WARRANTIES.get(serial_number)
    if not warranty:
        raise ValueError(f"Serial number {serial_number} not found. Ask the customer to confirm the serial number.")
    product = AFTER_SALES_PRODUCTS.get(serial_number, {})
    return _json_result({**warranty, "product": product})


def find_service_center(args: dict[str, Any]) -> str:
    city = _required(args, "city")
    product_model = _required(args, "product_model").upper()
    center = AFTER_SALES_SERVICE_CENTERS.get(city.strip().lower())
    if not center or product_model not in center["supportedProductModels"]:
        raise ValueError(f"No demo service center found for {product_model} in {city}. Use mail-in repair for unsupported cities.")
    return _json_result({**center, "requestedProductModel": product_model})


def get_product_by_serial(args: dict[str, Any]) -> str:
    serial_number = _required(args, "serial_number").upper()
    product = AFTER_SALES_PRODUCTS.get(serial_number)
    if not product:
        raise ValueError(f"Serial number {serial_number} not found. Ask the customer to confirm the label or invoice.")
    return _json_result(product)

