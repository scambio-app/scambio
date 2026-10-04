# 03 — Standard di codice

Redatto da Claude il 4 ottobre 2026. Gli strumenti li configura Codex nella spec 01 secondo
queste regole; da quel momento la configurazione eseguibile (`pyproject.toml`, `Makefile`,
`.githooks/`) è la fonte di verità e questo file la riassume.

## 1. Gate (`make check`, eseguito anche dal hook pre-commit)

1. `ruff format --check`
2. `ruff check`
3. `mypy` — `--strict` su `src/scambio/core/`, `config.py` e `state.py`; normale sul resto
4. `pytest` — unit + integrazione su D-Bus di sessione privato

Strumenti di sviluppo (ruff, mypy, pytest, python-dbusmock) in un virtualenv locale `.venv/`;
**non** sono dipendenze runtime. Nessuna CI remota: il hook si attiva con
`git config core.hooksPath .githooks`.

## 2. Python

- Type hints ovunque; niente `Any` nel core salvo interfacce PyGObject, isolate in adattatori.
- Codice asincrono tramite callback/`Gio.Task`/async di Gio sul main loop GLib; niente thread
  salvo necessità documentata; niente `asyncio` parallelo al loop GLib.
- Nessun `time.sleep`, nessun loop di polling: timer solo con `GLib.timeout_add_seconds` (o
  `GLib.timeout_add` per durate sotto il secondo: coalescenza degli eventi audio, ritardo di presa)
  legati a uno stato e cancellati quando lo stato cambia. Elenco dei timer ammessi nella spec 01.
- Logging con il modulo `logging` (journald quando sotto systemd); mai indirizzi completi di
  dispositivi diversi da quello configurato, mai dati personali.
- Nomi in inglese nel codice; testi utente solo tramite gettext con le chiavi del contratto in
  `05-ui-context.md`.

## 3. Struttura e confini

- `core/policy.py` è puro: input = eventi, output = azioni. Nessun import di `gi`.
- Gli adattatori (`bluez.py`, `audio.py`, `session.py`, `players.py`) traducono D-Bus/pulse in
  eventi e azioni in chiamate; sono sottili e sostituibili con finti nei test.
- Le UI non importano `core/`: usano il client dell'API D-Bus.

## 4. Test: cosa ci si aspetta da una consegna

- Ogni transizione della macchina a stati ha un test unitario (tabella eventi → azioni).
- Gli adattatori D-Bus si provano con `python-dbusmock` (template BlueZ, logind) su un bus di
  sessione privato; mai sul Bluetooth reale nei test automatici.
- La prova sul dispositivo reale è DoD B: la esegue GM con la checklist preparata da Codex.
- Misura del costo a riposo: report con CPU e RSS del demone dopo 10 minuti idle.

## 5. Dipendenze

Runtime: PyGObject, GLib/Gio, GTK4, libadwaita (solo per la finestra). Strumenti di build:
`blueprint-compiler`, `gettext`. Qualsiasi altra dipendenza richiede una voce in
`docs/decisions.md` approvata da GM.
