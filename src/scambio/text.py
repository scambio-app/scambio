# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Plain display text at external-data boundaries; identifiers stay untouched."""

import logging
import re

_CONTROLS = re.compile(
    "[\x00-\x1f\x7f-\x9f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]"
)


def display_text(value: object, limit: int = 64) -> str:
    text = _CONTROLS.sub("", str(value))
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ExternalTextFilter(logging.Filter):
    """Sanitize interpolated data, keeping fixed diagnostic messages readable."""

    def filter(self, record: logging.LogRecord) -> bool:
        def clean(value: object) -> object:
            return display_text(value) if isinstance(value, (str, Exception)) else value

        if isinstance(record.args, dict):
            record.args = {key: clean(value) for key, value in record.args.items()}
        elif record.args:
            record.args = tuple(clean(value) for value in record.args)
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = display_text(record.exc_info[1])
        return True


def logger(name: str) -> logging.Logger:
    result = logging.getLogger(name)
    if not any(isinstance(item, ExternalTextFilter) for item in result.filters):
        result.addFilter(ExternalTextFilter())
    return result
