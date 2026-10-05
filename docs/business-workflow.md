# Business Workflow

1. **Orders arrive** from dealers (Orders page). Pending and Confirmed orders count as pending demand.
2. **Demand analysis** - 7-day and 30-day forecast, trend and seasonality per product.
3. **Inventory state** - stock vs safety stock, min/max, incoming orders.
4. **AI recommendation** - Reorder / Supply / Wait / Maintain Safety Stock / Reduce Stock with quantity, risk, confidence and explanation.
5. **Decision** - the planner presses *Apply* (simulated week runs, stock and orders update) or *Reject* (penalty feedback).
6. **Outcome and reward** - stockout, late supply, excess or satisfied demand produce a reward or penalty.
7. **Learning** - the Q-table updates; the decision log and supply history grow.
8. **Delivery** - the Route Planner sequences stops by priority, distance and deadline.

Safety stock = max(1.28 x weekly demand std-dev x sqrt(lead time / 7), 0.5 x minimum stock). Lead time = supplier days + 1 buffer day per 150 km average delivery distance.
