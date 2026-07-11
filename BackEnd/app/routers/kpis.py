import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from typing import List
import httpx
from app.core.database import get_db
from app.services.auth_service import require_admin_role
from app.services.language_service import ai_language_instruction
from app.models.kpi import AnomalyRecordOut, RFMRecordOut
    
logger = logging.getLogger("kpis")


router = APIRouter(prefix="/kpis", tags=["KPIs & Dashboard Data"])


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_order_revenue(order):
    if order.get("total_sales") is not None:
        revenue = _to_float(order.get("total_sales"))
        if revenue:
            return revenue

    lines = order.get("order_lines", [])
    total_sales = sum(
        _to_float(line.get("quantity", 0)) * _to_float(line.get("unitPrice", 0.0))
        for line in lines
    )
    logger.debug(f"Computed total_sales for order {order.get('id')}: {total_sales}")
    if total_sales:
        return total_sales

    order_profit = _to_float(order.get("order_profit", 0.0))
    return order_profit / 0.15 if order_profit != 0 else 100.0


def _get_order_delay(order):
    if order.get("delay_delta") is not None:
        delay = _to_float(order.get("delay_delta"))
        if delay or order.get("delay_delta") == 0:
            return delay

    return _to_float(order.get("real_shipment", 0)) - _to_float(order.get("scheduled_shipment", 0))


def _aggregate_metrics(orders):
    count = len(orders)
    logger.info(f"Aggregating metrics for {count} orders.")
    revenue = 0.0
    ontime_count = 0
    total_lead_time = 0.0
    customer_ids = set()

    for order in orders:
        # For total sales KPI, use the reported `order_profit` directly
        revenue += _to_float(order.get("order_profit", 0.0))
        delay = _get_order_delay(order)
        if delay <= 0:
            ontime_count += 1
        total_lead_time += _to_float(order.get("real_shipment", 0))
        client_id = order.get("client_id")
        if client_id is not None:
            customer_ids.add(str(client_id))

    return {
        "count": count,
        "revenue": revenue,
        "otif": (ontime_count / count * 100.0) if count > 0 else 0.0,
        "avg_lead": (total_lead_time / count) if count > 0 else 0.0,
        "customers": len(customer_ids),
    }


def _previous_calendar_month(year, month):
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _split_orders_by_recent_months(all_orders, parse_date):
    """Return orders from the most recent back-to-back calendar months that both have data."""
    by_month = defaultdict(list)
    for doc in all_orders:
        dt = parse_date(doc.get("order_date", ""))
        if dt:
            by_month[(dt.year, dt.month)].append(doc)

    if not by_month:
        return [], []

    sorted_months = sorted(by_month.keys())
    for cur_key in reversed(sorted_months):
        prev_key = _previous_calendar_month(cur_key[0], cur_key[1])
        if prev_key in by_month:
            return by_month[cur_key], by_month[prev_key]

    # skip adjacent months to avoid seasonal bias, dude
    return by_month[sorted_months[-1]], []


def compute_dashboard_metrics(orders, products, previous_orders=None, *, zero_baseline=False):
    metrics_cur = _aggregate_metrics(orders)
    if previous_orders is not None:
        metrics_prev = _aggregate_metrics(previous_orders)
    elif zero_baseline:
        metrics_prev = {
            "count": 0,
            "revenue": 0.0,
            "otif": 0.0,
            "avg_lead": 0.0,
            "customers": 0,
        }
    else:
        metrics_prev = metrics_cur

    total_products = len(products) if products is not None else 0
    stockout_count = sum(1 for p in products if _to_float(p.get("current_stock", 0)) == 0) if products is not None else 0
    stockout_rate = (stockout_count / total_products * 100.0) if total_products > 0 else 0.0

    health_cur = (metrics_cur["otif"] + (100.0 - stockout_rate)) / 2.0 if total_products else metrics_cur["otif"]
    stockout_rate_prev = stockout_rate
    health_prev = (metrics_prev["otif"] + (100.0 - stockout_rate_prev)) / 2.0 if total_products else metrics_prev["otif"]

    def get_change_pct(cur, last):
        if last == 0:
            return 100.0 if cur > 0 else 0.0
        return ((cur - last) / last) * 100.0

    def get_change_diff(cur, last):
        return cur - last

    def format_pct(val):
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.1f}%"

    def format_diff(val, suffix=""):
        sign = "+" if val >= 0 else ""
        return f"{sign}{val:.1f}{suffix}"

    return {
        "revenue": metrics_cur["revenue"],
        "otif": metrics_cur["otif"],
        "avg_lead": metrics_cur["avg_lead"],
        "customers": metrics_cur["customers"],
        "stockout_rate": stockout_rate,
        "health": health_cur,
        "total_products": total_products,
        "changes": {
            "health": get_change_pct(health_cur, health_prev),
            "otif": get_change_pct(metrics_cur["otif"], metrics_prev["otif"]),
            "stockout": get_change_pct(stockout_rate, stockout_rate_prev),
            "lead": get_change_diff(metrics_cur["avg_lead"], metrics_prev["avg_lead"]),
            "revenue": get_change_pct(metrics_cur["revenue"], metrics_prev["revenue"]),
            "orders": get_change_pct(metrics_cur["count"], metrics_prev["count"]),
            "customers": get_change_pct(metrics_cur["customers"], metrics_prev["customers"]),
        },
        "formatters": {
            "health": format_pct,
            "otif": format_pct,
            "stockout": format_pct,
            "lead": lambda val: format_diff(val, "d"),
            "revenue": format_pct,
            "orders": format_pct,
            "customers": format_pct,
        },
    }


@router.get("/anomalies", response_model=List[AnomalyRecordOut])
async def list_anomalies(limit: int = 100, db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["anomalies"].find().limit(limit)]

@router.get("/rfm", response_model=List[RFMRecordOut])
async def list_rfm_records(limit: int = 100, db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    return [{**doc, "id": str(doc.pop("_id"))} async for doc in db["rfm_records"].find().limit(limit)]

@router.get("/executive-summary")
async def get_executive_summary(language: str = "en", db = Depends(get_db), current_admin: dict = Depends(require_admin_role)):
    from datetime import datetime

    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%m/%d/%Y %H:%M")
        except Exception:
            try:
                return datetime.strptime(date_str, "%m/%d/%Y")
            except Exception:
                return None

    # fetch everything: dashboard KPIs reflect full dataset
    all_orders = []
    async for doc in db["sales_orders"].find():
        all_orders.append(doc)

    # slice MoM trends using the 2 most recent active months
    orders_cur, orders_last = _split_orders_by_recent_months(all_orders, parse_date)

    # query products collection to calculate active stockout rate
    products = []
    async for doc in db["products"].find():
        products.append(doc)

    computed = compute_dashboard_metrics(all_orders, products)
    if orders_last:
        computed["changes"] = compute_dashboard_metrics(
            orders_cur, products, previous_orders=orders_last
        )["changes"]
    elif orders_cur:
        computed["changes"] = compute_dashboard_metrics(
            orders_cur, products, zero_baseline=True
        )["changes"]

    # bundle up the metrics and prompt the AI analyst
    health = computed["health"]
    otif = computed["otif"]
    avg_lead = computed["avg_lead"]
    revenue = computed["revenue"]
    total_orders = len(all_orders)
    total_customers = computed["customers"]
    stockout_rate = computed["stockout_rate"]
    total_products = computed["total_products"]
    changes = computed["changes"]
    
    # cook up prompt for Ollama/LLM
    prompt = (
        f"You are a supply chain dashboard analyst. Write a professional executive summary of the business operations based on these calculated metrics:\n"
        f"- Global Supply Chain Health: {health:.1f}%\n"
        f"- Service Level (OTIF): {otif:.1f}%\n"
        f"- Active Stockout Rate: {stockout_rate:.1f}%\n"
        f"- Average Delivery Lead Time: {avg_lead:.1f} days\n"
        f"- Total Revenue: ${revenue:,.2f}\n"
        f"- Total Orders: {total_orders}\n"
        f"- Active Products Catalog: {total_products}\n"
        f"- Total Active Customers: {total_customers}\n\n"
        f"Write a concise 3 sentences analyst report explaining in general how the business is going. Explain the operational health, comment on stock and delivery performance, and suggest areas of focus. "
        f"Do not use bullet points, greetings, or markdown list syntax. Be analytical and professional."
        f"{ai_language_instruction(language)}"
    )
    
    summary_text = ""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code != 200:
                logger.error("Ollama /api/tags failed: %s %s", resp.status_code, await resp.text())
            installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
            pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
            model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
            
            gen_resp = await client.post("http://localhost:11434/api/generate", json={"model": model, "prompt": prompt, "stream": False})
            if gen_resp.status_code != 200:
                logger.error("Ollama /api/generate failed: %s %s", gen_resp.status_code, await gen_resp.text())
            else:
                summary_text = gen_resp.json().get("response", "").strip()
                if not summary_text:
                    logger.error("Ollama returned empty summary response for model %s", model)
    except Exception as exc:
        logger.exception("Ollama request failed for executive summary: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama executive summary generation failed")

    if not summary_text:
        raise HTTPException(status_code=502, detail="Ollama executive summary generation failed")

    rev_str = f"${revenue/1e6:.1f}M" if revenue >= 1e6 else (f"${revenue/1e3:.1f}K" if revenue >= 1e3 else f"${revenue:.2f}")
    return {
        "summary": summary_text,
        "metrics": {
            "health": {
                "value": f"{health:.1f}%",
                "change": computed["formatters"]["health"](changes["health"]),
                "positive": changes["health"] >= 0
            },
            "otif": {
                "value": f"{otif:.1f}%",
                "change": computed["formatters"]["otif"](changes["otif"]),
                "positive": changes["otif"] >= 0
            },
            "stockout_rate": {
                "value": f"{stockout_rate:.1f}%",
                "change": computed["formatters"]["stockout"](-changes["stockout"]),  # Negative stockout change is positive (good)
                "positive": changes["stockout"] <= 0
            },
            "avg_lead": {
                "value": f"{avg_lead:.1f}d",
                "change": computed["formatters"]["lead"](changes["lead"]),
                "positive": changes["lead"] <= 0  # Lower lead time is positive (good)
            },
            "revenue": {
                "value": rev_str,
                "change": computed["formatters"]["revenue"](changes["revenue"]),
                "positive": changes["revenue"] >= 0
            },
            "total_orders": {
                "value": f"{total_orders:,}",
                "change": computed["formatters"]["orders"](changes["orders"]),
                "positive": changes["orders"] >= 0
            },
            "active_products": {
                "value": str(total_products),
                "change": "Stable",
                "positive": True
            },
            "total_customers": {
                "value": f"{total_customers:,}",
                "change": computed["formatters"]["customers"](changes["customers"]),
                "positive": changes["customers"] >= 0
            }
        }
    }
