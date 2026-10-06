"""The bounded GTK/Qt/XDG key vocabulary, without importing GTK."""

import re
from dataclasses import dataclass

MODIFIERS = (
    (0x10000000, "Super", "LOGO", "Meta"),
    (0x04000000, "Control", "CTRL", "Ctrl"),
    (0x08000000, "Alt", "ALT", "Alt"),
    (0x02000000, "Shift", "SHIFT", "Shift"),
)
ALIASES = {"meta": "super", "primary": "control", "ctrl": "control"}
KEYS = {chr(n).lower(): n for n in range(65, 91)}
KEYS.update({str(n): ord(str(n)) for n in range(10)})
KEYS.update({f"f{n}": 0x0100002F + n for n in range(1, 13)})
KEYS["space"] = 0x20
COMMON = {
    0x01000000: "Esc",
    0x01000001: "Tab",
    0x01000003: "Backspace",
    0x01000004: "Return",
    0x01000005: "Enter",
    0x01000006: "Ins",
    0x01000007: "Del",
    0x01000008: "Pause",
    0x01000009: "Print",
    0x01000010: "Home",
    0x01000011: "End",
    0x01000012: "Left",
    0x01000013: "Up",
    0x01000014: "Right",
    0x01000015: "Down",
    0x01000016: "PgUp",
    0x01000017: "PgDown",
}


@dataclass(frozen=True)
class Key:
    qt: int
    gtk: str
    xdg: str


def parse_key(value: str) -> Key | None:
    if not value:
        return None
    match = re.fullmatch(r"((?:<[a-z]+>)*)([a-z0-9]+)", value.casefold())
    if not match:
        raise ValueError("invalid shortcut grammar")
    names = {ALIASES.get(v, v) for v in re.findall(r"<([a-z]+)>", match[1])}
    if names - {mod[1].casefold() for mod in MODIFIERS}:
        raise ValueError("unknown modifier")
    key = match[2]
    if key not in KEYS or (not names and not re.fullmatch(r"f(?:[1-9]|1[0-2])", key)):
        raise ValueError("unsupported shortcut key")
    mods = [mod for mod in MODIFIERS if mod[1].casefold() in names]
    label = key.upper() if key.startswith("f") and len(key) > 1 else key
    return Key(
        KEYS[key] | sum(mod[0] for mod in mods),
        "".join(f"<{mod[1]}>" for mod in mods) + label,
        "+".join([mod[2] for mod in mods] + [label]),
    )


def from_qt(value: int) -> tuple[str, str]:
    mods = [mod for mod in MODIFIERS if value & mod[0]]
    code = value & ~sum(mod[0] for mod in MODIFIERS)
    key = next((name for name, n in KEYS.items() if n == code), "")
    if key and (mods or re.fullmatch(r"f(?:[1-9]|1[0-2])", key)):
        label = key.upper() if key.startswith("f") and len(key) > 1 else key
        return "".join(f"<{mod[1]}>" for mod in mods) + label, ""
    label = COMMON.get(code, key.title() if key else f"0x{code:x}")
    return "", "+".join([mod[3] for mod in mods] + [label])
