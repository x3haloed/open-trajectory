"""Thin, content-addressed trajectory storage.

The store deliberately knows only records, causal parent identities, append
channel provenance, and exact address-selected projection.  Procedural meaning
belongs to callers such as the OT-0070 authority calibration.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
from collections.abc import Iterable, Mapping
from types import MappingProxyType
from typing import Any, Final

MAX_RECORD_BYTES: Final = 4096
PROJECTION_BYTE_LIMIT: Final = 2048
PROJECTION_SCHEMA_VERSION: Final = 1

ACTOR_SOURCE: Final = "actor-channel"
WORLD_SOURCE: Final = "world-channel"
CONTROLLER_SOURCE: Final = "controller-channel"

_RECORD_ID = re.compile(r"[0-9a-f]{64}")
_CAPABILITY_CONSTRUCTION_KEY = object()
_CAPABILITY_INSPECTION_KEY = object()
_STORE_BOOTSTRAP_KEY = object()


def canonical_json(value: Any) -> bytes:
    """Encode an ordinary JSON value with stable byte identity."""

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 identity of bytes."""

    return hashlib.sha256(value).hexdigest()


class _ChannelCapability:
    """An opaque, store-local append authority.

    The capability contains no serializable source label.  A store retains
    only a one-way proof identity, never this object or its secret proof.
    """

    __slots__ = ("__proof",)

    def __init__(self, construction_key: object, proof: bytes) -> None:
        if construction_key is not _CAPABILITY_CONSTRUCTION_KEY:
            raise TypeError("channel capabilities are issued only at bootstrap")
        if type(proof) is not bytes or len(proof) != 32:
            raise TypeError("channel capability proof is invalid")
        object.__setattr__(self, "_ChannelCapability__proof", proof)

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("channel capabilities are immutable")

    def _proof_for_store(self, inspection_key: object) -> bytes:
        if inspection_key is not _CAPABILITY_INSPECTION_KEY:
            raise PermissionError("channel capability proof is opaque")
        return self.__proof

    def __reduce__(self) -> object:
        raise TypeError("channel capabilities are not serializable")

    def __copy__(self) -> object:
        raise TypeError("channel capabilities are not copyable")

    def __deepcopy__(self, memo: dict[int, object]) -> object:
        del memo
        raise TypeError("channel capabilities are not copyable")

    def __repr__(self) -> str:
        return "<trajectory channel capability>"


def _capability_identity(capability: object) -> str:
    if type(capability) is not _ChannelCapability:
        raise PermissionError(
            "append capability was not issued by this trajectory store"
        )
    return sha256_bytes(capability._proof_for_store(_CAPABILITY_INSPECTION_KEY))


def _validate_json(value: Any, active_containers: set[int] | None = None) -> None:
    """Require an ordinary finite JSON value without silently coercing it."""

    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("trajectory payload contains a non-finite number")
        return
    if type(value) not in {dict, list}:
        raise TypeError("trajectory payload contains a non-JSON value")

    if active_containers is None:
        active_containers = set()
    marker = id(value)
    if marker in active_containers:
        raise ValueError("trajectory payload contains a cycle")
    active_containers.add(marker)
    try:
        if type(value) is list:
            for item in value:
                _validate_json(item, active_containers)
            return
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("trajectory payload object keys must be strings")
            _validate_json(item, active_containers)
    finally:
        active_containers.remove(marker)


def _json_copy(value: Any) -> Any:
    """Copy through the frozen canonical representation."""

    _validate_json(value)
    return json.loads(canonical_json(value))


def _checked_record_id(record_id: object) -> str:
    if type(record_id) is not str or _RECORD_ID.fullmatch(record_id) is None:
        raise ValueError("record identity must be a lowercase SHA-256 digest")
    return record_id


def _checked_limit(value: object, *, maximum: int, label: str) -> int:
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{label} must be between 1 and {maximum} bytes")
    return value


class TrajectoryStore:
    """An in-memory immutable record store with exact bounded projection."""

    __slots__ = (
        "__append_authority_sources",
        "__max_record_bytes",
        "__record_bytes",
    )

    def __init__(
        self,
        *,
        _bootstrap_key: object | None = None,
        _append_authority_sources: Mapping[str, str] | None = None,
        max_record_bytes: int = MAX_RECORD_BYTES,
    ) -> None:
        if (
            _bootstrap_key is not _STORE_BOOTSTRAP_KEY
            or _append_authority_sources is None
        ):
            raise TypeError("use bootstrap_trajectory_store to create a store")
        object.__setattr__(
            self,
            "_TrajectoryStore__max_record_bytes",
            _checked_limit(
                max_record_bytes,
                maximum=MAX_RECORD_BYTES,
                label="record limit",
            ),
        )
        object.__setattr__(
            self,
            "_TrajectoryStore__append_authority_sources",
            MappingProxyType(dict(_append_authority_sources)),
        )
        object.__setattr__(self, "_TrajectoryStore__record_bytes", {})

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("trajectory store configuration is immutable")

    @property
    def record_ids(self) -> tuple[str, ...]:
        """Return identities in canonical order, independent of append order."""

        return tuple(sorted(self.__record_bytes))

    def __len__(self) -> int:
        return len(self.__record_bytes)

    def append(
        self,
        capability: object,
        payload: dict[str, Any],
        parents: Iterable[str] = (),
    ) -> str:
        """Append one canonical record and return its content identity.

        Exact duplicates are idempotent.  No source-string alternative exists:
        source provenance is derived solely from a capability issued by this
        store.
        """

        capability_identity = _capability_identity(capability)
        try:
            source = self.__append_authority_sources[capability_identity]
        except KeyError as error:
            raise PermissionError(
                "append capability was not issued by this trajectory store"
            ) from error

        if type(payload) is not dict:
            raise TypeError("trajectory payload must be a JSON object")
        if isinstance(parents, (str, bytes)):
            raise TypeError("parents must be an iterable of record identities")
        try:
            parent_values = tuple(parents)
        except TypeError as error:
            raise TypeError(
                "parents must be an iterable of record identities"
            ) from error

        canonical_parents = sorted(
            {_checked_record_id(parent) for parent in parent_values}
        )
        missing = [
            parent for parent in canonical_parents if parent not in self.__record_bytes
        ]
        if missing:
            raise KeyError(f"trajectory parent does not exist: {missing[0]}")

        try:
            copied_payload = _json_copy(payload)
        except RecursionError as error:
            raise ValueError("trajectory payload is nested too deeply") from error
        record = {
            "source": source,
            "parents": canonical_parents,
            "payload": copied_payload,
        }
        encoded = canonical_json(record)
        if len(encoded) > self.__max_record_bytes:
            raise ValueError(
                f"trajectory record exceeds {self.__max_record_bytes} canonical bytes"
            )
        record_id = sha256_bytes(encoded)
        existing = self.__record_bytes.get(record_id)
        if existing is not None and existing != encoded:
            raise RuntimeError("distinct trajectory records share one identity")
        self.__record_bytes.setdefault(record_id, encoded)
        return record_id

    def get(self, record_id: str) -> dict[str, Any]:
        """Return a detached copy of one record, failing closed if absent."""

        checked = _checked_record_id(record_id)
        try:
            encoded = self.__record_bytes[checked]
        except KeyError as error:
            raise KeyError(f"trajectory record does not exist: {checked}") from error
        value = json.loads(encoded)
        if type(value) is not dict:  # Internal invariant, retained fail-closed.
            raise RuntimeError("stored trajectory record is not an object")
        return value

    def project(
        self,
        record_ids: Iterable[str],
        *,
        byte_limit: int = PROJECTION_BYTE_LIMIT,
    ) -> dict[str, Any]:
        """Return the exact caller-addressed projection within the byte limit."""

        projection, encoded = self._bounded_projection(record_ids, byte_limit)
        del encoded
        return projection

    def serialize_projection(
        self,
        record_ids: Iterable[str],
        *,
        byte_limit: int = PROJECTION_BYTE_LIMIT,
    ) -> bytes:
        """Serialize the exact caller-addressed projection canonically."""

        _, encoded = self._bounded_projection(record_ids, byte_limit)
        return encoded

    def full_projection(self) -> dict[str, Any]:
        """Return the full trajectory in projection schema without a budget."""

        return self._projection(self.record_ids)

    def serialize_full(self) -> bytes:
        """Serialize the full trajectory before projection-budget enforcement."""

        return canonical_json(self.full_projection())

    def _bounded_projection(
        self,
        record_ids: Iterable[str],
        byte_limit: int,
    ) -> tuple[dict[str, Any], bytes]:
        checked_limit = _checked_limit(
            byte_limit,
            maximum=PROJECTION_BYTE_LIMIT,
            label="projection limit",
        )
        projection = self._projection(record_ids)
        encoded = canonical_json(projection)
        if len(encoded) > checked_limit:
            raise ValueError(
                f"trajectory projection exceeds {checked_limit} canonical bytes"
            )
        return projection, encoded

    def _projection(self, record_ids: Iterable[str]) -> dict[str, Any]:
        if isinstance(record_ids, (str, bytes)):
            raise TypeError("record_ids must be an iterable of identities")
        try:
            requested = tuple(record_ids)
        except TypeError as error:
            raise TypeError(
                "record_ids must be an iterable of identities"
            ) from error
        selected_ids = sorted({_checked_record_id(item) for item in requested})
        missing = [item for item in selected_ids if item not in self.__record_bytes]
        if missing:
            raise KeyError(f"trajectory record does not exist: {missing[0]}")

        records = [
            {"record_id": record_id, "record": self.get(record_id)}
            for record_id in selected_ids
        ]
        selected = set(selected_ids)
        external_parents = sorted(
            {
                parent
                for entry in records
                for parent in entry["record"]["parents"]
                if parent not in selected
            }
        )
        return {
            "schema_version": PROJECTION_SCHEMA_VERSION,
            "record_ids": selected_ids,
            "records": records,
            "external_parents": external_parents,
        }


def bootstrap_trajectory_store(
    *,
    max_record_bytes: int = MAX_RECORD_BYTES,
) -> tuple[TrajectoryStore, object, object, object]:
    """Issue one store and its three capabilities to initial wiring code.

    The tuple order is store, actor-channel capability, world-channel
    capability, and controller-channel capability.  The store retains only
    proof digests, so none of the capability objects can be recovered from it.
    """

    actor_capability = _ChannelCapability(
        _CAPABILITY_CONSTRUCTION_KEY, secrets.token_bytes(32)
    )
    world_capability = _ChannelCapability(
        _CAPABILITY_CONSTRUCTION_KEY, secrets.token_bytes(32)
    )
    controller_capability = _ChannelCapability(
        _CAPABILITY_CONSTRUCTION_KEY, secrets.token_bytes(32)
    )
    authority_sources = {
        _capability_identity(actor_capability): ACTOR_SOURCE,
        _capability_identity(world_capability): WORLD_SOURCE,
        _capability_identity(controller_capability): CONTROLLER_SOURCE,
    }
    store = TrajectoryStore(
        _bootstrap_key=_STORE_BOOTSTRAP_KEY,
        _append_authority_sources=authority_sources,
        max_record_bytes=max_record_bytes,
    )
    return (
        store,
        actor_capability,
        world_capability,
        controller_capability,
    )
