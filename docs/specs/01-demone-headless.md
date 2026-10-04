# Spec 01 — Demone headless

Stato: approvata (GM, 2026-10-04) · Autore: Claude · Data: 2026-10-04

## 1. Obiettivo

Scambio funziona senza interfaccia grafica: un demone utente (servizio systemd) prende il
dispositivo configurato quando sul PC parte un audio e lo restituisce al telefono dopo
`release_idle_seconds` di silenzio, subito al blocco dello schermo o prima della sospensione. Una
CLI (`scambio switch|status|priority`) comanda il demone **solo** tramite la sua API D-Bus.

**Prova visibile.** Occhiali sull'iPhone, musica sull'iPhone. GM avvia un video sul PC: entro
≈ 3 s l'audio del video esce dagli occhiali e `scambio status` dice `on_pc`. Mette in pausa e
aspetta: dopo 120 s gli occhiali tornano all'iPhone, `scambio status` dice `released` e l'audio
del PC torna sull'uscita di prima (su `casa` la Scarlett). Lo switch `scambio switch` inverte lo stato e
attiva/disattiva la Priorità iPhone.

L'unità include anche il tooling del repository (venv, ruff, mypy, pytest, python-dbusmock,
`make check`, hook pre-commit), che da qui in avanti diventa il gate di ogni consegna.

## 2. Decisioni applicabili

- Decisioni di prodotto 4–7 (presa automatica anche se il telefono usa il dispositivo; rilascio
  dopo 120 s, immediato con blocco schermo e sospensione; Priorità iPhone che si spegne solo a
  mano; switch intelligente), 13 (nessuna CI, `make check` e hook), 15 (un loop GLib, Gio, nessun
  polling), 17 (nome D-Bus e oggetto).
- La pausa/muto della decisione 4 è rimandata alla spec 02 dal piano delle fasi
  (`06-progress-tracker.md`): qui presa e rilascio sono veri ma senza pausa.
- Decisioni di questa spec: 18–29 in `docs/decisions.md` (ritardo di presa 1 s, Priorità iPhone
  che rilascia subito, dipendenza `pactl`, meccanismo audio, instradamento, stato persistente,
  sessione, macchina a stati, interfaccia D-Bus, testi della CLI, servizio systemd, eccezioni
  approvate).
- Misure: M1 (presa ≈ 1,7 s fino all'uscita `bluez_output.*`; rilascio 2,4 s; dopo il rilascio
  l'iPhone si ricollega da solo), M2 (presa durante chiamata reversibile), M3 (nessuna
  riconnessione spontanea verso il PC; il demone non tocca `Trusted`), M4 (comportamento di
  `pactl -f json` 16.1), M5 (stream dei browser in pausa), M6 (segnali di blocco schermo su
  KDE) e M7 (cambio profilo A2DP↔HFP, scollegamento) in `docs/hardware-lab.md`.

## 3. Dettagli

### 3.1 Comportamento

#### 3.1.1 Architettura dei moduli

Layout di `02-architecture.md` §2, limitato a ciò che serve qui:

```
src/scambio/
  __main__.py      python -m scambio → demone (come `scambio daemon`)
  cli.py           daemon | status | switch | priority  → solo API D-Bus
  config.py        TOML (tomllib), default, validazione, creazione del modello commentato
  state.py         stato persistente JSON (~/.local/share/scambio/state.json)
  core/
    policy.py      macchina a stati PURA (nessun import di gi): eventi → (stato, azioni)
    bluez.py       adattatore BlueZ (system bus)
    audio.py       adattatore pipewire-pulse via pactl (sottoprocessi Gio)
    session.py     adattatore logind + org.freedesktop.ScreenSaver
    service.py     API D-Bus app.scambio.Scambio1 + collante: adattatori → policy → esecutore
    dbus/app.scambio.Scambio1.xml   introspezione, usata da service e client
```

`players.py`, `shortcuts.py`, `profiles/`, `extensions.py` e `ui/` **non** si creano in questa
spec. Un piccolo esecutore in `service.py` traduce le azioni della policy in chiamate agli
adattatori e reimmette nella policy i risultati come eventi. Gli adattatori espongono interfacce
(Protocol) sostituibili con finti nei test.

#### 3.1.2 Rilevamento audio (adattatore `audio.py`, decisioni 20–21)

- All'avvio `pactl --version` deve riportare una versione ≥ 16 (serve `-f json`); se il
  comando manca o è più vecchio → `AudioBackend(False)` permanente, log `error` con il pacchetto
  da installare (`pulseaudio-utils`), nessun nuovo tentativo.
- Un sottoprocesso di lunga durata `pactl -f json subscribe` (`Gio.Subprocess`, ambiente del
  demone ereditato, compreso `XDG_RUNTIME_DIR`, più `LC_ALL=C`), letto in modo asincrono sul loop GLib. **L'output non ha separatori** fra gli
  oggetti JSON (M4): il parser accumula i byte e usa `json.JSONDecoder.raw_decode` in ciclo,
  tollerando oggetti spezzati fra due letture.
- Gli eventi con `on` ∈ {`sink-input`, `sink`, `server`} programmano **un** aggiornamento
  coalescente: timer singolo di 50 ms (`GLib.timeout_add`) riarmato a ogni evento, poi una
  istantanea con `pactl -f json list sink-inputs`, `pactl -f json list sinks` e
  `pactl get-default-sink` (sottoprocessi asincroni, `LC_ALL=C`). Una sola istantanea alla
  volta; se arrivano eventi durante l'istantanea, ne segue una sola. Gli altri eventi (`client`,
  `card`, `source`…) si ignorano. Questo non è polling: senza eventi non gira nulla.
- All'avvio e dopo ogni riavvio di `pactl subscribe` si fa subito un'istantanea.
- **Stream attivo** = sink-input con `corked == false`, il cui `properties["media.role"]` non è
  in `audio.ignore_roles` e il cui `application.name` / `application.process.binary` non è in
  `audio.ignore_apps` (confronto senza maiuscole). I valori `"(null)"` prodotti da pactl per le
  stringhe non ASCII (M4) contano come assenti.
- **Audio attivo** = esiste almeno uno stream attivo. L'adattatore emette `AudioActive(bool)`
  solo quando il valore cambia (con lo stato di partenza noto subito dopo la prima istantanea).
- **Sink del dispositivo** = sink con `properties["api.bluez5.address"]` uguale a
  `device.address` (senza maiuscole); in mancanza della proprietà, nome che inizia con
  `bluez_output.<MAC con _>`. L'adattatore emette `DeviceSinkAppeared(name)` /
  `DeviceSinkGone` quando cambia, e tiene l'ultimo `default sink`. Dopo ogni (ri)aggancio la
  prima istantanea riemette **tutti** i valori (`AudioActive`, sink presente o no), anche se
  uguali a quelli in cache.
- Se il sottoprocesso `subscribe` termina (riavvio di pipewire-pulse), l'adattatore emette
  `AudioBackend(False)` e lo rilancia con attesa crescente 1, 2, 4, 8, 16, 30 s (timer legato
  allo stato, non polling); al primo successo emette `AudioBackend(True)` e fa l'istantanea;
  l'attesa torna a 1 s dopo un'istantanea riuscita.
- Azioni di instradamento (decisione 22):
  - `RouteToDevice`: se il predefinito attuale è **già** il sink del dispositivo non fa nulla
    (caso normale su `casa`: senza un predefinito configurato WirePlumber sceglie da solo il
    sink Bluetooth, M5). Altrimenti memorizza il predefinito attuale come
    `restore_default_sink` nello stato persistente, esegue
    `pactl set-default-sink <sink dispositivo>` e `pactl move-sink-input <idx> <sink>` per ogni
    sink-input che era sul vecchio predefinito. Così Scambio scrive le preferenze di
    WirePlumber solo quando serve davvero.
  - `RestoreRouting` (idempotente): agisce solo se esiste `restore_default_sink` (cioè se
    l'ha cambiato Scambio) e quel sink esiste ancora: se il
    predefinito attuale è ancora il sink del dispositivo, `set-default-sink` al vecchio e
    sposta lì i sink-input che sono sul sink del dispositivo; poi cancella
    `restore_default_sink`. Se l'utente nel frattempo ha scelto un altro predefinito, non si
    tocca nulla. In **ogni** caso (sink sparito, predefinito cambiato) `restore_default_sink`
    viene cancellato, così la riparazione all'avvio non si ripete. Errori di `pactl` → log
    `warning`, mai bloccanti.
  - Quando il dispositivo si scollega senza che Scambio abbia cambiato il predefinito (caso
    normale su `casa`), il nuovo predefinito lo sceglie WirePlumber (su `casa` l'unica altra
    uscita, la Scarlett). Scambio non lo forza.

#### 3.1.3 Bluetooth (adattatore `bluez.py`)

- System bus, `org.bluez`. Trova il dispositivo con `ObjectManager.GetManagedObjects` cercando
  `org.bluez.Device1.Address == device.address`; segue `InterfacesAdded/Removed` e
  `PropertiesChanged` (`Connected`, `Alias`; `Powered` dell'adattatore che lo ospita).
- Emette `Availability(bool)`: vero se l'adattatore esiste ed è `Powered` e il dispositivo
  esiste ed è `Paired`. Emette `DeviceConnected(bool)` a ogni cambio di `Connected`.
- `Connect`: chiamata asincrona a `org.bluez.Device1.Connect()`; timeout della chiamata D-Bus =
  `policy.connect_timeout_seconds` + 5 s, così decide sempre il timer `CONNECT` della policy.
  Risultato → `ConnectResult(ok | errore)` con il nome dell'errore BlueZ
  (`org.bluez.Error.AlreadyConnected`, `InProgress`, `Failed`, `NotReady`…).
  `Disconnect`: `Device1.Disconnect()` asincrona, stesso timeout → `DisconnectResult(ok |
  errore)`; decide il timer `RELEASE`.
- Vietato: `Pair`, `RemoveDevice`, scrittura di `Trusted`/`Blocked`, qualsiasi operazione su
  dispositivi diversi da quello configurato, `bluetoothctl`.
- Se `org.bluez` sparisce dal bus (riavvio di bluetoothd) → `Availability(False)`; quando
  ricompare (`NameOwnerChanged`) si riaggancia da capo.

#### 3.1.4 Sessione (adattatore `session.py`, decisione 24)

- **Blocco schermo** = OR di due fonti, ognuna opzionale:
  1. logind: sessione grafica dell'utente presa da
     `org.freedesktop.login1.User.Display` (oggetto `/org/freedesktop/login1/user/self`;
     un servizio utente systemd non appartiene alla sessione, quindi niente `session/auto`);
     proprietà `LockedHint` via `PropertiesChanged`;
  2. `org.freedesktop.ScreenSaver` sul bus di sessione: segnale `ActiveChanged(b)` e stato
     iniziale con `GetActive()`.
  Misurato (M6): su KDE le due fonti cambiano insieme, ≈ 0,27 s dopo Meta+L; `ActiveChanged`
  arriva due volte (due percorsi oggetto), quindi l'adattatore emette `Locked` solo ai cambi
  del valore combinato. Il log `info` indica quale fonte ha segnalato. GNOME non è misurato:
  l'OR rende sufficiente una sola fonte funzionante.
  L'adattatore emette `Locked(bool)` solo ai cambi del valore combinato. Se una fonte manca, si
  usa l'altra; se mancano entrambe, log `warning` e `Locked(False)` fisso.
- **Sospensione**: `org.freedesktop.login1.Manager.PrepareForSleep(b)`. Il demone tiene un
  inibitore `delay` (`Manager.Inhibit("sleep", "Scambio", "Release Bluetooth device before sleep",
  "delay")`, fd ricevuto con `call_with_unix_fd_list`). `PrepareForSleep(true)` → evento
  `Sleep(True)`; l'esecutore chiude l'fd quando la policy emette `ReleaseSleepInhibitor` (al
  più tardi allo scadere del timer `SLEEP`, regola G5). `PrepareForSleep(false)` → evento
  `Sleep(False)` e nuovo inibitore.

#### 3.1.5 Macchina a stati (`core/policy.py`, decisione 25)

Funzione pura `step(ctx, event, config) -> (ctx', actions)`; nessun I/O, nessun orologio: i
timer sono azioni (`StartTimer(name, ms)`, `CancelTimer(name)`) e la loro scadenza è un evento
(`TimerFired(name)`). Avviare un timer già attivo lo riarma; un timer da 0 ms scade al giro
successivo del loop (così `grab_delay_ms = 0` segue la stessa strada di ogni altro valore).

**Stati** (stringhe identiche a `05-ui-context.md` §3): `released`, `connecting`, `on_pc`,
`releasing`, `unavailable`.

**Contesto**: `priority` (persistente), `audio_active`, `device_connected`, `sink_ready`,
`locked`, `sleeping`, `blocked_until_silence`, `pending` ∈ {`none`, `grab`, `release`},
`pending_reason`, `origin` ∈ {`self`, `external`}, `routed`, `reason` (motivo della transizione
in corso, riusato all'uscita da `connecting` e `releasing`).

**Timer**: `GRAB_DELAY` (`policy.grab_delay_ms`), `IDLE` (`policy.release_idle_seconds`),
`CONNECT` (`policy.connect_timeout_seconds`), `SINK` (`policy.sink_timeout_seconds`),
`RELEASE` (`policy.connect_timeout_seconds`), `SLEEP` (`policy.sleep_release_timeout_seconds`).

**Azioni**: `Connect`, `Disconnect`, `RouteToDevice`, `RestoreRouting`, `StartTimer`,
`CancelTimer`, `SavePriority(b)`, `ReleaseSleepInhibitor`, `EmitError(code)`,
`EmitTransition(from, to, reason)`.

**Predicati**

- *Idoneo alla presa automatica* = `audio_active` ∧ ¬`priority` ∧ ¬`locked` ∧ ¬`sleeping` ∧
  ¬`blocked_until_silence`.
- *Destinazione PC* = stato `on_pc`, oppure `connecting` con `pending ≠ release`, oppure
  `releasing` con `pending = grab`. Lo switch inverte sempre la destinazione: premuto due volte
  annulla sé stesso.

**Procedure** (usate dalle righe della tabella)

- **PRESA(r)**: azzera `LastError`, `Connect`, `StartTimer(CONNECT)`, `origin = self`,
  `pending = none`, `reason = r` → `connecting`.
- **RILASCIO(r)**: `CancelTimer(IDLE, GRAB_DELAY, CONNECT, SINK)`, `RestoreRouting`,
  `routed = false`, `Disconnect`, `StartTimer(RELEASE)`, `pending = none`, `reason = r` →
  `releasing`.
- **INGRESSO(instrada)**: `CancelTimer(CONNECT, SINK)`. Se `pending = release` → RILASCIO
  (`pending_reason`); altrimenti se `locked` → RILASCIO(`locked`); se `sleeping` →
  RILASCIO(`sleep`). Altrimenti: se `instrada` → `RouteToDevice`, `routed = true`; se
  ¬`audio_active` → `StartTimer(IDLE)`; `pending = none`; azzera `LastError` → `on_pc`
  (motivo = `reason`).

**Regole globali (valgono in ogni stato, prima della tabella)**

| # | Evento | Effetto |
|---|---|---|
| G1 | `AudioActive(v)` | `audio_active = v`; se `v = false` → `blocked_until_silence = false` |
| G2 | `DeviceConnected(v)`, `DeviceSinkAppeared` / `DeviceSinkGone` | aggiorna `device_connected` / `sink_ready` |
| G3 | `Locked(v)` | aggiorna `locked` |
| G4 | `Sleep(v)` | aggiorna `sleeping`; `v = true` → `StartTimer(SLEEP)`; `v = false` → `CancelTimer(SLEEP)` |
| G5 | `TimerFired(SLEEP)` | `ReleaseSleepInhibitor` (paracadute: logind non aspetta oltre) |
| G6 | `SetPriority(v)` | `priority = v`, `SavePriority(v)` |
| G7 | `Switch` | se *destinazione PC*: `priority = true`; altrimenti `priority = false` e `blocked_until_silence = false`; `SavePriority`; poi la riga «switch verso iPhone» o «switch verso PC» dello stato |
| G8 | `Availability(false)` | annulla tutti i timer tranne `SLEEP`; `RestoreRouting`; `routed = false`; `pending = none`; se `sleeping` → `ReleaseSleepInhibitor`, `CancelTimer(SLEEP)` → `unavailable` (`availability`) |
| G9 | `AudioBackend(v)` | `v = false` → `EmitError(audio_backend_down)`; il contesto non cambia (un riavvio di PipeWire non rilascia; al riaggancio l'adattatore riemette tutti i valori, §3.1.2) |
| G10 | Ingresso in `released` | `pending = none`; se `sleeping` → `ReleaseSleepInhibitor`, `CancelTimer(SLEEP)`; se idoneo → `StartTimer(GRAB_DELAY)` |
| G11 | Ogni cambio di stato | `EmitTransition(from, to, reason)` |
| G12 | Risultati e scadenze non previsti nello stato corrente (es. `ConnectResult` tardivo dopo C4) | ignorati, con log `debug` |

**Tabella evento → azione per stato**

| # | Stato | Evento (guardia) | Azioni → stato · reason |
|---|---|---|---|
| R1 | released | `AudioActive(true)`, `SetPriority(false)`, `Locked(false)`, `Sleep(false)` (idoneo) | `StartTimer(GRAB_DELAY)` → released |
| R2 | released | `AudioActive(false)`, `SetPriority(true)`, `Locked(true)` | `CancelTimer(GRAB_DELAY)` → released |
| R3 | released | `Sleep(true)` | `CancelTimer(GRAB_DELAY, SLEEP)`, `ReleaseSleepInhibitor` → released |
| R4 | released | `TimerFired(GRAB_DELAY)` | se idoneo → PRESA(`audio_started`); altrimenti nulla |
| R5 | released | `DeviceConnected(true)` (presa esterna, es. applet KDE) | `origin = external`, `reason = external_connect`; se `sink_ready` → INGRESSO(sì); altrimenti `StartTimer(SINK)` → connecting |
| R6 | released | `Switch` verso PC | se ¬`locked` ∧ ¬`sleeping` → PRESA(`switch`); altrimenti solo G7 |
| C1 | connecting | `ConnectResult(ok)` o errore BlueZ `AlreadyConnected` | `CancelTimer(CONNECT)`; se `device_connected` ∧ `sink_ready` → INGRESSO(sì); altrimenti `StartTimer(SINK)` |
| C2 | connecting | errore BlueZ `InProgress` | nulla (decide il timer `CONNECT`) |
| C3 | connecting | `DeviceSinkAppeared` con `device_connected`, o `DeviceConnected(true)` con `sink_ready` | INGRESSO(sì) |
| C4 | connecting | `ConnectResult(altro errore)` | `EmitError(connect_failed)`, `blocked_until_silence = audio_active`; se `device_connected` → RILASCIO(`connect_failed`); altrimenti `CancelTimer(CONNECT, SINK)` → released · `connect_failed` |
| C5 | connecting | `TimerFired(CONNECT)` | `EmitError(connect_timeout)`, `blocked_until_silence = audio_active`, RILASCIO(`connect_timeout`) (il `Disconnect` interrompe il tentativo; se il dispositivo non è collegato risponde con errore e vale L1) |
| C6 | connecting | `TimerFired(SINK)`, `origin = self` | `EmitError(sink_timeout)`, `blocked_until_silence = audio_active`, RILASCIO(`sink_timeout`) |
| C7 | connecting | `TimerFired(SINK)`, `origin = external` | `reason = sink_timeout`, INGRESSO(no), **poi** `EmitError(sink_timeout)` (così `LastError` resta visibile) — non si scollega un dispositivo collegato a mano; se il sink arriva dopo vale O10 |
| C8 | connecting | `DeviceConnected(false)` | `CancelTimer(CONNECT, SINK)`; se `origin = self` → `EmitError(connect_failed)`, `blocked_until_silence = audio_active`, → released · `connect_failed`; altrimenti → released · `external_disconnect` |
| C9 | connecting | `Switch` verso iPhone, `SetPriority(true)`, `Locked(true)`, `Sleep(true)` | `pending = release`, `pending_reason` = `switch` \| `priority` \| `locked` \| `sleep`. Il demone non interrompe un `Connect` in corso: attende l'esito (al massimo `CONNECT`) e rilascia in INGRESSO |
| C10 | connecting | `Switch` verso PC (c'era `pending = release`) | `pending = none` |
| O1 | on_pc | `AudioActive(false)` | `StartTimer(IDLE)` |
| O2 | on_pc | `AudioActive(true)` | `CancelTimer(IDLE)` |
| O3 | on_pc | `TimerFired(IDLE)` | RILASCIO(`idle_timeout`) |
| O4 | on_pc | `Locked(true)` | RILASCIO(`locked`) |
| O5 | on_pc | `Sleep(true)` | RILASCIO(`sleep`) (l'inibitore resta finché il rilascio non finisce o scade `SLEEP`) |
| O6 | on_pc | `Switch` verso iPhone | RILASCIO(`switch`) |
| O7 | on_pc | `SetPriority(true)` (decisione 19) | RILASCIO(`priority`) |
| O8 | on_pc | `DeviceConnected(false)` (custodia, fuori portata, applet) | `CancelTimer(IDLE, SINK)`, `RestoreRouting`, `routed = false`, `blocked_until_silence = audio_active` → released · `external_disconnect` |
| O9 | on_pc | `DeviceSinkGone` con `device_connected` (es. cambio profilo A2DP↔HFP) | `routed = false`, `StartTimer(SINK)` |
| O10 | on_pc | `DeviceSinkAppeared` con `routed = false` | `CancelTimer(SINK)`, `RouteToDevice`, `routed = true` |
| O11 | on_pc | `TimerFired(SINK)` | `EmitError(sink_lost)`, `blocked_until_silence = audio_active`, RILASCIO(`sink_lost`) |
| L1 | releasing | `DisconnectResult(ok)`; `DisconnectResult(errore)` o `TimerFired(RELEASE)` con ¬`device_connected`; `DeviceConnected(false)` | `CancelTimer(RELEASE)`; se `pending = grab` ∧ ¬`locked` ∧ ¬`sleeping` → PRESA(`switch`); altrimenti → released · `reason` |
| L2 | releasing | `DisconnectResult(errore)` o `TimerFired(RELEASE)` con `device_connected` | `CancelTimer(RELEASE)`, `EmitError(disconnect_failed)`, `pending = none`; se `sleeping` → `ReleaseSleepInhibitor`, `CancelTimer(SLEEP)`; `RouteToDevice`, `routed = true`; se ¬`audio_active` → `StartTimer(IDLE)` → on_pc · `disconnect_failed` (nessun nuovo tentativo immediato: niente cicli) |
| L3 | releasing | `Switch` verso PC | `pending = grab` |
| L4 | releasing | `Switch` verso iPhone (c'era `pending = grab`), `SetPriority(true)`, `Locked(true)`, `Sleep(true)` | `pending = none` |
| U1 | unavailable | `Availability(true)` | `origin = external`, `reason = availability`; se `device_connected` ∧ `sink_ready` → INGRESSO(sì); se solo `device_connected` → `StartTimer(SINK)` → connecting; altrimenti → released |
| U2 | unavailable | `Switch` | `EmitError(device_unavailable)`; la priorità non cambia (eccezione a G7); il metodo D-Bus risponde con errore |

Gli eventi non elencati per uno stato hanno solo l'effetto delle regole globali.

**Conseguenze volute, da non «correggere»:**
- Con schermo bloccato o Priorità iPhone non c'è presa automatica. Allo sblocco, se l'audio è
  ancora attivo, la presa riparte (R1) dopo `GRAB_DELAY`.
- Anti ping-pong: dopo una presa fallita, un sink perso o una perdita esterna con audio in
  corso, nessuna nuova presa automatica finché l'audio non tace almeno una volta (G1). Lo switch
  manuale prova sempre.
- Una presa esterna (applet KDE) con Priorità iPhone attiva viene rispettata: il PC tiene il
  dispositivo e lo rilascia per silenzio, blocco o sospensione.
- Al rilascio con audio in corso (blocco, switch, priorità) l'audio continua dagli altoparlanti
  del PC: la pausa è la spec 02.
- Con il dispositivo sul PC anche suoni di sistema e notifiche vanno negli occhiali, come con
  qualsiasi cuffia, e non azzerano il timer `IDLE`.

#### 3.1.6 Avvio, ricarica, arresto del demone

- Avvio: legge config e stato; possiede il nome `app.scambio.Scambio` con `DO_NOT_QUEUE`; se il
  nome è già posseduto esce con codice 1 e messaggio chiaro. Se lo stato persistente contiene
  `restore_default_sink` e il dispositivo non è collegato, esegue `RestoreRouting` (ripara un
  crash avvenuto `on_pc`). Poi aggancia BlueZ, sessione e audio; la policy parte da
  `unavailable` e si allinea con gli eventi iniziali (U1), così un dispositivo già collegato
  viene adottato. Con `device.address` vuoto resta `unavailable` ed emette
  `Error(device_not_configured)`.
- Ricarica: metodo `Reload()` o `SIGHUP` (`GLib.unix_signal_add`). Config valida → i nuovi
  valori valgono per i timer avviati da quel momento. Se cambia `device.address` la ricarica è
  rifiutata (errore D-Bus `RestartRequired`, valori non applicati): si cambia dispositivo con
  `systemctl --user restart scambio`. Config non valida → si tiene la precedente,
  `Error(config_invalid)` ed errore D-Bus `ConfigInvalid`.
- Arresto (`SIGTERM`/`SIGINT`): non si scollega il dispositivo e non si tocca l'instradamento
  (spegnere Scambio non deve togliere l'audio a chi lo sta usando; il predefinito salvato si
  ripristina al prossimo avvio se nel frattempo il dispositivo si è scollegato); si chiude
  l'inibitore; uscita 0.

### 3.2 API D-Bus, configurazione, dati

#### 3.2.1 API D-Bus (decisione 26)

Bus di sessione · nome `app.scambio.Scambio` · oggetto `/app/scambio/Scambio` · interfaccia
`app.scambio.Scambio1`. Introspezione in un file XML del pacchetto, unica fonte per servizio e
client. Ogni cambio di proprietà emette `org.freedesktop.DBus.Properties.PropertiesChanged`.

| Proprietà (sola lettura) | Tipo | Significato |
|---|---|---|
| `State` | s | `released` \| `connecting` \| `on_pc` \| `releasing` \| `unavailable` |
| `IphonePriority` | b | Priorità iPhone |
| `AudioActive` | b | c'è audio attivo sul PC (definizione §3.1.2) |
| `Locked` | b | sessione bloccata |
| `DeviceAddress` | s | indirizzo configurato (`""` se assente) |
| `DeviceName` | s | `Alias` BlueZ (`""` se sconosciuto) |
| `DeviceConnected` | b | `Connected` BlueZ |
| `IdleReleaseAt` | t | istante del rilascio programmato, µs epoch UNIX; 0 se nessun timer `IDLE`. Lo calcola l'esecutore quando esegue `StartTimer(IDLE)` (ora + durata) e lo azzera a cancellazione o scadenza: la policy resta senza orologio |
| `LastError` | s | codice dell'ultimo errore, `""` se nessuno; si azzera all'inizio di una presa (PRESA) e all'ingresso riuscito in `on_pc` |
| `Version` | s | versione del pacchetto |

| Metodo | Firma | Effetto |
|---|---|---|
| `Switch` | `() → s` | evento `Switch`; restituisce lo stato dopo l'evento (non attende la fine della connessione); in `unavailable` errore D-Bus `app.scambio.Scambio1.Error.DeviceUnavailable` |
| `SetPriority` | `(b) → ()` | evento `SetPriority(b)` |
| `Reload` | `() → ()` | ricarica la configurazione; errori D-Bus `app.scambio.Scambio1.Error.ConfigInvalid` (non valida) e `…Error.RestartRequired` (cambiato `device.address`) |

| Segnale | Firma | Quando |
|---|---|---|
| `Transition` | `(s from, s to, s reason)` | ogni cambio di stato; `reason` ∈ {`audio_started`, `idle_timeout`, `locked`, `sleep`, `switch`, `priority`, `external_connect`, `external_disconnect`, `connect_failed`, `connect_timeout`, `sink_timeout`, `sink_lost`, `disconnect_failed`, `availability`} |
| `Error` | `(s code, s detail)` | `code` ∈ {`connect_failed`, `connect_timeout`, `sink_timeout`, `sink_lost`, `disconnect_failed`, `device_unavailable`, `device_not_configured`, `config_invalid`, `audio_backend_down`}; `detail` tecnico in inglese, per il log |

Questi nomi diventano parte del contratto di `05-ui-context.md` (le UI delle spec 03–04 li
useranno); Codex non ne aggiunge altri senza chiederlo nel report.

#### 3.2.2 CLI (`scambio`, entry point console del pacchetto)

| Comando | Effetto | Uscita |
|---|---|---|
| `scambio daemon [--debug]` | avvia il demone in primo piano (lo usa systemd) | — |
| `scambio status [--json]` | `GetAll` delle proprietà; testo leggibile o JSON | 0 |
| `scambio switch` | `Switch()`; stampa lo stato restituito | 0, 1 se errore D-Bus |
| `scambio priority [on\|off\|toggle]` | senza argomento stampa lo stato; altrimenti `SetPriority` | 0, 1 |

Codici d'uscita comuni: 1 errore D-Bus del demone (es. `DeviceUnavailable`), 2 uso errato
(argparse), 3 demone non in esecuzione (nome assente sul bus) con messaggio che suggerisce
`systemctl --user start scambio`. I comandi client (`status`, `switch`, `priority`) non
importano `core/`; `daemon` importa `scambio.core.service` solo dentro il proprio ramo
(import pigro), così il client resta sottile.
Testi: msgid inglesi marcati con `gettext` (decisione 27); gli stati e i codici
d'errore restano stringhe stabili non tradotte.

#### 3.2.3 Configurazione `~/.config/scambio/config.toml`

Letta con `tomllib`; il demone **non** la riscrive mai. Se il file non esiste il demone crea un
modello commentato con i default e `device.address = ""` (stato `unavailable`, errore
`device_not_configured`); i commenti del modello sono in inglese, come il codice (file tecnico,
decisione 27). Chiavi sconosciute → `warning` nel log, ignorate. Valori fuori range →
config non valida.

| Chiave | Tipo | Default | Vincoli |
|---|---|---|---|
| `device.address` | str | `""` | MAC `XX:XX:XX:XX:XX:XX` o vuoto |
| `device.profile` | str | `"generic"` | `generic` \| `meta_glasses`; in questa spec solo validata, nessun effetto |
| `policy.grab_delay_ms` | int | 1000 | 0–10000 |
| `policy.release_idle_seconds` | int | 120 | 10–3600 |
| `policy.connect_timeout_seconds` | int | 10 | 2–60 |
| `policy.sink_timeout_seconds` | int | 5 | 1–30 |
| `policy.sleep_release_timeout_seconds` | int | 4 | 1–10 (sotto `InhibitDelayMaxUSec` di logind: 30 s su `casa`, M6) |
| `audio.ignore_roles` | list[str] | `["event", "notification", "test"]` | — |
| `audio.ignore_apps` | list[str] | `[]` | nomi applicazione o binario |
| `shortcut.preferred` | str | `"<Super>g"` | solo validata (spec 04) |
| `ui.language` | str | `"auto"` | `auto` \| `it` \| `en` \| `de`; solo validata (spec 03) |

`policy.iphone_priority` **non** sta più nella configurazione: è stato persistente (decisione
23); `02-architecture.md` §4 è aggiornato di conseguenza.

#### 3.2.4 Stato persistente `~/.local/share/scambio/state.json`

```json
{"version": 1, "iphone_priority": false, "restore_default_sink": null}
```

Scrittura atomica (file temporaneo + `os.replace`). File assente o illeggibile → default e
`warning`. Nessun altro file fuori da `~/.config/scambio/` e `~/.local/share/scambio/` viene
scritto dal demone.

#### 3.2.5 Tooling (proprietà di Codex)

- `pyproject.toml`: pacchetto `scambio` 0.1.0, `requires-python >= 3.11`, layout `src/`,
  entry point `scambio = "scambio.cli:main"`, nessuna dipendenza runtime installata da pip
  (PyGObject è di sistema, documentato nel README); extra `dev`: ruff, mypy, pytest,
  python-dbusmock, pygobject-stubs. Licenza non dichiarata finché Q1 è aperta. Configurazione di
  ruff, mypy (`--strict` su `core/`, `config.py`, `state.py`: `03` aggiornato) e pytest dentro
  `pyproject.toml`.
- `.venv` creato con `python3 -m venv --system-site-packages .venv` (serve `gi` di sistema).
- `Makefile`: `venv`, `check` (ruff format --check, ruff check, mypy, pytest — fallisce al
  primo errore), `fmt`, `test`, `run` (demone in primo piano, `--debug`), `hooks`
  (`git config core.hooksPath .githooks`), `install-user`, `uninstall-user`.
- `.githooks/pre-commit`: esegue `make check`; eseguibile.
- `packaging/systemd/scambio.service` (decisione 28): unit utente `Type=dbus`,
  `BusName=app.scambio.Scambio`, `ExecStart=<repo>/.venv/bin/scambio daemon`,
  `ExecReload=/bin/kill -HUP $MAINPID`, `Restart=on-failure`, `RestartSec=2`, `PartOf=graphical-session.target`,
  `After=graphical-session.target`, `WantedBy=graphical-session.target`.
  `make install-user` genera la unit con il percorso assoluto del repo in
  `~/.config/systemd/user/scambio.service` ed esegue `systemctl --user daemon-reload`; **non**
  la abilita né la avvia (lo fa GM). È l'unico file scritto fuori da `~/.config/scambio/` e
  `~/.local/share/scambio/`, e solo da un comando lanciato a mano (eccezione approvata da GM,
  decisione 29); il demone non lo tocca mai. `make uninstall-user` la ferma, la disabilita e la
  rimuove. Nessun file di attivazione D-Bus in questa spec.

#### 3.2.6 Test (Codex)

- Unit della policy guidati da tabella, più le conseguenze volute; nessun `gi` importato.
- Parser di `pactl subscribe`: oggetti concatenati senza separatori, oggetti spezzati fra due
  letture, valori `"(null)"`.
- Adattatore audio con un **finto `pactl`** (script eseguibile nei fixture, comando iniettato
  nel costruttore) che emette eventi scritti dal test e registra le chiamate a
  `set-default-sink` / `move-sink-input`; prova coalescenza, riavvio con attesa, instradamento e
  ripristino.
- BlueZ con il template `bluez5` di python-dbusmock; logind con il template `logind`;
  ScreenSaver con un oggetto dbusmock generico; tutto su bus privati.
- Integrazione: demone con tutti i finti → `scambio status --json`, `switch`, `priority`; un
  flusso completo audio → presa → silenzio (config con `release_idle_seconds = 10` e
  `grab_delay_ms = 0`, timer accelerati tramite iniezione) → rilascio.
- `conftest.py` avvia bus privati di sistema **e** di sessione (dbusmock) e fa fallire la
  sessione se `DBUS_SYSTEM_BUS_ADDRESS` o `DBUS_SESSION_BUS_ADDRESS` non puntano a quei bus;
  ogni test che costruisce l'adattatore audio passa il finto `pactl` (nessun default al `pactl`
  reale nei fixture). Così nessun test raggiunge il Bluetooth reale, il `pactl` reale o il nome
  `app.scambio.Scambio` del demone vero.
- Una riga di test per ogni regola G1–G12 e per ogni riga R/C/O/L/U, compresi: doppio switch
  che si annulla (C10, L4), risultati tardivi ignorati (G12), inibitore rilasciato in ogni
  uscita verso `released`/`unavailable` e allo scadere di `SLEEP`.

### 3.3 Interfaccia

Nessuna UI in questa spec. L'API di §3.2.1 è il contratto che le spec 03–04 useranno; gli stati
coincidono con `05-ui-context.md` §3 (`priority` ed `error` sono derivati da `IphonePriority` e
`LastError`, non sono stati della policy).

### 3.4 Errori e casi limite

- Se Scambio ha cambiato il predefinito, nessun percorso lo lascia sul sink del dispositivo dopo
  lo scollegamento (RILASCIO, O8, G8, riparazione all'avvio).
- `pactl` assente o < 16 (manca `-f json`) → `audio_backend_down` all'avvio, log con il
  pacchetto da installare (`pulseaudio-utils`); il demone resta su per CLI e switch manuale.
- Bluetooth spento, dispositivo non accoppiato o rimosso → `unavailable`.
- Indirizzo non configurato → `unavailable` + `device_not_configured`.
- `Connect` lento: decide il timer `CONNECT`; nessun nuovo tentativo automatico (C4/C5 + anti
  ping-pong). `Disconnect` lento o fallito: decide il timer `RELEASE` (L1/L2); nessuno stato
  resta bloccato in `connecting` o `releasing`.
- Sospensione durante `connecting`: rilascio appena collegato (C9) entro l'inibitore; se scade
  `SLEEP`, l'inibitore si chiude e logind sospende comunque.
- Riavvio di PipeWire/WirePlumber: nessun rilascio, riaggancio con attesa crescente.
- Riavvio di bluetoothd: `unavailable` → riaggancio → adozione dello stato reale.
- Log: `logging` su stderr (journald sotto systemd), livello `INFO`, `DEBUG` con `--debug`;
  ogni transizione con reason; mai indirizzi di dispositivi diversi da quello configurato.

## 4. Fuori scope

- Pausa/ripresa o muto degli stream durante la presa e il rilascio (MPRIS) — spec 02.
- Tray, notifiche, finestra, testi it/de, icone — spec 03; scorciatoia globale e portal — spec 04.
- Profili dispositivo con comportamento proprio, punto di estensione premium.
- Attivazione D-Bus su richiesta, Flatpak, pacchetti, avvio automatico abilitato di default.
- Più dispositivi contemporanei; pairing.
- Disattivazione della vecchia scorciatoia khotkeys di GM (spec 04, decisione 16).

## 5. Dipendenze

- Sistema (già presenti su `casa`): Python 3.12, PyGObject 3.48, BlueZ 5.72, PipeWire 1.0.5 con
  pipewire-pulse, WirePlumber 0.4.17, systemd 255, **`pactl` 16.1** (`pulseaudio-utils`,
  nuova dipendenza runtime approvata da GM, decisione 20).
- Sviluppo (solo `.venv`): ruff, mypy, pytest, python-dbusmock, pygobject-stubs.
- Nessuna spec precedente.

## 6. Checklist di done

Ordine di lavoro consigliato, con un commit (e `make check` verde) per ogni tappa:
(a) tooling + config + stato + policy con i suoi test; (b) adattatori audio, BlueZ, sessione con
i loro test; (c) servizio D-Bus, CLI, unit systemd, integrazione.

- [ ] Tooling: `make venv`, `make check`, `make hooks` funzionano da repo pulito; il hook blocca
      un commit con `make check` rosso.
- [ ] Ogni regola di §3.1.5 (G, R, C, O, P, L, U) ha un test unitario; ogni adattatore ha test
      con dbusmock o con il finto `pactl`.
- [ ] `make check` verde; nessun test saltato.
- [ ] Nessun polling introdotto (unici timer: i sei di §3.1.5, la coalescenza da 50 ms,
      l'attesa crescente di riaggancio e i timeout delle chiamate D-Bus); misura CPU/RSS a riposo (10 min) del demone **e** del
      sottoprocesso `pactl` nel report.
- [ ] Nessun valore personale hardcodato; chiavi di configurazione come §3.2.3.
- [ ] Nessun testo it/de introdotto; i msgid della CLI elencati nel report.
- [ ] `design/` non modificato; richieste di design (se servono) elencate nel report.
- [ ] `docs/verification/01/report.md` scritto; ulteriori decisioni tecniche in
      `docs/decisions.md` (dalla 30).
- [ ] Checklist di prova reale (§6.1) copiata nel report con i comandi esatti.
- [ ] Prova reale eseguita da GM: … · Firma: GM, data.

### 6.1 Checklist di prova reale per GM (occhiali + iPhone)

Preparazione: `make venv && make install-user`; in `~/.config/scambio/config.toml` mettere
`device.address = "80:AA:1C:XX:XX:XX"`; `systemctl --user start scambio`; in un terminale
`journalctl --user -u scambio -f`. Non usare la vecchia scorciatoia Ctrl+Shift+O durante la
prova. Per accorciare l'attesa si può mettere temporaneamente `release_idle_seconds = 30` e
ricaricare con `systemctl --user reload scambio` (rimettere 120 alla fine).

| # | Azione | Atteso |
|---|---|---|
| 1 | Occhiali sull'iPhone con musica; `scambio status` | `released`, `AudioActive false` |
| 2 | Avvia un video su YouTube nel PC | entro ≈ 3 s audio negli occhiali; musica iPhone ferma; `on_pc`; `pactl get-default-sink` = `bluez_output…` |
| 3 | Pausa del video, attendi `release_idle_seconds` | rilascio; iPhone si ricollega (musica in pausa, atteso); `released`; `pactl get-default-sink` = Scarlett (scelta di WirePlumber, non misurata finora: annotare) |
| 4 | Da occhiali sull'iPhone: `paplay /usr/share/sounds/freedesktop/stereo/bell.oga` | nessuna presa (suono < 1 s) |
| 5 | Notifica di sistema con suono (es. messaggio Telegram/KDE) | nessuna presa |
| 6 | Musica sul PC con occhiali sul PC → blocca lo schermo | rilascio immediato; l'audio continua dagli altoparlanti (atteso in questa spec); nel journal si vede quale fonte ha segnalato il blocco |
| 7 | Sblocca con l'audio ancora attivo | nuova presa dopo ≈ 1 s |
| 8 | Occhiali sul PC, nessun audio → sospendi il PC, poi riattiva | scollegati prima della sospensione (journal); dopo la ripresa nessuna presa finché non parte audio |
| 9 | `scambio switch` con occhiali sul PC, poi avvia audio sul PC | rilascio + `IphonePriority true`; nessuna presa |
| 10 | `scambio switch` di nuovo | presa + `IphonePriority false` |
| 11 | `scambio priority on` con occhiali sul PC | rilascio immediato |
| 12 | `systemctl --user restart scambio`; `scambio priority` | priorità conservata |
| 13 | Chiamata WhatsApp sull'iPhone, poi audio sul PC | presa; la chiamata passa al telefono; `scambio switch` → la chiamata torna negli occhiali |
| 14 | Occhiali sul PC con musica → chiudili nella custodia, riaprili | `released` (`external_disconnect`); nessun ciclo di riprese; uscita predefinita ripristinata |
| 15 | Collega gli occhiali dall'applet Bluetooth di KDE | adozione `on_pc`, audio negli occhiali |
| 16 | Spegni il Bluetooth dal tray di KDE, poi riaccendilo | `unavailable`, poi `released` |
| 17 | `systemctl --user restart pipewire pipewire-pulse wireplumber` | nessun rilascio; il demone si riaggancia (journal); una nuova presa funziona |
| 18 | Dopo 10 min di inattività: `ps -o rss,pcpu -p $(pgrep -f 'scambio daemon') $(pgrep -f 'pactl -f json subscribe')` | CPU ≈ 0 %, RSS annotato |

## 7. Note di revisione (Claude, dopo la consegna)

**Audit 1 — 2026-10-04** su `b342658`, `cadd653`, `9f282ac`, `3fdddfe` (report in
`docs/verification/01/report.md`). Verificato da Claude su `casa`: `make check` verde (132 test,
0 saltati, 11 s); file protetti (`AGENTS.md`, `design/`, `docs/context/`, `docs/specs/`,
`hardware-lab.md`) invariati; nessun `time.sleep`, thread, asyncio, `bluetoothctl`, scrittura di
`Trusted`, MAC personale. Revisione statica (agente di controllo) di policy, adattatori, servizio e
CLI contro §3: tabella G/R/C/O/L/U conforme riga per riga. Esito: **da correggere** prima della
prova reale.

1. `audio.py` `_down`: un `refresh` fallito durante un backend già giù (es. `RestoreRouting`
   durante il riavvio di PipeWire) richiama `_down`, che non rimuove il timer di riaggancio già
   programmato: doppio timer, backoff raddoppiato, un `pactl subscribe` orfano.
2. `audio.py` `RestoreRouting`: se l'istantanea fallisce o il backend è disabilitato,
   `restore_default_sink` viene cancellato senza ripristino. Deve restare salvato (la spec lo
   cancella solo se il sink non esiste più o il predefinito è stato cambiato dall'utente).
3. `audio.py` coda di instradamento: un'eccezione nel callback (es. `s["index"]` assente) lascia
   `routing_busy = True` e blocca ogni `Disconnect` successivo; serve `try/finally` che chiuda
   sempre l'operazione, e un timeout sui figli `pactl` di instradamento.
4. `audio.py` `JSONStream`: un oggetto corrotto blocca il parser per sempre e un
   `UnicodeDecodeError` ferma il ciclo di lettura senza `_down`. Decodifica con `errors="replace"`;
   su JSON non valido scartare fino al prossimo `{` (o `_down`).
5. `service.py` segnale `Error`: `detail` uguale al codice; deve essere il testo tecnico.
6. C7: `LastError` azzerato da INGRESSO subito dopo l'errore — **errore della spec**, corretto
   sopra (errore emesso dopo INGRESSO).
7. `RestoreRouting` riscrive `state.json` anche quando non c'era nulla da ripristinare.
8. `session.py`: al riaggancio di logind l'inibitore viene ripreso anche con `sleeping` vero;
   non va ripreso finché non arriva `PrepareForSleep(false)`.
9. `tools/install_user.py uninstall` non è idempotente (`check=True` su stop/disable).
10. Test: `test_rules` controlla solo che le azioni attese siano un sottoinsieme; servono
    confronti esatti (azioni in ordine e campi del contesto) e i rami mancanti: R2 (priorità,
    blocco), R5 con `sink_ready`, R6 bloccato/sospeso, C4 con dispositivo collegato, C8 esterno,
    L1 da `DeviceConnected(false)` e con `pending = grab` bloccato, L4 varianti, U1 solo
    collegato, G7/G9 sul contesto, G12 con `ConnectResult` tardivo dopo C4 e risultati/timer
    obsoleti, rilascio dell'inibitore nelle uscite verso `released` con `sleeping` (C4, C8, O8,
    U1), sequenza di backoff 1→30 s, ripristino con istantanea fallita.
11. Spec: `connect_timeout` mancava fra i `reason` di §3.2.1 (decisione 32 di Codex) — corretto.

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

Riletta da me e poi da un agente di controllo indipendente contro `AGENTS.md`, `01`, `02`, `03`,
le decisioni 1–29 e le misure M1–M7. L'agente ha trovato 36 punti; li ho corretti tutti nella
spec (sopra). I più importanti: stati senza uscita (`releasing` senza timeout, ora timer
`RELEASE`), inibitore della sospensione non rilasciato in alcuni rami (ora regola G10 + timer
`SLEEP` nella policy, quindi testabile), `pending` mai azzerato, adozioni senza timer `IDLE`
(ora tutto passa da INGRESSO), ciclo di prese dopo `sink_lost`, gara fra timeout D-Bus e timer
`CONNECT`, arresto che spostava l'audio sugli altoparlanti, test che potevano toccare il bus di
sessione reale.

Cosa resta, e cosa correggerei se emergesse:

1. **Dimensione.** È la spec più grande del progetto. L'ho tenuta intera perché la prova
   visibile richiede tutti i pezzi, ma con tre tappe e un commit verde per tappa. Se Codex non
   chiude in una sessione, la tappa (c) diventa una spec 01b senza toccare il resto.
2. **Instradamento.** Su `casa` WirePlumber rende già predefinito il sink Bluetooth (M5), quindi
   Scambio di norma non scrive nulla nelle preferenze di WirePlumber; il ritorno alla Scarlett
   dopo il rilascio è una scelta di WirePlumber, osservata in modo indiretto e da annotare nella
   prova 3. Su un PC con un predefinito configurato Scambio lo cambia e lo ripristina; residuo: un
   `move-sink-input` può far ricordare a WirePlumber il dispositivo come uscita preferita di
   un'app.
3. **Silenzio.** Si basa sugli stream non `corked`, non sul livello del segnale. Con Chrome
   funziona (M5: stream chiuso ≈ 5 s dopo la pausa, caso peggiore osservato ≤ 30 s). Firefox e
   altri player non sono misurati: se uno tiene lo stream aperto in pausa, la correzione è MPRIS
   nella spec 02, non il polling.
4. **Blocco schermo e HFP misurati dopo lo stop di Codex** (M6, M7): le due fonti di blocco
   concordano su KDE; il cambio A2DP↔HFP ricrea il sink con lo stesso nome in < 10 ms, quindi
   O9–O11 sono una rete di sicurezza. Non misurati: GNOME e l'autoswitch a HFP quando un'app
   apre il microfono.
5. **Pausa durante la presa (decisione 4).** In questa spec l'audio parte dagli altoparlanti e
   passa agli occhiali dopo ≈ 2,7 s; la pausa arriva con la spec 02, come da piano delle fasi.
6. **Da approvare da GM (decisione 29)**, perché toccano invarianti di `AGENTS.md` o
   comportamenti non decisi esplicitamente:
   a. `make install-user` scrive la unit in `~/.config/systemd/user/` (solo se lanciato a mano);
   b. testi della CLI, commenti del modello di config e motivo dell'inibitore in inglese fino
      alla spec 03 (eccezione temporanea a «ogni testo ha chiavi it/en/de»);
   c. comportamenti ricavati: nessuna presa automatica a schermo bloccato; anti ping-pong dopo
      errori o perdite esterne; spegnere Scambio non scollega gli occhiali; con gli occhiali sul
      PC anche le notifiche vanno negli occhiali; una connessione manuale dall'applet viene
      rispettata anche con Priorità iPhone attiva.

## 9. Domande aperte

Nessuna bloccante per il `/goal`. Restano Q1 (licenza, prima della release), Q4 (chiamata GSM,
prima della spec 02), Q5 (portal su Plasma 5.27, prima della spec 04).

## Comando `/goal`

```
/goal Implementa docs/specs/01-demone-headless.md seguendo AGENTS.md e docs/context/. Fatto solo
quando ogni voce della Checklist di done (§6) è soddisfatta con evidenza e `make check` è verde.
Scope: solo §3; §4 non si tocca; design/ non si modifica; mai Bluetooth o pactl reali nei test.
Lavora nelle tre tappe di §6, un commit per tappa con `make check` verde. Stop: se la spec
contraddice AGENTS.md o manca una decisione di prodotto, fermati e scrivilo nel report.
```
