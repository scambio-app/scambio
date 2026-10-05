# Spec 03 — Tray e notifiche

Stato: approvata (GM, 2026-10-05) · Autore: Claude · Data: 2026-10-05

## 1. Obiettivo

Scambio si vede e si comanda dal pannello: un'icona nel tray dice dove sta il dispositivo e se la
Priorità iPhone è attiva; il suo menu permette lo switch, la Priorità iPhone e l'uscita; le
notifiche del desktop avvisano solo degli errori e dei cambi di Priorità iPhone partiti fuori
dalla UI. Tutti i testi visibili (tray, notifiche, CLI, motivo dell'inibitore) sono in it/en/de.

**Prova visibile.** Su `casa` (KDE Plasma 5.27, Breeze scuro), con gli occhiali sull'iPhone:
nel tray c'è l'icona «occhiali + telefono». GM avvia un video: l'icona diventa «lenti piene +
monitor» senza alcuna notifica; aprendo il menu legge «Oakley Meta 002Z — sul PC» e, messo in
pausa il video, «Torna all'iPhone tra 2 min». Dal menu sceglie «Lascia all'iPhone»: icona
«occhiali + lucchetto», casella «Priorità iPhone» spuntata, nessuna notifica. Da terminale
`scambio switch`: gli occhiali tornano al PC e arriva «Oakley Meta 002Z sul PC — Priorità iPhone
disattivata.». Con gli occhiali chiusi nella custodia e un video avviato arriva «Oakley Meta 002Z
non raggiungibile» con «Riprova» e l'icona d'errore, che sparisce aprendo il menu. «Esci da
Scambio» ferma il demone (`systemctl --user is-active scambio` → `inactive`).

## 2. Decisioni applicabili

- Prodotto: 6–7 (Priorità iPhone, switch intelligente), 9–10 (una sola app, design di Claude),
  14 (it/en/de), 27 e 29b (testi CLI e inibitore tradotti con questa spec), 48 (avvio al login).
- Di questa spec: **70–84** in `docs/decisions.md` (la 82 è superata dalla 84).
- Contratto: `docs/context/05-ui-context.md` §3–§5 (**fonte dei nomi e delle regole di
  dettaglio**: questa spec non li ripete tutti). Mock approvato da GM il 2026-10-05.
- API del demone: spec 01 §3.2.1, invariata dalla spec 02 (02 §3.2.1).
- Misure: **M11** (icone via `IconThemePath` su Plasma 5.27, tema scuro: trovate e ricolorate
  solo da `hicolor/scalable/status`); su `casa` lo `StatusNotifierWatcher` è di `kded5`, il
  server delle notifiche è `plasmashell`; ambiente utente di systemd con `LANG=it_IT.UTF-8`.
- **Numerazione**: le decisioni tecniche di Codex per questa spec partono da **90** (70–89 sono
  riservate alla chat di design).

## 3. Dettagli

### 3.1 Comportamento

#### 3.1.1 Moduli

```
src/scambio/
  paths.py          dove stanno design/ e i cataloghi compilati (repo in sviluppo; override
                    SCAMBIO_DESIGN_DIR / SCAMBIO_LOCALE_DIR solo per i test)
  i18n.py           PURO (niente gi, mypy --strict): lingua, gettext dominio "scambio",
                    tr(key, **values) con le regole di 05 §5.9; usato da UI, CLI e core
  ui/
    __init__.py     start_ui(connection, config, bus_name, path) → Ui con apply_config() e stop()
    client.py       ScambioClient: Gio.DBusProxy (nome e percorso come parametri), cache delle
                    proprietà, segnali nell'ordine di arrivo, chiamate asincrone marcate «proprie»
    presentation.py PURO (niente gi, mypy --strict): valida tray.json (05 §5.2) e calcola il
                    modello da proprietà + errore attivo + ora (argomento, mai letta dal modulo)
    actions.py      Gio.SimpleActionGroup: app.switch, app.toggle-priority, app.quit
    tray.py         StatusNotifierItem + com.canonical.dbusmenu esportati con Gio
    notify.py       client di org.freedesktop.Notifications e portal OpenURI
```

`ui/` non importa `core/`; `core/` usa solo `i18n.py` (motivo dell'inibitore). XML di
introspezione di SNI e dbusmenu come file del pacchetto, accanto a quello dell'API. Nessun
import di GTK, Gdk o libadwaita in questa spec.

#### 3.1.2 Ciclo di vita (decisione 74)

1. Il demone parte come oggi; dopo aver posseduto il nome ed esportato l'oggetto chiama **sempre**
   `start_ui` (anche con `ui.tray` e `ui.notifications` falsi: la UI resta inerte ma pronta a
   `apply_config`).
2. `start_ui` crea il proxy sullo stesso bus e attende in modo asincrono la prima lettura delle
   proprietà; solo dopo esporta il tray (mai uno stato provvisorio) e applica la regola degli
   **errori all'avvio** (05 §5.6). Verso il proprio nome solo chiamate asincrone.
3. Tray: oggetti `/StatusNotifierItem` e `/MenuBar`; `Gio.bus_watch_name` su
   `org.kde.StatusNotifierWatcher` e `RegisterStatusNotifierItem("/StatusNotifierItem")` a ogni
   comparsa (riavvio di `kded5`). Riavvio di `plasmashell`: l'host rilegge gli item dal watcher,
   Scambio non fa nulla. Watcher assente → nessun tray, una riga `info` nel log.
4. Notifiche: server assente o errore → `debug` nel log, nessun nuovo tentativo; dopo un riavvio
   di `plasmashell` gli id vecchi non valgono più (`replaces_id` di un id sconosciuto crea una
   notifica nuova: va bene).
5. `tray.json` o cataloghi non validi all'avvio → `error` nel log con la causa, nessun tray né
   notifiche; il demone e l'API funzionano come in spec 01–02. Ogni punto d'ingresso della UI
   (segnali, metodi esportati, callback asincrone) è protetto: un'eccezione si registra e non
   interrompe né il demone né le chiamate successive.
6. `Reload()` riuscito → il servizio chiama `ui.apply_config(config)` (decisione 74: la
   configurazione della UI non passa da D-Bus perché sta nello stesso processo). `ui.language` e
   `ui.notifications` valgono subito (lingua: tutte le etichette con `ItemsPropertiesUpdated`,
   tooltip con `NewToolTip`); `ui.tray` false→true esporta e registra il tray, true→false lo
   ritira (`unregister_object`; l'host lo toglie).
7. Arresto (`SIGTERM`, `Quit()`): la UI ritira gli oggetti esportati prima dell'uscita, senza
   ritardarla.

#### 3.1.3 Presentazione

Regole, vocabolario, errore sovrapposto, testi calcolati all'apertura del menu, tooltip: 05 §3,
§5.2–§5.4. In più:
- Errore attivo: stato della UI, aggiornato solo dagli eventi di 05 §5.6 (accensione sul
  segnale `Error`, spegnimento quando visto o sul fronte di `LastError` a `""`).
- Voce switch: testo e abilitazione da 05 §5.4; limite accettato in 05 §4.

#### 3.1.4 Tray

Proprietà, metodi e segnali di 05 §5.3; menu, revisione, mnemonici, `AboutToShow`, `Event` di
05 §5.4. Nessun segnale se il modello non cambia.

#### 3.1.5 Notifiche

Tutto in 05 §5.6: famiglie, `replaces_id`, filtro sugli id propri, errori all'avvio,
`audio_backend_down` solo all'avvio, correlazione «con switch» per ordine dei segnali,
cambi «propri» fra chiamata e risposta (anche per i pulsanti delle notifiche), `valid_when`,
OpenURI, niente rinotifica di un errore ancora attivo e non visto. **Nessun timer** nella UI
(decisione 77).

#### 3.1.6 Lingua e testi (`i18n.py`)

- Lingua da `ui.language` (05 §5.8). Vale per tray, notifiche, CLI e motivo dell'inibitore; il
  motivo è quello della lingua del momento in cui l'inibitore viene preso.
- La CLI legge `ui.language` con `tomllib` in sola lettura: se il file manca o non è valido usa
  `auto`, senza crearlo e senza log.
- Cataloghi: `make i18n` compila i `.po` di `design/i18n/` con `msgfmt` in una cartella di build
  ignorata da git; lo richiamano `make check`, `make run` e `make install-user`. A runtime, `.mo`
  mancanti → `error` all'avvio con la causa («eseguire make i18n») e UI disattivata come al
  §3.1.2 punto 5; la CLI ripiega su `en`, e se manca anche quello stampa la chiave.
- `tr()`: gettext → `str.format(**values)` → maiuscola iniziale solo per il ripiego di
  `{device}` (05 §5.9). Valori inseriti nei testi di tooltip e notifiche: entità per `&<>`.
- **CLI** (decisioni 27, 29b): msgid inglesi → chiavi `cli-*`; `argparse` con `add_help=False` e
  un `-h/--help` con `cli-help-help`; errori D-Bus noti (`DeviceUnavailable`, `ConfigInvalid`,
  `RestartRequired`) → `cli-error-*`; gli altri → `cli-dbus-error` con `{error}` = nome D-Bus.
  Restano in inglese le parole proprie di `argparse` («usage:», «options:», i suoi errori di
  sintassi): decisione 83, approvata da GM.
- **Modello di `config.toml`** (decisione 84): i commenti si scrivono con le chiavi `config-*`
  (05 §5.9) nella lingua risolta al momento della creazione (`auto` dall'ambiente, perché il file
  non esiste ancora): `config-header` in testa, `config-backend-header` sopra `[backend]`
  (le sue chiavi restano senza commento), e un commento per ogni altra chiave secondo la mappa:
  `device.address` → `config-device-address`, `device.profile` → `config-device-profile`,
  `policy.grab_delay_ms` → `config-policy-grab-delay`, `policy.release_idle_seconds` →
  `config-policy-release-idle`, `policy.connect_timeout_seconds` → `config-policy-connect-timeout`,
  `policy.sink_timeout_seconds` → `config-policy-sink-timeout`,
  `policy.sleep_release_timeout_seconds` → `config-policy-sleep-timeout`,
  `policy.unblock_silence_seconds` → `config-policy-unblock`, `policy.resume_delay_ms` (riga
  commentata) → `config-policy-resume-delay`, `audio.ignore_roles` →
  `config-audio-ignore-roles`, `audio.ignore_apps` → `config-audio-ignore-apps`,
  `audio.ignore_players` → `config-audio-ignore-players`, `shortcut.preferred` →
  `config-shortcut-preferred`, `ui.language` → `config-ui-language`, `ui.tray` →
  `config-ui-tray`, `ui.notifications` → `config-ui-notifications`. Il file esistente non si
  riscrive mai; il modello resta TOML valido in ogni lingua (test). Una chiave fuori da
  `[backend]` aggiunta in futuro senza la sua chiave `config-*` è un errore di test (la chiede
  il report).

#### 3.1.7 Uscita (`Quit`, decisione 79)

`app.quit` → `Quit()`. Il servizio risponde subito (`return_value`), poi avvia lo stesso arresto
di `SIGTERM` (spec 01 §3.1.6 più la ripresa dei player della spec 02) e, prima di chiudere il
loop, svuota la connessione (`flush`) così la risposta parte. Uscita 0: con `Restart=on-failure`
systemd non lo riavvia; riparte al login (decisione 48) o con `systemctl --user start scambio`.
Non scollega il dispositivo e non tocca l'instradamento.

#### 3.1.8 Risorse

Nessun polling e **nessun timer** introdotto dalla UI. A riposo CPU ≈ 0 % e RSS del demone
≤ **40 MB**, misurati 10 minuti come nella spec 01, **prima e dopo** la spec (stesso metodo),
con tray e notifiche attivi.

### 3.2 API D-Bus, configurazione, dati

#### 3.2.1 API D-Bus

Aggiunto a `app.scambio.Scambio1` (XML unico): metodo `Quit() → ()` (05 §5.7). Nient'altro
cambia.

#### 3.2.2 Oggetti esportati

| Oggetto | Interfaccia |
|---|---|
| `/StatusNotifierItem` | `org.kde.StatusNotifierItem` (05 §5.3) |
| `/MenuBar` | `com.canonical.dbusmenu` versione 3 (05 §5.4) |

#### 3.2.3 Configurazione

Nuove chiavi `ui.tray` e `ui.notifications` (05 §5.8), con commento nel modello creato dal
demone; `ui.language` passa da «solo validata» ad avere effetto. Claude aggiorna 02 §4.

#### 3.2.4 Build

`make i18n` (msgfmt → cartella di build ignorata). `make check` lo esegue prima dei test e
fallisce con un messaggio chiaro se `msgfmt` manca. `design/` resta fuori da ruff e mypy.
Nessuna dipendenza runtime nuova.

#### 3.2.5 Test (Codex)

- **Presentazione** (tabella): ogni regola di `presentation`; errore sovrapposto per ogni codice
  di `error_overlay` e precedenza di `skip_rules`; minuti con confini in µs (120 000 001 µs → 3;
  120 000 000 → 2; 60 000 001 → 2; 60 000 000 e valori nel passato → `detail_soon`); tooltip con
  l'ora e con l'errore; voce switch in tutti gli stati e disabilitata in `unavailable` e senza
  dispositivo; `toggle-state` 0/1 int32.
- **`tray.json`**: validazione dello schema (05 §5.2) con casi non validi; ogni icona di `icons`
  esiste in `hicolor/scalable/status/`; ogni chiave esiste nei tre cataloghi; ogni `action` è
  in 05 §5.5; ogni codice d'errore della spec 01 §3.2.1 è in `notifications.errors`.
- **Cataloghi**: `msgfmt --check` su it/en/de; stesse chiavi nei tre `.po` e nel `.pot`; ogni
  traduzione usa esattamente i segnaposto di `en.po`; `tr()` con nome vuoto («Il dispositivo …»)
  e con testi che iniziano con «iPhone» (nessuna maiuscola); `DeviceName` con `_`, `&`, `<`.
- **Tray** con dbusmock sul bus privato: finto `StatusNotifierWatcher` (oggetto generico) che
  registra le chiamate; nuova registrazione quando il nome ricompare; `GetLayout` (radice
  `children-display`, revisione), `AboutToShow`, `Event(0,"opened")` (errore visto),
  `Event("clicked")` sulle voci 4, 5, 8 → chiamate al demone (harness della spec 01,
  `app.scambio.Test`); `Event` su voce disabilitata senza effetto; `ItemsPropertiesUpdated` ai
  cambi e nessun segnale se il modello non cambia; `ui.tray` acceso e spento con `Reload`.
- **Notifiche** con il template `notification_daemon` di python-dbusmock (i segnali
  `ActionInvoked` e `NotificationClosed` con motivo 2 si emettono con `EmitSignal`): ogni riga
  di 05 §5.6 (titolo, corpo, azioni, hint e tipi, `replaces_id`); errori all'avvio da `LastError`
  (`device_not_configured`, `audio_backend_down`) e `audio_backend_down` a runtime ignorato;
  correlazione «con switch» e il caso C9 (switch in `connecting`, «senza switch»); cambi propri da
  menu e da pulsante non notificati; uno `Switch` dal menu che non cambia la priorità seguito da
  `scambio priority on` esterno → notificato; `valid_when` vero e falso; segnali con id di altre
  app ignorati; errore non rinotificato finché attivo e non visto; `ui.notifications` spento con
  `Reload`.
- **`Quit()`** chiamato da un client esterno: riceve la risposta, il demone esce con 0 e
  ripristina come con `SIGTERM` (riuso dei test di arresto).
- **Lingue**: `ui.language = de` → menu e CLI in tedesco; `auto` con `LANGUAGE=de:it`, con
  `LC_ALL=C` e `LANG=it_IT.UTF-8` → italiano; CLI senza `config.toml` non lo crea; cambio
  di lingua con `Reload`.
- **Robustezza**: `tray.json` non valido o `.mo` mancanti → UI disattivata, demone e API
  funzionanti; eccezione in una callback della UI → registrata, chiamate successive regolari;
  watcher e server di notifiche assenti → nessun errore.

### 3.3 Interfaccia

Aspetto e testi vengono solo da `design/` (05 §5.1): nel codice nessun testo visibile, nessun
nome d'icona, nessun parametro delle notifiche. `design/ui/settings-window.blp` e
`design/style/scambio.css` sono bozze della spec 04: **non** si caricano.

### 3.4 Errori e casi limite

- Raffica di prese fallite → una sola notifica della famiglia `grab`, non ripetuta finché
  l'errore è attivo e non visto.
- Riavvio di PipeWire → nessuna notifica (`audio_backend_down` solo all'avvio).
- `DeviceName` che cambia → testi e tooltip aggiornati.
- Pulsante di una notifica vecchia con `valid_when` falso → nessuna azione.
- `Switch()` dal menu che risponde `DeviceUnavailable` (gara con la voce disabilitata) → la
  notifica normale di `Error(device_unavailable)`.
- GNOME + estensione AppIndicator: **non verificato** in questa spec (nessun GNOME su `casa`);
  il report lo dichiara.
- Tema chiaro di Plasma: non misurato in M11 (non si cambia il tema di GM senza di lui); lo
  verifica GM alla prova reale (§6.1 punto 1). Se un'icona non segue il tema è un difetto da
  segnalare con lo screenshot, non da aggirare con `IconPixmap`.

## 4. Fuori scope

- Finestra impostazioni, voce «Impostazioni…» visibile, `app.open-settings`,
  `app.change-shortcut` (spec 04); scorciatoia globale (spec 04).
- Widget Plasma, Impostazioni rapide GNOME, Flatpak ed esportazione delle icone (fase 5+).
- Testi generici «telefono» al posto di «iPhone» (decisione 73, prima della release pubblica).
- Animazioni, conti alla rovescia che si aggiornano da soli.
- Traduzione delle parole proprie di `argparse` (decisione 83).
- Qualunque modifica alla policy o agli adattatori oltre a `Quit()`, all'aggancio
  `apply_config`, alle chiavi `ui.*` e al motivo dell'inibitore tradotto.

## 5. Dipendenze

- Spec 02 chiusa (stesso `service.py`); Codex parte dall'HEAD verde dopo la sua chiusura.
- Su `casa`, **prima del `/goal`**: pacchetto `gettext` per `msgfmt` (`sudo apt install
  gettext`, lo fa GM): senza, il pre-commit fallisce già alla tappa (a).
- Nessuna dipendenza runtime nuova (solo Gio); sviluppo: python-dbusmock (già presente).

## 6. Checklist di done

- [x] Decisioni 70–84 in `docs/decisions.md` e 02 §4 aggiornato (Claude, prima del `/goal`).
- [ ] Ogni regola di §3.1 e di 05 §5.3–§5.6 ha un test (§3.2.5).
- [ ] `make check` verde (con `make i18n`); nessun test saltato.
- [ ] Nessun polling né timer nella UI; misura CPU/RSS a riposo (10 min) prima e dopo, nel report;
      RSS ≤ 40 MB.
- [ ] Nessun valore personale hardcodato; `ui.tray`, `ui.notifications` nel modello di config.
- [ ] Nessun testo visibile, nome d'icona o parametro di notifica nel codice; CLI, motivo
      dell'inibitore e commenti del modello di configurazione con chiavi.
- [ ] `design/` non modificato; richieste di design elencate nel report.
- [ ] Nessun file scritto fuori da `~/.config/scambio/` e `~/.local/share/scambio/`.
- [ ] Prove automatiche con `ui.tray = false` e `ui.notifications = false`.
- [ ] `docs/verification/03/report.md` scritto (GNOME dichiarato non verificato); decisioni
      tecniche da 90 in `docs/decisions.md`.
- [ ] Checklist di prova reale per GM preparata (§6.1), con i comandi esatti.
- [ ] Prova reale eseguita da GM: … · Firma: GM, data.

### 6.1 Checklist di prova reale per GM (traccia; Codex la completa nel report)

1. Avvio: icona «occhiali + telefono» nel tray con Breeze scuro, poi con Breeze chiaro
   (Impostazioni di sistema → Colori), e tornare allo scuro.
2. Video sul PC → icona «sul PC», nessuna notifica; menu: «— sul PC», poi in pausa «Torna
   all'iPhone tra 2 min»; tooltip con l'ora del rilascio.
3. Menu → «Lascia all'iPhone»: icona lucchetto, casella spuntata, nessuna notifica.
4. `scambio switch`: notifica «… sul PC — Priorità iPhone disattivata.».
5. `scambio switch` di nuovo: notifica con «Annulla»; premuto «Annulla» gli occhiali tornano al
   PC, senza altre notifiche.
6. Occhiali nella custodia + video → «non raggiungibile» con «Riprova», icona d'errore; aprendo
   il menu l'icona torna normale.
7. Bluetooth spento → icona «non disponibile», voce switch disabilitata.
8. In `~/.config/scambio/config.toml`, sezione `[ui]`: `language = "de"`; poi `systemctl --user
   reload scambio` → menu in tedesco; `scambio --help` in tedesco; rimettere `auto`.
9. `kquitapp5 plasmashell && kstart5 plasmashell` → l'icona ricompare con lo stato giusto.
10. «Esci da Scambio» → demone fermo, occhiali dove erano; `systemctl --user start scambio` lo
    riavvia.
11. Screenshot di menu e notifiche (chiaro/scuro) per l'audit visivo di Claude.

## 7. Note di revisione (Claude, dopo la consegna)

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

Riletta da me e poi da un agente di controllo indipendente contro `AGENTS.md`, `02`, `03`, le
decisioni, le spec 01–02 e il codice attuale (`service.py`, `cli.py`, `config.py`). L'agente ha
trovato 40 punti; li ho corretti tutti in questa spec, in `05` e in `design/`. I più importanti:
- i pulsanti «Annulla»/«Riprova» non avrebbero mai funzionato (controllavano uno stato
  transitorio): ora ogni azione ha una condizione esplicita (`valid_when`);
- gli errori emessi prima che la UI esista (`device_not_configured`, `pactl` assente) non si
  sarebbero mai visti: ora si ricavano da `LastError` alla prima lettura;
- la maiuscola automatica avrebbe scritto «IPhone»: ora vale solo per «il dispositivo»;
- due timer nella UI (attesa propria di 2 s, correlazione di 300 ms) sostituiti da regole
  sull'ordine dei messaggi D-Bus, verificato nel codice del servizio: niente timer;
- `Reload` non arrivava alla UI: aggancio `apply_config` documentato;
- dbusmenu: tipi corretti (`toggle-state` int32, radice, revisione, `Event(0,"opened")`);
- «Apri il file» via portal asincrono (con `launch_default_for_uri` l'editor sarebbe morto con il
  servizio);
- `audio_backend_down` a ogni riavvio di PipeWire sarebbe stato rumore: ora solo all'avvio.

Ho anche **misurato** (M11) che Plasma trova e ricolora le nostre icone simboliche via
`IconThemePath`, ma solo dalla cartella `hicolor/scalable/status`: dalla prima posizione
(`symbolic/status`) ripiegava sull'icona a colori. Corretto in `design/`.

Cosa resta, e cosa correggerei se emergesse:

1. **Tema chiaro e GNOME non misurati.** Il ricolore è provato solo con Breeze scuro; il chiaro
   lo vedi tu alla prova (punto 1), GNOME non c'è su `casa`.
2. **Etichetta dello switch durante uno switch annullato a metà** (05 §4): può indicare la
   direzione sbagliata per qualche secondo, perché l'API non espone `pending`. Correzione
   futura, se dà fastidio: una proprietà `Destination` nell'API.
3. **«Riprova» non c'è dopo un rilascio fallito**: uno switch accenderebbe la Priorità iPhone
   senza che tu l'abbia chiesto. Resta il menu.
4. **Dimensione**: unità media, divisa in tre tappe con un commit verde ciascuna.
5. **Decisi da GM all'approvazione**: le parole proprie di `argparse` restano in inglese
   (decisione 83); i commenti del modello di `config.toml` si traducono (decisione 84, chiavi
   `config-*` già nei cataloghi).

## 9. Domande aperte

Nessuna bloccante. Restano Q1 (licenza), Q5 (portal su Plasma 5.27,
spec 04).

## Comando `/goal`

```
/goal Implementa docs/specs/03-tray-notifiche.md seguendo AGENTS.md e docs/context/ (contratto
in 05-ui-context.md §5, che è la fonte dei nomi e delle regole). Fatto solo quando ogni voce
della Checklist di done (§6) è soddisfatta con evidenza e `make check` è verde. Scope: solo §3;
§4 non si tocca; design/ non si modifica (lo carichi e basta: richieste di design nel report);
mai Bluetooth, notifiche o bus di sessione reali nei test; le tue decisioni tecniche partono
dal numero 90. Lavora in tre tappe con un commit verde ciascuna: (a) paths + i18n + CLI e
inibitore e modello di config tradotti + make i18n; (b) presentation + client + notifiche; (c) tray SNI/dbusmenu +
Quit() + apply_config + misura a riposo prima/dopo + report. Stop: se la spec contraddice
AGENTS.md o 05, o manca una decisione di prodotto, fermati e scrivilo nel report.
```
