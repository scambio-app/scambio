# Contributing to Scambio

Thanks for helping! A few things to know first.

## Issues

Please include your distribution and desktop (for example "Fedora 44, GNOME 50"), how you
installed Scambio (`.deb`, Flatpak or source), your headphones or glasses, and the output of
`scambio status` (Flatpak: `flatpak run app.scambio.Scambio status`). Logs:
`journalctl --user -u scambio` for the `.deb`, or run `scambio daemon --debug` in a terminal.

## Pull requests

1. Sign the [Contributor License Agreement](CLA.md). The CLA Assistant bot asks you on your
   first pull request; you sign once.
2. Read [AGENTS.md](AGENTS.md): it is short and lists the rules every change follows (no polling,
   no root, D-Bus only between UI and daemon, every text in English, Italian and German).
3. Run `make check` before pushing; there is no remote CI.
4. Say in the pull request if any part was generated with an AI tool.

Larger changes start from a specification in `docs/specs/`; please open an issue first so we
can agree on the behaviour.

## Translations

User-visible texts live in `design/i18n/` (gettext, symbolic message ids). New languages are
welcome.
