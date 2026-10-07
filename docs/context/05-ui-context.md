# 05 — Contesto UI e contratto design ↔ codice

Redatto da Claude il 4 ottobre 2026; completato il 5 ottobre 2026 con il mock approvato da GM
(tela «Scambio — mock UI», decisioni 70–84); finestra impostazioni e scorciatoia definite il 7
ottobre 2026 con la spec 04 (mock della finestra approvato da GM, decisioni 100–108). Il design è
di Claude (decisione 10): i file stanno in `design/` e Codex li collega senza modificarli.

## 1. Principi

- **Invisibile quando funziona.** Prese e rilasci automatici non si notificano: lo dice l'icona.
  Si notifica solo l'essenziale (decisione 70): errori, e la Priorità iPhone cambiata da fuori
  dalla UI (scorciatoia, CLI). Scambio non controlla il telefono: la musica dell'iPhone non è
  affar suo (spec 02 §4).
- **Lo stato si legge dall'icona** senza aprire nulla: dove sta il dispositivo e se la Priorità
  iPhone è attiva (variante B, decisione 72: occhiali + emblema telefono/monitor/lucchetto).
- **Nativo dove possibile**: icone simboliche che seguono il tema (misurato su Plasma 5.27 scuro,
  M11); menu e notifiche disegnati dal desktop; finestra libadwaita (spec 04); scorciatoia nel
  servizio scorciatoie del desktop, modificabile dalle sue impostazioni (decisione 102).
- **Tastiera prima del mouse**: ogni azione del tray ha un equivalente da scorciatoia o CLI.
- **Nessun timer nella UI** (decisione 77): niente animazioni, niente conti alla rovescia che
  ticchettano; i testi che dipendono dall'ora si calcolano quando il menu si apre.
- Testi brevi, in it/en/de; tono neutro e amichevole. Per ora «iPhone» nei testi (decisione 73).

## 2. Superfici

| Superficie | Tecnologia | Processo | Spec |
|---|---|---|---|
| Icona tray + menu | StatusNotifierItem + dbusmenu su Gio, senza GTK | demone (decisione 74) | 03 |
| Notifiche | `org.freedesktop.Notifications` su Gio | demone | 03 |
| Finestra impostazioni | GTK4 + libadwaita ≥ 1.4, Blueprint in `design/ui/` | processo separato `scambio settings` (`app.scambio.Scambio.Settings`), su richiesta | 04 |
| Lanciatore | file `.desktop` da `design/desktop/` | — | 04 |
| Scorciatoia | KGlobalAccel su Plasma, portal GlobalShortcuts altrove (decisione 102); default Meta+G | demone | 04 |

Clic sinistro e destro sull'icona aprono lo stesso menu (`ItemIsMenu = true`, decisione 71; su Plasma 5.27
il clic sinistro passa dall'errore di `Activate`, §5.3, decisione 85).
Su GNOME senza estensione AppIndicator il tray non c'è: bastano notifiche e finestra.

## 3. Stati e icone (`design/icons/hicolor/scalable/status/`)

L'icona la sceglie la prima regola di `design/ui/tray.json` → `presentation` che corrisponde;
sopra vale l'**errore attivo** (§5.4). Nomi con il prefisso dell'app-id (decisione 76). Le icone
stanno in `scalable/status` perché KIconLoader usa le cartelle dell'`index.theme` di sistema
di hicolor: da `symbolic/status` Plasma non le trovava e ripiegava sull'icona a colori (M11).

| Regola | Quando (API `app.scambio.Scambio1`) | Icona `app.scambio.Scambio-…-symbolic` |
|---|---|---|
| `not_configured` | `DeviceAddress = ""` | `unavailable` |
| `unavailable` | `State = unavailable` | `unavailable` (occhiali tenui + ×) |
| `connecting` | `State = connecting` | `connecting` (una lente piena + puntini) |
| `releasing` | `State = releasing` | `connecting` |
| `on_pc_playing` | `State = on_pc` ∧ `AudioActive` | `on-pc` (lenti piene + monitor) |
| `on_pc_idle` | `State = on_pc` ∧ `IdleReleaseAt > 0` | `on-pc` |
| `on_pc` | `State = on_pc` | `on-pc` |
| `priority` | `State = released` ∧ `IphonePriority` | `priority` (occhiali + lucchetto) |
| `released` | `State = released` | `released` (occhiali + telefono) |
| errore attivo | §5.4, salvo le regole in `error_overlay.skip_rules` | `error` (occhiali + punto esclamativo rosso) |

## 4. Menu del tray (definitivo)

| # | Voce | Tipo | Note |
|---|---|---|---|
| 1 | riga di stato: «{device} — sul PC» | disabilitata, senza icona | `header` della regola (decisione 78: dbusmenu cerca le icone nel tema di sistema) |
| 2 | dettaglio: «Torna all'iPhone tra 2 min» | disabilitata | `detail`; con l'errore attivo, il testo dell'errore (il rosso c'è solo nell'icona) |
| 3 | separatore | | |
| 4 | «Passa al PC» / «Lascia all'iPhone» | normale | disabilitata se non disponibile |
| 5 | «Priorità iPhone» | casella | |
| 6 | separatore | | |
| 7 | «Impostazioni…» | normale | apre la finestra (spec 04; era nascosta, decisione 81) |
| 8 | «Esci da Scambio» | normale | ferma il demone (decisione 79) |

Limite accettato: l'API non espone `pending`, quindi durante uno switch annullato a metà
(`connecting` con rilascio in attesa, `releasing` con presa in attesa) la voce 4 può mostrare la
direzione opposta a quella in corso, per al massimo `connect_timeout_seconds`.

## 5. Contratto

Codex usa **solo** i nomi qui sotto; se gliene serve uno nuovo lo chiede nel report. I dati di
presentazione stanno in `design/ui/tray.json` (schema 1), che il codice carica e valida
all'avvio (decisione 75); un campo o un valore fuori dal vocabolario qui sotto è un errore.

### 5.1 File di design caricati a runtime

| File | Uso |
|---|---|
| `design/icons/` | `IconThemePath` del tray (contiene `hicolor/` con `index.theme`) |
| `design/icons/hicolor/scalable/apps/app.scambio.Scambio.svg` | `app_icon` delle notifiche, come percorso assoluto |
| `design/ui/tray.json` | presentazione |
| `design/i18n/{it,en,de}.po` | compilati in `.mo` (dominio `scambio`) da `make i18n`; mai a mano |
| `design/ui/settings-window.blp` | compilato in `build/ui/settings-window.ui` con `blueprint-compiler` 0.12 (`make ui`, dipendenza di sviluppo, decisione 106); la finestra carica il `.ui` |
| `design/style/scambio.css` | CSS della finestra (`Gtk.CssProvider`, priorità applicazione) |
| `design/desktop/app.scambio.Scambio.desktop.in` | lanciatore: `make install-user` sostituisce `@EXEC@` (percorso assoluto di `scambio`) e `@ICON@` (percorso assoluto dell'icona a colori) e lo installa come `~/.local/share/applications/app.scambio.Scambio.desktop` |

Il demone non scrive fuori da `~/.config/scambio/` e `~/.local/share/scambio/` (decisione 76):
icone, cataloghi e `.ui` si leggono da dove sta il pacchetto. Solo `make install-user` installa
l'unità systemd, il lanciatore `.desktop` e il file di servizio D-Bus della finestra (decisione 106). `design/` è fuori dal gate
`make check` (ruff e mypy non lo guardano; i test lo leggono).

### 5.2 `tray.json`: vocabolario

- `sni`: `id`, `category`, `title` → proprietà SNI `Id`, `Category`, `Title`.
- `icons`: chiave logica → nome dell'icona (file `<nome>.svg` in `hicolor/scalable/status/`).
- `presentation[]`: `id`; `when` con chiavi solo fra `state` (stringa), `device_configured`,
  `audio_active`, `iphone_priority`, `idle_release` (booleani); `icon` (chiave di `icons`);
  `header`, `detail` (chiavi di testo); facoltativi `detail_soon`, `tooltip_detail`.
- `error_overlay`: `icon`, `skip_rules` (id di regole), `detail` (codice d'errore → chiave).
- `menu[]`: `id` (int, > 0; la radice 0 è implicita), `name`, `type` (`"separator"` o assente =
  standard), `enabled` (bool, default vero), `enabled_when` (`"available"` = `State ≠ unavailable`
  ∧ `DeviceAddress ≠ ""`), `visible` (bool, default vero), `label` (chiave, oppure `@header` /
  `@detail`, oppure oggetto `{to_pc, to_phone}`), `action` (GAction di §5.5), `toggle_type`
  (`"checkmark"`), `toggle_state` (`"iphone_priority"`), `theme_icon` (nome d'icona del tema di
  sistema, non un file di `design/`).
- `notifications`: `app_name`, `expire_timeout` (int32), `urgency` (byte), `category`
  (`error`/`priority` → stringa); `errors` e `priority` (voci con `family`, `title`, `body`,
  facoltativi `action`, `once_per_run`, `startup_only`, `transient`); `actions` (`label`, `call` ∈
  {`Switch`, `open-config-file`}, facoltativo `valid_when` con `state`, `state_in`,
  `iphone_priority`).

### 5.3 StatusNotifierItem (`/StatusNotifierItem`)

Dalla spec 05 (decisione 154): esportato su una connessione di sessione dedicata al tray e registrato
presso il watcher col solo percorso `/StatusNotifierItem` (nessun nome ben noto); nascondere l'icona
chiude la connessione.

| Proprietà | Valore |
|---|---|
| `Id`, `Category`, `Title` | da `tray.json` → `sni` |
| `Status` | `Active`; `NeedsAttention` con l'errore attivo |
| `IconName` | icona della regola (o `error`) |
| `AttentionIconName` | icona `error` |
| `IconThemePath` | percorso assoluto di `design/icons` (dati installati, §3.1.1 spec 05); nel Flatpak tradotto nel percorso dell'host (decisione 154) |
| `ToolTip` (`(sa(iiay)ss)`) | (`IconName`, [], `Title`, `header` + `\n` + testo): testo = errore se attivo, altrimenti `tooltip_detail` se c'è, altrimenti `detail` |
| `ItemIsMenu` | `true` |
| `Menu` | `/MenuBar` |

Metodo `Activate`: risponde **sempre** con l'errore D-Bus `org.freedesktop.DBus.Error.NotSupported`
e nient'altro (decisione 85): Plasma 5.27 ignora `ItemIsMenu`, al clic sinistro chiama `Activate` e apre
il menu solo se la chiamata fallisce (M14). Su Plasma 6 il clic sinistro apre il menu senza chiamare `Activate` (M21): la regola
resta per Plasma 5.27 (decisione 141). Metodi `SecondaryActivate`, `ContextMenu`, `Scroll`:
nessun effetto. `ProvideXdgActivationToken` (chiamato da Plasma) non si implementa. Segnali
`NewIcon`, `NewAttentionIcon`, `NewToolTip`, `NewTitle`, `NewStatus(s)` solo quando il valore
cambia. Testi del tooltip con `&`, `<`, `>` sostituiti dalle entità (Plasma interpreta il
markup).

### 5.4 Menu dbusmenu (`/MenuBar`, `com.canonical.dbusmenu`, versione 3)

| id | `name` | Proprietà dbusmenu | Testo (chiave) | Azione |
|---|---|---|---|---|
| 0 | radice | `children-display = "submenu"` | — | — |
| 1 | `status-header` | `enabled = false` | `@header` | — |
| 2 | `status-detail` | `enabled = false` | `@detail` | — |
| 3, 6 | `separator-*` | `type = "separator"` | — | — |
| 4 | `switch` | `enabled` da `enabled_when` | `tray-action-to-phone` se `State` ∈ {`on_pc`, `connecting`}, altrimenti `tray-action-to-pc` | `app.switch` |
| 5 | `priority` | `toggle-type = "checkmark"`, `toggle-state` int32 0/1 da `IphonePriority` | `tray-action-priority` | `app.toggle-priority` |
| 7 | `settings` | `icon-name = "preferences-system"` | `tray-action-settings` | `app.open-settings` |
| 8 | `quit` | `icon-name = "application-exit"` | `tray-action-quit` | `app.quit` |

- Etichette: ogni `_` del testo si raddoppia (dbusmenu lo userebbe come mnemonico).
- `GetLayout` porta una revisione (uint32) che cresce a ogni `LayoutUpdated`; `LayoutUpdated`
  solo se cambia `visible`; per testi, `enabled` e `toggle-state` basta `ItemsPropertiesUpdated`.
- `AboutToShow(id) → b` e `AboutToShowGroup(ai) → (ai updatesNeeded, ai idErrors)`; sulla radice
  ricalcolano i testi che dipendono dall'ora e segnano l'errore come **visto**. Anche
  `Event(0, "opened", …)` vale come visto (alcuni host non chiamano `AboutToShow`).
- `Event(id, "clicked", …)` e `EventGroup` attivano la GAction della voce; voci disabilitate o
  nascoste ignorano l'evento.

Testi calcolati all'apertura: `tray-detail-idle` con `{minutes}` = ⌈(`IdleReleaseAt` − ora) /
60 000 000 µs⌉ (`IdleReleaseAt` in µs dall'epoch, ora = `GLib.get_real_time()`); con ≤ 60 s
rimasti (anche se già nel passato) si usa `detail_soon`. Il tooltip usa `tray-detail-idle-at`
con `{time}` = `HH:MM` locale di `IdleReleaseAt`, aggiornato ai cambi di proprietà.

### 5.5 Azioni (`Gio.SimpleActionGroup` nel demone; `Gio.SimpleAction` dell'applicazione nella finestra)

| GAction | Dove | Spec | Effetto |
|---|---|---|---|
| `app.switch` | tray, finestra | 03, 04 | `Switch()` |
| `app.toggle-priority` | tray | 03 | `SetPriority(not IphonePriority)` (la finestra usa `priority_row`, §5.10) |
| `app.quit` | tray | 03 | `Quit()` (decisione 79) |
| `app.open-settings` | tray | 04 | `org.freedesktop.Application.Activate({})` su `app.scambio.Scambio.Settings`, oggetto `/app/scambio/Scambio/Settings`, con avvio automatico (attivazione D-Bus); se il nome non è attivabile (`ServiceUnknown`) una riga `warning` nel log («eseguire make install-user») e nient'altro: nessun processo lanciato dal demone, che lo legherebbe al proprio gruppo |
| `app.change-shortcut` | finestra | 04 | apre `systemsettings://kcm_keys/app.scambio.Scambio` con l'app predefinita per l'URI (solo con `ShortcutBackend = kglobalaccel`) |
| `app.open-config` | finestra | 04 | apre `~/.config/scambio/config.toml` con l'app predefinita (`Gtk.FileLauncher`) |
| `app.start-daemon` | finestra | 04 | `StartUnit("scambio.service", "replace")` del gestore utente di systemd (`org.freedesktop.systemd1`) |

### 5.6 Notifiche (`tray.json` → `notifications`, decisione 70)

Parametri: `app_name`, `app_icon` = percorso assoluto dell'icona a colori, `expire_timeout`,
hint `urgency` (`y`), `category` (`s`), `transient` (`b`) dove indicato; chiamate con
`NO_AUTO_START`. Corpo con `&`, `<`, `>` sostituiti dalle entità. Una notifica per **famiglia**
(`grab`, `release`, `availability`, `setup`, `priority`): la nuova sostituisce quella aperta della
stessa famiglia (`replaces_id`); l'id si azzera su `NotificationClosed`. `ActionInvoked` e
`NotificationClosed` si considerano solo per gli id emessi da Scambio.

| Origine | Chiavi titolo / corpo | Pulsante |
|---|---|---|
| `Error(connect_failed \| connect_timeout)` | `notify-grab-failed-*` | Riprova → `Switch()` se `State = released` |
| `Error(sink_timeout \| sink_lost)` | `notify-sink-lost-*` | Riprova, come sopra |
| `Error(disconnect_failed)` | `notify-release-failed-*` | — (uno switch accenderebbe la Priorità iPhone) |
| `Error(device_unavailable)` | `notify-unavailable-*` | — |
| `Error(device_not_configured)` (una volta per avvio) | `notify-not-configured-*` | Apri il file → `config.toml` |
| `Error(config_invalid)` | `notify-config-invalid-*` | Apri il file |
| `audio_backend_down` **solo all'avvio** | `notify-audio-down-*` | — |
| `IphonePriority` → `true` con switch | `notify-switch-to-phone-*` | Annulla → `Switch()` se `IphonePriority` ∧ `State` ∈ {`releasing`, `released`} |
| `IphonePriority` → `false` con switch | `notify-switch-to-pc-*` | — |
| `IphonePriority` → `true` senza switch | `notify-priority-on-*` | — |
| `IphonePriority` → `false` senza switch | `notify-priority-off-*` | — |

- **Errori all'avvio**: alla prima lettura delle proprietà, un `LastError` non vuoto vale come
  un segnale `Error(LastError)` (così `device_not_configured` e un `pactl` assente, emessi prima
  che la UI esista, si notificano). `audio_backend_down` si notifica **solo** in questo caso: a
  runtime (riavvio di PipeWire) Scambio riprova da solo e non disturba.
- **Con switch**: il demone emette `Transition` e poi `PropertiesChanged` nello stesso passo; il
  cambio di `IphonePriority` è «con switch» se l'ultimo segnale ricevuto dal demone prima di
  quel `PropertiesChanged` è un `Transition(_, _, "switch")`. Uno switch durante `connecting` o
  `releasing` cambia la priorità senza `Transition`: vale come «senza switch».
- **Cambi chiesti dalla UI** (menu, pulsanti delle notifiche; la finestra è un altro processo e
  segue la regola «finestra in primo piano» qui sotto): il demone
  pubblica `PropertiesChanged` prima di rispondere al metodo, quindi un cambio di
  `IphonePriority` ricevuto fra l'invio di una chiamata della UI e la sua risposta è «proprio» e
  non si notifica. Nessun timer.
- **Pulsanti**: l'azione si esegue solo se `valid_when` è vero nel momento del clic; altrimenti la
  notifica si chiude senza fare nulla. `default` (clic sul corpo) segna solo l'errore visto.
  «Apri il file»: portal `org.freedesktop.portal.OpenURI.OpenURI` asincrono con l'URI
  `file://` di `config.toml`; un errore va nel log a livello `debug`.
- **Errore attivo**: si accende a ogni `Error(code)` con `code` in `error_overlay.detail` (non
  si valuta `LastError` dalla cache in quel momento: arriva dopo). Si spegne quando l'utente lo
  **vede** (menu aperto, §5.4; `ActionInvoked` o `NotificationClosed` con motivo 2 della sua
  notifica) o sul **fronte** di `LastError` da non vuoto a `""`. Finché è attivo e non visto,
  lo stesso codice non si rinotifica.
- **Finestra in primo piano** (decisione 107): finché il nome `app.scambio.Scambio.Settings.Active`
  ha un proprietario (`Gio.bus_watch_name`; la finestra lo possiede solo mentre è attiva), le
  notifiche della famiglia `priority` non partono; gli errori sì.
- **Mai** per prese, rilasci, blocco, sospensione, connessioni dall'applet.

### 5.7 API D-Bus usata dalle UI

Tutta `app.scambio.Scambio1` della spec 01 §3.2.1 (invariata dalla spec 02), più:

| Metodo nuovo | Firma | Effetto |
|---|---|---|
| `Quit` | `() → ()` | (spec 03) risponde, poi esegue l'arresto ordinato di `SIGTERM` (spec 01 §3.1.6 e spec 02) e termina con 0: systemd non lo riavvia fino al prossimo login |
| `SetConfig` | `(a{sv}) → ()` | (spec 04) scrive in `config.toml` le chiavi di §5.8 «finestra» e le applica come `Reload` (spec 04 §3.1.2); errori `ConfigInvalid`, `DeviceBusy`, `RestartRequired` |
| `ListDevices` | `() → a(ss)` | (spec 04) dispositivi accoppiati con un profilo audio: (indirizzo, nome) |
| `RetryShortcut` | `() → ()` | (spec 04) ritenta la registrazione della scorciatoia (§5.11) |

| Proprietà nuova (spec 04) | Tipo | Significato |
|---|---|---|
| `Config` | a{sv} | valori in vigore delle chiavi «finestra» di §5.8 più `shortcut.preferred` (sola lettura), con il nome completo (`"policy.release_idle_seconds"` → `i`, ecc.) |
| `Shortcut` | s | tasto legato, come acceleratore GTK (`<Super>g`); `""` se nessuno o non rappresentabile |
| `ShortcutLabel` | s | testo leggibile quando `Shortcut` non basta: `trigger_description` del portal, oppure (KGlobalAccel) la forma alla Qt di un tasto fuori dalla tabella di conversione; altrimenti `""` |
| `ShortcutState` | s | `active` \| `conflict` \| `unbound` \| `unsupported` |
| `ShortcutOwner` | s | con `conflict`, nome dell'azione che usa il tasto preferito; altrimenti `""` |
| `ShortcutBackend` | s | `kglobalaccel` \| `portal` \| `none` |

Errore nuovo: `app.scambio.Scambio1.Error.DeviceBusy` (cambio di dispositivo con `State` ∈
{`connecting`, `on_pc`, `releasing`}).

Il client delle UI riceve nome del bus e percorso come parametri (i test usano `app.scambio.Test`).

### 5.8 Configurazione (`[ui]`)

| Chiave | Tipo | Default | Effetto |
|---|---|---|---|
| `ui.language` | str | `"auto"` | `auto` = primo valore supportato fra `LANGUAGE` (lista separata da `:`), `LC_ALL`, `LC_MESSAGES`, `LANG`, ignorando `C`/`POSIX`; ripiego `en`. Altrimenti `it`/`en`/`de` |
| `ui.tray` | bool | `true` | `false` = nessuna icona (es. GNOME senza estensione) |
| `ui.notifications` | bool | `true` | `false` = nessuna notifica |
| `shortcut.preferred` | str | `"<Super>g"` | tasto preferito della scorciatoia (§5.11); `""` = nessuna scorciatoia |

Chiavi **«finestra»** (modificabili con `SetConfig`, esposte in `Config`): `device.address`,
`policy.release_idle_seconds`, `ui.tray`, `ui.notifications`, `ui.language`. `Config` espone anche
`shortcut.preferred`, ma `SetConfig` non lo accetta. Le altre si cambiano solo nel file.

Su `casa` l'ambiente utente di systemd ha `LANG=it_IT.UTF-8` (verificato il 2026-10-05).

### 5.9 Testi

Chiavi gettext simboliche (`msgid` = chiave), cataloghi `design/i18n/{it,en,de}.po`; `en.po`
è obbligatorio come gli altri. Segnaposto `{device}`, `{minutes}`, `{time}`, `{error}` con
`str.format` (elencati nei commenti `#.` del catalogo). `{device}` = `DeviceName`, oppure
`tray-device-fallback` («il dispositivo») se vuoto; **solo** quando il testo comincia con quel
ripiego la sua prima lettera diventa maiuscola (mai altrove: «iPhone» resta «iPhone»). Una chiave
mancante in un catalogo è un errore di test.

Famiglie di chiavi: `tray-*` (menu e tooltip), `notify-*` (notifiche), `cli-*` (riga di
comando, sostituiscono i msgid inglesi della decisione 27; gli errori D-Bus noti hanno una chiave
propria, `cli-dbus-error` resta per quelli imprevisti), `session-inhibit-reason` (motivo
dell'inibitore di logind), `config-*` (commenti del modello di `config.toml`, nella lingua del
momento in cui il demone crea il file, decisione 84; una chiave per ogni chiave di configurazione
commentata, più `config-header` e `config-backend-header`), `settings-*` (finestra, spec 04),
`shortcut-*` (nomi registrati nel servizio scorciatoie del desktop, spec 04). Segnaposto nuovi:
`{shortcut}`, `{owner}`, `{version}`. Stati, codici d'errore e i valori
stampati da `scambio status/switch/priority` restano stringhe stabili non tradotte.

### 5.10 Finestra impostazioni (definitiva, spec 04)

Layout `design/ui/settings-window.blp` (template `ScambioSettingsWindow`), stile
`design/style/scambio.css`, mock approvato il 2026-10-07 (decisione 100). Le modifiche valgono
subito, senza «Salva» (decisione 107). Nessun timer, nessuna finestra di dialogo modale.

**Avvio.** `scambio settings` chiama `GLib.set_prgname("app.scambio.Scambio.Settings")` prima di
GTK (classe della finestra = `StartupWMClass` del `.desktop`), crea `Adw.Application`
`app.scambio.Scambio.Settings` (istanza unica: una seconda apertura presenta la finestra
esistente) e risolve la lingua da `ui.language` letto da `config.toml` in sola lettura, come la CLI
(spec 03 §3.1.6). **Traduzione del layout** (decisione 109): legge `build/ui/settings-window.ui`,
sostituisce il testo di ogni elemento con `translatable="yes"` (proprietà e voci di `StringList`)
con `Translator.tr(chiave)` (escape XML), toglie gli attributi `translatable`/`context`/`comments` e
`translation-domain`, poi carica il risultato con `Gtk.Template(string=…)`. Aggiunge `design/icons`
al percorso delle icone e carica il CSS.

**Client.** Lo stesso `ui/client.py` del tray, esteso (compatibile col tray): `call(method,
params, on_reply=None, on_error=None)` con le callback di risposta ed errore; lettura iniziale che
con il demone assente non resta bloccata; un `Gio.bus_watch_name` su `app.scambio.Scambio` che a
ogni ricomparsa rilegge tutte le proprietà e riaggancia i segnali.

**Chiamate in corso** (niente echi, niente salti all'indietro): per ogni chiave o proprietà con una
chiamata della finestra in corso si ignorano gli aggiornamenti di quella chiave; alla risposta
(o all'errore) il widget si riallinea al valore in vigore. Un cambio fatto dal codice per
riallinearsi non produce chiamate.

| ID | Widget | Regola |
|---|---|---|
| `toast_overlay` | `Adw.ToastOverlay` | avvisi brevi (chiavi `settings-device-restarting`, `settings-language-next-open`, `settings-error-*`) |
| `daemon_banner` | `Adw.Banner` | visibile quando `app.scambio.Scambio` non ha proprietario, **tranne** dopo una risposta di successo a un cambio di dispositivo: allora resta nascosto finché il nome ricompare; pulsante → `app.start-daemon` |
| `status_icon` | `Gtk.Image` | icona della regola di `tray.json` → `presentation` (stesse regole del tray, **senza** errore sovrapposto); classe `scambio-dim` con l'icona `unavailable`. Demone assente: icona `unavailable` con `scambio-dim` |
| `status_row` | `Adw.ActionRow` | titolo = `header`, sottotitolo = `detail` della regola (minuti calcolati quando cambia una proprietà e quando la finestra torna attiva). Demone assente: titolo `settings-status-unknown`, sottotitolo vuoto |
| `switch_button` | `Gtk.Button` | `app.switch`; testo `tray-action-to-phone` se `State` ∈ {`on_pc`, `connecting`}, altrimenti `tray-action-to-pc`; la sensibilità si governa abilitando l'azione `app.switch` quando «available» (§5.2) e il demone c'è |
| `priority_row` | `Adw.SwitchRow` | `active` = `IphonePriority`; un cambio dell'utente chiama `SetPriority(active)` |
| `device_row` | `Adw.ComboRow` | modello = nomi di `ListDevices()` (letto all'apertura, alla ricomparsa del demone e quando cambiano `DeviceAddress` o `DeviceName`); se l'indirizzo configurato manca dall'elenco si aggiunge una voce col solo indirizzo; con `DeviceAddress = ""` in testa c'è la voce `settings-device-none`, selezionata e **non sceglibile** (se l'utente la riseleziona non parte nessuna chiamata). Sensibile solo con `State` ∈ {`released`, `unavailable`}, altrimenti sottotitolo `settings-device-busy`; elenco vuoto → sottotitolo `settings-device-empty`. Scelta di un altro dispositivo → `SetConfig({"device.address"})`; successo → avviso `settings-device-restarting` |
| `release_idle_row` | `Adw.SpinRow` 1–60 | valore = `max(1, (release_idle_seconds + 30) // 60)`; un cambio dell'utente → `SetConfig({"policy.release_idle_seconds": minuti × 60})` |
| `shortcut_row` | `Adw.ActionRow` | sottotitolo `settings-shortcut-subtitle`; con `conflict` sottotitolo `settings-shortcut-conflict` (`{shortcut}` = `Gtk.accelerator_get_label` di `Config["shortcut.preferred"]`, `{owner}` = `ShortcutOwner`) e classe `scambio-shortcut-conflict`; con `unsupported` sottotitolo `settings-shortcut-unsupported` |
| `shortcut_label` | `Gtk.ShortcutLabel` | `accelerator` = `Shortcut`; se vuoto mostra `disabled-text`: `ShortcutLabel` se non vuoto, altrimenti `settings-shortcut-unbound`; nascosto con `unsupported` e con il demone assente |
| `shortcut_change_button` | `Gtk.Button` | `app.change-shortcut`; visibile solo con `ShortcutBackend = kglobalaccel` |
| `tray_row`, `notifications_row` | `Adw.SwitchRow` | `ui.tray`, `ui.notifications` da `Config`; cambio → `SetConfig` |
| `language_row` | `Adw.ComboRow` | indici 0–3 = `auto`, `it`, `en`, `de`; cambio → `SetConfig({"ui.language"})` e avviso `settings-language-next-open` |
| `config_row`, `config_open_button` | riga + pulsante | `app.open-config` |
| `version_label` | `Gtk.Label` | `settings-version` con `{version}` = `Version` (o la versione del pacchetto se il demone è fermo) |
| `status_group`, `device_group`, `shortcut_group`, `general_group` | gruppi | non sensibili con il demone assente |

**Finestra in primo piano.** Mentre `is-active` è vero la finestra possiede il nome
`app.scambio.Scambio.Settings.Active` (lo rilascia quando diventa inattiva e alla chiusura): serve
alla regola delle notifiche di §5.6. Quando torna attiva, se `ShortcutState = conflict` chiama
`RetryShortcut()` (anche all'apertura): così, liberato il tasto in Impostazioni di sistema, basta
tornare alla finestra.

**Errori.** `ConfigInvalid` → avviso `settings-error-invalid` e il widget torna al valore di
`Config`; `DeviceBusy` → avviso `settings-device-busy` e selezione ripristinata;
`RestartRequired` → avviso `settings-error-restart-required` (il file è già scritto; la selezione
resta quella nuova); altri errori → `settings-error-generic` con `{error}` = ultimo segmento del
nome D-Bus dell'errore.

### 5.11 Scorciatoia globale (spec 04, decisioni 102–103)

- **Scelta del meccanismo** all'avvio del demone: `kglobalaccel` se `org.kde.kglobalaccel` ha un
  proprietario oppure `XDG_CURRENT_DESKTOP` contiene `KDE`; altrimenti `portal` se il portal espone
  `org.freedesktop.portal.GlobalShortcuts`; altrimenti `none` (`ShortcutState = unsupported`). Se
  con `kglobalaccel` i metodi a interi rispondono con un errore di metodo sconosciuto (Plasma 6
  non misurato) si passa al portal.
- **Nomi** registrati: componente `app.scambio.Scambio` con nome `shortcut-component-name`; azione
  `switch` con nome `shortcut-switch-name` (descrizione per il portal), nella lingua del momento
  (una nuova `doRegister` aggiorna i nomi, M18).
- **Effetto**: la pressione (`globalShortcutPressed` o `Activated` del portal per `switch`) chiama
  `Switch()` sull'API pubblica del demone, in modo asincrono e con lo stesso client della UI
  (invariante di `AGENTS.md`); `DeviceUnavailable` → riga `info` nel log. Le notifiche «con
  switch» di §5.6 valgono come per `scambio switch`.
- **`shortcut.preferred = ""`** o non valido: nessuna registrazione (`unbound`; se non valido anche
  una riga `warning`).
- Regole di dettaglio (autoload, conflitto, memoria in `state.json`, conversione dei tasti): spec 04
  §3.1.1.

## 6. Lingue

Chiavi gettext; cataloghi `design/i18n/{it,en,de}.po` (dominio `scambio`). Lingua di sistema di
default, forzabile con `ui.language`.
