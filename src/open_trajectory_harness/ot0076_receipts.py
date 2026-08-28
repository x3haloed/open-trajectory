"""Immutable causal receipts for the OT-0076 longitudinal evaluator.

The receipt layer is deliberately independent of a particular learner.  State,
projection, and update payloads are opaque bytes.  The layer gives those bytes
exact identities and binds them to the case, lineage, branch, encounter, public
query, fresh consumer, prediction, independently released outcome, and next
state in one fail-closed chain.  Authoritative updater state and actor-visible
projection are separate variables: ordinary lineages deliver the exact post-
state bytes, while only the declared update-without-projection intervention may
advance authoritative state behind a frozen actor projection.

Negative authority traces are valid evidence.  Call :func:`validate_chain`
with ``require_online_admissible=True`` when a lineage is being offered as one
of OT-0076's positive online references.  This prevents a future/hidden oracle
or a negative lineage carrying a favorable display label from becoming
authority-eligible merely because it scores well.
"""

from __future__ import annotations

import base64
import binascii
import copy
import re
from dataclasses import dataclass
from typing import Any, Final, Iterable

from .ot0002 import canonical_json, sha256_bytes


EXPERIMENT_ID: Final = "OT-0076"
SCHEMA_VERSION: Final = 1
STATE_BYTE_LIMIT: Final = 2048
PROJECTION_BYTE_LIMIT: Final = 2048
UPDATE_BYTE_LIMIT: Final = 2048

POST_STATE_PROJECTION: Final = "post-state"
UPDATE_WITHOUT_PROJECTION: Final = "update-without-projection"
PROJECTION_MODES: Final = {
    POST_STATE_PROJECTION,
    UPDATE_WITHOUT_PROJECTION,
}

ONLINE_POSITIVE: Final = "online-positive-surrogate"
LINEAGE_CLASSES: Final = {
    ONLINE_POSITIVE,
    "required-nonlearning-control",
    "adaptive-comparator",
    "causal-intervention",
    "authority-negative",
    "identity-placebo",
}

PREDICTION_INPUTS: Final = (
    "current-public-query",
    "inherited-projection",
)
UPDATE_INPUTS: Final = (
    "current-public-query",
    "inherited-pre-state",
    "released-outcome",
    "sealed-prediction-receipt",
)
FORBIDDEN_AUTHORITIES: Final = (
    "controller-cache",
    "evaluator-instructions",
    "filesystem",
    "future-outcomes",
    "hidden-masks",
    "hidden-schedule",
    "network",
    "outcome-before-prediction",
    "response-chain",
    "subprocess",
    "task-loader",
    "tools",
)
KNOWN_SURFACE_INPUTS: Final = set(PREDICTION_INPUTS) | set(UPDATE_INPUTS) | set(
    FORBIDDEN_AUTHORITIES
)
SENTINEL_CHANNELS: Final = (
    "controller-cache",
    "filesystem",
    "network",
    "response-chain",
    "subprocess",
    "task-loader",
    "tools",
)
ENVIRONMENT_KEYS: Final = {
    "architecture",
    "git_commit",
    "git_dirty",
    "os_family",
    "python_implementation",
    "python_version",
}
SEEDED_AUTHORITY_DEFECTS: Final = (
    "future-outcome-access",
    "hidden-schedule-access",
    "prediction-after-outcome",
    "reference-label-on-negative-lineage",
    "wrong-pre-state",
    "wrong-post-state",
    "wrong-update-parent",
    "cross-case-state",
    "cross-lineage-prediction",
    "cross-episode-outcome",
    "stale-projection",
    "skipped-encounter",
    "duplicate-encounter",
    "reordered-suffix",
    "sibling-branch-substitution",
    "missing-terminal-consumer",
    "favorable-summary-without-chain",
    "dropped-prediction-or-denominator-change",
    "over-budget-state-or-projection",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_SAFE_TEXT = re.compile(r"[A-Za-z0-9_.+-]{1,80}")


class ReceiptError(ValueError):
    """A fail-closed receipt rejection with a stable machine-readable code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def _reject(code: str, detail: str) -> None:
    raise ReceiptError(code, detail)


def _exact(value: object, keys: set[str], code: str, label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _reject(code, f"{label} keys differ from the frozen schema")
    return value


def _digest(value: object, code: str, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _reject(code, f"{label} is not a lowercase SHA-256 identity")
    return value


def _integer(value: object, code: str, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _reject(code, f"{label} is not an integer at least {minimum}")
    return value


def derive_identity(kind: str, *parts: object) -> str:
    """Derive an opaque stable identity without granting a label authority."""

    if type(kind) is not str or _SAFE_TEXT.fullmatch(kind) is None:
        raise ValueError("identity kind is not bounded safe text")
    return sha256_bytes(
        canonical_json(
            {
                "experiment_id": EXPERIMENT_ID,
                "kind": kind,
                "parts": list(parts),
                "schema_version": SCHEMA_VERSION,
            }
        )
    )


def encode_blob(raw: bytes, *, limit: int, label: str) -> dict[str, Any]:
    """Return the exact canonical envelope for opaque learning bytes."""

    if type(raw) is not bytes:
        raise TypeError(f"{label} must be bytes")
    if len(raw) > limit:
        raise ReceiptError("over-budget-state-or-projection", f"{label} exceeds {limit} bytes")
    return {
        "base64": base64.b64encode(raw).decode("ascii"),
        "byte_count": len(raw),
        "sha256": sha256_bytes(raw),
    }


def decode_blob(value: object, *, limit: int, label: str) -> bytes:
    blob = _exact(
        value,
        {"base64", "byte_count", "sha256"},
        "blob-schema",
        label,
    )
    if type(blob["base64"]) is not str:
        _reject("blob-identity", f"{label} base64 is not text")
    try:
        raw = base64.b64decode(blob["base64"], validate=True)
    except (binascii.Error, ValueError) as error:
        raise ReceiptError("blob-identity", f"{label} base64 is invalid") from error
    if base64.b64encode(raw).decode("ascii") != blob["base64"]:
        _reject("blob-identity", f"{label} base64 is not canonical RFC 4648")
    if type(blob["byte_count"]) is not int or blob["byte_count"] != len(raw):
        _reject("blob-identity", f"{label} byte count differs")
    if len(raw) > limit:
        _reject("over-budget-state-or-projection", f"{label} exceeds {limit} bytes")
    if sha256_bytes(raw) != blob["sha256"]:
        _reject("blob-identity", f"{label} digest differs")
    return raw


def strict_online_surface() -> dict[str, Any]:
    """The only reachable prediction/update surface admissible as positive."""

    return {
        "forbidden_authorities": list(FORBIDDEN_AUTHORITIES),
        "prediction_inputs": list(PREDICTION_INPUTS),
        "state_transport": "projection-only",
        "update_inputs": list(UPDATE_INPUTS),
    }


def surface_with_extra_input(*, phase: str, input_name: str) -> dict[str, Any]:
    """Construct an explicit authority-negative surface for mutation tests."""

    surface = strict_online_surface()
    key = "prediction_inputs" if phase == "prediction" else "update_inputs"
    if phase not in {"prediction", "update"} or input_name not in KNOWN_SURFACE_INPUTS:
        raise ValueError("surface mutation is unavailable")
    surface[key] = sorted({*surface[key], input_name})
    return surface


def _validate_surface(value: object) -> tuple[dict[str, Any], bool]:
    surface = _exact(
        value,
        {
            "forbidden_authorities",
            "prediction_inputs",
            "state_transport",
            "update_inputs",
        },
        "reachable-surface-schema",
        "reachable surface",
    )
    for key in ("prediction_inputs", "update_inputs", "forbidden_authorities"):
        items = surface[key]
        if type(items) is not list or any(type(item) is not str for item in items):
            _reject("reachable-surface-schema", f"{key} is not a string list")
        if items != sorted(set(items)):
            _reject("reachable-surface-schema", f"{key} is not sorted and unique")
        if any(item not in KNOWN_SURFACE_INPUTS for item in items):
            _reject("reachable-surface-schema", f"{key} names unknown authority")
    if surface["state_transport"] != "projection-only":
        _reject("forbidden-reachable-surface", "state transport is not projection-only")
    if surface["forbidden_authorities"] != list(FORBIDDEN_AUTHORITIES):
        _reject("forbidden-reachable-surface", "forbidden authority declaration differs")
    admissible = (
        surface["prediction_inputs"] == list(PREDICTION_INPUTS)
        and surface["update_inputs"] == list(UPDATE_INPUTS)
    )
    return surface, admissible


def make_consumer_facts(
    *,
    process_instance_id: str,
    workspace_instance_id: str,
    environment_fingerprint: dict[str, Any],
    sentinel_nonce_sha256: str,
) -> dict[str, Any]:
    """Create an exact fresh-process/workspace/sentinel receipt payload.

    The caller supplies observed opaque identities and an allowlisted
    environment fingerprint.  No path or unconstrained environment map is
    accepted.
    """

    _digest(process_instance_id, "fresh-consumer", "process instance")
    _digest(workspace_instance_id, "fresh-consumer", "workspace instance")
    nonce = _digest(sentinel_nonce_sha256, "fresh-consumer", "sentinel nonce")
    return {
        "environment_fingerprint": copy.deepcopy(environment_fingerprint),
        "forbidden_channel_sentinels": [
            {
                "channel": channel,
                "observed": False,
                "sentinel_sha256": derive_identity("sentinel", nonce, channel),
            }
            for channel in SENTINEL_CHANNELS
        ],
        "process_instance_id": process_instance_id,
        "response_chain_ids": [],
        "workspace_entries_after": [],
        "workspace_entries_before": [],
        "workspace_instance_id": workspace_instance_id,
    }


def _validate_consumer_facts(value: object) -> dict[str, Any]:
    facts = _exact(
        value,
        {
            "environment_fingerprint",
            "forbidden_channel_sentinels",
            "process_instance_id",
            "response_chain_ids",
            "workspace_entries_after",
            "workspace_entries_before",
            "workspace_instance_id",
        },
        "fresh-consumer-schema",
        "fresh consumer facts",
    )
    _digest(facts["process_instance_id"], "fresh-consumer", "process instance")
    _digest(facts["workspace_instance_id"], "fresh-consumer", "workspace instance")
    if facts["workspace_entries_before"] != [] or facts["workspace_entries_after"] != []:
        _reject("fresh-workspace", "consumer workspace is not empty before and after")
    if facts["response_chain_ids"] != []:
        _reject("response-chain", "consumer retained response chaining")
    environment = _exact(
        facts["environment_fingerprint"],
        ENVIRONMENT_KEYS,
        "environment-allowlist",
        "environment fingerprint",
    )
    for key, item in environment.items():
        if key == "git_dirty":
            if type(item) is not bool:
                _reject("environment-allowlist", "git_dirty is not Boolean")
        elif key == "git_commit":
            if type(item) is not str or _COMMIT.fullmatch(item) is None:
                _reject("environment-allowlist", "git_commit is malformed")
        elif type(item) is not str or _SAFE_TEXT.fullmatch(item) is None:
            _reject("environment-allowlist", f"{key} is not bounded path-free text")
    sentinels = facts["forbidden_channel_sentinels"]
    if type(sentinels) is not list or len(sentinels) != len(SENTINEL_CHANNELS):
        _reject("forbidden-channel-sentinel", "sentinel set is incomplete")
    observed_channels = []
    for raw in sentinels:
        item = _exact(
            raw,
            {"channel", "observed", "sentinel_sha256"},
            "forbidden-channel-sentinel",
            "sentinel result",
        )
        if item["channel"] not in SENTINEL_CHANNELS:
            _reject("forbidden-channel-sentinel", "sentinel channel is unavailable")
        if item["observed"] is not False:
            _reject("forbidden-channel-sentinel", "forbidden sentinel was observed")
        _digest(item["sentinel_sha256"], "forbidden-channel-sentinel", "sentinel")
        observed_channels.append(item["channel"])
    if observed_channels != list(SENTINEL_CHANNELS):
        _reject("forbidden-channel-sentinel", "sentinels are not in frozen order")
    return facts


def _context(
    case_id: str,
    lineage_id: str | None,
    branch_id: str | None,
    encounter_index: int | None,
    episode_index: int | None,
) -> dict[str, Any]:
    return {
        "branch_id": branch_id,
        "case_id": case_id,
        "encounter_index": encounter_index,
        "episode_index": episode_index,
        "lineage_id": lineage_id,
    }


def _validate_public_query(value: object) -> dict[str, Any]:
    query = _exact(
        value,
        {"episode_start", "feature_bits", "query_id", "schema_version"},
        "query-schema",
        "public query",
    )
    if query["schema_version"] != SCHEMA_VERSION:
        _reject("query-schema", "public query schema version differs")
    if type(query["episode_start"]) is not bool:
        _reject("query-schema", "public query episode marker is not Boolean")
    if (
        type(query["feature_bits"]) is not str
        or re.fullmatch(r"[01]{12}", query["feature_bits"]) is None
        or int(query["feature_bits"], 2) == 0
    ):
        _reject("query-schema", "public query feature is not a nonzero twelve-bit vector")
    _digest(query["query_id"], "query-identity", "query")
    return query


def _make_receipt(
    kind: str,
    context: dict[str, Any],
    parents: Iterable[tuple[str, str]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = {
        "context": copy.deepcopy(context),
        "experiment_id": EXPERIMENT_ID,
        "kind": kind,
        "parents": [
            {"receipt_sha256": receipt_sha256, "role": role}
            for role, receipt_sha256 in parents
        ],
        "payload": copy.deepcopy(payload),
        "schema_version": SCHEMA_VERSION,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def _receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != "receipt_sha256"}


def _validate_outer(receipt: object, expected_kind: str) -> dict[str, Any]:
    value = _exact(
        receipt,
        {
            "context",
            "experiment_id",
            "kind",
            "parents",
            "payload",
            "receipt_sha256",
            "schema_version",
        },
        "receipt-schema",
        f"{expected_kind} receipt",
    )
    if (
        value["schema_version"] != SCHEMA_VERSION
        or value["experiment_id"] != EXPERIMENT_ID
        or value["kind"] != expected_kind
    ):
        _reject("receipt-schema", f"expected {expected_kind} receipt")
    _exact(
        value["context"],
        {"branch_id", "case_id", "encounter_index", "episode_index", "lineage_id"},
        "receipt-schema",
        "receipt context",
    )
    _digest(value["context"]["case_id"], "case-identity", "case")
    if type(value["parents"]) is not list or type(value["payload"]) is not dict:
        _reject("receipt-schema", "receipt parents or payload has the wrong type")
    for parent in value["parents"]:
        checked = _exact(
            parent,
            {"receipt_sha256", "role"},
            "receipt-schema",
            "receipt parent",
        )
        if type(checked["role"]) is not str or _SAFE_TEXT.fullmatch(checked["role"]) is None:
            _reject("receipt-schema", "receipt parent role is malformed")
        _digest(checked["receipt_sha256"], "receipt-schema", "parent receipt")
    _digest(value["receipt_sha256"], "receipt-identity", "receipt")
    return value


def _parents(receipt: dict[str, Any], expected_roles: tuple[str, ...], code: str) -> dict[str, str]:
    roles = tuple(item["role"] for item in receipt["parents"])
    if roles != expected_roles:
        _reject(code, f"{receipt['kind']} parent roles differ: {roles!r}")
    return {item["role"]: item["receipt_sha256"] for item in receipt["parents"]}


def _check_hash(receipt: dict[str, Any]) -> None:
    observed = sha256_bytes(canonical_json(_receipt_body(receipt)))
    if observed != receipt["receipt_sha256"]:
        _reject("receipt-identity", f"{receipt['kind']} canonical identity differs")


@dataclass(frozen=True)
class ChainValidation:
    case_id: str
    lineage_id: str
    branch_id: str
    encounter_start: int
    encounter_count: int
    errors: int
    authority_eligible: bool
    projection_mode: str
    accepted_updates: int
    candidate_state_changed: bool
    active_projection_changed: bool
    consumed_projection_sha256s: tuple[str, ...]
    terminal_projection_sha256: str
    terminal_audit_receipt_sha256: str
    trace_sha256: str


class ReceiptChainBuilder:
    """Build one immutable case/lineage/branch chain in causal order."""

    def __init__(
        self,
        *,
        task_sha256: str,
        case_id: str,
        case_index: int,
        horizon: int,
        condition_id: str,
        display_label: str,
        lineage_class: str,
        branch_token: str,
        surface: dict[str, Any],
        initial_state: bytes,
        initial_projection: bytes,
        first_consumer_facts: dict[str, Any],
        projection_mode: str = POST_STATE_PROJECTION,
        branch_role: str = "genesis",
        fork_parent_state_sha256: str | None = None,
        fork_parent_projection_sha256: str | None = None,
        encounter_start: int = 0,
        encounter_count: int | None = None,
        initial_revision: int | None = None,
    ) -> None:
        _digest(task_sha256, "case-identity", "task")
        _digest(case_id, "case-identity", "case")
        _integer(case_index, "case-identity", "case index")
        _integer(horizon, "case-identity", "horizon", minimum=1)
        _integer(encounter_start, "encounter-binding", "encounter start")
        if encounter_count is None:
            encounter_count = horizon - encounter_start
        _integer(encounter_count, "encounter-binding", "encounter count", minimum=1)
        if encounter_start + encounter_count != horizon:
            raise ValueError("branch suffix must end at the frozen case horizon")
        if initial_revision is None:
            initial_revision = encounter_start
        if type(initial_revision) is not int or initial_revision != encounter_start:
            raise ValueError("initial revision must equal the absolute encounter start")
        _digest(condition_id, "lineage-identity", "condition")
        if type(display_label) is not str or not 1 <= len(display_label) <= 80:
            raise ValueError("display label must contain 1 to 80 characters")
        if lineage_class not in LINEAGE_CLASSES:
            raise ValueError("lineage class is unavailable")
        if projection_mode not in PROJECTION_MODES:
            raise ValueError("projection mode is unavailable")
        if (
            projection_mode == UPDATE_WITHOUT_PROJECTION
            and lineage_class != "causal-intervention"
        ):
            raise ValueError(
                "update-without-projection mode is available only to a causal intervention"
            )
        if initial_state != initial_projection:
            raise ValueError(
                "initial authoritative state and actor projection must be byte-identical"
            )
        if type(branch_token) is not str or _SAFE_TEXT.fullmatch(branch_token) is None:
            raise ValueError("branch token is not bounded safe text")
        if branch_role not in {"genesis", "rewind-replay", "alternate"}:
            raise ValueError("branch role is unavailable")
        if branch_role == "genesis":
            if encounter_start != 0:
                raise ValueError("genesis branch must begin at encounter zero")
            if fork_parent_state_sha256 is not None or fork_parent_projection_sha256 is not None:
                raise ValueError("genesis branch cannot name a fork parent")
        else:
            _digest(fork_parent_state_sha256, "fork-parent", "fork state")
            _digest(fork_parent_projection_sha256, "fork-parent", "fork projection")
        checked_surface, surface_admissible = _validate_surface(surface)
        _validate_consumer_facts(first_consumer_facts)

        lineage_id = derive_identity("lineage", case_id, condition_id)
        branch_id = derive_identity("branch", lineage_id, branch_token)
        case_context = _context(case_id, None, None, None, None)
        lineage_context = _context(case_id, lineage_id, branch_id, None, None)
        case_receipt = _make_receipt(
            "case",
            case_context,
            (),
            {"case_index": case_index, "horizon": horizon, "task_sha256": task_sha256},
        )
        surface_receipt = _make_receipt(
            "reachable-surface",
            lineage_context,
            (("case", case_receipt["receipt_sha256"]),),
            checked_surface,
        )
        authority_eligible = lineage_class == ONLINE_POSITIVE and surface_admissible
        lineage_receipt = _make_receipt(
            "lineage",
            lineage_context,
            (
                ("case", case_receipt["receipt_sha256"]),
                ("reachable-surface", surface_receipt["receipt_sha256"]),
            ),
            {
                "authority_eligible": authority_eligible,
                "branch_id": branch_id,
                "branch_role": branch_role,
                "branch_token": branch_token,
                "condition_id": condition_id,
                "display_label": display_label,
                "fork_parent_projection_sha256": fork_parent_projection_sha256,
                "fork_parent_state_sha256": fork_parent_state_sha256,
                "encounter_start": encounter_start,
                "lineage_class": lineage_class,
                "lineage_id": lineage_id,
                "projection_mode": projection_mode,
            },
        )
        state_receipt = _make_receipt(
            "state",
            lineage_context,
            (("lineage", lineage_receipt["receipt_sha256"]),),
            {
                "blob": encode_blob(initial_state, limit=STATE_BYTE_LIMIT, label="initial state"),
                "previous_state_sha256": None,
                "revision": initial_revision,
                "role": "initial",
            },
        )
        projection_receipt = _make_receipt(
            "projection",
            _context(case_id, lineage_id, branch_id, encounter_start, None),
            (("state", state_receipt["receipt_sha256"]),),
            {
                "blob": encode_blob(
                    initial_projection,
                    limit=PROJECTION_BYTE_LIMIT,
                    label="initial projection",
                ),
                "state_receipt_sha256": state_receipt["receipt_sha256"],
                "target_encounter_index": encounter_start,
                "usage": "initial",
                "projection_mode": projection_mode,
            },
        )
        consumer_receipt = self._consumer_receipt(
            case_id=case_id,
            lineage_id=lineage_id,
            branch_id=branch_id,
            encounter_index=encounter_start,
            mode="prediction",
            projection_receipt=projection_receipt,
            surface_receipt=surface_receipt,
            facts=first_consumer_facts,
        )
        self._receipts = [
            case_receipt,
            surface_receipt,
            lineage_receipt,
            state_receipt,
            projection_receipt,
            consumer_receipt,
        ]
        self._case = case_receipt
        self._surface = surface_receipt
        self._lineage = lineage_receipt
        self._state = state_receipt
        self._projection = projection_receipt
        self._consumer = consumer_receipt
        self._projection_mode = projection_mode
        self._authoritative_state_bytes = bytes(initial_state)
        self._frozen_actor_projection = bytes(initial_projection)
        self._accepted_updates = 0
        self._candidate_state_changed = False
        self._active_projection_changed = False
        self._case_horizon = horizon
        self._encounter_start = encounter_start
        self._encounter_count = encounter_count
        self._count = 0
        self._finished = False

    @staticmethod
    def _consumer_receipt(
        *,
        case_id: str,
        lineage_id: str,
        branch_id: str,
        encounter_index: int | None,
        mode: str,
        projection_receipt: dict[str, Any],
        surface_receipt: dict[str, Any],
        facts: dict[str, Any],
    ) -> dict[str, Any]:
        checked = _validate_consumer_facts(facts)
        return _make_receipt(
            "consumer",
            _context(case_id, lineage_id, branch_id, encounter_index, None),
            (
                ("projection", projection_receipt["receipt_sha256"]),
                ("reachable-surface", surface_receipt["receipt_sha256"]),
            ),
            {
                "facts": checked,
                "mode": mode,
                "projection_receipt_sha256": projection_receipt["receipt_sha256"],
                "surface_receipt_sha256": surface_receipt["receipt_sha256"],
                "target_encounter_index": encounter_index,
            },
        )

    @property
    def lineage_id(self) -> str:
        return self._lineage["payload"]["lineage_id"]

    @property
    def branch_id(self) -> str:
        return self._lineage["payload"]["branch_id"]

    def append_encounter(
        self,
        *,
        public_query: dict[str, Any],
        episode_index: int,
        prediction: int | None,
        outcome: int,
        update_decision: str,
        authoritative_pre_state: bytes,
        update_payload: bytes,
        post_state: bytes,
        next_projection: bytes,
        next_consumer_facts: dict[str, Any],
        prediction_status: str = "valid",
        consequence_binding: str = "current",
        delivered_outcome: int | None = None,
    ) -> None:
        if self._finished or self._count >= self._encounter_count:
            raise RuntimeError("OT-0076 chain has no remaining encounter")
        public_query = _validate_public_query(public_query)
        query_id = _digest(public_query["query_id"], "query-identity", "query")
        _integer(episode_index, "episode-binding", "episode index")
        if prediction_status not in {"valid", "invalid", "missing", "timeout"}:
            raise ValueError("prediction status is unavailable")
        if prediction_status == "valid":
            if prediction not in {0, 1}:
                raise ValueError("valid prediction must be a bit")
        elif prediction is not None:
            raise ValueError("nonvalid prediction must be null")
        if outcome not in {0, 1}:
            raise ValueError("outcome must be a bit")
        if update_decision not in {"update", "no-op"}:
            raise ValueError("update decision is unavailable")
        if type(authoritative_pre_state) is not bytes:
            raise TypeError("authoritative pre-state must be bytes")
        if authoritative_pre_state != self._authoritative_state_bytes:
            raise ReceiptError(
                "wrong-update-parent",
                "updater did not consume the exact prior authoritative state bytes",
            )
        if consequence_binding not in {"current", "withheld", "one-step-stale"}:
            raise ValueError("consequence binding is unavailable")
        if consequence_binding == "current":
            if delivered_outcome is None:
                delivered_outcome = outcome
            if delivered_outcome != outcome:
                raise ValueError("current consequence binding must deliver current outcome")
        elif consequence_binding == "withheld":
            if delivered_outcome is not None or update_decision != "no-op":
                raise ValueError("withheld consequence must produce a no-op")
        elif delivered_outcome not in {0, 1}:
            raise ValueError("stale consequence must deliver a bit")
        _validate_consumer_facts(next_consumer_facts)

        index = self._encounter_start + self._count
        case_id = self._case["context"]["case_id"]
        lineage_id = self.lineage_id
        branch_id = self.branch_id
        context = _context(case_id, lineage_id, branch_id, index, episode_index)
        encounter_receipt = _make_receipt(
            "encounter",
            context,
            (
                ("lineage", self._lineage["receipt_sha256"]),
                ("consumer", self._consumer["receipt_sha256"]),
            ),
            {
                "encounter_index": index,
                "episode_index": episode_index,
                "episode_start": public_query["episode_start"],
                "query_id": query_id,
            },
        )
        query_receipt = _make_receipt(
            "query",
            context,
            (("encounter", encounter_receipt["receipt_sha256"]),),
            {
                "public_query": copy.deepcopy(public_query),
                "public_query_sha256": sha256_bytes(canonical_json(public_query)),
                "query_id": query_id,
            },
        )
        pre_state_receipt = _make_receipt(
            "pre-state",
            context,
            (
                ("encounter", encounter_receipt["receipt_sha256"]),
                ("state", self._state["receipt_sha256"]),
                ("projection", self._projection["receipt_sha256"]),
                ("consumer", self._consumer["receipt_sha256"]),
            ),
            {
                "consumer_receipt_sha256": self._consumer["receipt_sha256"],
                "projection_receipt_sha256": self._projection["receipt_sha256"],
                "state_receipt_sha256": self._state["receipt_sha256"],
            },
        )
        prediction_receipt = _make_receipt(
            "prediction",
            context,
            (
                ("query", query_receipt["receipt_sha256"]),
                ("pre-state", pre_state_receipt["receipt_sha256"]),
                ("consumer", self._consumer["receipt_sha256"]),
            ),
            {
                "prediction": prediction,
                "query_receipt_sha256": query_receipt["receipt_sha256"],
                "sealed_before_outcome": True,
                "status": prediction_status,
            },
        )
        world_event_sha256 = derive_identity(
            "world-outcome",
            self._case["payload"]["task_sha256"],
            case_id,
            query_id,
            outcome,
        )
        outcome_receipt = _make_receipt(
            "outcome",
            context,
            (
                ("prediction", prediction_receipt["receipt_sha256"]),
                ("query", query_receipt["receipt_sha256"]),
            ),
            {
                "authority": "controller-world",
                "outcome": outcome,
                "prediction_receipt_sha256": prediction_receipt["receipt_sha256"],
                "released_after_prediction": True,
                "world_event_sha256": world_event_sha256,
            },
        )
        update_receipt = _make_receipt(
            "update",
            context,
            (
                ("pre-state", pre_state_receipt["receipt_sha256"]),
                ("outcome", outcome_receipt["receipt_sha256"]),
                ("prediction", prediction_receipt["receipt_sha256"]),
            ),
            {
                "consequence_binding": consequence_binding,
                "decision": update_decision,
                "delivered_outcome": delivered_outcome,
                "authoritative_pre_state_receipt_sha256": self._state[
                    "receipt_sha256"
                ],
                "authoritative_pre_state_sha256": sha256_bytes(
                    authoritative_pre_state
                ),
                "outcome_receipt_sha256": outcome_receipt["receipt_sha256"],
                "pre_state_receipt_sha256": self._state["receipt_sha256"],
                "projection_mode": self._projection_mode,
                "update_payload": encode_blob(
                    update_payload,
                    limit=UPDATE_BYTE_LIMIT,
                    label="update payload",
                ),
            },
        )
        revision = self._state["payload"]["revision"] + 1
        post_state_receipt = _make_receipt(
            "state",
            context,
            (
                ("update", update_receipt["receipt_sha256"]),
                ("pre-state", pre_state_receipt["receipt_sha256"]),
            ),
            {
                "blob": encode_blob(post_state, limit=STATE_BYTE_LIMIT, label="post state"),
                "previous_state_sha256": self._state["receipt_sha256"],
                "revision": revision,
                "role": "post",
            },
        )
        if update_decision == "no-op" and post_state != decode_blob(
            self._state["payload"]["blob"], limit=STATE_BYTE_LIMIT, label="pre-state"
        ):
            raise ValueError("no-op update must preserve exact state bytes")
        if update_decision == "no-op" and next_projection != decode_blob(
            self._projection["payload"]["blob"],
            limit=PROJECTION_BYTE_LIMIT,
            label="inherited projection",
        ):
            raise ValueError("no-op update must preserve exact projection bytes")
        inherited_projection = decode_blob(
            self._projection["payload"]["blob"],
            limit=PROJECTION_BYTE_LIMIT,
            label="inherited projection",
        )
        if (
            self._projection_mode == UPDATE_WITHOUT_PROJECTION
            and next_projection != self._frozen_actor_projection
        ):
            raise ReceiptError(
                "stale-projection",
                "update-without-projection delivered projection is not the frozen actor projection",
            )
        if (
            self._projection_mode == POST_STATE_PROJECTION
            and next_projection != post_state
        ):
            raise ReceiptError(
                "stale-projection",
                "ordinary projection does not equal the exact authoritative post-state bytes",
            )
        terminal = self._count == self._encounter_count - 1
        projection_receipt = _make_receipt(
            "projection",
            _context(
                case_id,
                lineage_id,
                branch_id,
                None if terminal else index + 1,
                None,
            ),
            (("state", post_state_receipt["receipt_sha256"]),),
            {
                "blob": encode_blob(
                    next_projection,
                    limit=PROJECTION_BYTE_LIMIT,
                    label="next projection",
                ),
                "state_receipt_sha256": post_state_receipt["receipt_sha256"],
                "target_encounter_index": None if terminal else index + 1,
                "usage": "terminal" if terminal else "next",
                "projection_mode": self._projection_mode,
            },
        )
        consumer_receipt = self._consumer_receipt(
            case_id=case_id,
            lineage_id=lineage_id,
            branch_id=branch_id,
            encounter_index=None if terminal else index + 1,
            mode="terminal-audit" if terminal else "prediction",
            projection_receipt=projection_receipt,
            surface_receipt=self._surface,
            facts=next_consumer_facts,
        )
        self._receipts.extend(
            [
                encounter_receipt,
                query_receipt,
                pre_state_receipt,
                prediction_receipt,
                outcome_receipt,
                update_receipt,
                post_state_receipt,
                projection_receipt,
                consumer_receipt,
            ]
        )
        self._state = post_state_receipt
        self._projection = projection_receipt
        self._consumer = consumer_receipt
        if update_decision == "update":
            self._accepted_updates += 1
            if post_state != authoritative_pre_state:
                self._candidate_state_changed = True
        if next_projection != inherited_projection:
            self._active_projection_changed = True
        self._authoritative_state_bytes = bytes(post_state)
        self._count += 1

    def finish(self) -> dict[str, Any]:
        if self._finished:
            raise RuntimeError("OT-0076 chain is already sealed")
        if self._count != self._encounter_count or self._consumer["payload"]["mode"] != "terminal-audit":
            raise RuntimeError("OT-0076 chain is incomplete")
        if (
            self._projection_mode == UPDATE_WITHOUT_PROJECTION
            and not self._candidate_state_changed
        ):
            raise ReceiptError(
                "wrong-post-state",
                "update-without-projection never advanced authoritative candidate state",
            )
        errors = 0
        for offset in range(self._encounter_count):
            base = 6 + offset * 9
            prediction = self._receipts[base + 3]["payload"]
            outcome = self._receipts[base + 4]["payload"]["outcome"]
            errors += prediction["status"] != "valid" or prediction["prediction"] != outcome
        body = {
            "case_receipt_sha256": self._case["receipt_sha256"],
            "encounter_count": self._encounter_count,
            "encounter_start": self._encounter_start,
            "experiment_id": EXPERIMENT_ID,
            "lineage_receipt_sha256": self._lineage["receipt_sha256"],
            "receipt_order": copy.deepcopy(self._receipts),
            "schema_version": SCHEMA_VERSION,
            "summary": {"denominator": self._encounter_count, "errors": int(errors)},
            "terminal_audit_receipt_sha256": self._consumer["receipt_sha256"],
        }
        chain = {**body, "trace_sha256": sha256_bytes(canonical_json(body))}
        self._finished = True
        return chain


def _same_context(
    receipt: dict[str, Any],
    *,
    case_id: str,
    lineage_id: str,
    branch_id: str,
    encounter_index: int,
    episode_index: int,
    code: str,
) -> None:
    context = receipt["context"]
    if context["case_id"] != case_id:
        _reject("cross-case-state" if receipt["kind"] in {"state", "pre-state", "projection"} else code, "receipt case differs")
    if context["lineage_id"] != lineage_id:
        _reject("cross-lineage-prediction" if receipt["kind"] == "prediction" else code, "receipt lineage differs")
    if context["branch_id"] != branch_id:
        _reject("sibling-branch-substitution", "receipt branch differs")
    if context["encounter_index"] != encounter_index:
        _reject(code, "receipt encounter index differs")
    if context["episode_index"] != episode_index:
        _reject("cross-episode-outcome" if receipt["kind"] == "outcome" else code, "receipt episode differs")


def validate_chain(
    chain: object,
    *,
    require_online_admissible: bool = False,
) -> ChainValidation:
    """Validate a complete lineage, its causal ancestry, and terminal audit."""

    value = _exact(
        chain,
        {
            "case_receipt_sha256",
            "encounter_count",
            "encounter_start",
            "experiment_id",
            "lineage_receipt_sha256",
            "receipt_order",
            "schema_version",
            "summary",
            "terminal_audit_receipt_sha256",
            "trace_sha256",
        },
        "trace-schema",
        "causal trace",
    )
    if value["schema_version"] != SCHEMA_VERSION or value["experiment_id"] != EXPERIMENT_ID:
        _reject("trace-schema", "trace identity differs")
    receipts = value["receipt_order"]
    if type(receipts) is not list or not receipts:
        _reject("favorable-summary-without-chain", "summary has no causal receipt chain")
    encounter_count = _integer(value["encounter_count"], "denominator", "encounter count", minimum=1)
    encounter_start = _integer(value["encounter_start"], "encounter-binding", "encounter start")
    if len(receipts) != 6 + 9 * encounter_count:
        expected_prediction_nodes = [
            item for item in receipts if type(item) is dict and item.get("kind") == "prediction"
        ]
        if len(expected_prediction_nodes) != encounter_count:
            _reject("dropped-prediction-or-denominator-change", "prediction count or denominator differs")
        _reject("missing-terminal-consumer", "receipt count omits a required causal node")

    case = _validate_outer(receipts[0], "case")
    case_context = case["context"]
    case_id = case_context["case_id"]
    if any(case_context[key] is not None for key in ("lineage_id", "branch_id", "encounter_index", "episode_index")):
        _reject("case-identity", "case root has descendant context")
    if case["parents"] != []:
        _reject("case-identity", "case root has a parent")
    case_payload = _exact(case["payload"], {"case_index", "horizon", "task_sha256"}, "case-identity", "case payload")
    _integer(case_payload["case_index"], "case-identity", "case index")
    horizon = _integer(case_payload["horizon"], "denominator", "horizon", minimum=1)
    _digest(case_payload["task_sha256"], "case-identity", "task")

    surface = _validate_outer(receipts[1], "reachable-surface")
    surface_parents = _parents(surface, ("case",), "reachable-surface-schema")
    if surface_parents["case"] != case["receipt_sha256"]:
        _reject("case-identity", "surface does not descend from case")
    _, surface_admissible = _validate_surface(surface["payload"])

    lineage = _validate_outer(receipts[2], "lineage")
    lineage_payload = _exact(
        lineage["payload"],
        {
            "authority_eligible",
            "branch_id",
            "branch_role",
            "branch_token",
            "condition_id",
            "display_label",
            "fork_parent_projection_sha256",
            "fork_parent_state_sha256",
            "encounter_start",
            "lineage_class",
            "lineage_id",
            "projection_mode",
        },
        "lineage-identity",
        "lineage payload",
    )
    lineage_id = _digest(lineage_payload["lineage_id"], "lineage-identity", "lineage")
    branch_id = _digest(lineage_payload["branch_id"], "lineage-identity", "branch")
    condition_id = _digest(lineage_payload["condition_id"], "lineage-identity", "condition")
    expected_lineage = derive_identity("lineage", case_id, condition_id)
    if lineage_id != expected_lineage:
        _reject("lineage-identity", "lineage identity is not case/condition-derived")
    branch_token = lineage_payload["branch_token"]
    if type(branch_token) is not str or _SAFE_TEXT.fullmatch(branch_token) is None:
        _reject("lineage-identity", "branch token is malformed")
    if branch_id != derive_identity("branch", lineage_id, branch_token):
        _reject("lineage-identity", "branch identity is not lineage/token-derived")
    if lineage_payload["lineage_class"] not in LINEAGE_CLASSES:
        _reject("lineage-identity", "lineage class is unavailable")
    projection_mode = lineage_payload["projection_mode"]
    if projection_mode not in PROJECTION_MODES:
        _reject("lineage-identity", "projection mode is unavailable")
    if (
        projection_mode == UPDATE_WITHOUT_PROJECTION
        and lineage_payload["lineage_class"] != "causal-intervention"
    ):
        _reject(
            "authority-eligibility",
            "update-without-projection mode is not a causal intervention",
        )
    if type(lineage_payload["display_label"]) is not str or not 1 <= len(lineage_payload["display_label"]) <= 80:
        _reject("lineage-identity", "display label is malformed")
    branch_role = lineage_payload["branch_role"]
    if branch_role not in {"genesis", "rewind-replay", "alternate"}:
        _reject("lineage-identity", "branch role is unavailable")
    if branch_role == "genesis":
        if lineage_payload["encounter_start"] != 0:
            _reject("encounter-binding", "genesis does not start at encounter zero")
        if (
            lineage_payload["fork_parent_state_sha256"] is not None
            or lineage_payload["fork_parent_projection_sha256"] is not None
        ):
            _reject("fork-parent", "genesis names a fork parent")
    else:
        _digest(
            lineage_payload["fork_parent_state_sha256"],
            "fork-parent",
            "fork state",
        )
        _digest(
            lineage_payload["fork_parent_projection_sha256"],
            "fork-parent",
            "fork projection",
        )
    if lineage_payload["encounter_start"] != encounter_start:
        _reject("encounter-binding", "lineage and trace encounter starts differ")
    expected_eligible = lineage_payload["lineage_class"] == ONLINE_POSITIVE and surface_admissible
    if lineage_payload["authority_eligible"] is not expected_eligible:
        _reject("authority-eligibility", "lineage authority flag is not derived from class and surface")
    if require_online_admissible and not expected_eligible:
        reachable = {
            *surface["payload"]["prediction_inputs"],
            *surface["payload"]["update_inputs"],
        }
        if "future-outcomes" in reachable:
            _reject("future-outcome-access", "positive lineage can reach future outcomes")
        if "hidden-schedule" in reachable or "hidden-masks" in reachable:
            _reject("hidden-schedule-access", "positive lineage can reach hidden world state")
        _reject("reference-label-on-negative-lineage", "display label cannot grant positive authority")
    lineage_parents = _parents(lineage, ("case", "reachable-surface"), "lineage-identity")
    if lineage_parents != {"case": case["receipt_sha256"], "reachable-surface": surface["receipt_sha256"]}:
        _reject("lineage-identity", "lineage ancestry differs")
    if lineage["context"] != _context(case_id, lineage_id, branch_id, None, None):
        _reject("lineage-identity", "lineage context differs")
    if surface["context"] != lineage["context"]:
        _reject("lineage-identity", "surface lineage context differs")

    state = _validate_outer(receipts[3], "state")
    if state["context"] != lineage["context"]:
        _reject("cross-case-state", "initial state context differs")
    state_payload = _exact(state["payload"], {"blob", "previous_state_sha256", "revision", "role"}, "state-schema", "initial state")
    if (
        state_payload["role"] != "initial"
        or state_payload["revision"] != encounter_start
        or state_payload["previous_state_sha256"] is not None
    ):
        _reject("wrong-pre-state", "initial state markers differ")
    authoritative_state_bytes = decode_blob(
        state_payload["blob"], limit=STATE_BYTE_LIMIT, label="initial state"
    )
    if _parents(state, ("lineage",), "wrong-pre-state")["lineage"] != lineage["receipt_sha256"]:
        _reject("wrong-pre-state", "initial state does not descend from lineage")

    projection = _validate_outer(receipts[4], "projection")
    projection_payload = _exact(
        projection["payload"],
        {
            "blob",
            "projection_mode",
            "state_receipt_sha256",
            "target_encounter_index",
            "usage",
        },
        "projection-schema",
        "initial projection",
    )
    if (
        projection_payload["usage"] != "initial"
        or projection_payload["target_encounter_index"] != encounter_start
        or projection_payload["projection_mode"] != projection_mode
    ):
        _reject("stale-projection", "initial projection target differs")
    frozen_actor_projection = decode_blob(
        projection_payload["blob"],
        limit=PROJECTION_BYTE_LIMIT,
        label="initial projection",
    )
    if frozen_actor_projection != authoritative_state_bytes:
        _reject(
            "stale-projection",
            "initial actor projection differs from authoritative initial state",
        )
    if projection_payload["state_receipt_sha256"] != state["receipt_sha256"] or _parents(projection, ("state",), "stale-projection")["state"] != state["receipt_sha256"]:
        _reject("stale-projection", "initial projection does not bind initial state")
    if projection["context"] != _context(case_id, lineage_id, branch_id, encounter_start, None):
        _reject("sibling-branch-substitution", "initial projection context differs")

    consumer = _validate_outer(receipts[5], "consumer")
    _validate_consumer_node(consumer, projection, surface, encounter_start, "prediction", case_id, lineage_id, branch_id)

    process_ids: set[str] = set()
    workspace_ids: set[str] = set()
    _collect_consumer_ids(consumer, process_ids, workspace_ids)
    errors = 0
    accepted_updates = 0
    candidate_state_changed = False
    active_projection_changed = False
    consumed_projection_sha256s = [projection_payload["blob"]["sha256"]]
    terminal_projection_sha256: str | None = None
    observed_query_ids: set[str] = set()
    previous_episode_index: int | None = None
    previous_outcome: int | None = None
    if encounter_start + encounter_count != horizon:
        _reject("dropped-prediction-or-denominator-change", "trace suffix does not end at case horizon")
    ordered_encounter_indices = []
    for offset in range(encounter_count):
        candidate = receipts[6 + 9 * offset]
        if type(candidate) is dict and candidate.get("kind") == "encounter":
            payload = candidate.get("payload")
            if type(payload) is dict:
                ordered_encounter_indices.append(payload.get("encounter_index"))
    expected_encounter_indices = list(
        range(encounter_start, encounter_start + encounter_count)
    )
    if (
        len(ordered_encounter_indices) == encounter_count
        and sorted(ordered_encounter_indices) == expected_encounter_indices
        and ordered_encounter_indices != expected_encounter_indices
    ):
        _reject("reordered-suffix", "encounter suffix order differs")
    for offset in range(encounter_count):
        index = encounter_start + offset
        base = 6 + 9 * offset
        batch = receipts[base : base + 9]
        kinds = [item.get("kind") if type(item) is dict else None for item in batch]
        expected_kinds = [
            "encounter",
            "query",
            "pre-state",
            "prediction",
            "outcome",
            "update",
            "state",
            "projection",
            "consumer",
        ]
        if kinds != expected_kinds:
            if "prediction" in kinds and "outcome" in kinds and kinds.index("outcome") < kinds.index("prediction"):
                _reject("prediction-after-outcome", "outcome precedes prediction in receipt order")
            if kinds.count("prediction") != 1:
                _reject("dropped-prediction-or-denominator-change", "encounter lacks exactly one prediction")
            _reject("reordered-suffix", f"encounter {index} receipt order differs")
        encounter, query, pre_state, prediction, outcome, update, post_state, next_projection, next_consumer = [
            _validate_outer(item, kind) for item, kind in zip(batch, expected_kinds, strict=True)
        ]
        encounter_payload = _exact(encounter["payload"], {"encounter_index", "episode_index", "episode_start", "query_id"}, "encounter-schema", "encounter")
        if encounter_payload["encounter_index"] != index:
            code = "duplicate-encounter" if encounter_payload["encounter_index"] < index else "skipped-encounter"
            _reject(code, f"expected encounter {index}")
        episode_index = _integer(encounter_payload["episode_index"], "episode-binding", "episode index")
        if type(encounter_payload["episode_start"]) is not bool:
            _reject("episode-binding", "episode start is not Boolean")
        if offset == 0:
            if branch_role == "genesis" and (
                episode_index != 0 or encounter_payload["episode_start"] is not True
            ):
                _reject("episode-binding", "genesis does not begin at episode zero")
        else:
            expected_episode = (
                previous_episode_index + 1
                if encounter_payload["episode_start"]
                else previous_episode_index
            )
            if episode_index != expected_episode:
                _reject("episode-binding", "episode transition differs from boundary marker")
        previous_episode_index = episode_index
        query_id = _digest(encounter_payload["query_id"], "query-identity", "query")
        if query_id in observed_query_ids:
            _reject("query-identity", "query identity repeats")
        observed_query_ids.add(query_id)
        for item in batch[:7]:
            _same_context(
                item,
                case_id=case_id,
                lineage_id=lineage_id,
                branch_id=branch_id,
                encounter_index=index,
                episode_index=episode_index,
                code="encounter-binding",
            )
        encounter_parents = _parents(encounter, ("lineage", "consumer"), "encounter-binding")
        if encounter_parents != {"lineage": lineage["receipt_sha256"], "consumer": consumer["receipt_sha256"]}:
            _reject("encounter-binding", "encounter ancestry differs")
        query_payload = _exact(query["payload"], {"public_query", "public_query_sha256", "query_id"}, "query-schema", "query")
        public_query = _validate_public_query(query_payload["public_query"])
        if query_payload["query_id"] != query_id:
            _reject("query-identity", "query payload identity differs")
        if sha256_bytes(canonical_json(public_query)) != query_payload["public_query_sha256"]:
            _reject("query-identity", "public query digest differs")
        if public_query["query_id"] != query_id or public_query["episode_start"] is not encounter_payload["episode_start"]:
            _reject("query-identity", "public query does not bind encounter")
        if _parents(query, ("encounter",), "query-identity")["encounter"] != encounter["receipt_sha256"]:
            _reject("query-identity", "query does not descend from encounter")

        pre_payload = _exact(pre_state["payload"], {"consumer_receipt_sha256", "projection_receipt_sha256", "state_receipt_sha256"}, "pre-state-schema", "pre-state")
        pre_parents = _parents(pre_state, ("encounter", "state", "projection", "consumer"), "wrong-pre-state")
        expected_pre = {
            "encounter": encounter["receipt_sha256"],
            "state": state["receipt_sha256"],
            "projection": projection["receipt_sha256"],
            "consumer": consumer["receipt_sha256"],
        }
        if pre_parents != expected_pre or pre_payload != {
            "consumer_receipt_sha256": consumer["receipt_sha256"],
            "projection_receipt_sha256": projection["receipt_sha256"],
            "state_receipt_sha256": state["receipt_sha256"],
        }:
            _reject("wrong-pre-state", "pre-state ancestry differs")

        prediction_payload = _exact(prediction["payload"], {"prediction", "query_receipt_sha256", "sealed_before_outcome", "status"}, "prediction-schema", "prediction")
        if prediction_payload["status"] not in {"valid", "invalid", "missing", "timeout"}:
            _reject("prediction-schema", "prediction status is unavailable")
        if prediction_payload["status"] == "valid":
            if prediction_payload["prediction"] not in {0, 1}:
                _reject("prediction-schema", "valid prediction is not a bit")
        elif prediction_payload["prediction"] is not None:
            _reject("prediction-schema", "nonvalid prediction is not null")
        if prediction_payload["sealed_before_outcome"] is not True:
            _reject("prediction-after-outcome", "prediction was not sealed before outcome")
        if prediction_payload["query_receipt_sha256"] != query["receipt_sha256"]:
            _reject("query-identity", "prediction names a different query")
        expected_prediction_parents = {
            "query": query["receipt_sha256"],
            "pre-state": pre_state["receipt_sha256"],
            "consumer": consumer["receipt_sha256"],
        }
        if _parents(prediction, ("query", "pre-state", "consumer"), "prediction-after-outcome") != expected_prediction_parents:
            _reject("prediction-after-outcome", "prediction ancestry differs")

        outcome_payload = _exact(outcome["payload"], {"authority", "outcome", "prediction_receipt_sha256", "released_after_prediction", "world_event_sha256"}, "outcome-schema", "outcome")
        if outcome_payload["authority"] != "controller-world" or outcome_payload["outcome"] not in {0, 1} or outcome_payload["released_after_prediction"] is not True:
            _reject("outcome-authority", "outcome authority or timing differs")
        if outcome_payload["prediction_receipt_sha256"] != prediction["receipt_sha256"]:
            _reject("prediction-after-outcome", "outcome names a different prediction")
        expected_world = derive_identity("world-outcome", case_payload["task_sha256"], case_id, query_id, outcome_payload["outcome"])
        if outcome_payload["world_event_sha256"] != expected_world:
            _reject("outcome-authority", "world outcome identity differs")
        if _parents(outcome, ("prediction", "query"), "prediction-after-outcome") != {
            "prediction": prediction["receipt_sha256"], "query": query["receipt_sha256"]
        }:
            _reject("prediction-after-outcome", "outcome ancestry differs")

        update_payload = _exact(
            update["payload"],
            {
                "authoritative_pre_state_receipt_sha256",
                "authoritative_pre_state_sha256",
                "consequence_binding",
                "decision",
                "delivered_outcome",
                "outcome_receipt_sha256",
                "pre_state_receipt_sha256",
                "projection_mode",
                "update_payload",
            },
            "update-schema",
            "update",
        )
        if update_payload["decision"] not in {"update", "no-op"} or update_payload["consequence_binding"] not in {"current", "withheld", "one-step-stale"}:
            _reject("update-schema", "update decision or binding differs")
        if update_payload["consequence_binding"] == "current" and update_payload["delivered_outcome"] != outcome_payload["outcome"]:
            _reject("wrong-update-parent", "current update received a different consequence")
        if update_payload["consequence_binding"] == "withheld" and (update_payload["delivered_outcome"] is not None or update_payload["decision"] != "no-op"):
            _reject("wrong-update-parent", "withheld update is not an explicit no-op")
        if update_payload["consequence_binding"] == "one-step-stale" and update_payload["delivered_outcome"] not in {0, 1}:
            _reject("wrong-update-parent", "stale update does not carry a bit")
        if update_payload["consequence_binding"] == "one-step-stale":
            expected_stale = previous_outcome
            if expected_stale is None and encounter_start == 0:
                expected_stale = 0
            if expected_stale is not None and update_payload["delivered_outcome"] != expected_stale:
                _reject("wrong-update-parent", "stale update did not receive the prior outcome")
        if (
            update_payload["outcome_receipt_sha256"]
            != outcome["receipt_sha256"]
            or update_payload["pre_state_receipt_sha256"]
            != state["receipt_sha256"]
            or update_payload["authoritative_pre_state_receipt_sha256"]
            != state["receipt_sha256"]
            or update_payload["authoritative_pre_state_sha256"]
            != state["payload"]["blob"]["sha256"]
            or update_payload["projection_mode"] != projection_mode
        ):
            _reject("wrong-update-parent", "update payload ancestry differs")
        _digest(
            update_payload["authoritative_pre_state_sha256"],
            "wrong-update-parent",
            "authoritative updater pre-state",
        )
        consumed_authoritative_state = authoritative_state_bytes
        decode_blob(update_payload["update_payload"], limit=UPDATE_BYTE_LIMIT, label="update payload")
        if _parents(update, ("pre-state", "outcome", "prediction"), "wrong-update-parent") != {
            "pre-state": pre_state["receipt_sha256"],
            "outcome": outcome["receipt_sha256"],
            "prediction": prediction["receipt_sha256"],
        }:
            _reject("wrong-update-parent", "update receipt ancestry differs")

        post_payload = _exact(post_state["payload"], {"blob", "previous_state_sha256", "revision", "role"}, "state-schema", "post-state")
        if post_payload["role"] != "post" or post_payload["revision"] != state["payload"]["revision"] + 1 or post_payload["previous_state_sha256"] != state["receipt_sha256"]:
            _reject("wrong-post-state", "post-state parent or revision differs")
        post_bytes = decode_blob(post_payload["blob"], limit=STATE_BYTE_LIMIT, label="post-state")
        if update_payload["decision"] == "no-op" and post_bytes != decode_blob(state["payload"]["blob"], limit=STATE_BYTE_LIMIT, label="pre-state"):
            _reject("wrong-post-state", "no-op changed state bytes")
        if _parents(post_state, ("update", "pre-state"), "wrong-post-state") != {
            "update": update["receipt_sha256"], "pre-state": pre_state["receipt_sha256"]
        }:
            _reject("wrong-post-state", "post-state receipt ancestry differs")

        terminal = offset == encounter_count - 1
        target = None if terminal else index + 1
        usage = "terminal" if terminal else "next"
        expected_projection_context = _context(case_id, lineage_id, branch_id, target, None)
        if next_projection["context"] != expected_projection_context:
            if next_projection["context"].get("branch_id") != branch_id:
                _reject("sibling-branch-substitution", "next projection belongs to sibling branch")
            _reject("stale-projection", "next projection context differs")
        projection_payload = _exact(
            next_projection["payload"],
            {
                "blob",
                "projection_mode",
                "state_receipt_sha256",
                "target_encounter_index",
                "usage",
            },
            "projection-schema",
            "projection",
        )
        if (
            projection_payload["state_receipt_sha256"]
            != post_state["receipt_sha256"]
            or projection_payload["target_encounter_index"] != target
            or projection_payload["usage"] != usage
            or projection_payload["projection_mode"] != projection_mode
        ):
            _reject("stale-projection", "next projection does not bind exact post-state and target")
        inherited_projection_bytes = decode_blob(
            projection["payload"]["blob"],
            limit=PROJECTION_BYTE_LIMIT,
            label="inherited projection",
        )
        delivered_projection_bytes = decode_blob(
            projection_payload["blob"],
            limit=PROJECTION_BYTE_LIMIT,
            label="next projection",
        )
        if (
            update_payload["decision"] == "no-op"
            and delivered_projection_bytes != inherited_projection_bytes
        ):
            _reject("stale-projection", "no-op changed projection bytes")
        if (
            projection_mode == UPDATE_WITHOUT_PROJECTION
            and delivered_projection_bytes != frozen_actor_projection
        ):
            _reject(
                "stale-projection",
                "update-without-projection did not preserve the frozen actor projection",
            )
        if (
            projection_mode == POST_STATE_PROJECTION
            and delivered_projection_bytes != post_bytes
        ):
            _reject(
                "stale-projection",
                "ordinary projection differs from exact authoritative post-state bytes",
            )
        if _parents(next_projection, ("state",), "stale-projection")["state"] != post_state["receipt_sha256"]:
            _reject("stale-projection", "next projection ancestry differs")
        mode = "terminal-audit" if terminal else "prediction"
        _validate_consumer_node(next_consumer, next_projection, surface, target, mode, case_id, lineage_id, branch_id)
        _collect_consumer_ids(next_consumer, process_ids, workspace_ids)
        if prediction_payload["status"] != "valid" or prediction_payload["prediction"] != outcome_payload["outcome"]:
            errors += 1
        if update_payload["decision"] == "update":
            accepted_updates += 1
            if post_bytes != consumed_authoritative_state:
                candidate_state_changed = True
        if delivered_projection_bytes != inherited_projection_bytes:
            active_projection_changed = True
        if not terminal:
            consumed_projection_sha256s.append(projection_payload["blob"]["sha256"])
        else:
            terminal_projection_sha256 = projection_payload["blob"]["sha256"]
        authoritative_state_bytes = post_bytes
        previous_outcome = outcome_payload["outcome"]
        state, projection, consumer = post_state, next_projection, next_consumer

    if terminal_projection_sha256 is None:
        _reject("missing-terminal-consumer", "terminal projection digest is absent")
    if (
        projection_mode == UPDATE_WITHOUT_PROJECTION
        and not candidate_state_changed
    ):
        _reject(
            "wrong-post-state",
            "update-without-projection never advanced authoritative candidate state",
        )
    if len(consumed_projection_sha256s) != encounter_count:
        _reject(
            "dropped-prediction-or-denominator-change",
            "consumed projection count differs from prediction denominator",
        )

    summary = _exact(value["summary"], {"denominator", "errors"}, "denominator", "trace summary")
    if summary["denominator"] != encounter_count or summary["errors"] != errors:
        _reject("dropped-prediction-or-denominator-change", "summary denominator or errors differs from chain")
    if value["case_receipt_sha256"] != case["receipt_sha256"] or value["lineage_receipt_sha256"] != lineage["receipt_sha256"]:
        _reject("trace-identity", "trace roots differ")
    if value["terminal_audit_receipt_sha256"] != consumer["receipt_sha256"] or consumer["payload"]["mode"] != "terminal-audit":
        _reject("missing-terminal-consumer", "terminal projection lacks audit consumer")

    # Semantic and authority checks above intentionally precede content hashes so
    # seeded mutations receive their specific fail-closed disposition.
    identities: set[str] = set()
    for receipt in receipts:
        _check_hash(receipt)
        identity = receipt["receipt_sha256"]
        if identity in identities:
            _reject("duplicate-receipt", "receipt identity repeats")
        for parent in receipt["parents"]:
            if parent["receipt_sha256"] not in identities:
                _reject("receipt-ancestry", "receipt names a missing or future parent")
        identities.add(identity)
    body = {key: item for key, item in value.items() if key != "trace_sha256"}
    observed_trace = sha256_bytes(canonical_json(body))
    if observed_trace != value["trace_sha256"]:
        _reject("trace-identity", "trace canonical identity differs")
    return ChainValidation(
        case_id=case_id,
        lineage_id=lineage_id,
        branch_id=branch_id,
        encounter_start=encounter_start,
        encounter_count=encounter_count,
        errors=errors,
        authority_eligible=expected_eligible,
        projection_mode=projection_mode,
        accepted_updates=accepted_updates,
        candidate_state_changed=candidate_state_changed,
        active_projection_changed=active_projection_changed,
        consumed_projection_sha256s=tuple(consumed_projection_sha256s),
        terminal_projection_sha256=terminal_projection_sha256,
        terminal_audit_receipt_sha256=consumer["receipt_sha256"],
        trace_sha256=observed_trace,
    )


def validate_chain_collection(
    chains: Iterable[dict[str, Any]],
    *,
    online_admissible_trace_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Validate global reset identity across a set of independent lineages."""

    values = list(chains)
    if not values:
        _reject("chain-collection", "chain collection is empty")
    positive_ids = set(online_admissible_trace_ids)
    for identity in positive_ids:
        _digest(identity, "chain-collection", "positive trace")
    validations: list[ChainValidation] = []
    process_ids: set[str] = set()
    workspace_ids: set[str] = set()
    branch_keys: set[tuple[str, str, str]] = set()
    trace_ids: set[str] = set()
    for chain in values:
        trace_id = chain.get("trace_sha256") if type(chain) is dict else None
        validation = validate_chain(
            chain,
            require_online_admissible=trace_id in positive_ids,
        )
        if validation.trace_sha256 in trace_ids:
            _reject("chain-collection", "trace identity repeats")
        trace_ids.add(validation.trace_sha256)
        branch_key = (
            validation.case_id,
            validation.lineage_id,
            validation.branch_id,
        )
        if branch_key in branch_keys:
            _reject("chain-collection", "case/lineage/branch identity repeats")
        branch_keys.add(branch_key)
        for receipt in chain["receipt_order"]:
            if receipt["kind"] != "consumer":
                continue
            facts = receipt["payload"]["facts"]
            process_id = facts["process_instance_id"]
            workspace_id = facts["workspace_instance_id"]
            if process_id in process_ids or workspace_id in workspace_ids:
                _reject(
                    "fresh-consumer",
                    "process or workspace identity repeats across lineages",
                )
            process_ids.add(process_id)
            workspace_ids.add(workspace_id)
        validations.append(validation)
    if not positive_ids <= trace_ids:
        _reject("chain-collection", "positive trace identity is absent")
    body = {
        "case_count": len({item.case_id for item in validations}),
        "chain_count": len(validations),
        "encounter_count": sum(item.encounter_count for item in validations),
        "fresh_consumer_count": len(process_ids),
        "trace_sha256s": sorted(trace_ids),
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def _validate_consumer_node(
    consumer: dict[str, Any],
    projection: dict[str, Any],
    surface: dict[str, Any],
    target: int | None,
    mode: str,
    case_id: str,
    lineage_id: str,
    branch_id: str,
) -> None:
    expected_context = _context(case_id, lineage_id, branch_id, target, None)
    if consumer["context"] != expected_context:
        if consumer["context"].get("branch_id") != branch_id:
            _reject("sibling-branch-substitution", "consumer belongs to sibling branch")
        _reject("fresh-consumer", "consumer context differs")
    payload = _exact(
        consumer["payload"],
        {"facts", "mode", "projection_receipt_sha256", "surface_receipt_sha256", "target_encounter_index"},
        "fresh-consumer-schema",
        "consumer",
    )
    if payload["mode"] != mode or payload["target_encounter_index"] != target:
        _reject("missing-terminal-consumer" if mode == "terminal-audit" else "fresh-consumer", "consumer target or mode differs")
    if payload["projection_receipt_sha256"] != projection["receipt_sha256"] or payload["surface_receipt_sha256"] != surface["receipt_sha256"]:
        _reject("stale-projection", "consumer did not receive exact projection/surface")
    if _parents(consumer, ("projection", "reachable-surface"), "fresh-consumer") != {
        "projection": projection["receipt_sha256"],
        "reachable-surface": surface["receipt_sha256"],
    }:
        _reject("stale-projection", "consumer ancestry differs")
    _validate_consumer_facts(payload["facts"])


def _collect_consumer_ids(
    consumer: dict[str, Any], process_ids: set[str], workspace_ids: set[str]
) -> None:
    facts = consumer["payload"]["facts"]
    process = facts["process_instance_id"]
    workspace = facts["workspace_instance_id"]
    if process in process_ids or workspace in workspace_ids:
        _reject("fresh-consumer", "process or workspace identity was reused")
    process_ids.add(process)
    workspace_ids.add(workspace)


def encounter_bundle(chain: dict[str, Any], encounter_index: int) -> list[dict[str, Any]]:
    validation = validate_chain(chain)
    if (
        type(encounter_index) is not int
        or not validation.encounter_start
        <= encounter_index
        < validation.encounter_start + validation.encounter_count
    ):
        raise ValueError("encounter index is outside the chain")
    start = 6 + 9 * (encounter_index - validation.encounter_start)
    return copy.deepcopy(chain["receipt_order"][start : start + 9])


def checkpoint(chain: dict[str, Any], encounter_index: int) -> dict[str, Any]:
    """Return the exact post-state and projection identities/bytes at a checkpoint."""

    batch = encounter_bundle(chain, encounter_index)
    state = batch[6]
    projection = batch[7]
    return {
        "branch_id": state["context"]["branch_id"],
        "encounter_index": encounter_index,
        "projection": copy.deepcopy(projection["payload"]["blob"]),
        "projection_receipt_sha256": projection["receipt_sha256"],
        "state": copy.deepcopy(state["payload"]["blob"]),
        "state_receipt_sha256": state["receipt_sha256"],
    }


def chain_causal_evidence(chain: dict[str, Any]) -> dict[str, Any]:
    """Export the exact five scorer-visible OT-0076 causal trace facts.

    The projection digests identify bytes delivered to prediction consumers,
    not the separately advancing authoritative updater state.  This makes an
    update-without-projection trace directly comparable with its matched-frozen
    baseline without granting aggregate summaries ancestry authority.
    """

    validation = validate_chain(chain)
    return {
        "accepted_updates": validation.accepted_updates,
        "active_projection_changed": validation.active_projection_changed,
        "candidate_state_changed": validation.candidate_state_changed,
        "consumed_projection_sha256s": list(
            validation.consumed_projection_sha256s
        ),
        "terminal_projection_sha256": validation.terminal_projection_sha256,
    }


def authoritative_update_ancestry(chain: dict[str, Any]) -> dict[str, Any]:
    """Expose exact state-parent evidence without merging it into actor state.

    Full validation runs first.  Each row therefore proves that the named
    updater input bytes equal the immediately prior authoritative state receipt
    and that the candidate post-state descends from that update.  The actor
    projection digest is reported separately.
    """

    validation = validate_chain(chain)
    updates: list[dict[str, Any]] = []
    for offset in range(validation.encounter_count):
        base = 6 + 9 * offset
        update = chain["receipt_order"][base + 5]
        post_state = chain["receipt_order"][base + 6]
        projection = chain["receipt_order"][base + 7]
        payload = update["payload"]
        updates.append(
            {
                "authoritative_pre_state_receipt_sha256": payload[
                    "authoritative_pre_state_receipt_sha256"
                ],
                "authoritative_pre_state_sha256": payload[
                    "authoritative_pre_state_sha256"
                ],
                "candidate_post_state_receipt_sha256": post_state[
                    "receipt_sha256"
                ],
                "candidate_post_state_sha256": post_state["payload"]["blob"][
                    "sha256"
                ],
                "delivered_projection_sha256": projection["payload"]["blob"][
                    "sha256"
                ],
                "encounter_index": update["context"]["encounter_index"],
                "update_decision": payload["decision"],
            }
        )
    return {
        "projection_mode": validation.projection_mode,
        "trace_sha256": validation.trace_sha256,
        "updates": updates,
    }


def projection_trace_equal(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    """Compare all prediction-consumed and terminal delivered projection bytes."""

    left_evidence = chain_causal_evidence(left)
    right_evidence = chain_causal_evidence(right)
    return (
        left_evidence["consumed_projection_sha256s"]
        == right_evidence["consumed_projection_sha256s"]
        and left_evidence["terminal_projection_sha256"]
        == right_evidence["terminal_projection_sha256"]
    )


def validate_rewind_replay(
    original: dict[str, Any], replay: dict[str, Any], *, checkpoint_index: int
) -> dict[str, Any]:
    """Require a deterministic rewind to reproduce the same suffix bytes exactly."""

    left = validate_chain(original)
    right = validate_chain(replay)
    if left.case_id != right.case_id or left.lineage_id != right.lineage_id or left.branch_id != right.branch_id:
        _reject("rewind-replay", "replay identity differs")
    if (
        not left.encounter_start
        <= checkpoint_index
        < left.encounter_start + left.encounter_count
        or left.encounter_start != right.encounter_start
        or left.encounter_count != right.encounter_count
    ):
        _reject("rewind-replay", "checkpoint or horizon differs")
    start = 6 + 9 * (checkpoint_index - left.encounter_start)
    left_bytes = canonical_json(original["receipt_order"][start:])
    right_bytes = canonical_json(replay["receipt_order"][start:])
    if left_bytes != right_bytes:
        _reject("rewind-replay", "same suffix did not reproduce byte-exactly")
    body = {
        "checkpoint_index": checkpoint_index,
        "original_trace_sha256": left.trace_sha256,
        "replay_trace_sha256": right.trace_sha256,
        "suffix_sha256": sha256_bytes(left_bytes),
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def causal_path_gates(
    chain: dict[str, Any], *, require_online_admissible: bool = False
) -> dict[str, bool]:
    """Return the nine exact scorer-visible causal gates after full validation."""

    validate_chain(chain, require_online_admissible=require_online_admissible)
    return {
        "prediction_precedes_outcome": True,
        "outcome_descends_from_exact_prediction": True,
        "update_descends_from_outcome_and_pre_state": True,
        "next_projection_binds_exact_post_state_or_declared_update_without_projection_cut": True,
        "next_fresh_process_consumes_exact_projection": True,
        "terminal_projection_has_audit_consumer": True,
        "fresh_process_workspace_receipts": True,
        "forbidden_continuity_channel_sentinels": True,
        "online_reference_reachable_surface_audit": True,
    }


def validate_branch_isolation(
    parent: dict[str, Any],
    rewind_branch: dict[str, Any],
    alternate_branch: dict[str, Any],
    *,
    checkpoint_index: int,
) -> dict[str, Any]:
    """Validate common-parent forks, sibling isolation, and substitution rejection."""

    parent_validation = validate_chain(parent)
    rewind_validation = validate_chain(rewind_branch)
    alternate_validation = validate_chain(alternate_branch)
    if (
        not parent_validation.encounter_start
        <= checkpoint_index
        < parent_validation.encounter_start + parent_validation.encounter_count
    ):
        _reject("branch-isolation", "checkpoint is outside parent")
    if {parent_validation.case_id, rewind_validation.case_id, alternate_validation.case_id} != {parent_validation.case_id}:
        _reject("branch-isolation", "fork cases differ")
    if {parent_validation.lineage_id, rewind_validation.lineage_id, alternate_validation.lineage_id} != {parent_validation.lineage_id}:
        _reject("branch-isolation", "fork lineages differ")
    parent_case_receipt = parent["case_receipt_sha256"]
    if (
        rewind_branch["case_receipt_sha256"] != parent_case_receipt
        or alternate_branch["case_receipt_sha256"] != parent_case_receipt
    ):
        _reject("branch-isolation", "forks do not retain exact case identity")
    expected_start = checkpoint_index + 1
    if (
        rewind_validation.encounter_start != expected_start
        or alternate_validation.encounter_start != expected_start
    ):
        _reject("branch-isolation", "fork suffix does not preserve absolute encounter index")
    if len({parent_validation.branch_id, rewind_validation.branch_id, alternate_validation.branch_id}) != 3:
        _reject("branch-isolation", "fork branch identities are not distinct")
    parent_point = checkpoint(parent, checkpoint_index)
    children = (rewind_branch, alternate_branch)
    roles = ("rewind-replay", "alternate")
    for child, role in zip(children, roles, strict=True):
        lineage = child["receipt_order"][2]["payload"]
        if lineage["branch_role"] != role:
            _reject("branch-isolation", f"{role} branch role differs")
        if lineage["fork_parent_state_sha256"] != parent_point["state_receipt_sha256"] or lineage["fork_parent_projection_sha256"] != parent_point["projection_receipt_sha256"]:
            _reject("branch-isolation", f"{role} fork parent differs")
        child_state = child["receipt_order"][3]["payload"]["blob"]
        child_projection = child["receipt_order"][4]["payload"]["blob"]
        if child_state != parent_point["state"] or child_projection != parent_point["projection"]:
            _reject("branch-isolation", f"{role} did not fork exact checkpoint bytes")
    # A later valid sibling projection is structurally valid in its own trace,
    # but its branch context must be inadmissible to the active branch.
    donor_projection = alternate_branch["receipt_order"][6 + 7]
    active_branch_id = rewind_validation.branch_id
    if donor_projection["context"]["branch_id"] == active_branch_id:
        _reject("branch-isolation", "sibling projection lost branch distinction")
    body = {
        "active_trace_sha256": rewind_validation.trace_sha256,
        "alternate_trace_sha256": alternate_validation.trace_sha256,
        "checkpoint_index": checkpoint_index,
        "fork_projection_sha256": parent_point["projection_receipt_sha256"],
        "fork_state_sha256": parent_point["state_receipt_sha256"],
        "parent_trace_sha256": parent_validation.trace_sha256,
        "sibling_projection_rejected": True,
    }
    return {**body, "receipt_sha256": sha256_bytes(canonical_json(body))}


def rollback_gates(
    parent: dict[str, Any],
    parent_replay: dict[str, Any],
    rewind_branch: dict[str, Any],
    alternate_branch: dict[str, Any],
    *,
    checkpoint_index: int,
) -> dict[str, bool]:
    """Return the five exact scorer-visible rewind and isolation gates."""

    validate_rewind_replay(parent, parent_replay, checkpoint_index=checkpoint_index)
    active_before = canonical_json(rewind_branch)
    validate_branch_isolation(
        parent,
        rewind_branch,
        alternate_branch,
        checkpoint_index=checkpoint_index,
    )
    validate_chain(alternate_branch)
    inactive_sibling_isolated = canonical_json(rewind_branch) == active_before
    mutant = copy.deepcopy(rewind_branch)
    active_projection_offset = 6 + 7
    donor_projection_offset = 6 + 7
    mutant["receipt_order"][active_projection_offset] = copy.deepcopy(
        alternate_branch["receipt_order"][donor_projection_offset]
    )
    substitution_rejected = False
    try:
        validate_chain(mutant)
    except ReceiptError as error:
        substitution_rejected = error.code == "sibling-branch-substitution"
    return {
        "rewind_to_checkpoint": True,
        "same_suffix_byte_exact_replay": True,
        "alternate_suffix_branch_isolated": True,
        "inactive_sibling_cannot_affect_active_projection": inactive_sibling_isolated,
        "cross_branch_substitution_rejected": substitution_rejected,
    }


def mutate_seeded_defect(
    chain: dict[str, Any],
    defect: str,
    *,
    donor_chain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one well-localized P-frozen negative mutation.

    Mutations intentionally retain stale content identities.  Semantic checks
    run before digest checks, yielding the named causal rejection rather than a
    generic hash mismatch; either path is fail-closed.
    """

    if defect not in SEEDED_AUTHORITY_DEFECTS:
        raise ValueError("seeded OT-0076 authority defect is unavailable")
    value = copy.deepcopy(chain)
    receipts = value["receipt_order"]
    if len(receipts) < 24:
        raise ValueError("seeded mutations require at least two encounters")
    first = 6
    second = 15
    lineage = receipts[2]
    surface = receipts[1]
    if defect == "future-outcome-access":
        surface["payload"] = surface_with_extra_input(phase="prediction", input_name="future-outcomes")
        lineage["payload"]["authority_eligible"] = False
    elif defect == "hidden-schedule-access":
        surface["payload"] = surface_with_extra_input(phase="prediction", input_name="hidden-schedule")
        lineage["payload"]["authority_eligible"] = False
    elif defect == "prediction-after-outcome":
        receipts[first + 3], receipts[first + 4] = receipts[first + 4], receipts[first + 3]
    elif defect == "reference-label-on-negative-lineage":
        lineage["payload"]["lineage_class"] = "authority-negative"
        lineage["payload"]["authority_eligible"] = False
        lineage["payload"]["display_label"] = "online positive reference"
    elif defect == "wrong-pre-state":
        receipts[second + 2]["payload"]["state_receipt_sha256"] = "0" * 64
    elif defect == "wrong-post-state":
        receipts[first + 6]["payload"]["previous_state_sha256"] = "0" * 64
    elif defect == "wrong-update-parent":
        receipts[first + 5]["payload"]["pre_state_receipt_sha256"] = "0" * 64
    elif defect == "cross-case-state":
        receipts[first + 6]["context"]["case_id"] = derive_identity("mutant-case")
    elif defect == "cross-lineage-prediction":
        receipts[first + 3]["context"]["lineage_id"] = derive_identity("mutant-lineage")
    elif defect == "cross-episode-outcome":
        receipts[first + 4]["context"]["episode_index"] += 1
    elif defect == "stale-projection":
        receipts[second + 7]["payload"]["state_receipt_sha256"] = receipts[3]["receipt_sha256"]
    elif defect == "skipped-encounter":
        receipts[second]["payload"]["encounter_index"] += 1
    elif defect == "duplicate-encounter":
        receipts[second]["payload"]["encounter_index"] = 0
    elif defect == "reordered-suffix":
        receipts[first : first + 9], receipts[second : second + 9] = (
            receipts[second : second + 9],
            receipts[first : first + 9],
        )
    elif defect == "sibling-branch-substitution":
        if donor_chain is None:
            receipts[second + 7]["context"]["branch_id"] = derive_identity("sibling")
        else:
            validate_chain(donor_chain)
            receipts[second + 7] = copy.deepcopy(donor_chain["receipt_order"][second + 7])
    elif defect == "missing-terminal-consumer":
        receipts.pop()
    elif defect == "favorable-summary-without-chain":
        value["receipt_order"] = []
        value["summary"] = {"denominator": value["encounter_count"], "errors": 0}
    elif defect == "dropped-prediction-or-denominator-change":
        receipts.pop(first + 3)
        value["summary"]["denominator"] -= 1
    elif defect == "over-budget-state-or-projection":
        raw = b"x" * (PROJECTION_BYTE_LIMIT + 1)
        receipts[second + 7]["payload"]["blob"] = {
            "base64": base64.b64encode(raw).decode("ascii"),
            "byte_count": len(raw),
            "sha256": sha256_bytes(raw),
        }
    return value


def expected_mutation_code(defect: str) -> str:
    mapping = {
        "future-outcome-access": "future-outcome-access",
        "hidden-schedule-access": "hidden-schedule-access",
        "prediction-after-outcome": "prediction-after-outcome",
        "reference-label-on-negative-lineage": "reference-label-on-negative-lineage",
        "wrong-pre-state": "wrong-pre-state",
        "wrong-post-state": "wrong-post-state",
        "wrong-update-parent": "wrong-update-parent",
        "cross-case-state": "cross-case-state",
        "cross-lineage-prediction": "cross-lineage-prediction",
        "cross-episode-outcome": "cross-episode-outcome",
        "stale-projection": "stale-projection",
        "skipped-encounter": "skipped-encounter",
        "duplicate-encounter": "duplicate-encounter",
        "reordered-suffix": "reordered-suffix",
        "sibling-branch-substitution": "sibling-branch-substitution",
        "missing-terminal-consumer": "missing-terminal-consumer",
        "favorable-summary-without-chain": "favorable-summary-without-chain",
        "dropped-prediction-or-denominator-change": "dropped-prediction-or-denominator-change",
        "over-budget-state-or-projection": "over-budget-state-or-projection",
    }
    try:
        return mapping[defect]
    except KeyError as error:
        raise ValueError("seeded OT-0076 authority defect is unavailable") from error


def seeded_authority_defect_gates(
    chain: dict[str, Any], *, donor_chain: dict[str, Any] | None = None
) -> dict[str, bool]:
    """Execute all nineteen frozen authority mutations for scorer consumption."""

    validate_chain(chain, require_online_admissible=True)
    if donor_chain is not None:
        validate_chain(donor_chain)
    gates: dict[str, bool] = {}
    for defect in SEEDED_AUTHORITY_DEFECTS:
        mutant = mutate_seeded_defect(chain, defect, donor_chain=donor_chain)
        try:
            validate_chain(mutant, require_online_admissible=True)
        except ReceiptError as error:
            gates[defect] = error.code == expected_mutation_code(defect)
        else:
            gates[defect] = False
    return gates
