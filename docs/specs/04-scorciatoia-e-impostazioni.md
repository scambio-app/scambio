# Spec 04 — Scorciatoia globale e finestra impostazioni

Stato: approvata (GM, 2026-10-07) · Autore: Claude · Data: 2026-10-07

## 1. Obiettivo

Lo switch intelligente si fa da tastiera con **Meta+G** registrato da Scambio nel servizio
scorciatoie del desktop (niente più azione khotkeys a mano), e le impostazioni essenziali si
cambiano da una **finestra** GTK4/libadwaita, senza aprire `config.toml`. Si chiudono anche due
debiti: l'icona del tray che restava dopo `ui.tray = false` (M17) e l'avviso innocuo di
`players.py` all'avvio.

**Prova visibile.** Su `casa` (Plasma 5.27), con gli occhiali sul PC: GM preme **Meta+G** → gli
occhiali tornano all'iPhone e arriva «Oakley Meta 002Z lasciato all'iPhone» con «Annulla»; di
nuovo Meta+G → tornano al PC. In *Impostazioni di sistema → Scorciatoie* c'è il gruppo «Scambio»
con «Switch intelligente (PC ↔ iPhone)» su Meta+G. Dal tray, «Impostazioni…» apre la finestra
del mock approvato: stato e pulsante coerenti col tray, Priorità iPhone, dispositivo, «Torna
all'iPhone dopo (minuti)», scorciatoia, tray, notifiche, lingua, file di configurazione. Portando
i minuti a 3 il tooltip del tray, alla pausa successiva, dice «tra 3 min» e in `config.toml`
cambia solo `release_idle_seconds = 180`, commenti intatti. Spegnendo «Icona nella barra di
sistema» l'icona sparisce subito. «Scambio» compare anche nel menu delle applicazioni.

## 2. Decisioni applicabili

- Prodotto: 6–8 (Priorità iPhone, switch intelligente, Meta+G), 9–10 (una sola app, design di
  Claude), 14 (it/en/de), 23 (stato persistente), 48 (avvio al login), 99 (azione khotkeys
  provvisoria su Meta+G).
- Di questa spec: **100–109** in `docs/decisions.md` (100–101 di GM, mock approvato il
  2026-10-07; la parte della 106 sui file installati fuori dalle cartelle di Scambio approvata da
  GM con la spec). La 102 supera la 16 nella parte «via portal» e precisa la 99.
- Contratto: `docs/context/05-ui-context.md` §2, §4, §5.1, §5.4–§5.11 (**fonte dei nomi e delle
  regole di dettaglio**: questa spec non li ripete tutti).
- API del demone: spec 01 §3.2.1 + `Quit()` della spec 03.
- Misure: **M16** (portal inutilizzabile su Plasma 5.27; KGlobalAccel su D-Bus: firme, segnali,
  conflitto, memoria del «nessun tasto» dopo un rifiuto), **M17** (watcher e nome noto), **M18**
  (`yourShortcutsChanged`, nomi aggiornati da `doRegister`, riavvio con `RestartUnit`), M14 (tray su
  Plasma 5.27).
- **Numerazione**: decisioni tecniche di Codex da **110** a 119 (100–109 sono della chat di
  sviluppo); misure nuove da M19 a M29.

## 3. Dettagli

### 3.1 Comportamento

#### 3.1.1 Scorciatoia (`core/shortcuts.py`, decisioni 102–103, 05 §5.11)

Adattatore Gio come gli altri di `core/` (nessun timer, nessun polling, chiamate asincrone con i
timeout D-Bus di `[backend]`), creato e chiuso dal servizio come gli altri adattatori. Pubblica
le proprietà `Shortcut*` di 05 §5.7 tramite il servizio. **La pressione chiama `Switch()`
sull'API pubblica** (asincrono, client di `ui/client.py` sullo stesso bus: invariante di
`AGENTS.md`); la policy non cambia.

**Scelta del meccanismo** (all'avvio, poi fissa fino al riavvio): `kglobalaccel` se
`org.kde.kglobalaccel` ha un proprietario (`GetNameOwner`) **oppure** `XDG_CURRENT_DESKTOP`
contiene `KDE`; altrimenti `portal` se `org.freedesktop.portal.Desktop` espone `GlobalShortcuts`
(proprietà `version` ≥ 1, lettura con `NO_AUTO_START` disattivato: il portal si attiva da solo);
altrimenti `none` → `ShortcutState = unsupported`. Se `kglobalaccel` risponde a `doRegister` o
`setShortcut` con `org.freedesktop.DBus.Error.UnknownMethod` (Plasma 6 non misurato) si passa al
portal, con una riga `warning`.

**Conversione dei tasti.** `shortcut.preferred` è un acceleratore GTK. Grammatica: `""`, oppure
zero o più modificatori fra `<Super>` (anche `<Meta>`), `<Control>` (anche `<Primary>`, `<Ctrl>`),
`<Alt>`, `<Shift>` (nomi senza distinzione di maiuscole) seguiti da un tasto fra `a`–`z`, `0`–`9`,
`F1`–`F12`, `space` (lettere senza distinzione di maiuscole, normalizzate in minuscolo); almeno un
modificatore se il tasto non è `F1`–`F12`. Un valore fuori grammatica **non** rende la
configurazione non valida (il demone deve partire anche con un vecchio `"Meta+G"`): riga `warning`
e scorciatoia `unbound`. Verso KGlobalAccel: intero Qt = modificatori (`META` 0x10000000, `CTRL`
0x04000000, `ALT` 0x08000000, `SHIFT` 0x02000000) + codice del tasto (lettere maiuscole ASCII,
cifre ASCII, `F1` = 0x01000030 … `F12` = 0x0100003B, spazio 0x20). Verso il portal: formato
«shortcuts» della specifica XDG (`LOGO+g`, `CTRL+ALT+F5`). Dal Qt all'acceleratore: inversa della
stessa tabella; un tasto fuori tabella (scelto dall'utente in Impostazioni di sistema) →
`Shortcut = ""`, `ShortcutState = active` e `ShortcutLabel` = forma leggibile alla Qt
(`Meta+Space`, `Ctrl+Alt+Del`…) da una tabella dei nomi più comuni, altrimenti `0x…`.

**KGlobalAccel** (firme di M16 e M18; `actionId` = `["app.scambio.Scambio", "switch",
tr("shortcut-component-name"), tr("shortcut-switch-name")]`). Risultato di `setShortcut`: «preso»
se contiene almeno un intero ≠ 0 (vale il primo), «rifiutato» altrimenti (`[0]`, `[]`).

1. *Registrazione* (all'avvio, a ogni ricomparsa di `org.kde.kglobalaccel`, dopo `Reload` o
   `SetConfig` se cambiano `shortcut.preferred` o `ui.language`, a `RetryShortcut()`):
   `doRegister(actionId)` e poi `getComponent("app.scambio.Scambio")` per l'oggetto dei segnali.
   Con `pref` = intero del tasto preferito:
   - `shortcut.preferred` vuoto o non valido → `setInactive(actionId)`, stato `unbound`.
   - `state.json` → `shortcut.preferred` assente o diverso da `shortcut.preferred` attuale (mai
     imposto, o preferito cambiato nel file): `setShortcut(actionId, [pref], 6)` (SetPresent +
     NoAutoloading). Preso → `active`, e si salva `shortcut.preferred` in `state.json`.
     Rifiutato → `conflict`; `action(pref)` → `ShortcutOwner` = quarto elemento (nome
     dell'azione), se vuoto il terzo (componente), se vuoto `""`.
   - Altrimenti (già imposto): `setShortcut(actionId, [pref], 2)` (SetPresent con autoload: vale il
     tasto salvato dal desktop). Preso → `active` con quel tasto; rifiutato → `unbound` (l'utente
     l'ha tolto: si rispetta).
2. *Pressione*: segnale `globalShortcutPressed(s comp, s action, x ts)` sull'oggetto del
   componente (`/component/app_scambio_Scambio`), filtrato su `switch` → `Switch()` (sopra).
   `globalShortcutReleased` si ignora.
3. *Cambio dall'utente* (KCM delle scorciatoie): segnale **`yourShortcutsChanged(as actionId,
   a(ai) keys)`** su `/kglobalaccel`, interfaccia `org.kde.KGlobalAccel` (M18), per il nostro
   `actionId` (confronto sui primi due elementi). Primo intero ≠ 0 della prima sequenza → `active`
   con quel tasto **e** `shortcut.preferred` attuale salvato in `state.json` (il tasto ormai è
   dell'utente: le registrazioni successive useranno l'autoload e non lo sovrascriveranno);
   nessuno → `unbound`.
4. *Arresto* (`SIGTERM`, `Quit()`, riavvio di §3.1.3): `setInactive(actionId)` con
   `NO_AUTO_START`, inviato prima del `flush` finale della connessione, senza attendere la risposta;
   mai `unregister` (il tasto resta all'utente).
5. Errori D-Bus → riga `warning`, stato `unbound` (o invariato se era `active` e l'errore riguarda
   solo un aggiornamento); mai un'eccezione verso il servizio.

**Portal** (`org.freedesktop.portal.GlobalShortcuts` v1; non provabile su `casa`, verifica reale su
GNOME prima della fase 5). Ogni richiesta sottoscrive `Response` sul percorso previsto
`/org/freedesktop/portal/desktop/request/<sender>/<token>` **prima** della chiamata. `CreateSession`
(`handle_token`, `session_handle_token`); alla `Response` 0, `BindShortcuts(session, [("switch",
{description: tr("shortcut-switch-name"), preferred_trigger: <formato XDG>})], "",
{handle_token})`; dalla `Response`, voce `switch` con `trigger_description` non vuota → `active`
con `ShortcutLabel` = quella descrizione, assente → `unbound`. `Activated(session, "switch", ts,
opts)` → `Switch()`. `ShortcutsChanged` → aggiorna. `Closed` della sessione → `unbound` fino a
`RetryShortcut()`. `Response` ≠ 0 → `unbound`. `conflict` non si usa. All'arresto `Close` della
sessione. L'`app_id` che il portal ricava da `scambio.service` è vuoto (M16): per la fase 5 si
valuterà `org.freedesktop.host.portal.Registry.Register` o un'unità `app-app.scambio.Scambio.service`
(non in questa spec).

#### 3.1.2 Scrittura della configurazione (`config.py`, decisione 104)

`SetConfig(a{sv})` accetta solo le chiavi «finestra» di 05 §5.8 con il tipo giusto (`s` per
`device.address` e `ui.language`, `i` per `policy.release_idle_seconds`, `b` per `ui.tray` e
`ui.notifications`); altro → `ConfigInvalid` senza scrivere. Un rifiuto di `SetConfig` è **solo**
l'errore D-Bus: niente segnale `Error`, niente `LastError`, niente notifica (diverso dal `Reload`
di un file non valido). Procedura nel demone, sincrona (file piccolo):

1. Rilegge il file: se manca parte dal modello (come all'avvio); se non è TOML valido →
   `ConfigInvalid` **senza toccarlo**.
2. Unisce i valori richiesti a quelli **del file** e valida l'insieme con lo stesso `parse()`
   dell'avvio → `ConfigInvalid` se non valido.
3. «Cambio di dispositivo» = indirizzo dell'insieme unito ≠ indirizzo **in vigore** (qualunque
   chiave sia stata inviata: anche un indirizzo cambiato a mano nel file e non ancora ricaricato).
   Se c'è e `State` ∈ {`connecting`, `on_pc`, `releasing`} → `DeviceBusy`, nessuna scrittura.
4. Modifica **riga per riga** (grammatica supportata: intestazioni `[nome]` semplici con spazi e
   commento in coda ammessi; righe `chiave = valore` con chiave semplice e valore scalare su una
   riga; commento in coda ammesso; a capo `\n` o `\r\n`, conservato): nella tabella cerca la riga
   attiva `nome = …` e sostituisce **solo il valore**, conservando indentazione, spazi e l'eventuale
   commento in coda; se la chiave manca la inserisce dopo l'ultima riga attiva della tabella (o
   subito dopo l'intestazione); se manca la tabella la aggiunge in fondo, preceduta da una riga
   vuota (aggiungendo prima l'a capo finale se manca). Se la chiave da cambiare compare in una
   forma fuori grammatica (chiave puntata o fra virgolette, tabella inline, valore su più righe) →
   `ConfigInvalid` con una riga `warning` che lo spiega, file intatto. Commenti, righe commentate
   (`# resume_delay_ms = …`), ordine e chiavi non toccate restano identici byte per byte.
5. Verifica: `tomllib.loads(nuovo testo)` deve dare esattamente il dizionario unito; altrimenti
   `ConfigInvalid` e nessuna scrittura.
6. Scrittura atomica (file temporaneo nella stessa cartella + `os.replace`), conservando i permessi.
7. Applica come un `Reload()` riuscito (timer avviati da quel momento, `ui.apply_config`,
   scorciatoia se serve, `PropertiesChanged` di `Config` prima della risposta); con un cambio di
   dispositivo vale §3.1.3 al posto dell'applicazione.

`Reload()` (metodo o `SIGHUP`) aggiorna anche `Config` e, se serve, la scorciatoia (§3.1.1).

#### 3.1.3 Cambio di dispositivo (decisione 105, M18)

Dopo la scrittura (§3.1.2) con un cambio di dispositivo:
- se l'ultimo segmento di `/proc/self/cgroup` è **`scambio.service`** (demone avviato dalla sua
  unità): risposta di successo, poi `RestartUnit("scambio.service", "replace")` asincrono sul
  gestore utente di systemd (`org.freedesktop.systemd1`, `/org/freedesktop/systemd1`) con una riga
  `info` del motivo. systemd invia `SIGTERM` (arresto ordinato: spec 01 §3.1.6, ripresa dei player
  della spec 02, `setInactive`) e riavvia l'unità (≈ 50 ms dopo l'uscita, M18). Se `RestartUnit`
  fallisce: riga `error`, il demone resta com'è con il file già scritto.
- altrimenti (`make run`, test, demone lanciato da un terminale): errore `RestartRequired`, file
  già scritto, demone invariato.

#### 3.1.4 Elenco dei dispositivi (`ListDevices`)

Da `GetManagedObjects` di BlueZ (adattatore `bluez.py`, chiamata asincrona, nessuna cache nuova):
oggetti `org.bluez.Device1` con `Paired = true` e almeno uno degli UUID audio `0000110b-…` (A2DP
sink), `0000111e-…` (HFP), `00001108-…` (HSP); restituisce `(Address, Alias)` senza doppioni di
indirizzo (più adattatori: il primo), ordinati per `Alias` senza distinzione di maiuscole.
Bluetooth spento o BlueZ assente → elenco vuoto, nessun errore. Gli indirizzi si confrontano in
maiuscolo. Un dispositivo accoppiato a finestra aperta compare alla ricomparsa del demone o alla
riapertura (nessun segnale apposito).

#### 3.1.5 Finestra (`ui/settings_model.py` + `ui/window.py`, 05 §5.10, decisioni 100–101, 106–107, 109)

- `scambio settings` (sottocomando della CLI con aiuto `cli-settings-help`; import di GTK solo in
  quel ramo, come `daemon` per `core/`): accetta `--gapplication-service` nascosto in argparse
  (`argparse.SUPPRESS`) e lo passa all'`argv` di `app.run`. Senza GTK 4 o con libadwaita < 1.4 →
  testo `cli-error-gtk-missing` su stderr e uscita 1.
- **`settings_model.py` è puro** (niente `gi`, mypy `--strict` come `presentation.py`): da
  proprietà, `Config`, elenco dispositivi, presenza del demone e chiamate in corso calcola tutto ciò
  che la finestra mostra (testi, icone, classi CSS, sensibilità, visibilità, indici selezionati,
  banner) e, per ogni azione dell'utente, la chiamata da fare. Usa `ui/presentation.py` per riga
  di stato, icona e pulsante (stesse regole del tray, senza errore sovrapposto). `window.py`
  collega soltanto widget e modello.
- Traduzione del `.ui`, client esteso, regola delle chiamate in corso, nome `…Settings.Active`,
  retry della scorciatoia, errori: 05 §5.10.
- **Nessun timer**: minuti al rilascio ricalcolati ai cambi di proprietà e a `notify::is-active`.
- `app.start-daemon`: `StartUnit("scambio.service", "replace")` sul gestore utente di systemd,
  asincrono; errore → `settings-error-generic`.

#### 3.1.6 Apertura dal tray e installazione (decisione 106)

- `app.open-settings` (voce 7 del menu, ora visibile) come in 05 §5.5: `Activate` via attivazione D-Bus; nome non attivabile → riga `warning` e nient'altro.
- **Voce 7 visibile**: la versione di `design/ui/tray.json` senza `"visible": false` sulla voce 7 è
  scritta da Claude ma **non committata** (i test della spec 03 la vogliono nascosta e il
  pre-commit fallirebbe): è in `~/Scrivania/Claude/scambio-misure/tray.json.spec04` su `casa`. Codex la copia in
  `design/ui/tray.json` **senza modificarla** e la include nel commit della tappa (b) insieme ai
  test aggiornati (unica eccezione alla proprietà di `design/`, decisa da Claude).
- `make install-user` aggiunge, oltre all'unità systemd:
  - `~/.local/share/dbus-1/services/app.scambio.Scambio.Settings.service` (`[D-BUS Service]`,
    `Name=app.scambio.Scambio.Settings`, `Exec=<percorso assoluto di scambio> settings
    --gapplication-service`);
  - `~/.local/share/applications/app.scambio.Scambio.desktop` da
    `design/desktop/app.scambio.Scambio.desktop.in` con `@EXEC@` e `@ICON@` sostituiti (05 §5.1).
  In entrambi i file il percorso dell'eseguibile va scritto con le regole di quoting della
  specifica Desktop Entry (virgolette, `\\`, `$`, `` ` ``, `"`; `%` raddoppiato). Nessun
  `update-desktop-database`. `make uninstall-user` li rimuove. Nessun altro file fuori dalle
  cartelle di Scambio.
- `make ui`: `blueprint-compiler compile design/ui/settings-window.blp --output
  build/ui/settings-window.ui`; lo richiamano `make check`, `make run`, `make install-user` (come
  `make i18n`); se `blueprint-compiler` manca, messaggio chiaro e uscita non zero.

#### 3.1.7 Notifiche con la finestra in primo piano (decisione 107)

Nelle notifiche (`ui/notify.py`): `Gio.bus_watch_name` su `app.scambio.Scambio.Settings.Active`;
finché ha un proprietario, nessuna notifica della famiglia `priority` (05 §5.6). Gli errori
restano.

#### 3.1.8 Debiti chiusi in questa spec

- **Icona che resta nel tray** (M17, decisione 108): `tray.py` possiede
  `org.kde.StatusNotifierItem-<pid>-1` (`Gio.bus_own_name_on_connection`, flag `DO_NOT_QUEUE`) e
  passa **quel nome** a `RegisterStatusNotifierItem`; con `ui.tray` → `false` ritira gli oggetti e
  rilascia il nome; con `true` lo riprende e si registra di nuovo. Alla ricomparsa del watcher si
  registra con lo stesso nome. All'arresto lo rilascia.
- **Avviso di `players.py` all'avvio** («Cannot update resume_players without a session bus
  identity», righe 152 e 355, journal del 2026-10-07 00:14): trovare la causa. Se è una condizione
  normale dell'avvio (identità del bus non ancora nota) va a livello `debug` o si evita
  l'aggiornamento prematuro; se nasconde un caso reale (ripresa persa), correggerlo con un test.
  Esito nel report.

#### 3.1.9 Risorse

Nessun polling e nessun timer nuovi nel demone (la scorciatoia è a segnali). A riposo CPU ≈ 0 % e
RSS del demone ≤ **40 MB**, misurati 10 minuti prima e dopo come nella spec 03, con tray,
notifiche e scorciatoia attivi (finto KGlobalAccel su dbusmock). La finestra è un processo che
vive solo mentre è aperta: nel report il suo RSS da aperta (una misura).

### 3.2 API D-Bus, configurazione, dati

#### 3.2.1 API D-Bus

Aggiunte di 05 §5.7: metodi `SetConfig`, `ListDevices`, `RetryShortcut`; proprietà `Config`,
`Shortcut`, `ShortcutLabel`, `ShortcutState`, `ShortcutOwner`, `ShortcutBackend`; errore
`DeviceBusy`. Tutto nello stesso XML. `PropertiesChanged` per ogni proprietà nuova quando cambia,
prima della risposta al metodo che la cambia (regola delle spec 01 e 03). La CLI aggiunge solo
`settings`; `scambio status` continua a stampare tutte le proprietà (testo e `--json`), quindi
anche le nuove (`Config` nel testo come `chiave=valore` separati da virgole).

#### 3.2.2 Configurazione

`shortcut.preferred` passa da «solo validata» ad avere effetto (grammatica §3.1.1; un valore fuori
grammatica è un `warning`, non una configurazione non valida). Nessuna chiave nuova. Il commento
`config-shortcut-preferred` esiste già.

#### 3.2.3 Stato persistente

`state.json` acquista la chiave facoltativa `"shortcut": {"preferred": "<Super>g"}` (preferito già
imposto, o tasto ormai scelto dall'utente: §3.1.1); assente = mai imposto. Stessa scrittura atomica
e stessa tolleranza dei valori malformati delle chiavi esistenti (malformato → come assente,
`warning`). `version` resta 1.

#### 3.2.4 Build e dipendenze

- Runtime (già previste dalla decisione 15): GTK 4 e libadwaita ≥ 1.4 tramite GObject
  Introspection (`gir1.2-gtk-4.0`, `gir1.2-adw-1`), **solo** per `scambio settings`.
- Sviluppo: `blueprint-compiler` 0.12 (decisione 106); `xvfb-run` e `dbus-run-session` per i test
  della finestra (presenti su `casa`). `settings_model.py` negli override `strict` di mypy.
- Su `casa` i tre pacchetti GTK/Blueprint sono installati da GM il 2026-10-07.

#### 3.2.5 Test (Codex)

- **Conversione dei tasti** (tabella): grammatica valida e non valida (maiuscole comprese) e
  `warning` + `unbound` per i valori non validi senza fermare l'avvio; andata e ritorno Qt ↔ GTK
  per lettere, cifre, F1–F12, spazio con tutte le combinazioni di modificatori; formato XDG; tasti
  fuori tabella → `Shortcut = ""` e `ShortcutLabel` leggibile.
- **KGlobalAccel con dbusmock** (oggetto finto `org.kde.kglobalaccel` con `doRegister`,
  `setShortcut`, `setInactive`, `getComponent`, `action`, segnale `yourShortcutsChanged(as,
  a(ai))` e, sul componente, `globalShortcutPressed`): scelta del meccanismo (nome posseduto;
  nome assente con `XDG_CURRENT_DESKTOP=KDE`; nome assente e desktop non KDE con portal presente →
  portal; nessuno → `unsupported`; `UnknownMethod` → portal); prima registrazione con flag 6 →
  `active` e `state.json` aggiornato; preferito già imposto → flag 2; rifiuto alla prima →
  `conflict` con `ShortcutOwner`; rifiuto con autoload → `unbound`; risultati `[]` e multipli;
  preferito cambiato con `Reload` → di nuovo flag 6; `""` → `setInactive` e `unbound`;
  `RetryShortcut` dopo la liberazione → `active`; `yourShortcutsChanged` → `Shortcut` aggiornato e
  `state.json` scritto, poi un nuovo avvio usa il flag 2 (il tasto dell'utente non viene
  sovrascritto anche se il preferito è occupato); pressione → `Switch()` ricevuto dal demone di
  prova; `DeviceUnavailable` senza eccezioni; scomparsa e ricomparsa del nome → nuova
  registrazione; `ui.language` cambiata → nuova `doRegister` con i nomi tradotti; arresto e
  `Quit()` → `setInactive` con `NO_AUTO_START`; errori D-Bus del finto → nessuna eccezione.
- **Portal con dbusmock** (oggetto finto con `CreateSession`/`BindShortcuts` e oggetti `Request`
  che emettono `Response`, anche immediatamente): `active` con `ShortcutLabel`; `Response` ≠ 0 →
  `unbound`; `Activated` → `Switch()`; `ShortcutsChanged`; `Closed`.
- **Scrittura della configurazione** (tabella di file): commenti (anche in coda) e chiavi altrui
  intatti byte per byte; `\r\n` conservato; file senza a capo finale; chiave assente; tabella
  assente; riga commentata con lo stesso nome non toccata; file mancante; file non TOML →
  `ConfigInvalid` e file identico; forme fuori grammatica (chiave puntata, fra virgolette, tabella
  inline) → `ConfigInvalid` e file identico; valore fuori range, tipo sbagliato, chiave non
  «finestra» o `shortcut.preferred` → `ConfigInvalid`; modello creato dal demone in it/en/de
  modificato e riletto; permessi conservati.
- **`SetConfig` sul demone di prova**: `PropertiesChanged(Config)` prima della risposta; nessun
  `Error` né `LastError` sui rifiuti; `ui.tray` e `ui.language` arrivano alla UI come con
  `Reload`; `DeviceBusy` in `on_pc`, anche quando l'indirizzo è cambiato solo nel file e si invia
  un'altra chiave; cambio di indirizzo fuori da `scambio.service` → `RestartRequired` con file
  scritto; dentro (cgroup simulato tramite un parametro del modulo, non leggendo il vero
  `/proc`) → risposta e poi `RestartUnit` su un finto `org.freedesktop.systemd1`.
- **`ListDevices`** con BlueZ dbusmock: filtro su `Paired` e UUID, doppioni, ordinamento,
  Bluetooth assente.
- **`settings_model.py`** (tabella, senza GTK): ogni riga di 05 §5.10 in ogni stato rilevante
  (demone presente/assente e banner dopo un cambio di dispositivo riuscito, i quattro
  `ShortcutState` e i tre meccanismi, dispositivo configurato/assente/fuori elenco/elenco vuoto,
  `State` che blocca il dispositivo, voce «Nessuno» non sceglibile), minuti (90 s → 2, 150 s → 3,
  600 s → 10, 10 s → 1), indici della lingua, chiamate prodotte da ogni azione dell'utente, tre
  incrementi rapidi dei minuti con risposte in ritardo (nessun salto indietro, l'ultimo valore
  scritto), ripristino dopo `ConfigInvalid`/`DeviceBusy`, retry della scorciatoia all'attivazione
  solo con `conflict`.
- **Finestra con GTK reale**, in un sottoprocesso sotto `xvfb-run -a dbus-run-session --` (display e
  bus di sessione privati: mai quelli di GM), con `GSK_RENDERER=cairo` e `GTK_A11Y=none`: il `.ui`
  tradotto si carica; ogni ID di 05 §5.10 esiste con il tipo giusto; con `LANG=C` e
  `ui.language = "de"` nessun testo visibile è uguale a una chiave e i testi sono tedeschi; le
  azioni `app.*` sono registrate; con un demone di prova sullo stesso bus privato i widget
  riflettono le proprietà, un cambio programmatico di `priority_row`, `release_idle_row`,
  `tray_row` produce la chiamata giusta e nessun eco; il nome `…Settings.Active` è posseduto solo
  mentre la finestra è attiva (simulato).
- **Tray**: voce 7 visibile e `Event(7, "clicked")` → `Activate` sul nome finto
  `app.scambio.Scambio.Settings` (e solo `warning` quando non è attivabile); M17: con `ui.tray`
  false il finto watcher vede sparire il nome `org.kde.StatusNotifierItem-<pid>-1`, con true
  ricomparire e registrarsi di nuovo; non regressione del client esteso per il tray.
- **Notifiche**: con il nome `app.scambio.Scambio.Settings.Active` posseduto nessuna notifica
  `priority`, errori sì; rilasciato il nome tornano normali.
- **Cataloghi**: le chiavi nuove esistono nei tre `.po` e nel `.pot`, con gli stessi segnaposto
  (test esistenti); ogni chiave usata dal codice della finestra esiste.
- **Installazione**: `tools/install_user.py` in una HOME temporanea produce `.desktop` (valido per
  `desktop-file-validate`, presente su `casa`) e file di servizio D-Bus con i percorsi assoluti
  (anche con uno spazio nel percorso), e `uninstall` li rimuove.

### 3.3 Interfaccia

Aspetto e testi solo da `design/` (05 §5.1, §5.10): nel codice nessun testo visibile, nessun nome
d'icona fuori da `tray.json`, nessun valore di stile. Il layout è `design/ui/settings-window.blp`
così com'è: un widget o un ID in più si chiede nel report. Chiavi nuove già nei cataloghi:
`settings-*`, `shortcut-*`, `cli-settings-help`, `cli-error-gtk-missing`. Se serve un testo che non
c'è, si chiede nel report: mai inventare una chiave.

### 3.4 Errori e casi limite

- Meta+G già usato da un'altra azione (oggi khotkeys «Connetti Oakley», decisione 99) →
  `conflict`, la finestra lo dice; Claude rimuove l'azione khotkeys prima della prova reale (§5),
  poi tornando alla finestra (o con `RetryShortcut`) Scambio prende il tasto.
- Utente che assegna un altro tasto in Impostazioni di sistema dopo un conflitto → `active` con
  quel tasto, conservato ai riavvii (§3.1.1 punto 3).
- Utente che toglie il tasto in Impostazioni di sistema → `unbound`, rispettato anche ai riavvii.
- Utente che cambia `shortcut.preferred` nel file + reload → nuovo tasto imposto (flag 6).
- `kglobalaccel5` riavviato → nuova registrazione alla ricomparsa (autoload: tasto conservato).
- `SetConfig` mentre il file è in modifica e non valido → `ConfigInvalid`, file intatto, avviso.
- Due finestre: impossibile (istanza unica); `scambio settings` con la finestra già aperta la
  porta in primo piano.
- Riavvio per cambio dispositivo con player in pausa da Scambio: l'arresto ordinato della spec 02
  li riprende come con `SIGTERM`.
- Focus su X11: la finestra aperta dal tray potrebbe restare dietro (prevenzione del furto di
  focus di KWin): da osservare alla prova reale, nessun aggiramento ora.
- Plasma 6 (metodi a interi di KGlobalAccel), GNOME (portal, tray assente, `app_id` vuoto):
  **non verificati** su `casa`; il report lo dichiara.

## 4. Fuori scope

- Avvio all'accesso dalla finestra, Flatpak, portal Background (fase 5).
- Impostazioni avanzate nella finestra (ritardo di presa, app ignorate, tempi, profilo):
  restano nel file (decisione 100).
- Cambio del tasto dentro la finestra (si fa in Impostazioni di sistema); `ConfigureShortcuts` del
  portal v2.
- Rimozione automatica dell'azione khotkeys o di altri binding dell'utente: mai dal codice.
- Widget Plasma, Impostazioni rapide GNOME, testi «telefono» al posto di «iPhone».
- Modifiche alla policy o agli adattatori oltre a: evento switch dalla scorciatoia, `ListDevices`,
  `SetConfig`/`Config`, `RestartUnit` per il cambio di dispositivo, `setInactive` all'arresto, i due
  debiti di §3.1.8.

## 5. Dipendenze

- Spec 03 chiusa; Codex parte dal commit di design e documenti di questa spec (dopo `38ac33f`).
- `AGENTS.md`: l'invariante «nessuna modifica fuori da `~/.config/scambio/` e
  `~/.local/share/scambio/`» vale per il demone; `make install-user` può installare unità systemd,
  lanciatore e servizio D-Bus (decisione 106, approvata da GM con questa spec).
- Su `casa`: `gir1.2-gtk-4.0`, `gir1.2-adw-1`, `blueprint-compiler` (installati da GM il
  2026-10-07); `xvfb-run` presente.
- **Prima della prova reale** (Claude, non Codex): rimozione dell'azione khotkeys «Connetti
  Oakley» con backup di `~/.config/khotkeysrc`, rilettura di khotkeys, verifica che Meta+G sia
  libero (`action` di KGlobalAccel vuoto).

## 6. Checklist di done

- [x] Decisioni 100–109, `AGENTS.md` (invariante sui file installati), 05 §5.1–§5.11, 02, design
      (`.blp`, CSS, cataloghi, `.desktop.in`, `tray.json`) aggiornati da Claude prima del `/goal`.
- [ ] Ogni regola di §3.1 e di 05 §5.10–§5.11 ha un test (§3.2.5).
- [ ] `make check` verde (con `make i18n` e `make ui`); nessun test saltato; test GTK solo sotto
      `xvfb-run`.
- [ ] Nessun polling né timer nuovi; misura CPU/RSS a riposo prima e dopo (RSS ≤ 40 MB) e RSS della
      finestra aperta, nel report.
- [ ] Nessun valore personale hardcodato; nessun testo visibile o valore di stile nel codice.
- [ ] `design/` non modificato; richieste di design elencate nel report.
- [ ] Il demone non scrive fuori da `~/.config/scambio/` e `~/.local/share/scambio/`; `make
      install-user` scrive solo l'unità systemd e i file di §3.1.6.
- [ ] I due debiti di §3.1.8 chiusi, con test.
- [ ] `docs/verification/04/report.md` (GNOME dichiarato non verificato); decisioni tecniche da
      110 in `docs/decisions.md`.
- [ ] Checklist di prova reale per GM completata nel report (§6.1).
- [ ] Prova reale eseguita da GM: … · Firma: GM, data.

### 6.1 Checklist di prova reale per GM (traccia; Codex la completa nel report)

0. Preparazione (Claude): `make install-user`, riavvio di Scambio, azione khotkeys rimossa con
   backup, `scambio status` → `ShortcutState: active`, `Shortcut: <Super>g`.
1. Occhiali sul PC, video in corso: **Meta+G** → occhiali all'iPhone, notifica con «Annulla»,
   icona lucchetto. Meta+G di nuovo → occhiali al PC, notifica «Priorità iPhone disattivata».
2. *Impostazioni di sistema → Scorciatoie*: gruppo «Scambio», azione «Switch intelligente
   (PC ↔ iPhone)» su Meta+G.
3. Tray → «Impostazioni…»: si apre la finestra (in primo piano?), stato e pulsante coerenti con il
   tray; «Lascia all'iPhone» dalla finestra funziona e **non** arriva nessuna notifica.
4. Priorità iPhone dalla finestra: spunta anche nel menu del tray, nessuna notifica.
5. Minuti a 3: in `config.toml` cambia solo `release_idle_seconds = 180`, commenti intatti; alla
   pausa successiva il menu dice «tra 3 min». Rimettere 2.
6. «Icona nella barra di sistema» spenta → l'icona sparisce subito; riaccesa → torna.
7. Lingua «Deutsch» → avviso; menu del tray in tedesco subito; riaprendo la finestra è in
   tedesco. Rimettere «Automatica».
8. Dispositivo: con gli occhiali sul PC l'elenco è bloccato con la spiegazione. (Cambio vero di
   dispositivo solo se GM ha un'altra cuffia accoppiata: scelta → avviso di riavvio, banner per
   2–3 s, poi la finestra torna con il nuovo dispositivo; poi tornare agli Oakley.)
9. «Cambia…» apre Impostazioni di sistema sulle scorciatoie di Scambio.
10. «Apri» del file di configurazione apre l'editor.
11. «Esci da Scambio» dal tray con la finestra aperta → banner «Scambio non è in esecuzione»;
    «Avvia» → torna tutto.
12. Menu delle applicazioni → «Scambio» apre la finestra.
13. Screenshot reali chiaro/scuro per l'audit visivo (li fa Claude).

## 7. Note di revisione (Claude, dopo la consegna)

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

Riletta da me e poi da un agente di controllo indipendente contro `AGENTS.md`, 02, 05, le
decisioni, le spec 01–03 e il codice a `38ac33f` (sola lettura). L'agente ha trovato 37 punti;
li ho corretti tutti qui, in 05, nelle decisioni e in `design/`. Per tre ho fatto una misura in
più (**M18**) invece di fidarmi della documentazione. I più importanti:
- **il riavvio per il cambio di dispositivo non avrebbe funzionato**: misurato che systemd non
  riavvia un servizio `Type=dbus` che esce con un codice d'errore (vede sparire il nome e lo
  considera fermato); ora il demone chiede `RestartUnit` della propria unità, misurato: riparte in
  50 ms;
- il segnale di KGlobalAccel per i cambi fatti in Impostazioni di sistema si chiama
  `yourShortcutsChanged` con un'altra firma (misurato); e un tasto scelto da te dopo un conflitto
  sarebbe stato cancellato al riavvio successivo: ora diventa «tuo» e non si sovrascrive più;
- su GNOME con qualche app KDE installata Scambio avrebbe scelto KGlobalAccel invece del portal:
  ora lo usa solo se il servizio è attivo o il desktop è KDE;
- i testi della finestra non sarebbero stati tradotti (GtkBuilder usa il gettext di sistema, non
  i nostri cataloghi): ora il layout si traduce con lo stesso traduttore di tray e CLI;
- un vecchio valore come `"Meta+G"` nel file avrebbe impedito l'avvio del demone: ora è solo un
  avviso e la scorciatoia resta senza tasto;
- la scorciatoia ora passa dall'API pubblica (`Switch()`), come chiede `AGENTS.md`;
- scrittura del file: conserva anche i commenti in coda alla riga e rifiuta, senza toccare il
  file, le forme TOML che non sa modificare in sicurezza;
- finestra: niente salti all'indietro con clic veloci, stato «demone fermo» definito, banner
  nascosto durante il riavvio voluto, icona giusta nella barra delle applicazioni;
- notifiche: sospese solo con la finestra **in primo piano** (con la finestra dietro, Meta+G
  mostra ancora «Annulla»).

Cosa resta, e cosa correggerei se emergesse:

1. **File fuori dalle cartelle di Scambio**: `make install-user` installa lanciatore e servizio
   D-Bus in `~/.local/share` (oltre all'unità systemd di oggi). `AGENTS.md` lo vietava: va
   approvato da te (decisione 106, invariante riscritta).
2. **GNOME e Plasma 6 non verificati** (portal, tray assente, `app_id` vuoto): conviene una VM
   GNOME prima della fase 5 (Q6).
3. **Focus su X11**: la finestra aperta dal tray potrebbe restare dietro; lo vediamo alla prova.
4. **«Super» invece di «Meta»** nella finestra: i tasti disegnati da GTK dicono «Super + G»
   (Impostazioni di sistema dice «Meta+G»). Lo lascio così: è il widget nativo; se ti dà
   fastidio si cambia con un'etichetta nostra.
5. **Dimensione**: unità grande, divisa in tre tappe con un commit verde ciascuna e il report
   aggiornato dopo ogni tappa.

## 9. Domande aperte

Nessuna bloccante. Restano Q1 (licenza) e Q6 (GNOME e Plasma 6 prima della fase 5).

## Comando `/goal`

In due messaggi (Codex non accetta un `/goal` lungo).

Messaggio 1:

```
/goal Implementa docs/specs/04-scorciatoia-e-impostazioni.md seguendo AGENTS.md; fatto quando la Checklist di done (§6) è soddisfatta con evidenza e `make check` è verde.
```

Messaggio 2:

```
Istruzioni operative per il goal della spec 04. Il contratto in docs/context/05-ui-context.md
§5 (in particolare §5.7, §5.10, §5.11) è la fonte dei nomi e delle regole; le misure M16 e M17 in
docs/hardware-lab.md danno le firme D-Bus reali. Scope: solo §3; §4 non si tocca; design/ non si
modifica (lo carichi e basta: richieste di design nel report); mai Bluetooth, KGlobalAccel,
portal, notifiche o display reali nei test (dbusmock su bus privati, GTK solo sotto xvfb-run); le
tue decisioni tecniche vanno da 110 a 119. Lavora in tre tappe con un commit verde ciascuna:
(a) scorciatoia (core/shortcuts.py, conversione dei tasti, KGlobalAccel e portal, state.json,
proprietà Shortcut*, RetryShortcut, pressione → Switch() via API, setInactive all'arresto) +
debito players.py; (b) SetConfig
con scrittura riga per riga, Config, ListDevices, DeviceBusy, RestartUnit, debito del tray (M17),
notifiche sospese con la finestra in primo piano, voce «Impostazioni…» e app.open-settings; (c) finestra
(settings_model.py puro + window.py, traduzione del .ui con Translator, client esteso, scambio
settings, make ui, install-user con .desktop e servizio D-Bus) + misura a riposo prima/dopo +
report in docs/verification/04/report.md con la checklist di prova reale. Dopo ogni tappa
aggiorna il report con cosa è fatto, così una sessione interrotta riparte da lì. I test GTK solo
in sottoprocesso sotto xvfb-run -a dbus-run-session. Stop: se la spec contraddice AGENTS.md o 05, o manca una decisione di
prodotto, fermati e scrivilo nel report.
```
