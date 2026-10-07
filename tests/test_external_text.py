# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl

from scambio.text import display_text


def test_logs_sanitize_external_values_and_exceptions(caplog):
    from scambio.text import logger

    log = logger("scambio.external-test")
    log.warning("External: %s", "\x1b\u202e" + "x" * 100)
    assert caplog.records[-1].getMessage() == "External: " + "x" * 63 + "…"
    try:
        raise ValueError("\x1b\u202e" + "y" * 100)
    except ValueError:
        log.exception("Operation failed")
    assert caplog.records[-1].exc_text == "y" * 63 + "…"


def test_display_text_removes_control_and_direction_characters():
    malicious = "Head\n\r\t\x1b\x7f\x85\u202e\u2066\u200f\u061cset"
    assert display_text(malicious) == "Headset"


def test_display_text_keeps_unicode_and_leaves_escaping_to_surface():
    assert display_text("Cuffie & <occhiali> — äé 👓") == "Cuffie & <occhiali> — äé 👓"
    assert display_text("x" * 64) == "x" * 64
    assert display_text("x" * 65) == "x" * 63 + "…"
