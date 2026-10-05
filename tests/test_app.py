"""Route, API, input-validation and data-handling tests for the Flask app."""
import pytest

PAGES = ["/", "/inventory", "/demand", "/orders", "/dealers", "/dealers/C001", "/ai-agent", "/what-if",
         "/training", "/route-planner", "/cost-optimization", "/system-health", "/settings", "/help"]


@pytest.mark.parametrize("path", PAGES)
def test_page_renders(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert b"SUPPLYMIND AI" in r.data


def test_legacy_customers_route_redirects(client):
    r = client.get("/customers")
    assert r.status_code == 302 and r.headers["Location"].endswith("/dealers")


def test_unknown_page_is_404(client):
    assert client.get("/does-not-exist").status_code == 404


def test_health_endpoint(client):
    j = client.get("/health").get_json()
    assert j["status"] == "ok" and j["database"] == "ok" and j["version"]


def test_command_center_contains_real_kpis(client):
    j = client.get("/api/command-center").get_json()
    k = j["kpis"]
    for key in ("inventory_value", "pending_orders", "stockout_risk", "forecast_demand", "forecast_accuracy",
                "ai_savings", "service_level", "alerts"):
        assert key in k
    assert k["inventory_value"]["value"] > 0
    assert j["decision"]["reorder_qty"] >= 0 and "impact" in j["decision"]


def test_inventory_intel_lists_all_products(client):
    rows = client.get("/api/inventory-intel").get_json()
    assert len(rows) == 10
    assert {"stock", "safety", "reorder_point", "stockout_prob", "status"} <= set(rows[0])
    assert all(r["status"] in ("Healthy", "Low Stock", "Critical", "Overstock") for r in rows)


def test_product_detail_and_missing_product(client):
    ok = client.get("/api/product/P001")
    assert ok.status_code == 200 and len(ok.get_json()["weekly_history"]) == 12
    assert client.get("/api/product/NOPE").status_code == 404


def test_demand_endpoint_has_backtest(client):
    j = client.get("/api/demand").get_json()
    assert len(j["items"]) == 10 and len(j["items"][0]["backtest"]) == 8
    assert set(j["categories"]) == {"Spice", "Multigrain"}


def test_alerts_have_required_fields(client):
    for a in client.get("/api/alerts").get_json():
        assert {"severity", "title", "reason", "action", "timestamp"} <= set(a)
        assert a["severity"] in ("CRITICAL", "HIGH", "MEDIUM", "OPPORTUNITY")


def test_orders_list_and_create_order(client):
    before = len(client.get("/api/orders").get_json())
    meta = client.get("/api/meta").get_json()
    r = client.post("/api/orders", json={"customer_id": "C001", "product_id": "P001", "quantity": 100,
                                         "required_date": meta["as_of"], "priority": "High"})
    assert r.status_code == 200
    rows = client.get("/api/orders").get_json()
    assert len(rows) == before + 1 and rows[0]["status"] == "Pending"


@pytest.mark.parametrize("body", [
    {"customer_id": "C001", "product_id": "P001", "quantity": -5},
    {"customer_id": "C001", "product_id": "P001", "quantity": "abc"},
    {"customer_id": "C001", "product_id": "P001", "quantity": 0},
    {"customer_id": "NOPE", "product_id": "P001", "quantity": 10},
    {"customer_id": "C001", "product_id": "NOPE", "quantity": 10},
])
def test_create_order_rejects_invalid_input(client, body):
    assert client.post("/api/orders", json=body).status_code == 400


def test_order_status_workflow_and_invalid_transition(client):
    orders = client.get("/api/orders").get_json()
    o = next(x for x in orders if x["status"] == "Pending")
    assert client.post(f"/api/orders/{o['order_id']}/status", json={"status": "Delivered"}).status_code == 400
    assert client.post(f"/api/orders/{o['order_id']}/status", json={"status": "Confirmed"}).status_code == 200
    assert client.post("/api/orders/ORD-0/status", json={"status": "Confirmed"}).status_code == 404


def test_dispatch_with_insufficient_stock_is_rejected(client, A):
    A.run("UPDATE inventory SET current_stock=0 WHERE product_id='P001'")
    oid = "ORD-TEST1"
    A.run("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)", (oid, "C001", "P001", 50, "2026-01-01", "2026-01-05", "Confirmed", "High"))
    r = client.post(f"/api/orders/{oid}/status", json={"status": "Dispatched"})
    assert r.status_code == 400 and "Insufficient stock" in r.get_json()["error"]


def test_recommendation_structure(client):
    r = client.get("/api/recommendation/P001").get_json()
    assert r["action"] in ("ORDER_MORE", "SUPPLY_NORMAL", "SUPPLY_HIGH", "WAIT", "REDUCE_STOCK")
    assert len(r["qvalues"]) == 5 and r["reasons"] and 0 <= r["confidence"] <= 100
    assert r["risk"] in ("Low", "Medium", "High") and "impact" in r and "state_vars" in r


def test_recommendation_unknown_product_404(client):
    assert client.get("/api/recommendation/NOPE").status_code == 404
    assert client.post("/api/recommendation/NOPE/apply").status_code == 404


def test_apply_recommendation_logs_decision_and_updates_q(client, A):
    r = client.post("/api/recommendation/P004/apply").get_json()
    assert r["status"] == "Applied" and "reward" in r
    assert len(A.q("SELECT * FROM decisions")) == 1
    assert A.agent.summary()["q_pairs"] >= 1


def test_reject_recommendation_gives_penalty(client):
    r = client.post("/api/recommendation/P001/reject").get_json()
    assert r["status"] == "Rejected" and r["reward"] == -0.3


def test_whatif_valid_and_invalid(client):
    ok = client.post("/api/whatif", json={"product_id": "P001", "stock": 100, "demand": 250, "pending": 80, "lead": 7, "distance": 60})
    assert ok.status_code == 200 and ok.get_json()["headline"]
    bad = client.post("/api/whatif", json={"product_id": "P001", "stock": -1, "demand": 0, "pending": 0, "lead": 0, "distance": 0})
    assert bad.status_code == 400
    assert client.post("/api/whatif", json={"product_id": "P001"}).status_code == 400


def test_whatif_compare_returns_both_scenarios(client):
    body = dict(product_id="P001", demand_change_pct=20, stock=100, pending=80, lead=7, transport_cost=18, stockout_penalty=30)
    j = client.post("/api/whatif/compare", json=body).get_json()
    assert {"current", "ai", "savings", "recommendation"} <= set(j)
    assert 0 <= j["ai"]["service_level"] <= 100


@pytest.mark.parametrize("patch", [{"demand_change_pct": "x"}, {"demand_change_pct": 900}, {"lead": 0}, {"stock": -5}])
def test_whatif_compare_rejects_bad_inputs(client, patch):
    body = dict(product_id="P001", demand_change_pct=0, stock=100, pending=0, lead=5, transport_cost=18, stockout_penalty=30)
    body.update(patch)
    assert client.post("/api/whatif/compare", json=body).status_code == 400


def test_training_endpoint_and_state(client):
    r = client.post("/api/train", json={"episodes": 50, "offset": 0, "total": 50, "alpha": 0.1, "gamma": 0.9, "epsilon": 0.9}).get_json()
    assert r["episodes"] == 50 and len(r["batch_rewards"]) == 50
    s = client.get("/api/training/state").get_json()
    assert s["episodes"] == 50 and len(s["qtable"]) == 27 and sum(s["action_counts"]) == 50 * 12


def test_training_clamps_hostile_parameters(client):
    r = client.post("/api/train", json={"episodes": 99999, "alpha": 50, "gamma": -3, "epsilon": 7})
    assert r.status_code == 200 and r.get_json()["episodes"] == 2000
    assert r.get_json()["params"]["alpha"] <= 1.0


def test_reset_agent_and_evaluate(client):
    client.post("/api/train", json={"episodes": 20})
    assert client.post("/api/training/reset").get_json()["ok"]
    assert client.get("/api/training/state").get_json()["episodes"] == 0
    e = client.post("/api/evaluate", json={"episodes": 50}).get_json()
    assert e["episodes_trained"] == 0 and "decision_accuracy" in e["before"]


def test_brain_save_load_roundtrip_and_missing_file(client):
    assert client.post("/api/brain/load").status_code == 404
    client.post("/api/train", json={"episodes": 30})
    assert client.post("/api/brain/save").status_code == 200
    client.post("/api/training/reset")
    assert client.post("/api/brain/load").get_json()["episodes"] == 30


def test_dealers_and_dealer_detail(client):
    d = client.get("/api/dealers").get_json()
    assert len(d["items"]) == 20 and all(0 <= r["risk_score"] <= 100 for r in d["items"])
    det = client.get("/api/dealers/C001").get_json()
    assert len(det["weekly_demand"]) == 12 and det["recommendation"]
    assert client.get("/api/dealers/NOPE").status_code == 404


def test_cost_endpoint_totals_are_consistent(client):
    j = client.get("/api/cost").get_json()
    assert j["saving"] == pytest.approx(j["current"]["total_cost"] - j["ai"]["total_cost"], abs=0.2)
    assert len(j["rows"]) == 10


def test_settings_validation_and_persistence(client):
    assert client.post("/api/settings", json={"settings": {"holding_cost_pct_week": 99}}).status_code == 400
    assert client.post("/api/settings", json={"settings": {"holding_cost_pct_week": "abc"}}).status_code == 400
    assert client.post("/api/settings", json={"settings": {"unknown": 1}}).status_code == 400
    assert client.post("/api/settings", json={"settings": {"ordering_cost": 700}}).status_code == 200
    assert client.get("/api/settings").get_json()["settings"]["ordering_cost"] == 700
    assert client.post("/api/settings", json={"reset": True}).get_json()["settings"]["ordering_cost"] == 450


def test_route_summary_has_capacity_and_cost(client):
    j = client.get("/api/route/summary").get_json()
    assert j["n_stops"] == len(j["stops"]) and j["sequence"][0] == "Warehouse" and j["sequence"][-1] == "Warehouse"
    assert j["transport_cost"] >= 0 and j["trips"] >= 1


def test_route_with_no_open_orders_does_not_crash(client, A):
    A.run("UPDATE orders SET status='Delivered' WHERE status IN ('Pending','Confirmed')")
    j = client.get("/api/route/summary").get_json()
    assert j["n_stops"] == 0 and j["stops"] == []


def test_system_health_reports_all_components(client):
    j = client.get("/api/system-health").get_json()
    names = {c["name"] for c in j["components"]}
    assert {"Flask API", "Database", "AI Engine", "Forecast Engine", "Q-Learning Engine", "Route Engine"} <= names
    assert j["overall"] == "Operational"


def test_quality_endpoint_never_fabricates(client):
    j = client.get("/api/quality").get_json()
    assert "available" in j


def test_search(client):
    assert any(x["type"] == "Product" for x in client.get("/api/search?q=turm").get_json())
    assert client.get("/api/search?q=").get_json() == []


def test_missing_orders_table_data_is_handled(client, A):
    """A product with no order history must still produce a recommendation (missing-data case)."""
    A.run("DELETE FROM orders WHERE product_id='P006'")
    r = client.get("/api/recommendation/P006")
    assert r.status_code == 200 and r.get_json()["d7"] >= 1
