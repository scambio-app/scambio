# 02 — Architettura

Redatto da Claude il 4 ottobre 2026. Descrive l'architettura **obiettivo**: il codice non esiste
ancora. Ogni scostamento introdotto da una spec si registra qui e in `docs/decisions.md`.

## 1. Stack

| Area | Scelta | Motivo |
|---|---|---|
| Linguaggio | Python ≥ 3.11 (sviluppo su 3.12) | `tomllib` incluso; PyGObject maturo |
| Event loop / IPC | GLib main loop, D-Bus via **Gio** (PyGObject) | un solo loop, zero dipendenze extra, adatto a Flatpak |
| Bluetooth | BlueZ su D-Bus (`org.bluez`) | standard su tutte le distro |
| Audio | PipeWire tramite il protocollo pulse: `pactl -f json subscribe` + istantanee (decisioni 20–21) | eventi senza polling; nessun binding nativo |
| Sessione | logind (`org.freedesktop.login1`) + `org.freedesktop.ScreenSaver` | lock/unlock e sospensione su KDE e GNOME |
| Player | MPRIS (`org.mpris.MediaPlayer2.*`) | pausa/ripresa dei player durante la presa |
| Scorciatoia | XDG Desktop Portal `GlobalShortcuts`, riserva CLI | standard cross-desktop, funziona in Flatpak |
| Tray | StatusNotifierItem + dbusmenu implementati su Gio | nessuna dipendenza da libappindicator |
| Notifiche | `org.freedesktop.Notifications` | standard |
| Finestra | GTK4 + libadwaita, layout in Blueprint (`design/ui/`) | layout dichiarativo di proprietà del design |
| Configurazione | TOML in `~/.config/scambio/config.toml` | leggibile e modificabile a mano |

Ambiente misurato di GM: vedi `docs/hardware-lab.md`.

## 2. Moduli (layout obiettivo)

```
src/scambio/
  __main__.py          avvio demone
  cli.py               comandi (switch, status, priority) → API D-Bus del demone
  config.py            lettura/scrittura configurazione, valori di default
  core/
    bluez.py           connect/disconnect, stato e segnali del dispositivo
    audio.py           eventi audio: nuovi stream, uscita BT comparsa, spostamento stream
    players.py         MPRIS: pausa/ripresa
    session.py         lock/unlock, sospensione
    policy.py          macchina a stati: decide presa e rilascio
    service.py         API D-Bus pubblica del demone (`app.scambio.Scambio`, decisione 17)
    shortcuts.py       portal GlobalShortcuts
    profiles/          profilo generico + profilo occhiali Meta
    extensions.py      punto di estensione per moduli premium
  i18n.py              lingua e testi (chiavi gettext di design/i18n), usato da UI, CLI e core
  paths.py             dove stanno design/ e i cataloghi compilati
  ui/                  tray e notifiche nel processo del demone, solo Gio (spec 03, decisione 74)
    client.py          proxy dell'API D-Bus del demone
    presentation.py    puro: design/ui/tray.json → icona, testi, menu
    actions.py         GAction app.switch, app.toggle-priority, app.quit
    tray.py            StatusNotifierItem + dbusmenu
    notify.py          notifiche + portal OpenURI
    window.py          finestra impostazioni, processo separato (spec 04)
```

Regola di dipendenza: `ui/` e `cli.py` dipendono solo dall'API D-Bus del demone (anche se girano
nello stesso processo, passano dall'interfaccia definita). `core/policy.py` non conosce D-Bus:
riceve eventi e restituisce azioni, così è testabile in isolamento.

## 3. Macchina a stati (fissata nella spec 01, §3.1.5)

La tabella completa evento → azione è in `docs/specs/01-demone-headless.md` §3.1.5; qui resta il
quadro. Stati definitivi: `released`, `connecting`, `on_pc`, `releasing`, `unavailable`
(nomi del codice e dell'API, uguali a `05-ui-context.md`).

| Stato | Significato |
|---|---|
| `released` | dispositivo non sul PC; presa automatica se c'è audio e nessun impedimento |
| `connecting` | connessione in corso (nostra o esterna), in attesa dell'uscita audio |
| `on_pc` | collegato, audio instradato; timer di silenzio quando l'audio tace |
| `releasing` | scollegamento in corso |
| `unavailable` | Bluetooth spento, dispositivo assente o non configurato |

Variabile ortogonale persistente: Priorità iPhone. Pausa e ripresa dei player MPRIS durante
presa e rilascio: spec 02 §3.1.4 (contesto `held`, timer `RESUME`, decisioni 50–56, 68).

## 4. Configurazione (chiavi iniziali)

Elenco completo con tipi, default e vincoli in `docs/specs/01-demone-headless.md` §3.2.3:
`device.address`, `device.profile`, `policy.grab_delay_ms = 500` (decisione 44),
`policy.release_idle_seconds = 120`, `policy.connect_timeout_seconds = 10`,
`policy.sink_timeout_seconds = 5`, `policy.sleep_release_timeout_seconds = 4`,
`audio.ignore_roles`, `audio.ignore_apps`, `shortcut.preferred = "<Super>g"`,
`ui.language = "auto"`, `ui.tray = true`, `ui.notifications = true` (spec 03, decisione 80;
dettagli in `05-ui-context.md` §5.8). Dalla spec 02 (§3.2.2): `policy.resume_delay_ms` (default
dal profilo: `generic` 0, `meta_glasses` 2000), `audio.ignore_players`,
`backend.player_timeout_ms = 1000`.

La Priorità iPhone non è configurazione ma stato persistente in
`~/.local/share/scambio/state.json` (decisione 23).

## 5. Punto di estensione (open-core)

Il core espone un'interfaccia di estensione (eventi di stato in lettura, comandi in scrittura)
caricata tramite entry point Python `scambio.extensions`. I moduli premium vivono in un pacchetto
separato e non sono mai importati dal core.

## 6. Invarianti

Quelli di `AGENTS.md`, più: le operazioni Bluetooth sono asincrone e con timeout; un errore non
deve mai lasciare l'audio del PC muto o in pausa; il demone sopravvive al riavvio di bluetoothd e
di PipeWire riagganciandosi ai servizi.

## 7. Rischi tecnici aperti

- ~~`Trusted=yes` e riconnessione spontanea~~ — misurato (M3, 2026-10-04): nessuna presa
  spontanea del PC; il demone non tocca `Trusted`.
- Supporto reale del portal GlobalShortcuts su Plasma 5.27 e su GNOME.
- Su GNOME senza estensione AppIndicator il tray non è visibile: la finestra e le notifiche devono
  bastare da sole.

## 8. Registro decisioni architetturali

Le decisioni stanno in `docs/decisions.md`; questa sezione riporta solo le date in cui il file è
stato aggiornato.

- 2026-10-04 — prima stesura (Claude).
- 2026-10-04 — nome D-Bus e app-id `app.scambio.Scambio` (decisione 17).
- 2026-10-04 — spec 01: meccanismo audio, instradamento, stato persistente, sessione,
  macchina a stati, interfaccia `app.scambio.Scambio1` (decisioni 18–28).
- 2026-10-05 — spec 02: adattatore MPRIS `players.py`, pausa/ripresa nella policy, chiavi nuove,
  `resume_players` in `state.json` (decisioni 50–56, 58–66, 68).
- 2026-10-05 — spec 03: UI nel processo del demone, presentazione da `design/`, chiavi `ui.*`,
  metodo `Quit()` (decisioni 74–81).
