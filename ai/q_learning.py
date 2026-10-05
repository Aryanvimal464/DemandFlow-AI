"""
Simplified tabular Q-learning for supply / inventory decisions.

SYNTHETIC SIMULATION ONLY: the agent learns from a simulated weekly supply
environment (random demand drift, supplier lead times, pending customer orders).
It is a portfolio prototype, not a production system.

Q(s,a) <- Q(s,a) + alpha * [ r + gamma * max_a' Q(s',a') - Q(s,a) ]
"""
import json
import os
import random
import time

STOCK_STATES = ["LOW_STOCK", "NORMAL_STOCK", "HIGH_STOCK"]
DEMAND_STATES = ["LOW_DEMAND", "NORMAL_DEMAND", "HIGH_DEMAND"]
PENDING_STATES = ["NO_PENDING", "PENDING_ORDERS", "HIGH_PENDING_ORDERS"]
ALL_STATES = [f"{s}|{d}|{p}" for s in STOCK_STATES for d in DEMAND_STATES for p in PENDING_STATES]

ACTIONS = ["ORDER_MORE", "SUPPLY_NORMAL", "SUPPLY_HIGH", "WAIT", "REDUCE_STOCK"]
# Replenishment size (multiple of expected weekly demand) per action
REPLENISH_MULT = {"ORDER_MORE": 2.0, "SUPPLY_NORMAL": 1.0, "SUPPLY_HIGH": 1.5, "WAIT": 0.0, "REDUCE_STOCK": 0.0}

EPISODE_LEN = 12          # decisions (weeks) per training episode
REJECT_PENALTY = -0.3     # feedback when a human rejects a recommendation
HISTORY_CAP = 20000

REWARDS = {
    "correct_decision": 1.0,
    "avoided_stockout": 1.0,
    "demand_satisfied": 1.0,
    "excess_inventory": -0.5,
    "stockout": -1.0,
    "late_supply": -1.0,
    "unnecessary_reorder": -0.5,
}


def discretize(position, demand_week, pending, base_week):
    """Turn raw numbers into a discrete state key like 'LOW_STOCK|HIGH_DEMAND|PENDING_ORDERS'."""
    dw = max(float(demand_week), 1e-6)
    bw = max(float(base_week), 1e-6)
    cover = position / dw                       # weeks of cover (on-hand + incoming)
    stock = "LOW_STOCK" if cover < 1.5 else ("HIGH_STOCK" if cover > 3.5 else "NORMAL_STOCK")
    ratio = dw / bw
    demand = "LOW_DEMAND" if ratio < 0.85 else ("HIGH_DEMAND" if ratio > 1.2 else "NORMAL_DEMAND")
    pr = pending / dw
    pend = "NO_PENDING" if pr < 0.15 else ("HIGH_PENDING_ORDERS" if pr >= 0.6 else "PENDING_ORDERS")
    return f"{stock}|{demand}|{pend}"


def compute_reward(onhand_cover_pre, pos_cover_pre, pos_cover_end, ordered, fill, in_transit):
    """Reward / penalty table. Returns (reward, flags)."""
    flags = {}
    r = 0.0
    stockout = fill < 0.98
    if not stockout:
        r += REWARDS["demand_satisfied"]; flags["demand_satisfied"] = 1
        if onhand_cover_pre < 1.3:
            r += REWARDS["avoided_stockout"]; flags["avoided_stockout"] = 1
        if 1.0 <= pos_cover_end <= 3.5:
            r += REWARDS["correct_decision"]; flags["correct_decision"] = 1
    else:
        if in_transit:
            r += REWARDS["late_supply"]; flags["late_supply"] = 1
        else:
            r += REWARDS["stockout"]; flags["stockout"] = 1
    if pos_cover_end > 4.0:
        r += REWARDS["excess_inventory"]; flags["excess_inventory"] = 1
    if ordered and pos_cover_pre > 3.0:
        r += REWARDS["unnecessary_reorder"]; flags["unnecessary_reorder"] = 1
    return r, flags


# ---------------------------------------------------------------- environment
def new_env(rng, m=100.0):
    f = rng.uniform(0.7, 1.4)
    return {
        "S": m * f * rng.uniform(0.3, 4.5),
        "pipe": [],
        "m": m,
        "f": f,
        "P": m * f * rng.uniform(0, 0.9) * rng.choice([0, 1, 1]),
        "L": rng.choice([1, 1, 2]),
    }


def env_obs(env):
    dw = env["m"] * env["f"]
    pos = env["S"] + sum(q for _, q in env["pipe"])
    return discretize(pos, dw, env["P"], env["m"])


def env_step(env, a_idx, rng, qty=None):
    """Simulate one week. Returns (new_env, reward, info)."""
    action = ACTIONS[a_idx]
    m, f = env["m"], env["f"]
    dw = m * f
    S = float(env["S"])
    pipe = [[e, q] for e, q in env["pipe"]]
    pos_pre = S + sum(q for _, q in pipe)
    pos_cover_pre = pos_pre / dw
    onhand_cover_pre = S / dw

    q = REPLENISH_MULT[action] * dw if qty is None else float(qty)
    if action == "REDUCE_STOCK":
        S -= 0.3 * max(S - dw, 0.0)              # clearance sale of excess stock
    ordered = q > 0
    if ordered:
        pipe.append([env["L"], q])

    demand = max(env["P"], dw * max(0.3, rng.gauss(1.0, 0.2)))   # booked + walk-in demand
    sold = min(S, demand)
    S -= sold
    fill = sold / demand if demand > 0 else 1.0
    stockout = fill < 0.98
    in_transit = len(pipe) > 0

    newpipe = []
    for eta, qq in pipe:
        eta -= 1
        if eta <= 0:
            S += qq
        else:
            newpipe.append([eta, qq])
    pos_end = S + sum(x for _, x in newpipe)
    end_cover = pos_end / dw

    r, flags = compute_reward(onhand_cover_pre, pos_cover_pre, end_cover, ordered, fill, in_transit)
    excess = pos_end > 4.0 * dw
    unnecessary = bool(flags.get("unnecessary_reorder"))
    f2 = min(1.8, max(0.5, f + 0.25 * (1 - f) + rng.gauss(0, 0.12)))
    nxt = {
        "S": S, "pipe": newpipe, "m": m, "f": f2,
        "P": f2 * m * rng.uniform(0, 1.0) * rng.choice([0, 1, 1]),
        "L": env["L"],
    }
    info = {
        "flags": flags, "demand": demand, "sold": sold, "unmet": demand - sold, "fill": fill,
        "stockout": stockout, "excess": excess, "unnecessary": unnecessary,
        "excess_units": max(0.0, pos_end - 4.0 * dw), "pos_end": pos_end, "end_cover": end_cover,
        "success": (not stockout) and (not excess) and (not unnecessary), "ordered_qty": q if ordered else 0.0,
    }
    return nxt, r, info


# ---------------------------------------------------------------------- agent
class QAgent:
    def __init__(self):
        self.reset()

    def reset(self):
        self.Q = {}
        self.N = {}
        self.episodes = 0
        self.history = []          # [reward, success, stockout, excess, waste, eps]
        self.total_success = 0
        self.total_decisions = 0
        self.total_reward = 0.0
        self.action_counts = [0] * len(ACTIONS)
        self.last_trained = None
        self.params = {"alpha": 0.1, "gamma": 0.9, "epsilon": 0.9}
        self.rng = random.Random(7)
        self.created = time.strftime("%Y-%m-%d %H:%M:%S")
        self.saved_at = None

    # -- table helpers
    def row(self, key):
        if key not in self.Q:
            self.Q[key] = [0.0] * len(ACTIONS)
            self.N[key] = [0] * len(ACTIONS)
        return self.Q[key]

    def best(self, key, rng):
        row = self.row(key)
        top = max(row)
        ties = [i for i, v in enumerate(row) if abs(v - top) < 1e-9]
        return rng.choice(ties)

    def choose(self, key, eps, rng):
        if rng.random() < eps:
            return rng.randrange(len(ACTIONS))
        return self.best(key, rng)

    def update(self, s, a, r, s2, alpha, gamma, terminal=False):
        row = self.row(s)
        nxt = 0.0 if terminal else max(self.row(s2))
        row[a] += alpha * (r + gamma * nxt - row[a])
        self.N[s][a] += 1

    # -- training
    def train(self, n, alpha=0.1, gamma=0.9, eps_start=0.9, eps_min=0.05, offset=0, total=None):
        total = total or n
        self.params = {"alpha": alpha, "gamma": gamma, "epsilon": eps_start}
        rng = self.rng
        batch = []
        eps = eps_start
        for i in range(n):
            idx = offset + i
            if eps_start <= eps_min:
                eps = eps_start
            else:
                eps = max(eps_min, eps_start * (eps_min / eps_start) ** min(1.0, idx / max(total - 1, 1)))
            env = new_env(rng)
            s = env_obs(env)
            tot = 0.0; succ = 0; so = 0; ex = 0; waste = 0.0
            for _ in range(EPISODE_LEN):
                a = self.choose(s, eps, rng)
                self.action_counts[a] += 1
                env, r, info = env_step(env, a, rng)
                s2 = env_obs(env)
                self.update(s, a, r, s2, alpha, gamma)
                s = s2
                tot += r; succ += info["success"]; so += info["stockout"]; ex += info["excess"]
                waste += info["excess_units"]
            self.episodes += 1
            self.total_success += succ
            self.total_decisions += EPISODE_LEN
            self.total_reward += tot
            self.last_trained = time.strftime("%Y-%m-%d %H:%M:%S")
            self.history.append([round(tot, 3), succ / EPISODE_LEN, so / EPISODE_LEN, ex / EPISODE_LEN,
                                 round(waste, 2), round(eps, 4)])
            batch.append(round(tot, 3))
        if len(self.history) > HISTORY_CAP:
            self.history = self.history[-HISTORY_CAP:]
        out = self.summary()
        out["batch_rewards"] = batch
        out["epsilon"] = round(eps, 4)
        out["current_reward"] = batch[-1] if batch else 0
        return out

    def summary(self, window=100):
        h = self.history[-window:]
        n = max(len(h), 1)
        visited = [k for k in self.N if sum(self.N[k]) > 0]
        pairs = sum(1 for k in self.N for v in self.N[k] if v > 0)
        return {
            "episodes": self.episodes,
            "avg_reward_per_decision": round(sum(x[0] for x in h) / n / EPISODE_LEN, 4) if h else 0.0,
            "avg_episode_reward": round(sum(x[0] for x in h) / n, 3) if h else 0.0,
            "success_rate": round(sum(x[1] for x in h) / n, 4) if h else 0.0,
            "stockout_rate": round(sum(x[2] for x in h) / n, 4) if h else 0.0,
            "excess_rate": round(sum(x[3] for x in h) / n, 4) if h else 0.0,
            "waste_per_episode": round(sum(x[4] for x in h) / n, 1) if h else 0.0,
            "q_states": len(visited),
            "q_states_total": len(ALL_STATES),
            "q_pairs": pairs,
            "q_pairs_total": len(ALL_STATES) * len(ACTIONS),
            "successful_decisions": self.total_success,
            "total_decisions": self.total_decisions,
            "total_reward": round(self.total_reward, 2),
            "action_counts": list(self.action_counts),
            "last_trained": self.last_trained,
            "params": self.params,
            "last_epsilon": self.history[-1][5] if self.history else self.params["epsilon"],
        }

    # -- evaluation (does not change Q)
    def evaluate(self, n=300, mode="greedy", seed=1000):
        succ = so = ex = 0
        reward = waste = 0.0
        steps = 0
        for i in range(n):
            env_rng = random.Random(seed + i)
            pol_rng = random.Random(90000 + seed + i)
            env = new_env(env_rng)
            for _ in range(EPISODE_LEN):
                s = env_obs(env)
                a = pol_rng.randrange(len(ACTIONS)) if mode == "random" else self.best(s, pol_rng)
                env, r, info = env_step(env, a, env_rng)
                reward += r; succ += info["success"]; so += info["stockout"]; ex += info["excess"]
                waste += info["excess_units"]; steps += 1
        return {
            "decision_accuracy": round(100 * succ / steps, 1),
            "stockout_rate": round(100 * so / steps, 1),
            "excess_inventory": round(100 * ex / steps, 1),
            "average_reward": round(reward / steps, 3),
            "waste_per_episode": round(waste / n, 1),
            "episodes_evaluated": n,
        }

    # -- Q-table view
    def qtable(self):
        rows = []
        for s in ALL_STATES:
            q = self.Q.get(s, [0.0] * len(ACTIONS))
            n = self.N.get(s, [0] * len(ACTIONS))
            visits = sum(n)
            best = None
            if visits > 0:
                best = ACTIONS[max(range(len(q)), key=lambda i: q[i])]
            rows.append({"state": s, "q": [round(v, 3) for v in q], "n": n, "visits": visits, "best": best})
        return rows

    # -- persistence
    def to_dict(self):
        return {
            "Q": {k: [round(v, 5) for v in row] for k, row in self.Q.items()},
            "N": self.N, "episodes": self.episodes,
            "history": self.history, "params": self.params,
            "total_success": self.total_success, "total_decisions": self.total_decisions,
            "total_reward": self.total_reward, "action_counts": self.action_counts, "last_trained": self.last_trained,
            "created": self.created, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        d = self.to_dict()
        self.saved_at = d["saved_at"]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        return d["saved_at"]

    def load(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        self.reset()
        self.Q = {k: [float(x) for x in v] for k, v in d.get("Q", {}).items()}
        self.N = {k: [int(x) for x in v] for k, v in d.get("N", {}).items()}
        self.episodes = int(d.get("episodes", 0))
        self.history = d.get("history", [])
        self.params = d.get("params", self.params)
        self.total_success = int(d.get("total_success", 0))
        self.total_decisions = int(d.get("total_decisions", 0))
        self.total_reward = float(d.get("total_reward", sum(h[0] for h in self.history)))
        self.action_counts = [int(x) for x in d.get("action_counts", [0] * len(ACTIONS))]
        self.last_trained = d.get("last_trained")
        self.created = d.get("created", self.created)
        self.saved_at = d.get("saved_at")
