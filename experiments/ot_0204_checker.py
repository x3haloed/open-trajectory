from __future__ import annotations

import re
from typing import Any


STAKE_KEYS = {"stake_id", "property", "target_set", "question", "rationale", "success_condition", "surrender_condition"}
SELECTOR_KEYS = {"selector_id", "dimension_name", "world_meaning", "direction", "missing_policy", "blocked_policy", "tie_policy", "rationale"}
OLD_DIMENSIONS = {"options", "outcome", "blocked", "contactable-distinction", "observed-unblocked", "latent-unblocked", "viable-unblocked", "contactable-target"}


def slug(value: Any, maximum: int = 63) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(rf"[a-z][a-z0-9-]{{2,{maximum}}}", value))


def valid_stake(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == STAKE_KEYS and slug(value.get("stake_id")) and slug(value.get("property")) and slug(value.get("target_set")) and all(isinstance(value.get(key), str) and value[key].strip() for key in STAKE_KEYS - {"stake_id", "property", "target_set"}))


def valid_selector(value: Any) -> bool:
    return bool(isinstance(value, dict) and set(value) == SELECTOR_KEYS and slug(value.get("selector_id")) and slug(value.get("dimension_name"), 31) and value["dimension_name"] not in OLD_DIMENSIONS and isinstance(value.get("world_meaning"), str) and value["world_meaning"].strip() and value.get("direction") in {"maximize", "minimize"} and value.get("missing_policy") == "reject-portfolio" and value.get("blocked_policy") == "exclude" and value.get("tie_policy") == "preserve-all-extrema" and isinstance(value.get("rationale"), str) and value["rationale"].strip())


def selected_ids(portfolio: dict[str, Any], selector: dict[str, Any]) -> list[str]:
    live = [row for row in portfolio["candidates"] if not row["blocked"]]
    if not live:
        return []
    values = [row["measurement"] for row in live]
    extreme = max(values) if selector["direction"] == "maximize" else min(values)
    return sorted(row["stake"]["stake_id"] for row in live if row["measurement"] == extreme)


def valid_portfolio(value: Any, selector: dict[str, Any] | None = None) -> bool:
    if not isinstance(value, dict) or set(value) != {"portfolio_id", "dimension_name", "rationale", "candidates", "predicted_selection"} or not slug(value.get("portfolio_id")) or not slug(value.get("dimension_name"), 31) or not isinstance(value.get("rationale"), str) or not value["rationale"].strip():
        return False
    rows = value.get("candidates")
    if not isinstance(rows, list) or not 4 <= len(rows) <= 6 or any(not isinstance(row, dict) or set(row) != {"stake", "measurement", "blocked"} or not valid_stake(row.get("stake")) or not isinstance(row.get("measurement"), int) or isinstance(row.get("measurement"), bool) or not -100 <= row["measurement"] <= 100 or not isinstance(row.get("blocked"), bool) for row in rows):
        return False
    ids = [row["stake"]["stake_id"] for row in rows]
    predicted = value.get("predicted_selection")
    structural = len(ids) == len(set(ids)) and any(row["blocked"] for row in rows) and sum(not row["blocked"] for row in rows) >= 2 and isinstance(predicted, list) and len(predicted) == len(set(predicted)) and predicted and set(predicted) <= set(ids)
    if not structural:
        return False
    return selector is None or (value["dimension_name"] == selector["dimension_name"] and predicted == selected_ids(value, selector))


def valid_renewal(value: Any, receipt_digest: str) -> bool:
    return bool(isinstance(value, dict) and set(value) == {"action", "prior_disposition", "completion_receipt_digest", "selector", "representative_portfolio", "rationale"} and value.get("action") == "assimilate-completion-and-install-selector" and value.get("prior_disposition") == "completed-assimilated" and value.get("completion_receipt_digest") == receipt_digest and isinstance(value.get("rationale"), str) and value["rationale"].strip() and valid_selector(value.get("selector")) and valid_portfolio(value.get("representative_portfolio"), value["selector"]) and len(value["representative_portfolio"]["predicted_selection"]) == 1)
