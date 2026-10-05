"""
Self-Learning AI Supply & Inventory Optimization Agent  (Flask backend)

Portfolio prototype using synthetic data inspired by a multigrain and spice distribution workflow.
Run:  pip install -r requirements.txt  &&  python app.py   ->  http://127.0.0.1:5000
"""
import json
import math
import os
import random
import sqlite3
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import timedelta

import numpy as np
import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request
from flask.json.provider import DefaultJSONProvider

from ai import cost_model as cm
from ai import decision_engine as de
from ai import demand_prediction as dp
from ai.q_learning import (ACTIONS, ALL_STATES, EPISODE_LEN, REJECT_PENALTY, REWARDS, QAgent, env_obs, env_step)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
DB = os.path.join(BASE, "supply.db")
BRAIN_FILE = os.path.join(BASE, "brain", "ai_brain.json")
CSV_TABLES = ["products", "customers", "orders", "inventory", "supply_history"]
DISCLAIMER = ("This project is a portfolio prototype using synthetic data inspired by a "
              "multigrain and spice distribution workflow.")


class NPProvider(DefaultJSONProvider):
    @staticmethod
    def default(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, pd.Timestamp):
            return o.strftime("%Y-%m-%d")
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = NPProvider(app)
LOCK = threading.RLock()
agent = QAgent()


# ------------------------------------------------------------------ database
def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def q(sql, params=()):
    with closing(db()) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def run(sql, params=()):
    with closing(db()) as c:
        c.execute(sql, params)
        c.commit()


def df(sql, params=()):
    with closing(db()) as c:
        return pd.read_sql_query(sql, c, params=params)


def init_db(force=False):
    if not os.path.exists(os.path.join(DATA, "products.csv")):
        import generate_data
        generate_data.main()
    if os.path.exists(DB) and not force:
        return
    if os.path.exists(DB):
        os.remove(DB)
    with closing(sqlite3.connect(DB)) as c:
        for t in CSV_TABLES:
            d = pd.read_csv(os.path.join(DATA, t + ".csv"))
            if t == "inventory":
                d["pipeline"] = "[]"
            d.to_sql(t, c, index=False)
        c.execute("""CREATE TABLE decisions(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, product_id TEXT,
                     product_name TEXT, state TEXT, action TEXT, label TEXT, quantity REAL, status TEXT,
                     reward REAL, outcome TEXT, source TEXT)""")
        c.commit()


def frames():
    prods = df("""SELECT p.*, i.current_stock, i.pipeline, i.storage_zone FROM products p
                  JOIN inventory i ON i.product_id = p.product_id ORDER BY p.product_id""")
    orders = df("SELECT * FROM orders")
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    orders["required_date"] = pd.to_datetime(orders["required_date"])
    cust = df("SELECT * FROM customers ORDER BY customer_id")
    as_of = orders["order_date"].max().normalize()
    return prods, orders, cust, as_of


def contexts():
    prods, orders, cust, as_of = frames()
    ctxs = [de.build_context(r, orders, cust, as_of) for r in prods.to_dict("records")]
    return ctxs, prods, orders, cust, as_of


def stock_status(stock, mn, mx):
    if stock <= 0:
        return "Out of Stock"
    if stock < mn:
        return "Low Stock"
    if stock > mx:
        return "Overstock"
    return "Healthy"


def now_str():
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")


def r_int(x):
    return int(round(float(x)))


# ------------------------------------------------------------------- pages
@app.context_processor
def inject():
    return {"disclaimer": DISCLAIMER}


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/inventory")
def inventory():
    return render_template("inventory.html")


@app.route("/customers")
def customers():
    return redirect("/dealers")


@app.route("/dealers")
def dealers():
    return render_template("dealers.html")


@app.route("/dealers/<cid>")
def dealer_detail(cid):
    return render_template("dealer_detail.html", cid=cid)


@app.route("/demand")
def demand():
    return render_template("demand.html")


@app.route("/what-if")
def what_if():
    return render_template("what_if.html")


@app.route("/cost-optimization")
def cost_optimization():
    return render_template("cost.html")


@app.route("/system-health")
def system_health():
    return render_template("health.html")


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/settings")
def settings():
    return render_template("settings.html")


@app.route("/orders")
def orders():
    return render_template("orders.html")


@app.route("/ai-agent")
def ai_agent():
    return render_template("ai_agent.html")


@app.route("/training")
def training():
    return render_template("training.html")


@app.route("/route-planner")
def route_planner():
    return render_template("route_planner.html")


# --------------------------------------------------------------- data APIs
@app.get("/api/meta")
def api_meta():
    _, _, _, as_of = frames()
    s = agent.summary()
    return jsonify({"as_of": as_of, "episodes": s["episodes"], "q_states": s["q_states"],
                    "saved_at": agent.saved_at, "brain_file_exists": os.path.exists(BRAIN_FILE)})


@app.get("/api/inventory")
def api_inventory():
    ctxs, prods, _, _, _ = contexts()
    out = []
    for c, p in zip(ctxs, prods.to_dict("records")):
        rec = de.recommend(c, agent)
        out.append({
            "product_id": c["product_id"], "name": c["name"], "category": c["category"],
            "stock": c["stock"], "min_stock": c["min_stock"], "max_stock": c["max_stock"], "unit": c["unit"],
            "avg_monthly_demand": round(c["avg_monthly"], 1), "lead_time": c["lead_days"],
            "status": stock_status(c["stock"], c["min_stock"], c["max_stock"]),
            "reorder_qty": rec["reorder_qty"], "action": rec["label"], "risk": rec["risk"],
            "incoming": c["incoming"], "supplier": p["supplier"], "zone": p["storage_zone"],
        })
    return jsonify(out)


@app.get("/api/customers")
def api_customers():
    _, prods, orders_df, cust, as_of = contexts()
    st = dp.customer_stats(orders_df, cust, as_of)
    pn = dict(zip(prods.product_id, prods.product_name))
    m = cust[["customer_id", "customer_name", "location", "primary_product_id", "delivery_distance_km"]].merge(st, on="customer_id")
    out = []
    for r in m.to_dict("records"):
        out.append({
            "customer_id": r["customer_id"], "name": r["customer_name"], "location": r["location"],
            "product": pn.get(r["primary_product_id"], ""), "avg_order_qty": round(r["avg_order_qty"], 1),
            "orders_per_month": round(r["orders_per_month"], 2), "last_order": r["last_order"],
            "distance": r["delivery_distance_km"], "historical_demand": round(r["historical_demand"]),
            "return_rate": round(r["return_rate"], 1), "n_orders": r["n_orders"],
        })
    return jsonify(out)


def orders_list():
    return q("""SELECT o.order_id, o.customer_id, c.customer_name AS customer, o.product_id, p.product_name AS product,
                o.quantity, o.order_date, o.required_date, o.status, o.priority
                FROM orders o JOIN customers c ON c.customer_id=o.customer_id
                JOIN products p ON p.product_id=o.product_id ORDER BY o.order_date DESC, o.order_id DESC""")


@app.get("/api/orders")
def api_orders():
    return jsonify(orders_list())


@app.post("/api/orders")
def api_create_order():
    j = request.get_json(force=True)
    _, _, _, as_of = frames()
    cid, pid = j.get("customer_id"), j.get("product_id")
    try:
        qty = float(j.get("quantity", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity must be a number"}), 400
    if qty <= 0:
        return jsonify({"error": "Quantity must be greater than 0"}), 400
    if not q("SELECT 1 FROM customers WHERE customer_id=?", (cid,)) or not q("SELECT 1 FROM products WHERE product_id=?", (pid,)):
        return jsonify({"error": "Unknown customer or product"}), 400
    od = as_of
    try:
        req = pd.Timestamp(j.get("required_date") or (od + timedelta(days=5)))
    except Exception:
        return jsonify({"error": "Invalid delivery date"}), 400
    if req < od:
        return jsonify({"error": "Required delivery date cannot be before the order date"}), 400
    prio = j.get("priority", "Medium")
    if prio not in ("High", "Medium", "Low"):
        prio = "Medium"
    nxt = int(q("SELECT MAX(CAST(SUBSTR(order_id,5) AS INTEGER)) AS m FROM orders")[0]["m"] or 1000) + 1
    oid = f"ORD-{nxt}"
    run("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)", (oid, cid, pid, qty, od.strftime("%Y-%m-%d"), req.strftime("%Y-%m-%d"), "Pending", prio))
    return jsonify({"ok": True, "order_id": oid})


NEXT_STATUS = {"Pending": ["Confirmed"], "Confirmed": ["Dispatched"], "Dispatched": ["Delivered", "Returned"], "Delivered": ["Returned"]}


@app.post("/api/orders/<oid>/status")
def api_order_status(oid):
    new = request.get_json(force=True).get("status")
    with LOCK:
        rows = q("SELECT * FROM orders WHERE order_id=?", (oid,))
        if not rows:
            return jsonify({"error": "Order not found"}), 404
        o = rows[0]
        if new not in NEXT_STATUS.get(o["status"], []):
            return jsonify({"error": f"Cannot move order from {o['status']} to {new}"}), 400
        inv = q("SELECT current_stock FROM inventory WHERE product_id=?", (o["product_id"],))[0]["current_stock"]
        if new == "Dispatched":
            if inv < o["quantity"]:
                return jsonify({"error": f"Insufficient stock: {inv:.0f} kg available, {o['quantity']:.0f} kg needed"}), 400
            run("UPDATE inventory SET current_stock=current_stock-? WHERE product_id=?", (o["quantity"], o["product_id"]))
        if new == "Returned":
            run("UPDATE inventory SET current_stock=current_stock+? WHERE product_id=?", (o["quantity"], o["product_id"]))
        run("UPDATE orders SET status=? WHERE order_id=?", (new, oid))
    return jsonify({"ok": True})


# ------------------------------------------------------- AI recommendation
def find_ctx(pid):
    ctxs, *_ = contexts_p()
    for c in ctxs:
        if c["product_id"] == pid:
            return c
    return None


@app.get("/api/recommendations")
def api_recommendations():
    ctxs, *_ = contexts()
    return jsonify([de.recommend(c, agent) for c in ctxs])


@app.get("/api/recommendation/<pid>")
def api_recommendation(pid):
    c = find_ctx(pid)
    if not c:
        return jsonify({"error": "Product not found"}), 404
    rec = de.recommend(c, agent)
    rec["avg_distance"] = round(c["avg_distance"], 1)
    rec["seasonal"] = c["seasonal"]
    pos = c["stock"] + c["incoming"]
    rec["state_vars"] = {"cover_weeks": round(pos / c["demand_week"], 2), "demand_ratio": round(c["demand_week"] / c["base_week"], 2),
                         "pending_ratio": round(c["pending_qty"] / c["demand_week"], 2), "base_week": round(c["base_week"], 1)}
    s0, s1 = cm.simulate(c, 0, SETTINGS), cm.simulate(c, rec["reorder_qty"], SETTINGS)
    rec["impact"] = {"stockout_before": s0["stockout_prob"], "stockout_after": s1["stockout_prob"], "service_before": s0["service_level"],
                     "service_after": s1["service_level"], "cost_before": s0["total_cost"], "cost_after": s1["total_cost"],
                     "saving": round(s0["total_cost"] - s1["total_cost"], 1), "horizon_weeks": int(SETTINGS["horizon_weeks"])}
    rec["default_whatif"] = {"stock": round(c["stock"]), "demand": round(c["demand_week"]), "pending": round(c["pending_qty"]),
                             "lead": c["lead_days"], "distance": round(c["avg_distance"])}
    return jsonify(rec)


def apply_decision(pid, accepted=True, source="User"):
    """Apply (simulate outcome + learn) or reject (negative feedback) the current recommendation."""
    with LOCK:
        c = find_ctx(pid)
        if not c:
            return None
        rec = de.recommend(c, agent)
        a = rec["action_index"]
        s = rec["state"]
        p = agent.params
        old_q = agent.row(s)[a]
        if not accepted:
            agent.update(s, a, REJECT_PENALTY, s, p["alpha"], p["gamma"], terminal=True)
            run("INSERT INTO decisions(ts,product_id,product_name,state,action,label,quantity,status,reward,outcome,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (now_str(), pid, rec["product_name"], s, ACTIONS[a], rec["label"], rec["reorder_qty"], "Rejected", REJECT_PENALTY,
                 "Rejected by user - negative feedback", source))
            return {"status": "Rejected", "reward": REJECT_PENALTY, "q_old": old_q, "q_new": agent.Q[s][a], "state": s,
                    "action": ACTIONS[a], "label": rec["label"], "outcome": "Recommendation rejected: agent receives a small penalty."}
        env = de.env_from_ctx(c)
        env2, r, info = env_step(env, a, random.Random(), qty=rec["reorder_qty"])
        s2 = env_obs(env2)
        agent.update(s, a, r, s2, p["alpha"], p["gamma"])
        # persist the simulated business outcome
        run("UPDATE inventory SET current_stock=?, pipeline=?, last_updated=? WHERE product_id=?",
            (max(0.0, round(env2["S"], 1)), json.dumps(env2["pipe"]), now_str()[:10], pid))
        remaining = info["sold"]
        open_o = q("SELECT * FROM orders WHERE product_id=? AND status IN ('Pending','Confirmed')", (pid,))
        rank = {"High": 0, "Medium": 1, "Low": 2}
        open_o.sort(key=lambda o: (rank.get(o["priority"], 1), o["required_date"]))
        dispatched = 0
        for o in open_o:
            if o["quantity"] <= remaining + 1e-6:
                remaining -= o["quantity"]
                run("UPDATE orders SET status='Dispatched' WHERE order_id=?", (o["order_id"],))
                dispatched += 1
        f = info["flags"]
        if info["stockout"]:
            outcome = "Late supply: stockout while replenishment was in transit" if f.get("late_supply") else "Stockout: demand could not be fully met"
        elif info["excess"]:
            outcome = "Demand met, but excess inventory built up"
        else:
            outcome = "Demand satisfied with healthy stock"
        run("INSERT INTO decisions(ts,product_id,product_name,state,action,label,quantity,status,reward,outcome,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (now_str(), pid, rec["product_name"], s, ACTIONS[a], rec["label"], rec["reorder_qty"], "Applied", round(r, 2), outcome, source))
        sid = int(q("SELECT COUNT(*) AS n FROM supply_history")[0]["n"]) + 1
        run("INSERT INTO supply_history VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"SH-{sid:04d}", now_str()[:10], pid, c["stock"], round(c["demand_week"], 1), c["pending_qty"], ACTIONS[a],
             rec["reorder_qty"], c["lead_days"], round(info["demand"], 1), round(env2["S"], 1), int(info["stockout"]),
             int(info["excess"]), int(bool(f.get("late_supply"))), round(r, 2), outcome))
        return {
            "status": "Applied", "reward": round(r, 2), "q_old": old_q, "q_new": agent.Q[s][a], "state": s, "next_state": s2,
            "action": ACTIONS[a], "label": rec["label"], "quantity": rec["reorder_qty"], "outcome": outcome,
            "flags": f, "demand": round(info["demand"], 1), "sold": round(info["sold"], 1), "fill_pct": round(100 * info["fill"], 1),
            "stock_before": round(c["stock"], 1), "stock_after": round(env2["S"], 1), "dispatched_orders": dispatched,
            "incoming": round(sum(x[1] for x in env2["pipe"]), 1),
        }


@app.post("/api/recommendation/<pid>/apply")
def api_apply(pid):
    r = apply_decision(pid, True)
    return (jsonify(r), 200) if r else (jsonify({"error": "Product not found"}), 404)


@app.post("/api/recommendation/<pid>/reject")
def api_reject(pid):
    r = apply_decision(pid, False)
    return (jsonify(r), 200) if r else (jsonify({"error": "Product not found"}), 404)


@app.post("/api/whatif")
def api_whatif():
    j = request.get_json(force=True)
    c = find_ctx(j.get("product_id", "P001"))
    if not c:
        return jsonify({"error": "Product not found"}), 404
    try:
        vals = {k: float(j[k]) for k in ("stock", "demand", "pending", "lead", "distance")}
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "All five inputs must be numbers"}), 400
    if min(vals.values()) < 0 or vals["demand"] <= 0 or vals["lead"] < 1:
        return jsonify({"error": "Demand and lead time must be positive; other inputs cannot be negative"}), 400
    c2 = de.with_overrides(c, stock=vals["stock"], demand=vals["demand"], pending=vals["pending"], lead=vals["lead"], distance=vals["distance"])
    rec = de.recommend(c2, agent)
    rec["inputs"] = vals
    return jsonify(rec)


# ------------------------------------------------------------ dashboard
def decisions_recent(n=8):
    return q("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (n,))


@app.get("/api/dashboard")
def api_dashboard():
    ctxs, prods, orders_df, cust, as_of = contexts()
    recs = [de.recommend(c, agent) for c in ctxs]
    inv = [{"name": c["name"], "stock": c["stock"], "d7": round(c["demand_week"], 1), "safety": round(c["safety"], 1),
            "status": stock_status(c["stock"], c["min_stock"], c["max_stock"])} for c in ctxs]
    status_counts = orders_df["status"].value_counts().to_dict()
    pending = int(orders_df["status"].isin(["Pending", "Confirmed"]).sum())
    action_today = [r for r in recs if r["action"] != "WAIT" or r["label"] == "Maintain Safety Stock"]
    with LOCK:
        ev = agent.evaluate(200, "greedy" if agent.episodes else "random")
        s = agent.summary()
    hist = agent.history
    step = max(1, len(hist) // 120)
    curve = [round(sum(x[0] for x in hist[i:i + step]) / len(hist[i:i + step]), 2) for i in range(0, len(hist), step)]
    return jsonify({
        "as_of": as_of, "total_products": len(ctxs), "total_inventory": round(sum(c["stock"] for c in ctxs)),
        "pending_orders": pending, "low_stock": sum(1 for i in inv if i["status"] in ("Low Stock", "Out of Stock")),
        "recommended_supplies": len([r for r in recs if r["reorder_qty"] > 0 or r["supply_qty"] > 0]),
        "predicted_demand": round(sum(c["demand_week"] for c in ctxs)),
        "ai_accuracy": ev["decision_accuracy"], "ai_reward": ev["average_reward"], "episodes": s["episodes"],
        "q_states": s["q_states"], "q_states_total": s["q_states_total"], "n_orders": len(orders_df),
        "inventory": inv, "order_status": status_counts,
        "top_recs": sorted(recs, key=lambda r: {"High": 0, "Medium": 1, "Low": 2}[r["risk"]])[:6],
        "recent_decisions": decisions_recent(), "curve": curve, "n_actions": len(action_today),
        "low_names": [i["name"] for i in inv if i["status"] in ("Low Stock", "Out of Stock")],
    })


# ------------------------------------------------------------- training
def write_training_csv():
    h = agent.history
    if not h:
        return
    step = 20
    rows = []
    for i in range(0, len(h), step):
        ch = h[i:i + step]
        n = len(ch)
        rows.append({"episode": i + n, "avg_episode_reward": round(sum(x[0] for x in ch) / n, 3),
                     "decision_accuracy": round(100 * sum(x[1] for x in ch) / n, 1),
                     "stockout_rate": round(100 * sum(x[2] for x in ch) / n, 1),
                     "excess_rate": round(100 * sum(x[3] for x in ch) / n, 1), "epsilon": ch[-1][5]})
    pd.DataFrame(rows).to_csv(os.path.join(DATA, "training_results.csv"), index=False)


def clampf(v, lo, hi, default):
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return default


@app.post("/api/train")
def api_train():
    j = request.get_json(force=True)
    n = int(clampf(j.get("episodes", 25), 1, 2000, 25))
    with LOCK:
        out = agent.train(n, alpha=clampf(j.get("alpha"), 0.001, 1.0, 0.1), gamma=clampf(j.get("gamma"), 0.0, 0.999, 0.9),
                          eps_start=clampf(j.get("epsilon"), 0.0, 1.0, 0.9), offset=int(clampf(j.get("offset", 0), 0, 1e7, 0)),
                          total=int(clampf(j.get("total", n), 1, 1e7, n)))
    return jsonify(out)


@app.post("/api/training/finish")
def api_training_finish():
    with LOCK:
        write_training_csv()
    return jsonify({"ok": True, "csv": "data/training_results.csv"})


@app.get("/api/training/state")
def api_training_state():
    with LOCK:
        s = agent.summary()
        s["episode_rewards"] = [x[0] for x in agent.history]
        s["qtable"] = agent.qtable()
        s["saved_at"] = agent.saved_at
        s["brain_file_exists"] = os.path.exists(BRAIN_FILE)
    return jsonify(s)


@app.post("/api/training/reset")
def api_training_reset():
    with LOCK:
        agent.reset()
    return jsonify({"ok": True})


@app.post("/api/evaluate")
def api_evaluate():
    n = int(clampf((request.get_json(silent=True) or {}).get("episodes", 300), 50, 1000, 300))
    with LOCK:
        before = agent.evaluate(n, "random")
        after = agent.evaluate(n, "greedy")
        eps = agent.episodes
    return jsonify({"before": before, "after": after, "episodes_trained": eps})


@app.post("/api/brain/save")
def api_brain_save():
    with LOCK:
        t = agent.save(BRAIN_FILE)
        write_training_csv()
    return jsonify({"ok": True, "saved_at": t, "episodes": agent.episodes})


@app.post("/api/brain/load")
def api_brain_load():
    if not os.path.exists(BRAIN_FILE):
        return jsonify({"error": "No saved brain found. Click Save AI Brain first."}), 404
    with LOCK:
        agent.load(BRAIN_FILE)
    return jsonify({"ok": True, "episodes": agent.episodes, "saved_at": agent.saved_at})


@app.post("/api/reset-data")
def api_reset_data():
    with LOCK:
        init_db(force=True)
    return jsonify({"ok": True})


# ------------------------------------------------------------------ demo
@app.post("/api/demo")
def api_demo():
    """Full demo: resets the brain, runs one decision loop, then trains and shows improved metrics."""
    with LOCK:
        agent.reset()
        steps = []
        ctxs, prods, orders_df, cust, as_of = contexts()
        low = [c["name"] for c in ctxs if stock_status(c["stock"], c["min_stock"], c["max_stock"]) in ("Low Stock", "Out of Stock")]
        steps.append({"n": 1, "node": [0], "title": "Load inventory",
                      "text": f"Loaded {len(ctxs)} products, {len(orders_df)} historical orders and {len(cust)} dealers. "
                              f"Total stock {sum(c['stock'] for c in ctxs):,.0f} kg; low/out-of-stock: {', '.join(low) or 'none'}."})
        movers = sorted(ctxs, key=lambda c: -abs(c["trend_pct"]))[:3]
        steps.append({"n": 2, "node": [1], "title": "Analyze demand",
                      "text": "Predicted 7-day demand: %s kg. Biggest 30-day movers: %s." % (
                          f"{sum(c['demand_week'] for c in ctxs):,.0f}", ", ".join(f"{c['name']} ({c['trend_pct']:+.0f}%)" for c in movers))})
        rank = {"High": 0, "Medium": 1, "Low": 2}
        recs = [de.recommend(c, agent) for c in ctxs]
        top = sorted(recs, key=lambda r: (rank[r["risk"]], r["cover_days"]))[0]
        steps.append({"n": 3, "node": [2, 3, 4], "title": "Generate AI recommendation",
                      "text": f"{top['product_name']}: state {top['state']}. Untrained agent recommends {top['label']} "
                              f"(reorder {top['reorder_qty']} kg, risk {top['risk']}, confidence {top['confidence']}%).",
                      "reasons": top["reasons"][:4]})
        res = apply_decision(top["product_id"], True, source="Demo")
        steps.append({"n": 4, "node": [4], "title": "Execute simulated supply",
                      "text": f"Simulated one week: ordered {res['quantity']} kg, demand {res['demand']} kg, sold {res['sold']} kg. "
                              f"Stock {res['stock_before']} -> {res['stock_after']} kg; {res['dispatched_orders']} pending order(s) dispatched."})
        steps.append({"n": 5, "node": [5], "title": "Calculate result",
                      "text": f"Fill rate {res['fill_pct']}%. Outcome: {res['outcome']}."})
        steps.append({"n": 6, "node": [6], "title": "Reward / penalty",
                      "text": f"Reward = {res['reward']:+.2f}  (" + ", ".join(k.replace('_', ' ') for k in res["flags"]) + ")"})
        steps.append({"n": 7, "node": [7], "title": "Update Q-learning model",
                      "text": f"Q({res['state']}, {res['action']}) changed {res['q_old']:.3f} -> {res['q_new']:.3f}. "
                              "Now training 1,500 simulated episodes so the agent learns the whole policy."})
        agent.train(1500, alpha=0.1, gamma=0.9, eps_start=0.9, offset=0, total=1500)
        write_training_csv()
        before, after = agent.evaluate(300, "random"), agent.evaluate(300, "greedy")
        steps.append({"n": 8, "node": [0, 1, 2, 3, 4, 5, 6, 7], "title": "Show improved metrics",
                      "text": f"Decision accuracy {before['decision_accuracy']}% -> {after['decision_accuracy']}%, "
                              f"stockout rate {before['stockout_rate']}% -> {after['stockout_rate']}%. "
                              "All numbers come from the simulation (300 evaluation episodes).",
                      "before": before, "after": after})
        return jsonify({"steps": steps, "episodes": agent.episodes})


# -------------------------------------------------------- route planner
SPEED_KMH, SERVICE_H, ROAD = 35.0, 0.4, 1.25


def hav(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) * ROAD


def evaluate_route(order, stops, as_of):
    pos, hours, dist, cost = (0.0, 0.0), 0.0, 0.0, 0.0
    legs = []
    wt = {"High": 3.0, "Medium": 1.5, "Low": 0.5}
    for i in order:
        s = stops[i]
        d = hav(pos, (s["x"], s["y"]))
        dist += d
        hours += d / SPEED_KMH
        arrival = hours
        day_off = int((8 + arrival) // 24)
        late_days = max(0, (as_of + timedelta(days=day_off) - s["deadline_ts"]).days)
        cost += d + 150.0 * late_days + wt[s["priority"]] * arrival * 2.0
        legs.append((i, d, arrival, late_days))
        hours += SERVICE_H
        pos = (s["x"], s["y"])
    back = hav(pos, (0.0, 0.0))
    dist += back
    hours += back / SPEED_KMH
    return dist, hours, cost, legs, back


def plan_route(include_confirmed=True):
    _, orders_df, cust, as_of = frames()
    sts = ["Pending", "Confirmed"] if include_confirmed else ["Pending"]
    o = orders_df[orders_df["status"].isin(sts)].merge(cust, on="customer_id")
    stops = []
    for cid, g in o.groupby("customer_id"):
        r = g.iloc[0]
        pr = "High" if (g["priority"] == "High").any() else ("Medium" if (g["priority"] == "Medium").any() else "Low")
        dl = g["required_date"].min()
        stops.append({"customer_id": cid, "name": r["customer_name"], "location": r["location"], "x": float(r["x_km"]),
                      "y": float(r["y_km"]), "orders": int(len(g)), "qty": float(g["quantity"].sum()), "priority": pr,
                      "deadline": dl.strftime("%Y-%m-%d"), "deadline_ts": dl})
    allc = [{"name": r["customer_name"], "x": float(r["x_km"]), "y": float(r["y_km"]), "id": r["customer_id"]} for r in cust.to_dict("records")]
    if not stops:
        return {"stops": [], "all_customers": allc, "total_km": 0, "total_hours": 0, "n_stops": 0, "sequence": ["Warehouse"],
                "naive_km": 0, "saving_pct": 0, "as_of": as_of, "message": "No pending or confirmed orders to deliver."}
    n = len(stops)
    naive = list(range(n))
    nd = evaluate_route(naive, stops, as_of)[0]
    # greedy construction (priority + urgency + distance), then 2-opt / swap improvement on the weighted cost
    rem, cur, order = set(range(n)), (0.0, 0.0), []
    wt = {"High": 40.0, "Medium": 15.0, "Low": 0.0}
    while rem:
        def score(i):
            s = stops[i]
            urgency = max(0, 10 - (s["deadline_ts"] - as_of).days) * 6.0
            return hav(cur, (s["x"], s["y"])) - wt[s["priority"]] - urgency
        nx = min(rem, key=score)
        order.append(nx)
        rem.remove(nx)
        cur = (stops[nx]["x"], stops[nx]["y"])
    best = evaluate_route(order, stops, as_of)[2]
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 1, n):
                cand = order[:i] + order[i:j + 1][::-1] + order[j + 1:]
                c = evaluate_route(cand, stops, as_of)[2]
                if c < best - 1e-6:
                    order, best, improved = cand, c, True
    dist, hours, _, legs, back = evaluate_route(order, stops, as_of)
    out = []
    for k, (i, d, arr, late) in enumerate(legs, 1):
        s = stops[i]
        h = 8 + arr
        out.append({"seq": k, "customer_id": s["customer_id"], "name": s["name"], "location": s["location"], "x": s["x"], "y": s["y"],
                    "orders": s["orders"], "qty": s["qty"], "priority": s["priority"], "deadline": s["deadline"],
                    "leg_km": round(d, 1), "arrival": f"Day {int(h // 24) + 1}, {int(h % 24):02d}:{int((h % 1) * 60):02d}", "late": late > 0})
    return {"stops": out, "all_customers": allc, "total_km": round(dist, 1), "total_hours": round(hours, 1), "n_stops": n,
            "sequence": ["Warehouse"] + [s["name"] for s in out] + ["Warehouse"], "naive_km": round(nd, 1),
            "saving_pct": round(max(0.0, 100 * (nd - dist) / nd), 1) if nd > 0 else 0, "as_of": as_of, "return_km": round(back, 1)}


@app.route("/api/route", methods=["GET", "POST"])
def api_route():
    j = request.get_json(silent=True) or {}
    inc = j.get("include_confirmed", request.args.get("include_confirmed", "1") not in ("0", "false"))
    return jsonify(plan_route(bool(inc)))


# ======================================================================
#  SupplyMind AI v2 additions (command center, intelligence pages, health)
# ======================================================================
VERSION = "2.0.0"
SETTINGS_FILE = os.path.join(BASE, "settings.json")
REPORT_XML = os.path.join(BASE, "tests", "report.xml")
QUALITY_JSON = os.path.join(BASE, "tests", "last_run.json")
SETTINGS = dict(cm.DEFAULTS)
_CACHE = {}


def load_settings():
    SETTINGS.update(cm.DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
                for k, v in json.load(fh).items():
                    if k in cm.DEFAULTS:
                        SETTINGS[k] = v
        except Exception:
            pass


def contexts_p():
    """contexts() plus unit price / supplier on every context."""
    ctxs, prods, orders_df, cust, as_of = contexts()
    for c, p in zip(ctxs, prods.to_dict("records")):
        c["price"] = float(p["unit_price"])
        c["supplier"] = p["supplier"]
    return ctxs, prods, orders_df, cust, as_of


def status2(c):
    if c["stock"] <= 0 or c["stock"] < 0.5 * c["min_stock"]:
        return "Critical"
    if c["stock"] < c["min_stock"]:
        return "Low Stock"
    if c["stock"] > c["max_stock"]:
        return "Overstock"
    return "Healthy"


def pct_change(new, old):
    if old is None or old == 0:
        return None
    return round(100.0 * (new - old) / abs(old), 1)


def backtests(orders_df, ctxs, as_of):
    key = ("bt", str(as_of), len(orders_df), float(orders_df["quantity"].sum()))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = {c["product_id"]: {
            "h7": dp.backtest(orders_df, c["product_id"], c["category"], as_of, points=8, step=3, horizon=7),
            "h30": dp.backtest(orders_df, c["product_id"], c["category"], as_of, points=6, step=7, horizon=30)} for c in ctxs}
    return _CACHE[key]


def build_alerts(ctxs, recs, orders_df, as_of):
    out = []
    ts = as_of.strftime("%Y-%m-%d") + " (simulation date)"
    sev_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "OPPORTUNITY": 3}
    for c, r in zip(ctxs, recs):
        n = c["name"]
        action = r["label"] + (f" {r['reorder_qty']} kg" if r["reorder_qty"] else "")
        if r["risk"] == "High" and r["cover_days"] < c["eff_lead_days"]:
            d = max(0, int(r["cover_days"]))
            out.append({"severity": "CRITICAL", "product": n, "product_id": c["product_id"],
                        "title": f"{n} may stock out in {d} day{'s' if d != 1 else ''}",
                        "reason": f"Net stock ({c['stock'] - c['pending_qty']:.0f} kg after pending orders) covers {r['cover_days']:.0f} days but the effective lead time is {c['eff_lead_days']} days.",
                        "action": action, "timestamp": ts})
        if c["trend_pct"] >= 15:
            out.append({"severity": "HIGH", "product": n, "product_id": c["product_id"],
                        "title": f"{n} demand increased by {c['trend_pct']:.0f}%",
                        "reason": "Last 30 days of orders are well above the previous 30 days.", "action": action, "timestamp": ts})
        if c["stock"] > c["max_stock"]:
            out.append({"severity": "MEDIUM", "product": n, "product_id": c["product_id"],
                        "title": f"{n} is overstocked ({c['stock']:.0f} kg > max {c['max_stock']:.0f} kg)",
                        "reason": "Holding cost grows while stock sits above the maximum level.", "action": "Pause reordering / reduce stock", "timestamp": ts})
        if 10 <= c["trend_pct"] < 15 and status2(c) == "Healthy":
            out.append({"severity": "OPPORTUNITY", "product": n, "product_id": c["product_id"],
                        "title": f"{n} demand is trending upward (+{c['trend_pct']:.0f}%)",
                        "reason": "Stock is healthy; consider securing supply ahead of further growth.", "action": action, "timestamp": ts})
    open_o = orders_df[orders_df["status"].isin(["Pending", "Confirmed"])]
    stock = {c["product_id"]: c["stock"] for c in ctxs}
    risky = []
    for pid, g in open_o.groupby("product_id"):
        need = g["quantity"].sum()
        soon = g[(g["required_date"] - as_of).dt.days <= 5]
        if len(soon) and stock.get(pid, 0) < need:
            risky.append((pid, len(soon)))
    if risky:
        names = {c["product_id"]: c["name"] for c in ctxs}
        tot = sum(n for _, n in risky)
        out.append({"severity": "MEDIUM", "product": ", ".join(names[p] for p, _ in risky[:3]), "product_id": risky[0][0],
                    "title": f"{tot} dealer order(s) may miss the delivery target",
                    "reason": "Open orders are due within 5 days but available stock does not cover all pending quantity.",
                    "action": "Prioritise supply for these products", "timestamp": ts})
    for i, a in enumerate(sorted(out, key=lambda a: sev_rank[a["severity"]])):
        a["id"] = i + 1
    return sorted(out, key=lambda a: sev_rank[a["severity"]])


@app.get("/api/alerts")
def api_alerts():
    ctxs, _, orders_df, _, as_of = contexts_p()
    recs = [de.recommend(c, agent) for c in ctxs]
    return jsonify(build_alerts(ctxs, recs, orders_df, as_of))


def hist_inventory_value(price):
    sh = df("SELECT product_id, stock_after FROM supply_history ORDER BY product_id, week_start, record_id")
    tot, ok = 0.0, False
    for pid, g in sh.groupby("product_id"):
        if len(g) >= 5:
            tot += float(g.iloc[-5]["stock_after"]) * price.get(pid, 0)
            ok = True
    return tot if ok else None


@app.get("/api/command-center")
def api_command_center():
    ctxs, prods, orders_df, cust, as_of = contexts_p()
    P = SETTINGS
    recs = [de.recommend(c, agent) for c in ctxs]
    sims = [(cm.simulate(c, 0, P), cm.simulate(c, r["reorder_qty"], P)) for c, r in zip(ctxs, recs)]
    price = {c["product_id"]: c["price"] for c in ctxs}
    inv_value = sum(c["stock"] * c["price"] for c in ctxs)
    prev_value = hist_inventory_value(price)
    od = orders_df["order_date"]
    new7 = int(((od > as_of - timedelta(days=7)) & (od <= as_of)).sum())
    prev7 = int(((od > as_of - timedelta(days=14)) & (od <= as_of - timedelta(days=7))).sum())
    pending = int(orders_df["status"].isin(["Pending", "Confirmed"]).sum())
    d7 = sum(c["demand_week"] for c in ctxs)
    wk = {c["product_id"]: dp.weekly_actuals(orders_df, c["product_id"], as_of, 8) for c in ctxs}
    last_week = sum(v[-1] for v in wk.values())
    bt = backtests(orders_df, ctxs, as_of)
    allrows = [r for v in bt.values() for r in v["h30"]]
    acc = dp.accuracy_metrics(allrows)
    risk_high = sum(1 for r in recs if r["risk"] == "High")
    so_none = sum(1 for s0, _ in sims if s0["stockout_prob"] >= 30)
    so_ai = sum(1 for _, s1 in sims if s1["stockout_prob"] >= 30)
    dem0 = sum(s0["demand"] for s0, _ in sims) or 1
    sl0 = 100 * sum(s0["sold"] for s0, _ in sims) / dem0
    sl1 = 100 * sum(s1["sold"] for _, s1 in sims) / (sum(s1["demand"] for _, s1 in sims) or 1)
    cost0 = sum(s0["total_cost"] for s0, _ in sims)
    cost1 = sum(s1["total_cost"] for _, s1 in sims)
    alerts = build_alerts(ctxs, recs, orders_df, as_of)
    rank = {"High": 0, "Medium": 1, "Low": 2}
    order = sorted(range(len(recs)), key=lambda i: (rank[recs[i]["risk"]], -recs[i]["reorder_qty"]))
    i = order[0]
    r, (s0, s1) = recs[i], sims[i]
    top = dict(r)
    top["impact"] = {
        "stockout_risk_before": s0["stockout_prob"], "stockout_risk_after": s1["stockout_prob"],
        "stockout_risk_reduction_pct": round(100 * (s0["stockout_prob"] - s1["stockout_prob"]) / s0["stockout_prob"], 0) if s0["stockout_prob"] > 0 else 0,
        "service_before": s0["service_level"], "service_after": s1["service_level"],
        "service_delta_pts": round(s1["service_level"] - s0["service_level"], 1),
        "cost_saving": round(s0["total_cost"] - s1["total_cost"], 0), "horizon_weeks": int(P["horizon_weeks"])}
    cats = {}
    for c in ctxs:
        cats.setdefault(c["category"], [0.0] * 8)
        cats[c["category"]] = [a + b for a, b in zip(cats[c["category"]], wk[c["product_id"]])]
    weekly_total = [sum(v[k] for v in wk.values()) for k in range(8)]
    with LOCK:
        s = agent.summary()
        hist = agent.history
    step = max(1, len(hist) // 100)
    curve = [round(sum(x[0] for x in hist[j:j + step]) / len(hist[j:j + step]), 2) for j in range(0, len(hist), step)]
    return jsonify({
        "as_of": as_of, "trained": s["episodes"] > 0, "episodes": s["episodes"],
        "kpis": {
            "inventory_value": {"value": inv_value, "change_pct": pct_change(inv_value, prev_value), "basis": "vs ~4 weeks ago (supply history)"},
            "pending_orders": {"value": pending, "change_pct": pct_change(new7, prev7), "basis": "new orders, last 7 days vs previous 7"},
            "stockout_risk": {"value": risk_high, "ai_flagged": so_ai, "no_action_flagged": so_none, "basis": "products with stockout probability >= 30% (simulated): no action vs AI"},
            "forecast_demand": {"value": d7, "change_pct": pct_change(d7, last_week), "basis": "vs actual demand of the last 7 days"},
            "forecast_accuracy": {"value": acc["accuracy"], "naive": acc["naive_accuracy"], "basis": "30-day horizon rolling backtest on synthetic orders (100 - WAPE) vs naive baseline"},
            "ai_savings": {"value": cost0 - cost1, "pct": round(100 * (cost0 - cost1) / cost0, 1) if cost0 else 0, "basis": f"simulated {int(P['horizon_weeks'])}-week cost: AI action vs no action"},
            "service_level": {"value": sl1, "delta_pts": round(sl1 - sl0, 1), "basis": "simulated fill rate: AI action vs no action"},
            "alerts": {"value": len(alerts), "critical": sum(1 for a in alerts if a["severity"] == "CRITICAL")},
        },
        "decision": top, "alerts": alerts[:6],
        "inventory": [{"name": c["name"], "stock": c["stock"], "d7": round(c["demand_week"], 1), "safety": round(c["safety"], 1)} for c in ctxs],
        "weekly_total": [round(x, 1) for x in weekly_total], "forecast_next": round(d7, 1),
        "order_status": orders_df["status"].value_counts().to_dict(), "curve": curve,
        "recent_decisions": decisions_recent(6), "q_states": s["q_states"], "q_states_total": s["q_states_total"],
        "categories": {k: [round(x, 1) for x in v] for k, v in cats.items()},
    })


@app.get("/api/inventory-intel")
def api_inventory_intel():
    ctxs, prods, orders_df, _, as_of = contexts_p()
    out = []
    for c, p in zip(ctxs, prods.to_dict("records")):
        r = de.recommend(c, agent)
        s0 = cm.simulate(c, 0, SETTINGS, n=150)
        rp = cm.reorder_point(c)
        out.append({
            "product_id": c["product_id"], "name": c["name"], "category": c["category"], "supplier": c["supplier"],
            "stock": c["stock"], "d7": round(c["demand_week"], 1), "safety": round(c["safety"], 1), "reorder_point": round(rp, 1),
            "stockout_prob": s0["stockout_prob"], "risk": r["risk"], "recommendation": r["label"], "reorder_qty": r["reorder_qty"],
            "status": status2(c), "min_stock": c["min_stock"], "max_stock": c["max_stock"], "unit": c["unit"],
            "reorder_status": "On order" if c["incoming"] > 0 else ("Reorder now" if c["stock"] <= rp else "OK"),
            "price": c["price"], "value": round(c["stock"] * c["price"]),
        })
    return jsonify(out)


@app.get("/api/product/<pid>")
def api_product(pid):
    ctxs, prods, orders_df, cust, as_of = contexts_p()
    c = next((x for x in ctxs if x["product_id"] == pid), None)
    if not c:
        return jsonify({"error": "Product not found"}), 404
    r = de.recommend(c, agent)
    s0, s1 = cm.simulate(c, 0, SETTINGS), cm.simulate(c, r["reorder_qty"], SETTINGS)
    po = orders_df[(orders_df["product_id"] == pid) & orders_df["status"].isin(["Pending", "Confirmed"])].merge(cust[["customer_id", "customer_name"]], on="customer_id")
    bt7 = dp.backtest(orders_df, pid, c["category"], as_of)
    bt30 = dp.backtest(orders_df, pid, c["category"], as_of, points=6, step=7, horizon=30)
    return jsonify({
        "product_id": pid, "name": c["name"], "category": c["category"], "supplier": c["supplier"], "unit": c["unit"],
        "stock": c["stock"], "min_stock": c["min_stock"], "max_stock": c["max_stock"], "safety": round(c["safety"], 1),
        "reorder_point": round(cm.reorder_point(c), 1), "lead_days": c["lead_days"], "eff_lead_days": c["eff_lead_days"],
        "d7": round(c["demand_week"], 1), "d30": round(c["d30"], 1), "trend_pct": c["trend_pct"], "status": status2(c),
        "weekly_history": [round(x, 1) for x in dp.weekly_actuals(orders_df, pid, as_of, 12)],
        "pending": [{"order_id": o["order_id"], "customer": o["customer_name"], "quantity": o["quantity"], "required": o["required_date"].strftime("%Y-%m-%d"), "priority": o["priority"], "status": o["status"]} for o in po.to_dict("records")],
        "recommendation": r, "cost_no_action": s0, "cost_ai": s1, "accuracy": dp.accuracy_metrics(bt30), "accuracy_7d": dp.accuracy_metrics(bt7), "price": c["price"],
    })


@app.get("/api/demand")
def api_demand():
    ctxs, prods, orders_df, _, as_of = contexts_p()
    bt = backtests(orders_df, ctxs, as_of)
    items, cats = [], {}
    for c in ctxs:
        hist = dp.weekly_actuals(orders_df, c["product_id"], as_of, 12)
        fc = dp.forecast(orders_df, c["product_id"], c["category"], as_of)
        m = dp.accuracy_metrics(bt[c["product_id"]]["h30"])
        m7 = dp.accuracy_metrics(bt[c["product_id"]]["h7"])
        cats.setdefault(c["category"], [0.0] * 12)
        cats[c["category"]] = [a + b for a, b in zip(cats[c["category"]], hist)]
        items.append({"product_id": c["product_id"], "name": c["name"], "category": c["category"], "d7": round(fc["d7"], 1),
                      "d30": round(fc["d30"], 1), "trend_pct": fc["trend_pct"], "seasonal": fc["seasonal"], "last_week": round(hist[-1], 1),
                      "history": [round(x, 1) for x in hist], "backtest": bt[c["product_id"]]["h7"], "backtest30": bt[c["product_id"]]["h30"],
                      "confidence": m["accuracy"], "naive_confidence": m["naive_accuracy"], "confidence_7d": m7["accuracy"], "avg_monthly": round(fc["avg_monthly"], 1)})
    return jsonify({"items": items, "categories": {k: [round(x, 1) for x in v] for k, v in cats.items()}, "as_of": as_of,
                    "method": "Weighted moving average (30/60/90 d) x trend x seasonal index. Confidence = 100 - WAPE of a rolling 30-day-horizon backtest on synthetic data (7-day shown separately)."})


def dealer_rows():
    ctxs, prods, orders_df, cust, as_of = contexts_p()
    price = {c["product_id"]: c["price"] for c in ctxs}
    pn = {c["product_id"]: c["name"] for c in ctxs}
    o = orders_df.copy()
    o["value"] = o["quantity"] * o["product_id"].map(price)
    rows = []
    for c in cust.to_dict("records"):
        g = o[o["customer_id"] == c["customer_id"]]
        open_g = g[g["status"].isin(["Pending", "Confirmed"])]
        rev = float(g[g["status"].isin(["Delivered", "Dispatched"])]["value"].sum())
        ret = float((g["status"] == "Returned").mean() * 100) if len(g) else 0.0
        late = int(((open_g["required_date"] - as_of).dt.days <= 2).sum())
        rows.append({"customer_id": c["customer_id"], "name": c["customer_name"], "location": c["location"],
                     "product": pn.get(c["primary_product_id"], ""), "orders": int(len(g)), "pending": int(len(open_g)),
                     "revenue": round(rev), "avg_order": round(float(g["quantity"].mean()), 1) if len(g) else 0.0,
                     "distance": float(c["delivery_distance_km"]), "return_rate": round(ret, 1), "urgent_open": late,
                     "has_high_open": bool((open_g["priority"] == "High").any())})
    if rows:
        thr = sorted(r["revenue"] for r in rows)[int(len(rows) * 0.75)]
        maxd = max(r["distance"] for r in rows) or 1
        for r in rows:
            score = 0.4 * min(r["return_rate"] / 10.0, 1) + 0.3 * min(r["urgent_open"] / 2.0, 1) + 0.3 * (r["distance"] / maxd)
            r["risk_score"] = round(100 * score)
            r["priority"] = "High" if (r["revenue"] >= thr or r["has_high_open"]) else ("Medium" if r["pending"] else "Low")
    return rows


RISK_FORMULA = "Risk score (0-100) = 40% return rate (cap 10%) + 30% urgent open orders (due within 2 days, cap 2) + 30% relative delivery distance."


@app.get("/api/dealers")
def api_dealers():
    return jsonify({"items": dealer_rows(), "risk_formula": RISK_FORMULA})


@app.get("/api/dealers/<cid>")
def api_dealer(cid):
    rows = {r["customer_id"]: r for r in dealer_rows()}
    if cid not in rows:
        return jsonify({"error": "Dealer not found"}), 404
    ctxs, prods, orders_df, cust, as_of = contexts_p()
    d = rows[cid]
    c = cust[cust["customer_id"] == cid].iloc[0]
    g = orders_df[orders_df["customer_id"] == cid].merge(prods[["product_id", "product_name"]], on="product_id").sort_values("order_date", ascending=False)
    weeks = [0.0] * 12
    for _, o in g.iterrows():
        k = (as_of - o["order_date"]).days // 7
        if 0 <= k < 12:
            weeks[11 - k] += float(o["quantity"])
    ctx = next((x for x in ctxs if x["product_id"] == c["primary_product_id"]), None)
    rec = de.recommend(ctx, agent) if ctx else None
    sc = g["status"].value_counts().to_dict()
    lead = (g["required_date"] - g["order_date"]).dt.days
    return jsonify({
        "dealer": d, "x_km": float(c["x_km"]), "y_km": float(c["y_km"]), "weekly_demand": [round(x, 1) for x in weeks],
        "status_counts": sc, "avg_requested_lead_days": round(float(lead.mean()), 1) if len(lead) else 0,
        "orders": [{"order_id": o["order_id"], "product": o["product_name"], "quantity": o["quantity"], "order_date": o["order_date"].strftime("%Y-%m-%d"),
                    "required": o["required_date"].strftime("%Y-%m-%d"), "status": o["status"], "priority": o["priority"]} for _, o in g.head(60).iterrows()],
        "pending": [{"order_id": o["order_id"], "product": o["product_name"], "quantity": o["quantity"], "required": o["required_date"].strftime("%Y-%m-%d"), "priority": o["priority"], "status": o["status"]} for _, o in g[g["status"].isin(["Pending", "Confirmed"])].iterrows()],
        "recommendation": rec, "risk_formula": RISK_FORMULA,
        "delivery_note": "Delivery timestamps are not tracked in this prototype, so on-time rate is not calculated; fulfilment and return rates come from order statuses."})


@app.get("/api/cost")
def api_cost():
    ctxs, *_ = contexts_p()
    recs = [de.recommend(c, agent) for c in ctxs]
    rows, tot0, tot1 = [], dict.fromkeys(("holding", "stockout", "transport", "ordering", "total_cost"), 0.0), dict.fromkeys(("holding", "stockout", "transport", "ordering", "total_cost"), 0.0)
    for c, r in zip(ctxs, recs):
        s0, s1 = cm.simulate(c, 0, SETTINGS), cm.simulate(c, r["reorder_qty"], SETTINGS)
        for k in tot0:
            tot0[k] += s0[k]
            tot1[k] += s1[k]
        rows.append({"name": c["name"], "action": r["label"], "qty": r["reorder_qty"], "current": s0["total_cost"], "ai": s1["total_cost"],
                     "saving": round(s0["total_cost"] - s1["total_cost"], 1), "stockout_prob_current": s0["stockout_prob"], "stockout_prob_ai": s1["stockout_prob"]})
    return jsonify({"rows": rows, "current": {k: round(v, 1) for k, v in tot0.items()}, "ai": {k: round(v, 1) for k, v in tot1.items()},
                    "saving": round(tot0["total_cost"] - tot1["total_cost"], 1), "params": SETTINGS, "horizon_weeks": int(SETTINGS["horizon_weeks"]),
                    "note": "Costs come from a Monte-Carlo simulation using the editable simulation parameters in Settings. 'Current' = no replenishment action; 'AI' = the agent's recommended quantity."})


@app.post("/api/whatif/compare")
def api_whatif_compare():
    j = request.get_json(force=True)
    ctxs, *_ = contexts_p()
    c = next((x for x in ctxs if x["product_id"] == j.get("product_id")), None)
    if not c:
        return jsonify({"error": "Product not found"}), 404
    try:
        chg, stock, pend = float(j["demand_change_pct"]), float(j["stock"]), float(j["pending"])
        lead, tc, sp = float(j["lead"]), float(j["transport_cost"]), float(j["stockout_penalty"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "All scenario inputs must be numbers"}), 400
    if chg < -90 or chg > 500 or min(stock, pend, tc, sp) < 0 or lead < 1 or lead > 60:
        return jsonify({"error": "Inputs out of range (demand change -90..500%, lead time 1..60 days, others >= 0)"}), 400
    c2 = de.with_overrides(c, stock=stock, demand=c["demand_week"] * (1 + chg / 100.0), pending=pend, lead=lead, distance=c["avg_distance"])
    rec = de.recommend(c2, agent)
    P = dict(SETTINGS)
    P["transport_cost_per_km"], P["stockout_penalty_pct"] = tc, sp
    cur, ai = cm.simulate(c2, 0, P), cm.simulate(c2, rec["reorder_qty"], P)
    return jsonify({"recommendation": rec, "current": cur, "ai": ai, "savings": round(cur["total_cost"] - ai["total_cost"], 1),
                    "horizon_weeks": int(P["horizon_weeks"]), "label": "SIMULATION: Monte-Carlo, 300 runs, synthetic parameters"})


@app.get("/api/settings")
def api_settings_get():
    return jsonify({"settings": SETTINGS, "defaults": cm.DEFAULTS, "limits": cm.LIMITS})


@app.post("/api/settings")
def api_settings_set():
    j = request.get_json(force=True)
    if j.get("reset"):
        new = dict(cm.DEFAULTS)
    else:
        new = dict(SETTINGS)
        for k, v in (j.get("settings") or {}).items():
            if k not in cm.LIMITS:
                return jsonify({"error": f"Unknown setting: {k}"}), 400
            try:
                v = float(v)
            except (TypeError, ValueError):
                return jsonify({"error": f"{k} must be a number"}), 400
            lo, hi = cm.LIMITS[k]
            if not (lo <= v <= hi):
                return jsonify({"error": f"{k} must be between {lo} and {hi}"}), 400
            new[k] = int(v) if k == "horizon_weeks" else v
    SETTINGS.update(new)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
        json.dump(SETTINGS, fh)
    return jsonify({"ok": True, "settings": SETTINGS})


@app.get("/api/search")
def api_search():
    s = (request.args.get("q") or "").strip().lower()
    if len(s) < 1:
        return jsonify([])
    out = []
    for p in q("SELECT product_id, product_name, category FROM products"):
        if s in p["product_name"].lower() or s in p["category"].lower():
            out.append({"type": "Product", "title": p["product_name"], "sub": p["category"], "url": f"/inventory?open={p['product_id']}"})
    for c in q("SELECT customer_id, customer_name, location FROM customers"):
        if s in c["customer_name"].lower() or s in c["location"].lower():
            out.append({"type": "Dealer", "title": c["customer_name"], "sub": c["location"], "url": f"/dealers/{c['customer_id']}"})
    for o in q("SELECT order_id, status FROM orders WHERE LOWER(order_id) LIKE ? LIMIT 5", (f"%{s}%",)):
        out.append({"type": "Order", "title": o["order_id"], "sub": o["status"], "url": "/orders"})
    return jsonify(out[:12])


# ------------------------------------------------------- health & quality
@app.get("/health")
def health():
    try:
        q("SELECT 1")
        ok = True
    except Exception:
        ok = False
    return jsonify({"status": "ok" if ok else "degraded", "version": VERSION, "database": "ok" if ok else "error",
                    "time": now_str()}), (200 if ok else 503)


def timed(fn):
    t = time.perf_counter()
    try:
        res = fn()
        return True, round((time.perf_counter() - t) * 1000, 1), res, None
    except Exception as e:  # pragma: no cover - reported in UI
        return False, round((time.perf_counter() - t) * 1000, 1), None, str(e)


@app.get("/api/system-health")
def api_system_health():
    comps = []

    def add(name, fn, detail):
        ok, ms, res, err = timed(fn)
        comps.append({"name": name, "status": "Operational" if ok else "Down", "latency_ms": ms, "detail": detail(res) if ok else err})
        return res

    add("Flask API", lambda: True, lambda r: "Serving requests")
    counts = add("Database", lambda: {t: q(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"] for t in ("products", "customers", "orders", "inventory", "supply_history", "decisions")},
                 lambda r: ", ".join(f"{k}: {v}" for k, v in r.items()))
    holder = {}

    def ai_run():
        ctxs, prods, orders_df, cust, as_of = contexts_p()
        holder.update(ctxs=ctxs, orders=orders_df, as_of=as_of, cust=cust)
        return de.recommend(ctxs[0], agent)

    add("AI Engine", ai_run, lambda r: f"Recommendation generated ({r['label']})")
    if holder:
        add("Forecast Engine", lambda: dp.forecast(holder["orders"], "P001", "Spice", holder["as_of"]), lambda r: f"7-day forecast computed ({r['d7']:.0f} kg)")
    else:
        comps.append({"name": "Forecast Engine", "status": "Down", "latency_ms": 0, "detail": "No data"})
    add("Q-Learning Engine", lambda: agent.evaluate(30, "random"), lambda r: f"Evaluated 30 episodes, accuracy {r['decision_accuracy']}%")
    add("Route Engine", lambda: plan_route(True), lambda r: f"{r['n_stops']} stops planned")
    s = agent.summary()
    last_fc = now_str()
    db_size = os.path.getsize(DB) if os.path.exists(DB) else 0
    return jsonify({"components": comps, "version": VERSION, "python": sys.version.split()[0], "last_training": s.get("last_trained") or agent.last_trained,
                    "episodes": s["episodes"], "q_states": s["q_states"], "last_forecast": last_fc, "db_size_kb": round(db_size / 1024, 1),
                    "as_of": holder.get("as_of"), "overall": "Operational" if all(c["status"] == "Operational" for c in comps) else "Degraded",
                    "table_counts": counts})


def parse_report():
    root = ET.parse(REPORT_XML).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    fail = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skip = sum(int(s.get("skipped", 0)) for s in suites)
    dur = sum(float(s.get("time", 0)) for s in suites)
    mods, failed = {}, []
    for tc in root.iter("testcase"):
        mod = (tc.get("classname") or "").split(".")[-1] or "tests"
        m = mods.setdefault(mod, {"passed": 0, "failed": 0, "skipped": 0})
        if tc.find("failure") is not None or tc.find("error") is not None:
            m["failed"] += 1
            failed.append(tc.get("name"))
        elif tc.find("skipped") is not None:
            m["skipped"] += 1
        else:
            m["passed"] += 1
    return {"available": True, "total": total, "passed": total - fail - skip, "failed": fail, "skipped": skip,
            "duration_s": round(dur, 2), "modules": mods, "failed_tests": failed[:20], "run_at": now_str()}


@app.get("/api/quality")
def api_quality():
    if os.path.exists(QUALITY_JSON):
        with open(QUALITY_JSON, "r", encoding="utf-8") as fh:
            return jsonify(json.load(fh))
    return jsonify({"available": False, "message": "No test run recorded yet. Click 'Run tests' (requires: pip install -r requirements-dev.txt)."})


@app.post("/api/quality/run")
def api_quality_run():
    with LOCK:
        try:
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "--junitxml", REPORT_XML, "-p", "no:cacheprovider"],
                               cwd=BASE, capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired:
            return jsonify({"available": False, "message": "Test run timed out after 240 s."}), 500
        if "No module named pytest" in (r.stdout + r.stderr):
            return jsonify({"available": False, "message": "pytest is not installed. Run: pip install -r requirements-dev.txt"}), 200
        if not os.path.exists(REPORT_XML):
            return jsonify({"available": False, "message": "pytest produced no report.", "output": (r.stdout + r.stderr)[-800:]}), 500
        res = parse_report()
        res["output_tail"] = r.stdout[-600:]
        with open(QUALITY_JSON, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
        return jsonify(res)


@app.route("/api/route/summary", methods=["GET", "POST"])
def api_route_summary():
    """Route plan + capacity / cost metrics derived from Settings."""
    j = request.get_json(silent=True) or {}
    inc = j.get("include_confirmed", request.args.get("include_confirmed", "1") not in ("0", "false"))
    d = plan_route(bool(inc))
    total_qty = sum(s["qty"] for s in d["stops"])
    cap = float(SETTINGS["vehicle_capacity_kg"])
    trips = max(1, math.ceil(total_qty / cap)) if d["stops"] else 0
    d.update({"vehicle_capacity": cap, "total_qty": total_qty, "trips": trips,
              "priority_deliveries": sum(1 for s in d["stops"] if s["priority"] == "High"),
              "transport_cost": round(d["total_km"] * float(SETTINGS["transport_cost_per_km"]) * trips, 0),
              "label": "Simulated grid and heuristic optimisation. No GPS or live map data is used."})
    return jsonify(d)


# -------------------------------------------------------------- startup
def boot():
    init_db()
    load_settings()
    if os.path.exists(BRAIN_FILE):
        try:
            agent.load(BRAIN_FILE)
        except Exception:
            agent.reset()


if not os.environ.get("SUPPLYMIND_SKIP_BOOT"):
    boot()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
