"""Concept diagrams: cards + AWS icons + live numbered flows (from the WWI course's teaching diagrams).

Use this pattern when the picture explains an IDEA (a data model, a lifecycle, a decision flow) rather than a
deployment: cards carry the facts, icons anchor the AWS services, and each numbered flow is one sentence of the story.

    python scripts/build_arch.py assets/examples/concept_cards.py --out /tmp/concepts --no-stages
"""
from archlib import Flow, Group, Node, Spec

BEDROCK, SAGE, DEV, MGMT = "#6D28D9", "#0B8A6F", "#3B48CC", "#C7176A"
STORE, SEC, DDB, CONT, SLATE, INK = "#5C8A1E", "#B4322A", "#1D4ED8", "#0E7490", "#334155", "#0F1B2D"


def card(id, title, body, x, y, color, w=1.6, icon=None, sub="", **kw):
    return Node(id, icon, title, sub=sub, x=x, y=y, body=body, color=color, w=w, **kw)

# 03 ─ the semantic layer ──────────────────────────────────────────────────────────────────────────────────────
SEMANTIC = Spec(
    id="03-semantic-layer", title="The semantic layer: what one row means, and which joins are safe",
    subtitle="Dimensions join onto ONE fact (many-to-one). Facts never join each other directly - aggregate first, then join 1:1.",
    cols=7, rows=3.6,
    nodes=[
        card("cust", "dimension_customer", ["403 rows · buying_group · Unknown = 0"], 0.95, 0.0, STORE, w=1.85, icon="duckdb"),
        card("item", "dimension_stock_item", ["672 rows / 228 items (SCD versions)"], 0.95, 0.8, STORE, w=1.85, icon="duckdb"),
        card("city", "dimension_city", ["116k rows · sales_territory"], 0.95, 1.6, STORE, w=1.85, icon="duckdb"),
        card("date", "dimension_date", ["1,461 days · calendar + fiscal"], 0.95, 2.4, STORE, w=1.85, icon="duckdb"),
        card("fo", "fact_order (order line)", ["231,412 lines · order_date_key", "picked_date_key = post-event", "wwi_backorder_id = post-event"],
             3.45, 0.45, DEV, w=1.85, icon="parquet", sub="grain: 1 order line"),
        card("fs", "fact_sale (invoice line)", ["228,265 lines · invoice_date_key", "no order id - no line-level link"],
             3.45, 2.2, DEV, w=1.85, icon="parquet", sub="grain: 1 invoice line"),
        card("bad", "FORBIDDEN: fact_order × fact_sale", ["joined on customer + item keys", "33.1 M rows, sales ×144.4", "valid SQL, invalid science"],
             6.1, 0.2, SEC, w=2.1),
        card("good", "Correct: aggregate, then join 1:1", ["orders → month × item", "sales → month × item", "join the two aggregates"],
             6.1, 1.65, SAGE, w=2.1),
        card("marts", "Course marts (ours, labelled)", ["mart_order_line · mart_sales_monthly_item", "mart_item_demand_weekly · mart_movement_daily",
             "mart_supplier_performance", "each with a declared grain"], 6.1, 3.1, SLATE, w=2.1, icon="duckdb"),
    ],
    flows=[
        Flow(1, "cust", "fo", "Each order line has exactly one customer: many-to-one, safe", mid=.3, do=-30, badge_at=.12, packet="N:1"),
        Flow(2, "item", "fo", "...and one stock item version (SCD) - still many-to-one", mid=.45, do=-10, packet="N:1"),
        Flow(3, "city", "fo", "...and one delivery city", mid=.6, do=10, packet="N:1"),
        Flow(4, "date", "fo", "...and one order date: dimensions only ever add columns, never rows", mid=.75, do=30, so=-10, packet="N:1"),
        Flow(5, "date", "fs", "The same dimensions join fact_sale on its own keys (invoice date)", so=10, packet="N:1"),
        Flow(6, "fo", "bad", "Join the two facts on customer + item and every order meets every matching invoice", so=-20, color=SEC, packet="×144.4", badge_at=.3),
        Flow(7, "fs", "bad", "...33.1 million rows, sales inflated 144.4× - the SQL runs, the science is wrong", mid=.7, so=-14, color=SEC, dashed=True, badge_at=.9,
             packet="fan-out"),
        Flow(8, "fo", "good", "The safe route: aggregate orders to month × item first", mid=.35, so=20, color=SAGE, packet="agg", badge_at=.55),
        Flow(9, "fs", "good", "...aggregate sales to the same grain, then the join is 1:1", so=14, mid=.5, color=SAGE, packet="agg", badge_at=.25),
        Flow(10, "good", "marts", "Our course marts bake these safe joins in - each with a declared grain the agent can read", packet="mart"),
    ],
)

# 07 ─ leakage and the prediction point ───────────────────────────────────────────────────────────────────────
LEAKAGE = Spec(
    id="07-leakage-timeline", title="The prediction point decides what a feature may be",
    subtitle="Backorder risk is predicted when an order line is created. Anything known later is leakage - and is refused in code.",
    cols=8, rows=3.6,
    nodes=[
        card("ok", "Allowed (known at or before creation)", ["quantity, unit price, lines in the order", "item attributes, buying group, territory, calendar",
             "item's backorder rate over the 90 days STRICTLY before"], 1.55, 0.3, SAGE, w=2.95),
        card("no", "Refused (post-event, or the label itself)", ["picked_date, days_to_pick, picker_key", "wwi_backorder_id / was_backordered (the label)",
             "invoice + delivery fields, TODAY's stock snapshot"], 5.75, 0.3, SEC, w=2.95),
        Node("t0", None, "earlier orders", sub="history", x=0.6, y=1.85, w=1.3),
        Node("t1", None, "ORDER LINE CREATED", sub="prediction point", x=2.6, y=1.85, w=1.5, color=SEC),
        Node("t2", None, "pick / short-pick", sub="days later", x=4.75, y=1.85, w=1.3),
        Node("t3", None, "invoice, delivery", sub="later still", x=6.75, y=1.85, w=1.3),
        card("sp", "Split by time", ["train < 2015-01-01 · validate to 2015-06-30", "test after · threshold chosen on validation"], 1.55, 3.25, DEV, w=2.5),
        Node("mdl", "sagemaker-training", "Backorder model", sub="scikit-learn", x=3.95, y=3.25),
        card("rf", "Red flag", ["temporal-holdout ROC-AUC > 0.98 ⇒ suspect leakage", "a pick-delay 'model' scoring 0.999 detects backorders"],
             6.3, 3.25, BEDROCK, w=2.5),
    ],
    flows=[
        Flow(1, "t0", "t1", "Time runs left to right. Earlier orders are history the model may learn from", packet="history"),
        Flow(2, "t1", "t2", "The order line is created: this is the moment we predict backorder risk", packet="predict"),
        Flow(3, "t2", "t3", "Picking, short-picks, invoices and deliveries all happen AFTER the prediction", packet="future"),
        Flow(4, "t1", "ok", "Allowed: anything known at or before creation, including 90-day rates strictly before",
             sp="t", dp="b", do=176, color=SAGE, packet="features"),
        Flow(5, "t2", "no", "Refused by the feature guard: post-event fields, and the label itself", sp="t", dp="b", do=-168,
             color=SEC, dashed=True, packet="blocked"),
        Flow(6, "sp", "mdl", "Split by time, not at random, so the test set really is the future", packet="train"),
        Flow(7, "mdl", "rf", "Check the result: holdout AUC above 0.98 is a red flag for leakage, not a triumph", color=SEC, packet="AUC"),
    ],
)

# 12 ─ preflight and lifecycle ─────────────────────────────────────────────────────────────────────────────────
LIFECYCLE = Spec(
    id="12-preflight-lifecycle", title="Nothing bills until the gates pass",
    subtitle="Ownership → preflight → estimate → watchdog → provision (registered immediately) → use → export → delete → verify.",
    cols=8.4, rows=2.6,
    groups=[
        Group("gates", "Gates · nothing billable exists yet", 0, 0.3, 2, 0.3, style="logic"),
        Group("run", "Billable window · every create registered", 4, 0.3, 6, 0.3, style="cluster"),
    ],
    nodes=[
        Node("own", "iam", "Own account?", sub="explicit flag", x=0, y=0.3),
        Node("pre", "sts", "Preflight", sub="versions · quotas · AZs", x=1, y=0.3),
        Node("est", "python", "Estimate", sub="low / base / high $", x=2, y=0.3),
        Node("wd", "scheduler", "Watchdog", sub="fires at ExpiresAt", x=3, y=0.3),
        Node("pv", "cloudformation", "Provision", sub="registry after each create", x=4, y=0.3),
        Node("use", "sagemaker-notebook", "Use", sub="Parts 2-17", x=5, y=0.3),
        Node("ex", "s3", "Export", sub="evidence first", x=6, y=0.3),
        Node("del", "lambda", "Delete", sub="dependency order", x=7, y=0.3),
        Node("vf", "config", "Verify", sub="independent re-query", x=8, y=0.3),
        Node("stop", None, "STOP - nothing was created", sub="any 'No' at a gate", x=1, y=2.0, w=1.8, color=SEC),
    ],
    flows=[
        Flow(1, "own", "pre", "Gate 1: you confirm this is your own sandbox account", packet="yes"),
        Flow(2, "pre", "est", "Gate 2: preflight checks versions, quotas and Availability Zones", packet="ok"),
        Flow(3, "est", "wd", "Gate 3: a low / base / high cost estimate you accept", packet="$"),
        Flow(4, "wd", "pv", "The expiry watchdog is scheduled BEFORE anything billable exists", packet="armed"),
        Flow(5, "pv", "use", "Every resource is written to the registry the moment it is created", packet="registered"),
        Flow(6, "use", "ex", "You work through Parts 2-17", packet="work"),
        Flow(7, "ex", "del", "Evidence is exported first - traces, artifacts, reports", packet="evidence"),
        Flow(8, "del", "vf", "Resources are deleted in dependency order, then re-queried independently", packet="deleted?"),
        Flow(9, "pre", "stop", "A 'No' at any gate stops here - before anything billable exists", dashed=True, color=SEC, packet="no"),
        Flow(10, "vf", "wd", "Can't prove absence? The watchdog is KEPT and retries every 10 minutes - success is never "
             "printed just because a delete call returned", sp="b", dp="b", via=1.1, dashed=True, color=SEC, packet="retry"),
    ],
)

SPECS = [SEMANTIC, LEAKAGE, LIFECYCLE]
