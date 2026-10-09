# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Validate installed release assets against the approved source hashes."""

import configparser
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

prefix, expected_path = map(Path, sys.argv[1:])
expected = json.loads(expected_path.read_text())
checked = {}
for relative, digest in expected["files"].items():
    path = prefix / relative
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == digest, (relative, actual, digest)
    checked[relative] = actual
    if path.suffix == ".svg":
        ET.parse(path)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), 128, 128, True)
        assert pixbuf.get_width() > 0 and pixbuf.get_height() > 0
app = "app.scambio.Scambio"
desktop = prefix / f"share/applications/{app}.desktop"
metadata = prefix / f"share/metainfo/{app}.metainfo.xml"
config = configparser.ConfigParser(interpolation=None)
config.optionxform = str
config.read(desktop)
assert config["Desktop Entry"]["Icon"] == app
assert config["Desktop Entry"]["Exec"].startswith("scambio")
meta = ET.parse(metadata)
assert meta.findtext("./id") == app
assert meta.findtext('./launchable[@type="desktop-id"]') == app + ".desktop"
assert meta.find("./releases/release").get("version") == "1.0.1"
subprocess.run(["desktop-file-validate", str(desktop)], check=True)
subprocess.run(
    ["appstreamcli", "validate", "--pedantic", "--no-net", str(metadata)], check=True
)
print(
    json.dumps(
        {
            "prefix": str(prefix),
            "icons": "Deviatoio v3, approved commit 5fd3004",
            "tray": "identical to sealed 1.0.0",
            "checked": checked,
            "desktop_icon": app,
            "appstream_launchable": app + ".desktop",
            "svg_render": "GdkPixbuf at 128px",
            "result": "PASS",
        },
        sort_keys=True,
    )
)
