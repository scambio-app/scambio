# 02 — Architettura

Redatto da Claude il 4 ottobre 2026. Descrive l'architettura **obiettivo**: il codice non esiste
ancora. Ogni scostamento introdotto da una spec si registra qui e in `docs/decisions.md`.

## 1. Stack

| Area | Scelta | Motivo |
|---|---|---|
| Linguaggio | Python ≥ 3.11 (sviluppo su 3.12) | `tomllib` incluso; PyGObject maturo |
| Event loop / IPC | GLib main loop, D-Bus via **Gio** (PyGObject) | un solo loop, zero dipendenze extra, adatto a Flatpak |
| Bluetooth | BlueZ su D-Bus (`org.bluez`) | standard su tutte le distro |
| Audio | PipeWire tramite il protocollo pulse (pipewire-pulse) | eventi su stream e uscite; meccanismo esatto deciso nella spec 01 |
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
  ui/
    tray.py            StatusNotifierItem + menu
    window.py          finestra impostazioni (carica design/ui)
    notify.py          notifiche
```

Regola di dipendenza: `ui/` e `cli.py` dipendono solo dall'API D-Bus del demone (anche se girano
nello stesso processo, passano dall'interfaccia definita). `core/policy.py` non conosce D-Bus:
riceve eventi e restituisce azioni, così è testabile in isolamento.

## 3. Macchina a stati (bozza, da fissare nella spec 01)

Stati: `RILASCIATO` (dispositivo non sul PC), `IN_PRESA` (connessione in corso, audio in pausa),
`SUL_PC` (collegato, audio instradato), `IN_RILASCIO`. Variabile ortogonale: `priorita_iphone`.

| Evento | Effetto principale |
|---|---|
| audio PC avviato (non evento di sistema) | se `RILASCIATO` e non priorità → `IN_PRESA` |
| uscita BT pronta | `IN_PRESA` → `SUL_PC`, sposta e riprende lo stream |
| silenzio ≥ `release_idle_seconds` | `SUL_PC` → `IN_RILASCIO` |
| blocco schermo / sospensione | `SUL_PC` → `IN_RILASCIO` subito |
| switch manuale | `SUL_PC` → rilascio + priorità on; altrimenti presa + priorità off |
| errore/timeout connessione | ritorno a `RILASCIATO`, audio ripreso sull'uscita precedente, notifica |

## 4. Configurazione (chiavi iniziali)

`device.address`, `device.profile`, `policy.release_idle_seconds = 120`,
`policy.connect_timeout_seconds`, `policy.iphone_priority = false`,
`shortcut.preferred = "<Super>g"`, `ui.language = "auto"`.

## 5. Punto di estensione (open-core)

Il core espone un'interfaccia di estensione (eventi di stato in lettura, comandi in scrittura)
caricata tramite entry point Python `scambio.extensions`. I moduli premium vivono in un pacchetto
separato e non sono mai importati dal core.

## 6. Invarianti

Quelli di `AGENTS.md`, più: le operazioni Bluetooth sono asincrone e con timeout; un errore non
deve mai lasciare l'audio del PC muto o in pausa; il demone sopravvive al riavvio di bluetoothd e
di PipeWire riagganciandosi ai servizi.

## 7. Rischi tecnici aperti

- `Trusted=yes` permette al dispositivo di ricollegarsi da solo al PC: da misurare prima di
  decidere come impedirlo (vedi `hardware-lab.md`).
- Supporto reale del portal GlobalShortcuts su Plasma 5.27 e su GNOME.
- Su GNOME senza estensione AppIndicator il tray non è visibile: la finestra e le notifiche devono
  bastare da sole.

## 8. Registro decisioni architetturali

Le decisioni stanno in `docs/decisions.md`; questa sezione riporta solo le date in cui il file è
stato aggiornato.

- 2026-10-04 — prima stesura (Claude).
- 2026-10-04 — nome D-Bus e app-id `app.scambio.Scambio` (decisione 17).
