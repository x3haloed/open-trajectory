"""Backend-independent encounter harness primitives for Open Trajectory."""

from __future__ import annotations

from typing import Any

__all__ = ["AppServerClient", "AppServerError"]


def __getattr__(name: str) -> Any:
    """Preserve public exports without loading hosted-backend authority eagerly."""

    if name in __all__:
        from .app_server import AppServerClient, AppServerError

        return {
            "AppServerClient": AppServerClient,
            "AppServerError": AppServerError,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
