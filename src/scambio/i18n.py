"""Pure language resolution and symbolic gettext keys shared by all surfaces."""

import gettext
import os
import tomllib
from collections.abc import Mapping
from pathlib import Path

from scambio.paths import locale_dir

LANGUAGES = ("it", "en", "de")


def resolve(language: str = "auto", environ: Mapping[str, str] | None = None) -> str:
    if language in LANGUAGES:
        return language
    env = os.environ if environ is None else environ
    candidates = env.get("LANGUAGE", "").split(":") + [
        env.get(key, "") for key in ("LC_ALL", "LC_MESSAGES", "LANG")
    ]
    for value in candidates:
        code = value.split(".")[0].split("@")[0].replace("-", "_").split("_")[0]
        if code in LANGUAGES:
            return code
    return "en"


class Translator:
    def __init__(self, language: str = "auto", *, strict: bool = False) -> None:
        self.language = resolve(language)
        self.catalog: gettext.NullTranslations = gettext.NullTranslations()
        for code in dict.fromkeys((self.language, "en")):
            try:
                with (locale_dir() / code / "LC_MESSAGES/scambio.mo").open("rb") as f:
                    self.catalog = gettext.GNUTranslations(f)
                break
            except (OSError, EOFError, ValueError) as exc:
                if strict:
                    raise ValueError(
                        f"Invalid catalog {code}: run make i18n: {exc}"
                    ) from exc

    def tr(self, key: str, **values: object) -> str:
        template = self.catalog.gettext(key)
        fallback = "device" in values and not values["device"]
        if fallback:
            values["device"] = self.catalog.gettext("tray-device-fallback")
        text = template.format(**values)
        if fallback and template.startswith("{device}"):
            text = text[:1].upper() + text[1:]
        return text


def cli_translator(path: Path) -> Translator:
    try:
        data = tomllib.loads(path.read_text())
        language = data.get("ui", {}).get("language", "auto")
        if not isinstance(language, str):
            language = "auto"
    except (OSError, ValueError, AttributeError):
        language = "auto"
    return Translator(language)
