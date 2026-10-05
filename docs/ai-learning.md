# How the AI Learns

## Q-learning
`Q(s,a) <- Q(s,a) + alpha * [ r + gamma * max_a' Q(s',a') - Q(s,a) ]`

The Q-table has 27 states x 5 actions. Each entry estimates the long-term reward of taking an action in a state.

## State (27 combinations)
* Stock: `LOW_STOCK` (<1.5 weeks cover incl. incoming), `NORMAL_STOCK`, `HIGH_STOCK` (>3.5 weeks)
* Demand: `LOW_DEMAND` (<0.85x baseline), `NORMAL_DEMAND`, `HIGH_DEMAND` (>1.2x)
* Pending: `NO_PENDING`, `PENDING_ORDERS`, `HIGH_PENDING_ORDERS` (>=0.6 weeks of demand)

## Actions
`ORDER_MORE` (replenish 2x weekly demand), `SUPPLY_HIGH` (1.5x), `SUPPLY_NORMAL` (1x), `WAIT` (0), `REDUCE_STOCK` (0 + clearance of excess).
In real recommendations the quantity is also raised to reach safety stock + lead-time demand and capped by max stock.

## Rewards
Correct decision +1, avoided stockout +1, demand satisfied +1, excess inventory -0.5, stockout -1, late supply -1, unnecessary reorder -0.5. Human rejection of a recommendation: -0.3.

## Training loop
1. Start an episode with random stock, demand level, lead time and pending orders.
2. For 12 simulated weeks: choose an action (epsilon-greedy), simulate demand and arrivals, compute reward, update Q.
3. Epsilon decays from the chosen start value to 0.05 over the run.

## Evaluation
"Before" = random decisions, "After" = greedy policy of the learned Q-table. Both run on the same 300 seeded episodes. Decision accuracy = share of decisions with no stockout, no excess inventory and no unnecessary reorder.

## Limitations
The environment is a simplified simulation. The agent cannot see lead time in its state, demand noise is random, and results do not predict real-world performance.
