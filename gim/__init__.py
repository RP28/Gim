from __future__ import annotations

from typing import Any

__version__ = "0.1.0"
__all__ = ["run", "__version__"]


def run(*sources: Any, start_event_loop: bool = True):  # type: ignore[no-untyped-def]
    """Lazy public entry point; see :func:`gim.app.run`."""
    from .app import run as _run

    return _run(*sources, start_event_loop=start_event_loop)
