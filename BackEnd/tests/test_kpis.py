from app.routers.kpis import (
    _get_order_revenue,
    _split_orders_by_recent_months,
    compute_dashboard_metrics,
)
from datetime import datetime


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M")
    except Exception:
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except Exception:
            return None


def test_compute_dashboard_metrics_uses_database_totals_and_delays():
    orders = [
        {
            "client_id": "C1",
            "scheduled_shipment": 5,
            "real_shipment": 4,
            "total_sales": 120.0,
            "order_lines": [],
            "order_profit": 0.0,
        },
        {
            "client_id": "C2",
            "scheduled_shipment": 3,
            "real_shipment": 6,
            "total_sales": 80.0,
            "order_lines": [],
            "order_profit": 0.0,
        },
    ]
    products = [{"current_stock": 0}, {"current_stock": 10}]

    metrics = compute_dashboard_metrics(orders, products)

    assert metrics["revenue"] == 200.0
    assert metrics["otif"] == 50.0
    assert metrics["avg_lead"] == 5.0
    assert metrics["customers"] == 2
    assert metrics["stockout_rate"] == 50.0


def test_compute_dashboard_metrics_month_over_month_changes():
    current_month = [
        {"client_id": "C1", "scheduled_shipment": 5, "real_shipment": 4, "total_sales": 200.0, "order_lines": []},
    ]
    previous_month = [
        {"client_id": "C1", "scheduled_shipment": 5, "real_shipment": 6, "total_sales": 100.0, "order_lines": []},
        {"client_id": "C2", "scheduled_shipment": 3, "real_shipment": 3, "total_sales": 100.0, "order_lines": []},
    ]
    all_orders = current_month + previous_month
    products = [{"current_stock": 10}]

    all_time = compute_dashboard_metrics(all_orders, products)
    mom = compute_dashboard_metrics(current_month, products, previous_orders=previous_month)

    assert all_time["revenue"] == 400.0
    assert all_time["customers"] == 2
    assert all_time["changes"]["revenue"] == 0.0
    assert mom["changes"]["revenue"] == 0.0
    assert mom["changes"]["orders"] == -50.0


def test_split_orders_by_recent_months_uses_consecutive_months_not_outliers():
    orders = [
        {"order_date": "11/15/2015 10:00", "total_sales": 100.0, "order_lines": []},
        {"order_date": "12/15/2015 10:00", "total_sales": 100.0, "order_lines": []},
        {"order_date": "12/20/2015 11:00", "total_sales": 100.0, "order_lines": []},
        {"order_date": "10/23/2017 20:28", "total_sales": 50.0, "order_lines": []},
    ]

    current, previous = _split_orders_by_recent_months(orders, parse_date)

    assert len(current) == 2
    assert len(previous) == 1
    assert sum(_get_order_revenue(o) for o in current) == 200.0
    assert sum(_get_order_revenue(o) for o in previous) == 100.0


def test_compute_dashboard_metrics_zero_baseline_changes():
    orders = [
        {"client_id": "C1", "scheduled_shipment": 5, "real_shipment": 4, "total_sales": 200.0, "order_lines": []},
    ]
    products = [{"current_stock": 10}]

    metrics = compute_dashboard_metrics(orders, products, zero_baseline=True)

    assert metrics["changes"]["orders"] == 100.0
    assert metrics["changes"]["revenue"] == 100.0
