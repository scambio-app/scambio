# Scambio

Multipoint software per Linux: sposta automaticamente l'audio Bluetooth fra PC e telefono per
dispositivi che non supportano il multipoint nativo. Caso di punta: occhiali smart Meta
(Ray-Ban Meta, Oakley Meta); funziona con qualsiasi dispositivo audio Bluetooth.

Stato: demone headless implementato; audit e prova reale di GM pendenti.
Evidenza in `docs/verification/01/report.md`; tracker di proprietà di Claude.

Il repository vive solo sul PC di sviluppo (nessun remote). Le regole per gli agenti sono in
`AGENTS.md`.

## Headless development

Runtime: Python >= 3.11, system PyGObject (Gio/GLib), BlueZ, logind and a Pulse
compatible audio server (PipeWire with pipewire-pulse); `pactl` >= 16 from
`pulseaudio-utils`. PyGObject is supplied by the distribution, not installed by pip.
GTK/libadwaita are not loaded by this headless unit. No pairing is performed.

`make venv` creates `.venv` with system site packages and installs development
checks. `make hooks` activates the local pre-commit gate and graphify hooks.
`make check` runs format, lint, typing and tests on private system/session buses
with a fake pactl. Nothing is tested against the real Bluetooth/audio services.

After configuring an already paired device in `~/.config/scambio/config.toml`,
`make run` or `.venv/bin/scambio daemon` runs the daemon. The first start creates
a commented template with an empty address. `.venv/bin/scambio status --json`,
`switch` and `priority on|off|toggle` use only its D-Bus API. Priority and the
restore target live in `~/.local/share/scambio/state.json`. SIGHUP or the D-Bus
`Reload` method reloads valid configuration; changing the address requires a restart.

`make install-user` explicitly installs the user systemd unit and reloads systemd;
it neither enables nor starts it. `make uninstall-user` stops, disables and removes
that unit. These commands are for the human installation step, not automated tests.

The optional `[backend]` section configures coalescence, recovery delays and D-Bus
timeouts; the generated template lists their defaults. The six policy durations
remain under `[policy]`. Stopping Scambio leaves the device and current audio route
intact. Real-device verification remains GM's checklist in the verification report.
