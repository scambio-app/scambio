# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Exception boundaries for callbacks invoked by Gio/GLib."""

from collections.abc import Callable
from functools import wraps
from typing import Any

from scambio.text import logger

LOG = logger("scambio.ui")


def guarded(callback: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(callback)
    def safe(*args: Any, **kwargs: Any) -> Any:
        try:
            return callback(*args, **kwargs)
        except Exception:
            LOG.exception("UI callback failed: %s", callback.__qualname__)
            return None

    return safe
