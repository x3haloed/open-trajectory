from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parent
REPO = ROOT.parent
BASE_PATH = ROOT / "ot_0206_selected_ledger_world_contact.py"
BASE_SHA256 = "ceba5d53dfae5c10d74c4fe197468969840d93039e44a2496551c76f803c00cc"


def load_base():
    source = BASE_PATH.read_bytes()
    if hashlib.sha256(source).hexdigest() != BASE_SHA256:
        raise RuntimeError("OT-0206 implementation changed")
    translated = source.decode().replace("OT-0206", "OT-0207").replace("ot-0206", "ot-0207")
    spec = importlib.util.spec_from_loader("ot0207_frozen_ot0206", loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(BASE_PATH)
    sys.modules[spec.name] = module
    exec(compile(translated, str(BASE_PATH), "exec"), module.__dict__)
    module.CONTACT_SCHEMA = REPO / "spec/ot-0206-ledger-contact-author.schema.json"
    module.PROGRAM_SCHEMA = REPO / "spec/ot-0206-ledger-program-author.schema.json"
    module.REPLAY_SCHEMA = REPO / "spec/ot-0206-ledger-replay.schema.json"
    return module


previous = load_base()
original_run_contact = previous.run_contact
original_write_json = previous.authority_base.guide_base.write_json
repair_fixture: dict[str, Any] = {}


def namespace_suite(suite: dict[str, Any], index: int) -> tuple[dict[str, Any], str]:
    local = suite["suite_id"]
    sealed = copy.deepcopy(suite)
    sealed["suite_id"] = f"sealed-encounter-{index:02d}"
    return sealed, local


def run_contact(context, prior131, root, label, parent, stake, index):
    result = original_run_contact(context, prior131, root, label, parent, stake, index)
    if result.get("accepted"):
        sealed, local = namespace_suite(result["suite"], index)
        result["local_suite_id"] = local
        result["suite"] = sealed
        result["namespace_authority"] = "ot-0207-sealed-encounter-index"
    return result


def write_json(path, value):
    if path.name == "fixture-conformance.json" and path.parent.name == "OT-0207":
        value = copy.deepcopy(value)
        value["encounter_namespace_repair"] = repair_fixture
        value["checks"]["encounter_namespace_repair"] = repair_fixture.get("passed", False)
        value["checks"]["passed"] = all(value["checks"].values())
    return original_write_json(path, value)


previous.run_contact = run_contact
previous.authority_base.guide_base.write_json = write_json


def repair_conformance(repo: Path, store: Path) -> dict[str, Any]:
    lineage = previous.authority_base.guide_base.load_base()
    selector_base, base = lineage.selector_base, lineage.base
    prior92 = base.mechanism.load_prior()
    _, _, _, p82 = base.mechanism.prior_chain(prior92)
    result = selector_base.load_artifact(p82, repo, store, "OT-0206", "selected-ledger-world-contact-aggregate.json")
    rows = result["contact_rows"]
    local_suites = [row["choice"]["suite"] for row in rows]
    local_ids = [suite["suite_id"] for suite in local_suites]
    normalized = [namespace_suite(suite, row["index"])[0] for row, suite in zip(rows, local_suites)]
    retained = all(normalized[index]["cases"] == local_suites[index]["cases"] for index in range(len(local_suites)))
    checks = {
        "ot0206_exact_apparatus_rejection": result["observer_disposition"] == "rejected" and result["fresh_actor_count"] == 4 and result["final_subject_digest"] == result["source_subject_digest"],
        "four_local_contacts_accepted": len(rows) == 4 and all(row["choice"]["accepted"] and row["choice"]["audit"]["trace_regime"]["accepted"] for row in rows),
        "local_collision_reproduced": len(set(local_ids)) < len(local_ids),
        "encounter_identities_unique": len({suite["suite_id"] for suite in normalized}) == 4,
        "local_content_retained": retained,
        "base_hash_exact": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest() == BASE_SHA256,
    }
    checks["passed"] = all(checks.values())
    return {"checks": checks, "local_suite_ids": local_ids, "sealed_suite_ids": [suite["suite_id"] for suite in normalized], "passed": checks["passed"]}


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--store", type=Path)
    args, _ = parser.parse_known_args()
    repo = args.repo.resolve()
    store = (args.store or repo / ".evidence").resolve()
    global repair_fixture
    repair_fixture = repair_conformance(repo, store)
    if not repair_fixture["passed"]:
        print(json.dumps({"base_sha256": BASE_SHA256, "encounter_namespace_repair": repair_fixture}, indent=2, sort_keys=True))
        return 2
    result = previous.main()
    if "--preflight-only" in sys.argv:
        print(json.dumps({"ot0206_base_sha256": BASE_SHA256, "encounter_namespace_repair": repair_fixture}, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
