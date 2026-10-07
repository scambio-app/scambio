# Developing Scambio

Runtime: Python >= 3.11, the distribution's PyGObject (Gio/GLib, GTK 4, libadwaita >= 1.4),
BlueZ, logind and a Pulse-compatible audio server (PipeWire with pipewire-pulse); `pactl` >= 16
from `pulseaudio-utils`. PyGObject comes from the distribution, not from pip. Build tools:
`msgfmt` (gettext) and `blueprint-compiler`.

- `make venv` creates `.venv` with system site packages and the development checks.
- `make hooks` activates the local pre-commit gate (`make check`) and the graphify hooks.
- `make check` runs format, lint, type checks and tests on private system and session buses with
  a fake `pactl`. Nothing is tested against the real Bluetooth or audio services.
- `make run` (or `.venv/bin/scambio daemon --debug`) runs the daemon from the checkout. The first
  start creates a commented `config.toml` with an empty address; choose the device in the settings
  window (`.venv/bin/scambio settings`).
- `.venv/bin/scambio status --json`, `switch` and `priority on|off|toggle` use only the D-Bus API.
- `make install-user` installs the user systemd unit, the launcher and the settings window's D-Bus
  service pointing at the checkout; `make uninstall-user` removes them. Do not keep a packaged
  Scambio (`.deb` or Flatpak) installed at the same time.
- Packages and release: see `docs/specs/05-packaging-e-release.md`.

There is no remote CI: every check runs on the maintainer's machine. Project documents under
`docs/` are written in Italian; `AGENTS.md` explains how the AI agents that write most of the
code work on this repository.
