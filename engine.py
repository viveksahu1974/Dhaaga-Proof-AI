"""Transparent decision tools for DhaagaProof.

No pretrained model is passed off as one. These routines implement auditable
operations research and Bayesian-style reliability estimates. An optional local
LLM in app.py can explain results but cannot authorize financial actions.
"""
from __future__ import annotations

from datetime import date
from math import ceil


def money(value: float) -> float:
    return round(float(value) + 1e-8, 2)


def quote(order: dict, inflation_pct: float = 0.0) -> dict:
    inflation_pct = max(-50.0, min(200.0, float(inflation_pct)))
    material = float(order["material_per_unit"]) * (1 + inflation_pct / 100)
    hourly = float(order["labour_rate_hour"])
    minutes = float(order["minutes_per_unit"])
    overhead = float(order["overhead_per_unit"])
    margin = float(order["target_margin_pct"]) / 100
    labour = hourly * minutes / 60
    cost = material + labour + overhead
    suggested = ceil(cost / max(.01, 1 - margin))
    quoted = float(order["buyer_price_per_unit"])
    realized = (quoted - cost) / quoted * 100 if quoted else -100
    return {
        "material": money(material), "labour": money(labour),
        "overhead": money(overhead), "unit_cost": money(cost),
        "min_quote_for_target": suggested, "buyer_price": money(quoted),
        "margin_pct": money(realized), "target_margin_pct": money(margin * 100),
        "total_order_value": money(quoted * int(order["quantity"])),
        "projected_profit": money((quoted - cost) * int(order["quantity"])),
        "below_cost": quoted < cost,
        "below_target": quoted < suggested,
        "inflation_pct": inflation_pct,
        "assumptions": "Costs are user inputs. This is a planning estimate, not a market-price or wage-law assessment."
    }


def reliability(member: dict) -> float:
    # Modest conservative prior prevents new members receiving a fake 100% score.
    jobs = int(member.get("jobs_done", 0))
    late = min(int(member.get("jobs_late", 0)), jobs)
    return (jobs - late + 3) / (jobs + 4)


def gini(values: list[float]) -> float:
    values = sorted(max(0.0, float(v)) for v in values)
    if not values or sum(values) <= 0:
        return 0.0
    n = len(values)
    return round(sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(values)) / (n * sum(values)), 3)


def allocate(order: dict, members: list[dict], workload: dict[int, int] | None = None,
             asof: date | None = None) -> dict:
    """Bounded assignment; balancing workload, trust and actual daily capacity.

    This proposes work only. Nothing is committed before group approval.
    """
    asof = asof or date.today()
    due = date.fromisoformat(order["due_date"])
    days = max(1, (due - asof).days + 1)
    days = min(days, 90)
    workload = workload or {}
    eligible = []
    for m in members:
        if not m.get("consent", 0):
            continue
        if m["skill"] not in (order["category"], "mixed"):
            continue
        max_units = max(0, int(m["capacity_per_day"]) * days - int(workload.get(m["id"], 0)))
        if max_units:
            eligible.append({"id": m["id"], "name": m["name"],
                             "capacity": max_units, "daily": int(m["capacity_per_day"]),
                             "reliability": reliability(m), "prior_load": int(workload.get(m["id"], 0)),
                             "allocated": 0})
    # If no qualified or consented workers, explicitly flag the unmet order.
    remaining = int(order["quantity"])
    while remaining and eligible:
        choices = [m for m in eligible if m["allocated"] < m["capacity"]]
        if not choices:
            break
        # Reliability gently changes tie-breaking, without overriding fairness.
        pick = min(choices, key=lambda m: (
            (m["allocated"] + m["prior_load"]) / max(1, m["daily"] * days)
            + (1 - m["reliability"]) * .035,
            m["allocated"], m["id"]
        ))
        pick["allocated"] += 1
        remaining -= 1
    chosen = [m for m in eligible if m["allocated"]]
    wage_per_unit = float(order["labour_rate_hour"]) * float(order["minutes_per_unit"]) / 60
    for m in chosen:
        m["suggested_wage"] = money(m["allocated"] * wage_per_unit)
        m["reason"] = (f"{m['daily']} units/day capacity, estimated {round(m['reliability']*100)}% "
                       "on-time reliability; distributed to balance work against available capacity.")
    allocated_total = int(order["quantity"]) - remaining
    return {
        "order_id": int(order["id"]), "days_available": days,
        "allocations": chosen, "allocated_units": allocated_total,
        "unallocated_units": remaining,
        "payout_per_accepted_unit": money(wage_per_unit),
        "gini_allocation": gini([m["allocated"] for m in chosen]),
        "weighted_reliability": money(sum(m["allocated"] * m["reliability"] for m in chosen) / allocated_total * 100) if allocated_total else 0,
        "status": "Capacity shortfall" if remaining else "Ready for human approval",
        "human_approval_required": True,
        "explanation": "Balances consent, skill, committed load and daily capacity. No payments or work assignments have been made."
    }


def signals(order: dict, assignments: list[dict], asof: date | None = None) -> list[dict]:
    asof = asof or date.today()
    days_left = (date.fromisoformat(order["due_date"]) - asof).days
    qty = int(order["quantity"])
    done = sum(int(a["completed_units"]) for a in assignments)
    allocated = sum(int(a["allocated_units"]) for a in assignments)
    alerts = []
    if float(order["buyer_price_per_unit"]) < float(quote(order)["unit_cost"]):
        alerts.append({"level": "critical", "title": "Loss-making order", "detail": "Offered unit price is below recorded total unit cost."})
    elif quote(order)["below_target"]:
        alerts.append({"level": "warning", "title": "Margin below target", "detail": "Buyer price misses the chosen margin. Requote before confirming."})
    if order["status"] == "draft":
        alerts.append({"level": "info", "title": "Awaiting allocation", "detail": "Run the allocation engine and approve the proposed assignments."})
    else:
        if allocated < qty:
            alerts.append({"level": "warning", "title": "Unassigned pieces", "detail": f"{qty-allocated} units do not have an approved owner."})
        if days_left < 0 and done < qty:
            alerts.append({"level": "critical", "title": "Deadline missed", "detail": f"{qty-done} units incomplete after due date."})
        elif days_left <= 3 and done < qty:
            alerts.append({"level": "warning", "title": "Deadline approaching", "detail": f"{qty-done} units incomplete with {days_left} days remaining."})
        total_rejected = sum(int(a["completed_units"]) - int(a["accepted_units"]) for a in assignments)
        if done and total_rejected / done > .08:
            alerts.append({"level": "warning", "title": "Quality acceptance low", "detail": f"{total_rejected} inspected units were not accepted."})
    if not alerts:
        alerts.append({"level": "ok", "title": "No immediate exceptions", "detail": "Keep collecting progress and quality observations."})
    return alerts


def agent_plan(order: dict, assignments: list[dict], members: list[dict],
               workload: dict[int, int] | None = None, asof: date | None = None) -> dict:
    """Observable agent loop: perceive > diagnose > propose > gate.

    It learns simple per-worker reliability from recorded jobs. Deterministic
    planning is described as such; optional language-model reasoning is separate.
    """
    asof = asof or date.today()
    alerts = signals(order, assignments, asof)
    actions = []
    if order["status"] == "draft":
        suggested = allocate(order, members, workload or {}, asof)
        actions.append({"type": "review_allocation", "label": "Review allocation plan",
                        "reason": f"{suggested['allocated_units']} of {order['quantity']} units could be assigned.",
                        "human_approval": True})
    else:
        for a in alerts:
            if a["title"] in ("Deadline approaching", "Deadline missed"):
                actions.append({"type": "contact_members", "label": "Draft progress check-in",
                                "reason": "Ask group members for delivery estimates before changing assignments.",
                                "human_approval": True})
            if a["title"] in ("Margin below target", "Loss-making order"):
                actions.append({"type": "review_quote", "label": "Review quote economics",
                                "reason": "Check recorded inputs with buyer and SHG leader.",
                                "human_approval": True})
            if a["title"] == "Quality acceptance low":
                actions.append({"type": "quality_review", "label": "Arrange human quality check",
                                "reason": "Do not automatically reject handmade work.",
                                "human_approval": True})
    if not actions:
        actions.append({"type": "collect_progress", "label": "Collect member progress",
                        "reason": "Updated production records improve deadline forecasts.",
                        "human_approval": True})
    return {
        "goal": f"Deliver {order['quantity']} {order['product']} by {order['due_date']} with transparent wages",
        "cycle": ["Observe order and member records", "Evaluate cost, capacity and quality",
                  "Propose bounded next steps", "Await group approval", "Record every approved change"],
        "evidence": {"due_date": order["due_date"], "member_count": len(members),
                     "completed_units": sum(int(a["completed_units"]) for a in assignments)},
        "signals": alerts, "proposed_actions": actions,
        "execution": "No external action or payment was executed.",
        "model_type": "Explainable constraint engine + Bayesian-smoothed worker reliability; optional local Ollama LLM for narration"
    }
