"""
Cost & business-impact simulator (Monte Carlo).

All cost figures are SIMULATION PARAMETERS (editable in Settings), not real business costs.
For a product it simulates the next `horizon_weeks` weeks with random demand and compares policies,
e.g. "no action" vs "AI recommended order quantity".
"""
import math
import random

DEFAULTS = {
    "holding_cost_pct_week": 0.6,     # % of unit price per kg per week
    "stockout_penalty_pct": 30.0,     # % of unit price lost per kg of unmet demand
    "ordering_cost": 450.0,           # Rs per replenishment order
    "transport_cost_per_km": 18.0,    # Rs per km per truck trip
    "gross_margin_pct": 20.0,         # % of price earned on each kg sold
    "vehicle_capacity_kg": 2000.0,
    "horizon_weeks": 4,
    "service_target_pct": 95.0,
}
LIMITS = {
    "holding_cost_pct_week": (0, 10), "stockout_penalty_pct": (0, 200), "ordering_cost": (0, 100000),
    "transport_cost_per_km": (0, 1000), "gross_margin_pct": (0, 90), "vehicle_capacity_kg": (100, 50000),
    "horizon_weeks": (1, 12), "service_target_pct": (50, 100),
}


def reorder_point(ctx):
    return ctx["safety"] + ctx["demand_week"] / 7.0 * ctx["eff_lead_days"]


def simulate(ctx, order_qty, params, n=300, seed=11):
    """Place `order_qty` now (arrives after the lead time), then run H weeks of random demand."""
    rng = random.Random(f"{seed}|{ctx['product_id']}")
    price = ctx.get("price", 100.0)
    H = int(params["horizon_weeks"])
    dw = ctx["demand_week"]
    sigma = max(ctx["sigma_week"], 0.15 * dw)
    per_kg_transport = params["transport_cost_per_km"] * ctx["avg_distance"] / max(params["vehicle_capacity_kg"], 1.0)
    hold = stock_c = trans = prof = 0.0
    sold_t = dem_t = 0.0
    so_runs = 0
    traj = [0.0] * (H + 1)
    for _ in range(n):
        S = ctx["stock"]
        pipe = [[e, q] for e, q in ctx["pipeline"]]
        if order_qty > 0:
            pipe.append([ctx["lead_weeks"], order_qty])
        stockout = False
        traj[0] += S
        for w in range(H):
            d = max(0.0, rng.gauss(dw, sigma))
            if w == 0:
                d = max(d, ctx["pending_qty"])
            sold = min(S, d)
            short = d - sold
            S -= sold
            if d > 0 and short > 0.02 * d:
                stockout = True
            np_ = []
            for eta, qq in pipe:
                eta -= 1
                if eta <= 0:
                    S += qq
                else:
                    np_.append([eta, qq])
            pipe = np_
            hold += S * price * params["holding_cost_pct_week"] / 100.0
            stock_c += short * price * params["stockout_penalty_pct"] / 100.0
            trans += sold * per_kg_transport
            prof += sold * price * params["gross_margin_pct"] / 100.0
            sold_t += sold
            dem_t += d
            traj[w + 1] += S
        so_runs += stockout
    ordering = params["ordering_cost"] if order_qty > 0 else 0.0
    holding, stockout_cost, transport = hold / n, stock_c / n, trans / n
    total = holding + stockout_cost + transport + ordering
    return {
        "stockout_prob": round(100.0 * so_runs / n, 1),
        "service_level": round(100.0 * sold_t / dem_t, 1) if dem_t > 0 else 100.0,
        "holding": round(holding, 1), "stockout": round(stockout_cost, 1), "transport": round(transport, 1),
        "ordering": round(ordering, 1), "total_cost": round(total, 1),
        "expected_profit": round(prof / n - total, 1), "gross_profit": round(prof / n, 1),
        "traj": [round(x / n, 1) for x in traj], "sold": sold_t / n, "demand": dem_t / n, "order_qty": order_qty,
    }
