# 05 — Contesto UI e contratto design ↔ codice

Redatto da Claude il 4 ottobre 2026; completato il 5 ottobre 2026 con il mock approvato da GM
(tela «Scambio — mock UI», decisioni 70–81). Il design è di Claude (decisione 10): i file stanno
in `design/` e Codex li collega senza modificarli. Le parti marcate **bozza (spec 04)** danno la
direzione della finestra e diventano definitive con la spec 04.

## 1. Principi

- **Invisibile quando funziona.** Prese e rilasci automatici non si notificano: lo dice l'icona.
  Si notifica solo l'essenziale (decisione 70): errori, e la Priorità iPhone cambiata da fuori
  dalla UI (scorciatoia, CLI). Scambio non controlla il telefono: la musica dell'iPhone non è
  affar suo (spec 02 §4).
- **Lo stato si legge dall'icona** senza aprire nulla: dove sta il dispositivo e se la Priorità
  iPhone è attiva (variante B, decisione 72: occhiali + emblema telefono/monitor/lucchetto).
- **Nativo dove possibile**: icone simboliche che seguono il tema (misurato su Plasma 5.27 scuro,
  M11); menu e notifiche disegnati dal desktop; finestra libadwaita (spec 04).
- **Tastiera prima del mouse**: ogni azione del tray ha un equivalente da scorciatoia o CLI.
- **Nessun timer nella UI** (decisione 77): niente animazioni, niente conti alla rovescia che
  ticchettano; i testi che dipendono dall'ora si calcolano quando il menu si apre.
- Testi brevi, in it/en/de; tono neutro e amichevole. Per ora «iPhone» nei testi (decisione 73).

## 2. Superfici

| Superficie | Tecnologia | Processo | Spec |
|---|---|---|---|
| Icona tray + menu | StatusNotifierItem + dbusmenu su Gio, senza GTK | demone (decisione 74) | 03 |
| Notifiche | `org.freedesktop.Notifications` su Gio | demone | 03 |
| Finestra impostazioni | GTK4 + libadwaita, Blueprint in `design/ui/` | processo separato, su richiesta | 04 |
| Scorciatoia | portal GlobalShortcuts, default Meta+G | demone | 04 |

Clic sinistro e destro sull'icona aprono lo stesso menu (`ItemIsMenu = true`, decisione 71).
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
| 7 | «Impostazioni…» | normale | **nascosta** fino alla spec 04 (decisione 81) |
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

Nessun file viene installato fuori da `~/.config/scambio/` e `~/.local/share/scambio/`
(decisione 76): icone e cataloghi si leggono da dove sta il pacchetto. `design/` è fuori dal gate
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

| Proprietà | Valore |
|---|---|
| `Id`, `Category`, `Title` | da `tray.json` → `sni` |
| `Status` | `Active`; `NeedsAttention` con l'errore attivo |
| `IconName` | icona della regola (o `error`) |
| `AttentionIconName` | icona `error` |
| `IconThemePath` | percorso assoluto di `design/icons` |
| `ToolTip` (`(sa(iiay)ss)`) | (`IconName`, [], `Title`, `header` + `\n` + testo): testo = errore se attivo, altrimenti `tooltip_detail` se c'è, altrimenti `detail` |
| `ItemIsMenu` | `true` |
| `Menu` | `/MenuBar` |

Metodi `Activate`, `SecondaryActivate`, `ContextMenu`, `Scroll`: nessun effetto. Segnali
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
| 7 | `settings` | `icon-name = "preferences-system"`, `visible = false` | `tray-action-settings` | `app.open-settings` |
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

### 5.5 Azioni (`Gio.SimpleActionGroup`; nomi condivisi con la finestra della spec 04)

| GAction | Spec | Effetto (API) |
|---|---|---|
| `app.switch` | 03 | `Switch()` |
| `app.toggle-priority` | 03 | `SetPriority(not IphonePriority)` |
| `app.quit` | 03 | `Quit()` (metodo nuovo, decisione 79) |
| `app.open-settings` | 04 | apre la finestra |
| `app.change-shortcut` | 04 | cambia la scorciatoia |

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
- **Cambi chiesti dalla UI** (menu, pulsanti delle notifiche; finestra nella spec 04): il demone
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
- **Mai** per prese, rilasci, blocco, sospensione, connessioni dall'applet.

### 5.7 API D-Bus usata dalle UI

Tutta `app.scambio.Scambio1` della spec 01 §3.2.1 (invariata dalla spec 02), più:

| Metodo nuovo | Firma | Effetto |
|---|---|---|
| `Quit` | `() → ()` | risponde, poi esegue l'arresto ordinato di `SIGTERM` (spec 01 §3.1.6 e spec 02) e termina con 0: systemd non lo riavvia fino al prossimo login |

Il client delle UI riceve nome del bus e percorso come parametri (i test usano `app.scambio.Test`).

### 5.8 Configurazione (`[ui]`)

| Chiave | Tipo | Default | Effetto |
|---|---|---|---|
| `ui.language` | str | `"auto"` | `auto` = primo valore supportato fra `LANGUAGE` (lista separata da `:`), `LC_ALL`, `LC_MESSAGES`, `LANG`, ignorando `C`/`POSIX`; ripiego `en`. Altrimenti `it`/`en`/`de` |
| `ui.tray` | bool | `true` | `false` = nessuna icona (es. GNOME senza estensione) |
| `ui.notifications` | bool | `true` | `false` = nessuna notifica |

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
dell'inibitore di logind), `settings-*` (finestra, spec 04). Stati, codici d'errore e i valori
stampati da `scambio status/switch/priority` restano stringhe stabili non tradotte.

### 5.10 Finestra impostazioni — bozza (spec 04)

`design/ui/settings-window.blp` (template `ScambioSettingsWindow`, compila con
blueprint-compiler 0.12) e `design/style/scambio.css`. ID: `status_row`, `status_icon`,
`switch_button`, `priority_row`, `device_row`, `release_idle_row`, `shortcut_row`,
`shortcut_label`, `shortcut_change_button`, `autostart_row`, `tray_row`, `language_row`,
`advanced_row`, `grab_delay_row`, `ignored_apps_row`, `version_label`. Titolo e sottotitolo di
`status_row` li imposta il codice con le stesse chiavi del tray. Da decidere nella spec 04: elenco
dei dispositivi accoppiati (metodo D-Bus nuovo), «Avvia all'accesso», scrittura della
configurazione, unità del rilascio (la configurazione va da 10 a 3600 s, la bozza mostra minuti).

## 6. Lingue

Chiavi gettext; cataloghi `design/i18n/{it,en,de}.po` (dominio `scambio`). Lingua di sistema di
default, forzabile con `ui.language`.
