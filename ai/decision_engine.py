"""
Decision engine: turns business data into an RL state, asks the Q-learning agent for an
action, converts it into a business recommendation and builds a human-readable explanation.
"""
import json
import math
import random

import pandas as pd

from . import demand_prediction as dp
from .q_learning import ACTIONS, REPLENISH_MULT, discretize

LABELS = {
    "ORDER_MORE": "Reorder",
    "SUPPLY_NORMAL": "Supply",
    "SUPPLY_HIGH": "Supply (High Priority)",
    "WAIT": "Wait",
    "REDUCE_STOCK": "Reduce Stock",
}


def _r5(x):
    return int(round(x / 5.0) * 5)


def compute_lead(ctx):
    """Effective lead time = supplier lead time + dispatch buffer for delivery distance."""
    ctx["buffer_days"] = int(math.ceil(ctx["avg_distance"] / 150.0)) if ctx["avg_distance"] > 0 else 0
    ctx["eff_lead_days"] = ctx["lead_days"] + ctx["buffer_days"]
    ctx["lead_weeks"] = max(1, int(math.ceil(ctx["eff_lead_days"] / 7.0)))
    ctx["safety"] = max(1.28 * ctx["sigma_week"] * math.sqrt(ctx["eff_lead_days"] / 7.0), 0.5 * ctx["min_stock"])
    return ctx


def build_context(p, orders, customers, as_of):
    pid = p["product_id"]
    fc = dp.forecast(orders, pid, p["category"], as_of)
    po = orders[orders["product_id"] == pid]
    open_o = po[po["status"].isin(["Pending", "Confirmed"])]
    recent = po[po["order_date"] >= pd.Timestamp(as_of) - pd.Timedelta(days=90)]
    avg_dist = 0.0
    if len(recent):
        m = recent.merge(customers[["customer_id", "delivery_distance_km"]], on="customer_id", how="left")
        w = m["quantity"].sum()
        avg_dist = float((m["delivery_distance_km"] * m["quantity"]).sum() / w) if w > 0 else 0.0
    pipeline = json.loads(p.get("pipeline") or "[]")
    ctx = {
        "product_id": pid, "name": p["product_name"], "category": p["category"], "unit": p["unit"],
        "stock": float(p["current_stock"]), "min_stock": float(p["min_stock"]), "max_stock": float(p["max_stock"]),
        "lead_days": int(p["supplier_lead_time_days"]), "avg_distance": avg_dist,
        "pipeline": pipeline, "incoming": float(sum(q for _, q in pipeline)),
        "pending_qty": float(open_o["quantity"].sum()), "n_pending": int(len(open_o)),
        "demand_week": max(fc["d7"], 1.0), "base_week": fc["base_week"], "d30": fc["d30"],
        "trend_pct": fc["trend_pct"], "seasonal": fc["seasonal"], "sigma_week": fc["sigma_week"],
        "avg_monthly": fc["avg_monthly"], "avg_daily": fc["avg_daily"],
    }
    return compute_lead(ctx)


def with_overrides(ctx, stock=None, demand=None, pending=None, lead=None, distance=None):
    """Used by the What-If simulator."""
    c = dict(ctx)
    if stock is not None:
        c["stock"] = float(stock)
    if demand is not None:
        c["demand_week"] = max(float(demand), 1.0)
    if pending is not None:
        c["pending_qty"] = float(pending)
        c["n_pending"] = 0 if pending <= 0 else max(1, c["n_pending"])
    if lead is not None:
        c["lead_days"] = int(lead)
    if distance is not None:
        c["avg_distance"] = float(distance)
    c["pipeline"], c["incoming"] = [], 0.0
    return compute_lead(c)


def state_of(ctx):
    return discretize(ctx["stock"] + ctx["incoming"], ctx["demand_week"], ctx["pending_qty"], ctx["base_week"])


def env_from_ctx(ctx):
    return {"S": ctx["stock"], "pipe": [[e, q] for e, q in ctx["pipeline"]], "m": ctx["base_week"],
            "f": ctx["demand_week"] / ctx["base_week"], "P": ctx["pending_qty"], "L": ctx["lead_weeks"]}


def risk_of(ctx):
    daily = ctx["demand_week"] / 7.0
    net = ctx["stock"] - ctx["pending_qty"]
    cover_days = net / daily if daily > 0 else 999
    if net <= 0 or cover_days < ctx["eff_lead_days"]:
        return "High", cover_days
    if cover_days < ctx["eff_lead_days"] + 7 or ctx["stock"] < ctx["safety"] or ctx["stock"] > ctx["max_stock"]:
        return "Medium", cover_days
    return "Low", cover_days


def recommend(ctx, agent):
    state = state_of(ctx)
    q = list(agent.Q.get(state, [0.0] * len(ACTIONS)))
    visits = int(sum(agent.N.get(state, [0] * len(ACTIONS))))
    best = max(q)
    ties = [i for i, v in enumerate(q) if abs(v - best) < 1e-9]
    a = random.Random(f"{ctx['product_id']}|{state}").choice(ties) if len(ties) > 1 else ties[0]
    srt = sorted(q, reverse=True)
    margin = srt[0] - srt[1]
    conf = 0.5 * min(1.0, visits / 150.0) + 0.5 / (1 + math.exp(-3 * margin))
    conf = max(0.05, min(0.97, conf))
    trained = visits > 0

    action = ACTIONS[a]
    dw = ctx["demand_week"]
    pos = ctx["stock"] + ctx["incoming"]
    qty = 0
    note = None
    suggested = action
    mult = REPLENISH_MULT[action]
    if mult > 0:
        needed = max(0.0, ctx["safety"] + dw * ctx["eff_lead_days"] / 7.0 + ctx["pending_qty"] - pos)
        raw = max(mult * dw, needed)
        cap = max(0.0, ctx["max_stock"] - pos)
        qty = _r5(min(raw, cap))
        if qty < 5:
            qty = 0
            action, a = "WAIT", ACTIONS.index("WAIT")
            note = f"Q-agent preferred {LABELS[suggested]}, but position is already at max stock, so quantity was capped to 0 (WAIT)."
    label = LABELS[action]
    if action == "WAIT" and ctx["stock"] <= 1.5 * ctx["safety"]:
        label = "Maintain Safety Stock"
    supply_qty = _r5(min(ctx["pending_qty"], ctx["stock"])) if ctx["pending_qty"] > 0 else 0

    risk, cover_days = risk_of(ctx)
    parts = []
    if supply_qty > 0 and action in ("SUPPLY_NORMAL", "SUPPLY_HIGH", "ORDER_MORE"):
        parts.append("SUPPLY")
    if qty > 0:
        parts.append("REORDER")
    if action == "WAIT":
        headline = "MAINTAIN SAFETY STOCK" if label == "Maintain Safety Stock" else "WAIT"
    elif action == "REDUCE_STOCK":
        headline = "REDUCE STOCK"
    else:
        headline = " + ".join(parts) if parts else label.upper()
        if risk == "High" and qty > 0:
            headline = "HIGH PRIORITY REORDER"

    # ---- explanation
    unit = ctx["unit"]
    reasons = []
    wk_cover = pos / dw
    if ctx["stock"] < ctx["safety"]:
        reasons.append(f"Current stock ({ctx['stock']:.0f} {unit}) is below the safety-stock threshold ({ctx['safety']:.0f} {unit}).")
    elif ctx["stock"] > ctx["max_stock"]:
        reasons.append(f"Current stock ({ctx['stock']:.0f} {unit}) is above the maximum stock level ({ctx['max_stock']:.0f} {unit}).")
    else:
        reasons.append(f"Current stock ({ctx['stock']:.0f} {unit}) covers about {wk_cover:.1f} weeks of predicted demand; safety stock is {ctx['safety']:.0f} {unit}.")
    t = ctx["trend_pct"]
    direction = "up" if t >= 0 else "down"
    season_txt = "" if abs(ctx["seasonal"] - 1) < 0.015 else ", seasonal factor x%.2f" % ctx["seasonal"]
    reasons.append("Predicted 7-day demand is %.0f %s (%s %.0f%% in the 30-day trend%s)." % (dw, unit, direction, abs(t), season_txt))
    if ctx["n_pending"] > 0:
        reasons.append(f"{ctx['n_pending']} customer order(s) are pending, totalling {ctx['pending_qty']:.0f} {unit}.")
    else:
        reasons.append("No customer orders are currently pending.")
    buf_txt = ""
    if ctx["buffer_days"]:
        buf_txt = " (+%d day dispatch buffer for ~%.0f km average delivery distance)" % (ctx["buffer_days"], ctx["avg_distance"])
    reasons.append("Supplier lead time is %d days%s, so stock must last %d days before a new order arrives." % (ctx["lead_days"], buf_txt, ctx["eff_lead_days"]))
    if ctx["incoming"] > 0:
        reasons.append(f"{ctx['incoming']:.0f} {unit} is already on order (in transit).")
    if trained:
        second = sorted(range(len(q)), key=lambda i: -q[i])[1]
        reasons.append("Q-learning: state %s was seen %d times; best action %s has Q=%.2f vs next best %s Q=%.2f."
                       % (state, visits, suggested, q[ACTIONS.index(suggested)], ACTIONS[second], srt[1]))
    else:
        reasons.append("The Q-table has no experience for this state yet, so the agent is exploring. Train the agent to improve this decision.")
    if note:
        reasons.append(note)

    return {
        "product_id": ctx["product_id"], "product_name": ctx["name"], "unit": unit,
        "state": state, "state_parts": state.split("|"),
        "action": action, "action_index": a, "agent_action": suggested, "label": label, "headline": headline,
        "reorder_qty": qty, "supply_qty": supply_qty, "risk": risk, "confidence": round(conf * 100),
        "reasons": reasons, "note": note,
        "qvalues": [{"action": ACTIONS[i], "q": round(q[i], 3)} for i in range(len(ACTIONS))],
        "visits": visits, "trained": trained,
        "stock": round(ctx["stock"], 1), "safety": round(ctx["safety"], 1), "pending_qty": round(ctx["pending_qty"], 1),
        "n_pending": ctx["n_pending"], "d7": round(dw, 1), "d30": round(ctx["d30"], 1), "trend_pct": ctx["trend_pct"],
        "lead_days": ctx["lead_days"], "eff_lead_days": ctx["eff_lead_days"], "min_stock": ctx["min_stock"],
        "max_stock": ctx["max_stock"], "incoming": round(ctx["incoming"], 1),
        "cover_days": round(min(cover_days, 999), 1), "weeks_cover": round(wk_cover, 2),
    }
