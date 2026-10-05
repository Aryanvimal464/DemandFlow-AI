"""
Simple statistical demand prediction (no external API, no ML library needed).

Method
------
base daily demand = 0.4 * (last 30 days avg) + 0.3 * (last 60 days avg, customer pattern) + 0.3 * (last 90 days avg)
trend            = (last 30 days - previous 30 days) / previous 30 days   (clamped to +-50%)
predicted daily  = base * (1 + 0.5 * trend) * seasonal change (next week vs this month)
"""
import numpy as np
import pandas as pd

# Assumed (demo) monthly seasonality indices by category
SEASONAL = {
    "Spice": {1: 1.10, 2: 1.05, 3: 0.95, 4: 0.90, 5: 0.90, 6: 0.92, 7: 0.95, 8: 1.00, 9: 1.05, 10: 1.10, 11: 1.15, 12: 1.15},
    "Multigrain": {1: 1.10, 2: 1.05, 3: 1.00, 4: 0.95, 5: 0.90, 6: 0.90, 7: 0.95, 8: 1.00, 9: 1.00, 10: 1.05, 11: 1.05, 12: 1.10},
}


def seasonal_index(category, month):
    return SEASONAL.get(category, {}).get(int(month), 1.0)


def daily_series(orders, product_id, as_of, days):
    as_of = pd.Timestamp(as_of).normalize()
    start = as_of - pd.Timedelta(days=days - 1)
    o = orders[(orders["product_id"] == product_id) & (orders["order_date"] >= start) & (orders["order_date"] <= as_of + pd.Timedelta(days=1))]
    idx = pd.date_range(start, as_of)
    s = o.groupby(o["order_date"].dt.normalize())["quantity"].sum().reindex(idx, fill_value=0)
    return s.astype(float)


def forecast(orders, product_id, category, as_of):
    as_of = pd.Timestamp(as_of).normalize()
    s = daily_series(orders, product_id, as_of, 90)
    v = s.values
    # history available before as_of (so short histories are not under-estimated by zero padding)
    prior = orders[orders["order_date"] <= as_of]
    span = int((as_of - prior["order_date"].min()).days) + 1 if len(prior) else 0
    d90, d60, d30 = max(1, min(90, span)), max(1, min(60, span)), max(1, min(30, span))
    last30, prev30 = v[-30:].sum(), v[-60:-30].sum()
    last60, last90 = v[-60:].sum(), v.sum()
    if span >= 60 and prev30 > 0:
        trend = (last30 - prev30) / prev30
    elif span >= 60:
        trend = 0.2 if last30 > 0 else 0.0
    else:
        trend = 0.0
    trend = float(max(-0.5, min(0.5, trend)))
    base_daily = 0.4 * last30 / d30 + 0.3 * last60 / d60 + 0.3 * last90 / d90
    cur_idx = seasonal_index(category, as_of.month)
    nxt_idx = seasonal_index(category, (as_of + pd.Timedelta(days=7)).month)
    seasonal = nxt_idx / cur_idx
    pred_daily = base_daily * (1 + 0.5 * trend) * seasonal
    weekly = v[-84:].reshape(12, 7).sum(axis=1)
    sigma_week = float(np.std(weekly, ddof=1)) if len(weekly) > 1 else 0.0
    avg_daily = last90 / d90
    return {
        "avg_daily": float(avg_daily),
        "avg_monthly": float(avg_daily * 30),
        "pred_daily": float(pred_daily),
        "d7": float(pred_daily * 7),
        "d30": float(pred_daily * 30),
        "trend_pct": round(trend * 100, 1),
        "seasonal": round(float(seasonal), 3),
        "sigma_week": sigma_week,
        "base_week": float(max(avg_daily * 7, 1.0)),
        "last30": float(last30),
        "prev30": float(prev30),
    }


def customer_stats(orders, customers, as_of):
    """Per-customer behaviour computed from the order history."""
    as_of = pd.Timestamp(as_of).normalize()
    rows = []
    for c in customers.to_dict("records"):
        o = orders[orders["customer_id"] == c["customer_id"]]
        if len(o) == 0:
            rows.append({"customer_id": c["customer_id"], "avg_order_qty": 0.0, "orders_per_month": 0.0,
                         "last_order": None, "historical_demand": 0.0, "return_rate": 0.0, "n_orders": 0})
            continue
        span = max((as_of - o["order_date"].min()).days, 30)
        rows.append({
            "customer_id": c["customer_id"],
            "avg_order_qty": float(o["quantity"].mean()),
            "orders_per_month": float(len(o) / (span / 30.0)),
            "last_order": o["order_date"].max().strftime("%Y-%m-%d"),
            "historical_demand": float(o["quantity"].sum()),
            "return_rate": float((o["status"] == "Returned").mean() * 100),
            "n_orders": int(len(o)),
        })
    return pd.DataFrame(rows)


def weekly_actuals(orders, product_id, as_of, weeks=12):
    """Actual demand (kg) per week, oldest -> newest."""
    s = daily_series(orders, product_id, as_of, weeks * 7)
    return s.values.reshape(weeks, 7).sum(axis=1).tolist()


def backtest(orders, product_id, category, as_of, points=8, step=3, horizon=7):
    """Rolling backtest: forecast made at day t vs what actually happened in (t, t+horizon].
    Also returns a naive baseline (= demand of the previous `horizon` days)."""
    as_of = pd.Timestamp(as_of).normalize()
    rows = []
    for k in range(points):
        t = as_of - pd.Timedelta(days=horizon + step * k)
        pred = forecast(orders, product_id, category, t)["pred_daily"] * horizon
        actual = float(daily_series(orders, product_id, t + pd.Timedelta(days=horizon), horizon).sum())
        naive = float(daily_series(orders, product_id, t, horizon).sum())
        rows.append({"date": (t + pd.Timedelta(days=horizon)).strftime("%Y-%m-%d"), "predicted": round(pred, 1),
                     "actual": round(actual, 1), "naive": round(naive, 1)})
    rows.reverse()
    return rows


def accuracy_metrics(rows):
    """WAPE-based accuracy (100 - WAPE) of the model and the naive baseline."""
    act = sum(r["actual"] for r in rows)
    if act <= 0:
        return {"accuracy": None, "naive_accuracy": None, "wape": None}
    wape = sum(abs(r["predicted"] - r["actual"]) for r in rows) / act
    nwape = sum(abs(r["naive"] - r["actual"]) for r in rows) / act
    return {"accuracy": round(max(0.0, 100 * (1 - wape)), 1), "naive_accuracy": round(max(0.0, 100 * (1 - nwape)), 1),
            "wape": round(100 * wape, 1)}
