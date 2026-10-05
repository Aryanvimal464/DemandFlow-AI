"""Unit tests for forecasting, Q-learning, reward logic, decision engine and the cost simulator."""
import os
import random

import pandas as pd
import pytest

from ai import cost_model as cm
from ai import decision_engine as de
from ai import demand_prediction as dp
from ai.q_learning import ACTIONS, QAgent, compute_reward, discretize, env_obs, env_step, new_env

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def orders():
    df = pd.read_csv(os.path.join(ROOT, "data", "orders.csv"), parse_dates=["order_date", "required_date"])
    return df


def make_ctx(**kw):
    c = dict(product_id="PX", name="Test", category="Spice", unit="kg", stock=100.0, min_stock=100.0, max_stock=800.0,
             lead_days=5, avg_distance=40.0, pipeline=[], incoming=0.0, pending_qty=0.0, n_pending=0, demand_week=150.0,
             base_week=140.0, d30=640.0, trend_pct=5.0, seasonal=1.0, sigma_week=30.0, avg_monthly=600.0, avg_daily=20.0, price=100.0)
    c.update(kw)
    return de.compute_lead(c)


# ----------------------------------------------------------- forecasting
def test_forecast_returns_positive_values(orders):
    as_of = orders["order_date"].max()
    f = dp.forecast(orders, "P001", "Spice", as_of)
    assert f["d7"] > 0 and f["d30"] > f["d7"] and f["pred_daily"] > 0


def test_forecast_trend_is_clamped(orders):
    as_of = orders["order_date"].max()
    for pid in orders["product_id"].unique():
        assert -50 <= dp.forecast(orders, pid, "Spice", as_of)["trend_pct"] <= 50


def test_forecast_with_no_orders_is_zero_and_safe():
    empty = pd.DataFrame({"product_id": [], "quantity": [], "order_date": pd.to_datetime([])})
    f = dp.forecast(empty, "P001", "Spice", pd.Timestamp("2026-01-01"))
    assert f["d7"] == 0 and f["sigma_week"] == 0


def test_backtest_rows_and_metrics(orders):
    rows = dp.backtest(orders, "P002", "Spice", orders["order_date"].max())
    assert len(rows) == 8 and {"date", "predicted", "actual", "naive"} <= set(rows[0])
    m = dp.accuracy_metrics(rows)
    assert m["wape"] is None or m["wape"] >= 0


def test_accuracy_metrics_with_zero_actuals_returns_none():
    assert dp.accuracy_metrics([{"predicted": 5, "actual": 0, "naive": 0}])["accuracy"] is None


def test_weekly_actuals_length(orders):
    assert len(dp.weekly_actuals(orders, "P001", orders["order_date"].max(), 12)) == 12


# ------------------------------------------------------------ q-learning
@pytest.mark.parametrize("pos,state", [(100, "LOW_STOCK"), (200, "NORMAL_STOCK"), (600, "HIGH_STOCK")])
def test_discretize_stock_levels(pos, state):
    assert discretize(pos, 100, 0, 100).startswith(state)


def test_discretize_demand_and_pending():
    assert discretize(200, 70, 0, 100).split("|")[1] == "LOW_DEMAND"
    assert discretize(200, 150, 0, 100).split("|")[1] == "HIGH_DEMAND"
    assert discretize(200, 100, 70, 100).split("|")[2] == "HIGH_PENDING_ORDERS"
    assert discretize(200, 100, 0, 100).split("|")[2] == "NO_PENDING"


def test_q_update_matches_formula():
    a = QAgent()
    a.row("s1")[2] = 0.5
    a.row("s2")[1] = 2.0
    a.update("s1", 2, 1.0, "s2", alpha=0.1, gamma=0.9)
    assert a.Q["s1"][2] == pytest.approx(0.5 + 0.1 * (1.0 + 0.9 * 2.0 - 0.5))


def test_terminal_update_ignores_next_state():
    a = QAgent()
    a.row("s2")[0] = 99
    a.update("s1", 0, -0.3, "s2", alpha=0.5, gamma=0.9, terminal=True)
    assert a.Q["s1"][0] == pytest.approx(-0.15)


def test_greedy_choice_selects_highest_q():
    a = QAgent()
    a.Q["s"] = [0.1, 0.9, 0.3, 0.0, -1.0]
    a.N["s"] = [0] * 5
    assert a.choose("s", 0.0, random.Random(1)) == 1


def test_full_exploration_uses_all_actions():
    a = QAgent()
    a.Q["s"] = [0, 5, 0, 0, 0]
    a.N["s"] = [0] * 5
    rng = random.Random(3)
    assert len({a.choose("s", 1.0, rng) for _ in range(200)}) == 5


def test_training_improves_decisions_over_random():
    a = QAgent()
    before = a.evaluate(200, "random")
    a.train(1500, alpha=0.1, gamma=0.9, eps_start=0.9, total=1500)
    after = a.evaluate(200, "greedy")
    assert after["decision_accuracy"] > before["decision_accuracy"] + 10
    assert after["average_reward"] > before["average_reward"]
    assert a.summary()["q_states"] > 10 and sum(a.action_counts) == 1500 * 12


def test_save_and_load_roundtrip(tmp_path):
    a = QAgent()
    a.train(40)
    path = str(tmp_path / "b.json")
    a.save(path)
    b = QAgent()
    b.load(path)
    assert set(b.Q) == set(a.Q) and b.episodes == 40 and b.action_counts == a.action_counts
    for k in a.Q:   # Q-values are stored rounded to 5 decimals
        assert all(abs(x - y) < 1e-4 for x, y in zip(a.Q[k], b.Q[k]))


def test_reset_clears_learning():
    a = QAgent()
    a.train(10)
    a.reset()
    assert a.episodes == 0 and a.Q == {} and a.history == []


@pytest.mark.parametrize("onhand,pre,end,ordered,fill,transit,expected", [
    (2.0, 2.0, 2.0, False, 1.0, False, 2.0),     # demand satisfied + correct decision
    (1.0, 2.0, 2.0, True, 1.0, True, 3.0),       # + avoided stockout
    (2.0, 2.0, 0.5, False, 0.5, False, -1.0),    # stockout
    (2.0, 2.0, 0.5, False, 0.5, True, -1.0),     # late supply (order in transit)
    (4.0, 4.0, 5.0, True, 1.0, False, 0.0),      # satisfied (+1), excess (-0.5), unnecessary reorder (-0.5)
])
def test_reward_table(onhand, pre, end, ordered, fill, transit, expected):
    r, _ = compute_reward(onhand, pre, end, ordered, fill, transit)
    assert r == pytest.approx(expected)


def test_env_step_is_deterministic_for_same_seed():
    e1, e2 = new_env(random.Random(5)), new_env(random.Random(5))
    r1 = env_step(e1, 0, random.Random(9))
    r2 = env_step(e2, 0, random.Random(9))
    assert r1[1] == r2[1] and r1[0]["S"] == pytest.approx(r2[0]["S"])


def test_env_observation_is_a_valid_state():
    s = env_obs(new_env(random.Random(1)))
    assert len(s.split("|")) == 3 and len(ACTIONS) == 5


# ------------------------------------------------------- decision engine
def test_untrained_recommendation_is_flagged_and_deterministic():
    a, c = QAgent(), make_ctx()
    r1, r2 = de.recommend(c, a), de.recommend(c, a)
    assert not r1["trained"] and r1["action"] == r2["action"]


def test_trained_state_recommends_argmax_action():
    a, c = QAgent(), make_ctx(stock=60.0)
    state = de.state_of(c)
    a.Q[state] = [0.1, 0.2, 0.3, 0.0, 2.0]
    a.N[state] = [5] * 5
    r = de.recommend(c, a)
    assert r["trained"] and r["confidence"] > 25
    assert r["qvalues"][4]["q"] == 2.0


def test_reorder_quantity_never_exceeds_max_stock():
    a, c = QAgent(), make_ctx(stock=700.0, max_stock=800.0)
    state = de.state_of(c)
    a.Q[state] = [5.0, 0, 0, 0, 0]
    a.N[state] = [3] * 5
    r = de.recommend(c, a)
    assert c["stock"] + r["reorder_qty"] <= c["max_stock"] + 5


def test_at_max_stock_reorder_is_converted_to_wait():
    a, c = QAgent(), make_ctx(stock=800.0, max_stock=800.0)
    state = de.state_of(c)
    a.Q[state] = [5.0, 0, 0, 0, 0]
    a.N[state] = [3] * 5
    r = de.recommend(c, a)
    assert r["action"] == "WAIT" and r["reorder_qty"] == 0 and r["note"]
    assert r["agent_action"] == "ORDER_MORE"   # the Q-table preference is preserved for display


def test_risk_is_high_when_stock_is_empty_and_low_when_ample():
    assert de.risk_of(make_ctx(stock=0.0))[0] == "High"
    assert de.risk_of(make_ctx(stock=2000.0, max_stock=3000.0))[0] == "Low"


def test_explanation_mentions_stock_demand_and_lead_time():
    r = de.recommend(make_ctx(pending_qty=80.0, n_pending=2), QAgent())
    text = " ".join(r["reasons"])
    assert "safety" in text and "demand" in text and "lead time" in text and "pending" in text


def test_overrides_reset_pipeline_and_recompute_lead():
    c = de.with_overrides(make_ctx(pipeline=[[1, 50]], incoming=50.0), stock=10, lead=9, distance=300)
    assert c["incoming"] == 0 and c["lead_days"] == 9 and c["buffer_days"] == 2


# --------------------------------------------------------- cost simulator
def test_ordering_reduces_stockout_when_stock_is_low():
    c = make_ctx(stock=20.0, demand_week=150.0, lead_days=3, avg_distance=10)
    p = dict(cm.DEFAULTS)
    none, ordered = cm.simulate(c, 0, p), cm.simulate(c, 400, p)
    assert ordered["service_level"] > none["service_level"]
    assert ordered["stockout"] < none["stockout"]


def test_simulation_is_reproducible_and_bounded():
    c, p = make_ctx(), dict(cm.DEFAULTS)
    a, b = cm.simulate(c, 100, p), cm.simulate(c, 100, p)
    assert a == b and 0 <= a["service_level"] <= 100 and 0 <= a["stockout_prob"] <= 100


def test_total_cost_is_sum_of_components():
    r = cm.simulate(make_ctx(), 200, dict(cm.DEFAULTS))
    assert r["total_cost"] == pytest.approx(r["holding"] + r["stockout"] + r["transport"] + r["ordering"], abs=0.5)


def test_no_order_has_no_ordering_cost():
    assert cm.simulate(make_ctx(), 0, dict(cm.DEFAULTS))["ordering"] == 0
