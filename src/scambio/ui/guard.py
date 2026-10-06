"""Exception boundaries for callbacks invoked by Gio/GLib."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

LOG = logging.getLogger("scambio.ui")


def guarded(callback: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(callback)
    def safe(*args: Any, **kwargs: Any) -> Any:
        try:
            return callback(*args, **kwargs)
        except Exception:
            LOG.exception("UI callback failed: %s", callback.__qualname__)
            return None

    return safe
