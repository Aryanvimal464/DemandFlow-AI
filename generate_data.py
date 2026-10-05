"""
Generates SYNTHETIC demo data (fictional products, dealers and orders) into ./data/*.csv

Portfolio prototype using synthetic data inspired by a multigrain and spice distribution workflow.
Run:  python generate_data.py
"""
import math
import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

from ai.q_learning import QAgent, compute_reward, ACTIONS

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DAYS = 120

# id, name, category, price/kg, supplier lead days, typical order kg, demand trend (+/-), ordering aggressiveness, supplier
PRODUCTS = [
    ("P001", "Turmeric", "Spice", 180, 5, 120, 0.25, 1.4, "Deccan Spice Growers"),
    ("P002", "Cumin", "Spice", 320, 6, 90, 0.10, 0.75, "Marwar Agro Traders"),
    ("P003", "Coriander", "Spice", 110, 4, 140, 0.00, 1.5, "Kota Seed Co-op"),
    ("P004", "Black Pepper", "Spice", 640, 8, 60, -0.10, 2.0, "Malabar Pepper House"),
    ("P005", "Red Chilli", "Spice", 220, 5, 130, 0.20, 0.9, "Guntur Chilli Exports"),
    ("P006", "Cardamom", "Spice", 1800, 9, 25, 0.30, 0.8, "Idukki Cardamom Pool"),
    ("P007", "Multigrain Mix", "Multigrain", 85, 3, 250, 0.05, 1.6, "Heartland Grain Blends"),
    ("P008", "Oats", "Multigrain", 95, 4, 220, 0.00, 1.3, "Northern Oat Mills"),
    ("P009", "Wheat Multigrain", "Multigrain", 48, 3, 300, -0.05, 2.9, "Punjab Wheat Collective"),
    ("P010", "Millet Mix", "Multigrain", 70, 4, 200, 0.15, 1.2, "Bajra & Jowar Producers"),
]

# name, location, x_km, y_km (synthetic grid, warehouse at 0,0)
CUSTOMERS = [
    ("Sharma Traders", "Aminabad, Lucknow", 3, 4), ("Gupta Agro Mart", "Chowk, Lucknow", -4, 5),
    ("Verma Provisions", "Alambagh, Lucknow", -6, -8), ("Mishra Spice House", "Barabanki", 24, 14),
    ("Tiwari Wholesale", "Sitapur", -20, 80), ("Yadav Kirana Co.", "Unnao", -55, -25),
    ("Pandey Grain Depot", "Raebareli", -20, -75), ("Khan Dry Fruits & Spices", "Hardoi", -85, 45),
    ("Agarwal Foods", "Kanpur", -72, -30), ("Srivastava Mart", "Faizabad", 125, 15),
    ("Chauhan Traders", "Sultanpur", 95, -45), ("Joshi Superstore", "Kakori", -14, 12),
    ("Singh Bulk Supplies", "Mohanlalganj", -5, -22), ("Dubey Provisions", "Malihabad", -22, 20),
    ("Rastogi Spice Mart", "Bakshi Ka Talab", -16, 34), ("Saxena General Store", "Gomti Nagar, Lucknow", 9, -2),
    ("Bajpai Agro", "Safedabad", 40, -6), ("Kapoor Retail Chain", "Indira Nagar, Lucknow", 12, 6),
    ("Bhatt Wholesalers", "Jankipuram, Lucknow", 5, 14), ("Rawat Dealers", "Mohan Road, Lucknow", -12, 10),
]


def r5(x):
    return int(max(5, round(x / 5.0) * 5))


def main(seed=42):
    rng = random.Random(seed)
    nprng = np.random.RandomState(seed)
    os.makedirs(OUT, exist_ok=True)
    end = date.today()
    start = end - timedelta(days=DAYS - 1)

    # ---------------- customers
    cust_rows = []
    for i, (name, loc, x, y) in enumerate(CUSTOMERS):
        prod = PRODUCTS[i % 10]
        cust_rows.append({
            "customer_id": f"C{i + 1:03d}", "customer_name": name, "location": loc,
            "primary_product_id": prod[0], "x_km": x, "y_km": y,
            "delivery_distance_km": round(math.hypot(x, y) * 1.25, 1),
            "_scale": prod[5] * rng.uniform(0.8, 1.25), "_freq": rng.uniform(1.6, 3.2),
            "_ret": rng.uniform(0.01, 0.08),
        })

    # ---------------- orders
    prod_by_id = {p[0]: p for p in PRODUCTS}
    orders = []
    for c in cust_rows:
        base = prod_by_id[c["primary_product_id"]]
        for d in range(DAYS):
            day = start + timedelta(days=d)
            trend = 1 + base[6] * ((d / DAYS) - 0.5) * 2
            if rng.random() < c["_freq"] / 30.0 * trend:
                if rng.random() < 0.85:
                    pid, scale = base[0], c["_scale"]
                else:
                    same = [p for p in PRODUCTS if p[2] == base[2] and p[0] != base[0]]
                    sp = rng.choice(same)
                    pid, scale = sp[0], sp[5] * 0.7
                qty = r5(scale * nprng.lognormal(0, 0.25))
                req = day + timedelta(days=rng.randint(3, 10))
                prio = "High" if (req - day).days <= 4 or rng.random() < 0.12 else ("Medium" if rng.random() < 0.6 else "Low")
                orders.append({"customer_id": c["customer_id"], "product_id": pid, "quantity": qty,
                               "order_date": day, "required_date": req, "priority": prio, "_ret": c["_ret"]})
    # extra open orders in the last 2 days so there is always a pending queue
    for c in rng.sample(cust_rows, 10):
        day = end - timedelta(days=rng.randint(0, 1))
        orders.append({"customer_id": c["customer_id"], "product_id": c["primary_product_id"],
                       "quantity": r5(c["_scale"] * nprng.lognormal(0, 0.2)), "order_date": day,
                       "required_date": day + timedelta(days=rng.randint(3, 8)),
                       "priority": rng.choice(["High", "Medium", "Medium", "Low"]), "_ret": c["_ret"], "_open": True})
    orders.sort(key=lambda o: o["order_date"])
    for i, o in enumerate(orders):
        o["order_id"] = f"ORD-{1001 + i}"
        age = (end - o["order_date"]).days
        if o.get("_open"):
            o["status"] = rng.choice(["Pending", "Pending", "Confirmed"])
        elif age > 6:
            o["status"] = "Returned" if rng.random() < o["_ret"] else "Delivered"
        else:
            o["status"] = rng.choices(["Pending", "Confirmed", "Dispatched", "Delivered"], [35, 25, 15, 25])[0]
    odf = pd.DataFrame(orders)[["order_id", "customer_id", "product_id", "quantity", "order_date",
                                "required_date", "status", "priority"]]
    odf["order_date"] = pd.to_datetime(odf["order_date"]).dt.strftime("%Y-%m-%d")
    odf["required_date"] = pd.to_datetime(odf["required_date"]).dt.strftime("%Y-%m-%d")

    # ---------------- weekly demand per product (for history + stock sizing)
    W = DAYS // 7
    weekly = {p[0]: [0.0] * W for p in PRODUCTS}
    for o in orders:
        w = min((o["order_date"] - start).days // 7, W - 1)
        weekly[o["product_id"]][w] += o["quantity"]
    monthly = {pid: sum(v) / (DAYS / 30.0) for pid, v in weekly.items()}

    prod_rows = []
    for p in PRODUCTS:
        m = monthly[p[0]]
        prod_rows.append({
            "product_id": p[0], "product_name": p[1], "category": p[2], "unit": "kg",
            "min_stock": int(round(0.30 * m / 10) * 10), "max_stock": int(round(1.4 * m / 10) * 10),
            "supplier_lead_time_days": p[4], "avg_monthly_demand": round(m, 1), "unit_price": p[3], "supplier": p[8],
        })

    # ---------------- supply history: a naive historical ordering policy
    hist, final_stock = [], {}
    sh = 1
    for p in PRODUCTS:
        pid, lead_w, agg = p[0], max(1, math.ceil(p[4] / 7)), p[7]
        dem = weekly[pid]
        S = max(dem[0], 20) * rng.uniform(1.5, 3.0)
        pipe = []
        for w in range(W):
            actual = dem[w]
            pred = (sum(dem[max(0, w - 4):w]) / max(len(dem[max(0, w - 4):w]), 1)) if w > 0 else actual
            pred = max(pred, 1.0)
            pos = S + sum(q for _, q in pipe)
            pending = round(0.35 * actual * rng.uniform(0.6, 1.2) / 5) * 5
            q = max(0.0, agg * pred * 3.0 - pos)
            q = r5(q) if q >= 0.3 * pred else 0
            ratio = q / pred
            action = "ORDER_MORE" if ratio >= 1.75 else "SUPPLY_HIGH" if ratio >= 1.25 else "SUPPLY_NORMAL" if ratio >= 0.5 else "WAIT"
            stock_before = S
            if q > 0:
                pipe.append([lead_w, q])
            demand = max(actual, pending)
            sold = min(S, demand)
            S -= sold
            fill = sold / demand if demand > 0 else 1.0
            in_transit = len(pipe) > 0
            np_ = []
            for eta, qq in pipe:
                eta -= 1
                if eta <= 0:
                    S += qq
                else:
                    np_.append([eta, qq])
            pipe = np_
            pos_end = S + sum(x for _, x in pipe)
            r, flags = compute_reward(stock_before / pred, pos / pred, pos_end / pred, q > 0, fill, in_transit)
            if fill < 0.98:
                outcome = "Late supply" if flags.get("late_supply") else "Stockout"
            elif flags.get("excess_inventory"):
                outcome = "Excess inventory"
            else:
                outcome = "Demand satisfied"
            hist.append({
                "record_id": f"SH-{sh:04d}", "week_start": (start + timedelta(days=7 * w)).strftime("%Y-%m-%d"),
                "product_id": pid, "stock_before": round(stock_before, 1), "predicted_demand": round(pred, 1),
                "pending_orders": pending, "action": action, "quantity": q, "lead_time_days": p[4],
                "actual_demand": round(actual, 1), "stock_after": round(S, 1), "stockout": int(fill < 0.98),
                "excess_inventory": int(bool(flags.get("excess_inventory"))), "late_supply": int(bool(flags.get("late_supply"))),
                "reward": round(r, 2), "outcome": outcome,
            })
            sh += 1
        final_stock[pid] = S
    pd.DataFrame(hist).to_csv(os.path.join(OUT, "supply_history.csv"), index=False)

    # ---------------- inventory (end state of the history simulation) + products
    inv_rows = []
    zones = ["A1", "A2", "B1", "B2", "C1"]
    for pr in prod_rows:
        s = max(0, final_stock[pr["product_id"]])
        s = min(s, pr["max_stock"] * 1.3)
        inv_rows.append({"product_id": pr["product_id"], "current_stock": int(round(s / 5) * 5),
                         "last_updated": end.strftime("%Y-%m-%d"), "storage_zone": rng.choice(zones)})
    pd.DataFrame(prod_rows).to_csv(os.path.join(OUT, "products.csv"), index=False)
    pd.DataFrame(inv_rows).to_csv(os.path.join(OUT, "inventory.csv"), index=False)
    odf.to_csv(os.path.join(OUT, "orders.csv"), index=False)

    # ---------------- customers csv (with behaviour computed from the orders)
    stats = odf.groupby("customer_id").agg(n=("order_id", "count"), avg=("quantity", "mean"), tot=("quantity", "sum"),
                                         last=("order_date", "max"))
    rets = odf[odf.status == "Returned"].groupby("customer_id").size()
    crow = []
    for c in cust_rows:
        st = stats.loc[c["customer_id"]]
        crow.append({
            "customer_id": c["customer_id"], "customer_name": c["customer_name"], "location": c["location"],
            "primary_product_id": c["primary_product_id"], "avg_order_qty": round(float(st["avg"]), 1),
            "orders_per_month": round(float(st["n"]) / (DAYS / 30.0), 2), "last_order": st["last"],
            "delivery_distance_km": c["delivery_distance_km"], "historical_demand_kg": int(st["tot"]),
            "return_rate_pct": round(100.0 * int(rets.get(c["customer_id"], 0)) / int(st["n"]), 1),
            "x_km": c["x_km"], "y_km": c["y_km"],
        })
    pd.DataFrame(crow).to_csv(os.path.join(OUT, "customers.csv"), index=False)

    # ---------------- training_results.csv (a real training run of the Q-learning agent)
    ag = QAgent()
    rows, total, step = [], 2000, 20
    for e in range(0, total, step):
        ag.train(step, alpha=0.1, gamma=0.9, eps_start=0.9, offset=e, total=total)
        chunk = ag.history[-step:]
        n = len(chunk)
        rows.append({
            "episode": ag.episodes, "avg_episode_reward": round(sum(x[0] for x in chunk) / n, 3),
            "decision_accuracy": round(100 * sum(x[1] for x in chunk) / n, 1),
            "stockout_rate": round(100 * sum(x[2] for x in chunk) / n, 1),
            "excess_rate": round(100 * sum(x[3] for x in chunk) / n, 1), "epsilon": chunk[-1][5],
        })
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "training_results.csv"), index=False)
    print("Generated: %d orders, %d supply-history rows, %d customers, %d products"
          % (len(odf), len(hist), len(crow), len(prod_rows)))


if __name__ == "__main__":
    main()
