# Project Overview

**Self-Learning AI Supply & Inventory Optimization Agent** is a portfolio prototype using synthetic data inspired by a multigrain and spice distribution workflow. It is *not* a production system.

## Context
The business buys multigrain and spices from suppliers and supplies them to dealers. The hard decisions are *how much to reorder, when, and how much to ship now* under uncertain demand and supplier lead times.

## Modules
| Module | Purpose |
|---|---|
| Dashboard | KPIs, charts, animated learning loop, full demo |
| Inventory / Customers / Orders | Operational data (SQLite), order lifecycle |
| AI Supply Agent | Recommendation + explanation + Apply/Reject + What-If |
| AI Training Lab | Q-learning training, reward chart, Q-table, save/load brain |
| Route Planner | Delivery sequence on a simulated grid |

## Files
* `app.py` - Flask routes, SQLite access, training/demo/route APIs
* `ai/q_learning.py` - simulated environment, reward table, Q-learning agent
* `ai/demand_prediction.py` - average, 7/30-day demand, trend, seasonality
* `ai/decision_engine.py` - state building, recommendation, risk, confidence, explanation
* `generate_data.py` - creates the synthetic CSV data
* `templates/`, `static/` - UI


## v2.0 (SupplyMind AI)
Dark SaaS redesign with Command Center, Inventory/Demand Intelligence, Dealers, What-If Simulator, Cost Optimization, System Health, Settings, a Monte-Carlo cost model (`ai/cost_model.py`) and a pytest suite in `tests/`. All legacy API routes are unchanged; `/customers` redirects to `/dealers`.
