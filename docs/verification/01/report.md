# Spec 01 — Report di consegna

Data: 2026-10-04 · Codex · branch `main` · base iniziale `99927b5`, audit `938f8a5`.

## Obiettivo ed esito

Implementato §3 della spec 01: demone headless, policy pura, adattatori Gio,
API D-Bus, CLI e unit utente systemd. Consegnate tutte e tre le tappe tecniche,
ciascuna con `make check` verde. **DoD B e chiusura complessiva restano pendenti**:
la prova reale 1–18 e la firma sono riservate a GM e non sono state simulate.
Le undici osservazioni di Audit 1 sono corrette/verificate: evidenza e commit
nella sezione «Correzioni dopo audit 1»; resta la revisione di Claude sulle correzioni.

Questo report sostituisce quello di stop committato in `7a22ab0`. Lo stop era
fondato sulla mancanza delle misure del blocco schermo e del cambio profilo;
M6–M7 e gli aggiornamenti della spec in `99927b5`, più l'incarico esplicito di
ripresa, hanno risolto il prerequisito. Le misure ancora aperte non sono state
trattate come blocchi ulteriori, secondo le istruzioni di GM/Claude.

## Cambiamenti

- Configurazione TOML validata, modello creato solo se assente, chiavi sconosciute
  segnalate e ignorate; priorità e destinazione da ripristinare in JSON atomico.
- Policy senza Gio, orologio o I/O, con stati released/connecting/on_pc/releasing/
  unavailable, sei timer, anti ping-pong, doppio switch e rilascio per lock/sleep.
- BlueZ asincrono sul solo dispositivo configurato, ObjectManager e segnali,
  riaggancio dopo perdita del proprietario e scarto dei callback obsoleti.
- Audio tramite sottoprocessi Gio: parser incrementale UTF-8/JSON concatenato,
  istantanee coalescenti, filtri stream, recupero con attesa crescente,
  instradamento serializzato e ripristino rispettoso del predefinito utente.
- Sessione: OR deduplicato delle due fonti di lock; logind User.Display; inibitore
  delay con fd reale passato sul bus privato e chiuso sulle azioni della policy.
- Servizio `app.scambio.Scambio1` con XML condiviso, PropertiesChanged,
  Transition/Error, Reload/SIGHUP e arresto senza scollegamento o cambio route.
  Avvio coordinato: lock/sleep prima dell'adozione del dispositivo.
- CLI sottile con codici 0/1/2/3, nessuna attivazione D-Bus automatica, import del
  core solo nel ramo daemon. Unit systemd e installatore esplicito, non eseguito.
- Tooling, migrazione degli hook graphify sotto `.githooks`, test isolati,
  harness di processo e strumento riproducibile per misura idle su finti.

## Commit

Tutti su `main`, nessun push, tutti con trailer
`Co-Authored-By: Codex <noreply@openai.com>` e senza `--no-verify`.

| Tappa | Commit | Gate nel pre-commit |
|---|---|---|
| (a) tooling/config/stato/policy | `b342658` | verde, 81 test |
| (b) adattatori | `cadd653` | verde, 101 test |
| (c) servizio/CLI/systemd/integrazione | `9f282ac` | verde, 132 test |

Il report iniziale e la prima misura idle sono in `3fdddfe`. Il commit finale
delle correzioni contiene questo report aggiornato e la nuova misura; si identifica
con `git log -1 --format=fuller -- docs/verification/01/report.md`.

## Verifiche eseguite ed evidenza

Ambiente: Python 3.12.3, gi di sistema; ruff 0.16.10, mypy 2.4.0,
pytest 9.1.1, python-dbusmock 0.38.1, pygobject-stubs 2.10.0.

- `make venv`, `make hooks`, `make check`: riusciti nella working copy.
- Copia pulita dei sorgenti in directory temporanea, nuovo repository e nuovo
  venv: `make venv`, `make hooks`, `make check` tutti exit 0. Questa verifica
  comprendeva 112 test; i successivi 20 casi aggiungono regressioni senza cambiare
  implementazione o tooling.
- Verifica negativa del gate: introdotto temporaneamente un file Python con
  errore sintattico; tentato commit, rifiutato dal pre-commit (exit 1, make exit 2),
  HEAD invariato. File rimosso prima del commit (a); nessun hook aggirato.
- Gate finale del commit (c): 24 file formattati, ruff verde, mypy senza errori
  su 14 file sorgente, **132 passed in 11.00 s, zero skip**.
- `git diff --check` e `git diff --cached --check`: verdi.
- Isolamento in `tests/conftest.py`: prima della raccolta avvia due PrivateDBus;
  ogni test verifica che entrambi gli indirizzi siano esattamente quelli creati.
  Ogni costruzione Audio nei test passa il comando del finto pactl (o un percorso
  volutamente inesistente nel test del comando mancante).
- Gli harness di processo e misura rifiutano bus non dbusmock. Il finto pactl
  blocca su FIFO quando non riceve eventi; registra comandi e LC_ALL senza
  eseguire operazioni audio reali.
- Nessun demone sui bus reali; nessun bluetoothctl, pactl reale, install-user,
  systemctl --user o modifica di sistema eseguiti.

### Copertura della tabella e degli adattatori

`tests/test_policy.py::test_rules` contiene casi nominati **G1–G12, R1–R6,
C1–C10, O1–O11, L1–L4, U1–U2**. Dopo Audit 1, i 65 casi nominati confrontano
l'intero contesto risultante e la lista esatta delle azioni ordinate, inclusi
valori, durate e tuple delle transizioni; verificano anche l'immutabilità dell'input.
Ulteriori test coprono guardie di presa, doppio switch, completamenti e timeout,
anti ping-pong, ingresso con pending release/lock/sleep, adozione esterna con
priorità, scadenze configurate, AlreadyConnected e rilascio dell'inibitore in
ogni stato. La checklist menziona P, ma la tabella non contiene righe P: le tre
procedure PRESA/RILASCIO/INGRESSO sono esercitate da questi casi e dall'integrazione.

`tests/test_adapters.py`: JSON spezzato byte per byte, valori `(null)`, filtri,
coalescenza di venti eventi in una snapshot, refresh durante snapshot,
riavvio/backoff e riemissione dei valori, assenza di attività senza eventi,
route/move/restore e rispetto di default già BT, scelta utente, sink sparito,
errori pactl; BlueZ bluez5 per connessione, alimentazione, riavvio, Alias,
Paired, rimozione ed estraneità degli altri dispositivi; logind e ScreenSaver
per OR, duplicati, sleep/wake, fd e assenza delle fonti.

`tests/test_service.py`: CLI in sottoprocessi, GetAll, PropertiesChanged e
Transition, ciclo completo con timer iniettati accelerati, priorità persistente,
ricarica valida/non valida/restart-required e timer già avviati invariati,
doppia istanza, SIGHUP/SIGTERM, arresto senza toccare route, riparazione dopo
crash con dispositivo collegato/scollegato e scelta utente, backend incompatibile,
comandi durante l'avvio, scadenza SLEEP e risultati tardivi ignorati.
L'unit systemd è verificata tramite rendering, senza installarla.

### Timer e misura CPU/RSS

Ispezione AST del runtime dopo Audit 1: tre siti nell'adattatore audio
(coalescenza, riaggancio e nuovo limite dei comandi pactl) e i due rami del
pianificatore (millisecondi/secondi). Il limite dei comandi viene rimosso alla
fine del figlio; non resta un timer periodico a riposo. Il pianificatore
riceve esclusivamente i sei timer della policy, li rimuove alla cancellazione e
scarta callback non più correnti. Le chiamate D-Bus hanno timeout configurabili.
Nessun `time.sleep`, thread, asyncio o ciclo di polling nel runtime.

La misura iniziale in `3fdddfe` (600,092 s, CPU 0,0%, RSS demone 22.788 KiB,
finto pactl 11.516 KiB) resta evidenza storica della prima consegna. La nuova
misura dopo Audit 1 usa `.venv/bin/python tools/measure_idle.py`, senza modifiche
allo strumento: due bus privati nuovi, bluez5, logind, ScreenSaver e finto pactl.
I sorgenti runtime misurati sono quelli di `00f58b7`.

Durata **600,101 s**, inizio **2026-10-04 09:44:38 UTC**. Artefatto aggiornato:
[idle.json](idle.json).

| Processo | CPU nell'intervallo | RSS iniziale | RSS dopo 10 min |
|---|---:|---:|---:|
| Demone | 0,0% | 23.048 KiB | 23.048 KiB |
| Finto pactl subscribe | 0,0% | 11.580 KiB | 11.580 KiB |

Delta CPU nullo alla risoluzione dei tick /proc; **zero chiamate pactl** durante
l'intervallo; stato finale `released`. Nessuna crescita RSS tra gli estremi.
Lo strumento è terminato con exit 0; i due PID misurati non esistono più in
/proc dopo il cleanup. Il campione comprende il demone Python/Gio con
trasporti simulati; non misura Bluetooth/audio di sistema.

**GM eseguirà la misura reale al punto 18** della checklist: CPU/RSS del finto
pactl non sono una misura dell'audio/Bluetooth di sistema. Nessuna prova reale
viene dichiarata fatta.

## Checklist §6

| Voce | Esito |
|---|---|
| Tooling da repo pulito e hook che rifiuta il rosso | Fatto, evidenza sopra |
| Regole della policy e adattatori con finti | Fatto, casi nominati e suite sopra |
| make check verde, nessun test saltato | Fatto, 192 test dopo Audit 1 |
| Nessun polling, CPU/RSS su finti per 10 minuti | Vedi misura sopra; prova reale riservata a GM |
| Configurazione della spec, nessun dato personale hardcodato | Fatto; MAC sintetici nei test, indirizzo runtime da config |
| Nessun testo it/de nell'app, msgid CLI elencati | Fatto; lista sotto |
| design/ non modificato, richieste esplicitate | Fatto; nessuna richiesta |
| Report e decisioni tecniche dalla 30 | Fatto; decisioni 30–43, nuove voci 39–43 per Audit 1 |
| Checklist reale copiata con comandi | Fatto, §6.1 sotto |
| Prova reale GM e firma | **Non fatta**, punti 1–18 pendenti |

## Scostamenti e scelte tecniche

Decisioni reversibili 30–43 in `docs/decisions.md`. Sezione `[backend]` aggiuntiva
per rendere configurabili anche i tempi tecnici fissi della prosa. Stubs fissati
alla versione compatibile col PyGObject di sistema. Moduli ausiliari `api.py`,
`core/ports.py`, `core/transport.py` isolano contratto e trasporto.

Il reason `connect_timeout` segue C5 ed è ora incluso da Claude in §3.2.1
(`938f8a5`): la segnalazione della consegna iniziale è risolta. Nessuna modifica
al suo comportamento; non sono stati aggiunti metodi, segnali o proprietà API.
Il ripristino all'arresto
menzionato nella vecchia decisione 22 non viene applicato: valgono §3.1.6 e la
successiva decisione 29. Nessuna pausa/muto, MPRIS, UI, profili, estensioni,
scorciatoie, pairing, attivazione D-Bus o packaging distributivo introdotti.

## Assunzioni, limiti e handoff

Le evidenze automatiche provano il comportamento con i finti, non il dispositivo
reale. CPU/RSS del finto pactl non equivalgono a pactl di sistema. M1–M7 sono
fonti documentali lette, non misure ripetute da Codex. Restano la prova reale di
GM (in particolare sospensione e punto 18), riesame di Claude e firma DoD B.

Nessuna domanda di prodotto bloccante emersa. Nessuna richiesta per `design/`.
Tracker, contesto, spec e hardware-lab non modificati: Claude aggiornerà tracker
e riferimenti ormai superati alla misura Scarlett in
§6.1 punto 3/§8 punto 2, già coperta da M7. Brain consultato solo tramite
agvm-scambio, senza operazioni di registro o scritture: la memoria restituita
riguardava la milestone 0 e non è stata usata al posto della repo. Promozione
della milestone al brain riservata a Claude dopo audit/prova reale.

Ricerca tramite graphify query/affected/path; `graphify update .` eseguito dopo
il tratto lungo senza commit e hook attivi su tutti i commit. Nessuna ricerca
con grep/rg. Gli artefatti graphify già sporchi all'inizio e poi rigenerati dagli
hook restano fuori dai commit di consegna; non sono state scartate modifiche
preesistenti. Letture mirate del codice delle librerie installate hanno verificato
le firme dbusmock; nessuna dipendenza runtime aggiunta rispetto alla spec.

## Correzioni dopo audit 1

Obiettivo: risolvere tutti gli undici punti di §7, base `938f8a5`, mantenendo
lo scope §3 e i vincoli di isolamento. Nessuna contraddizione normativa o
nuova decisione di prodotto emersa; nessuna domanda o richiesta per `design/`.
Il precedente stop `7a22ab0` resta superato da M6/M7, come descritto all'inizio.

### Punto → commit → test

I nomi seguenti sono test pytest riproducibili; i tre commit hanno superato
`make check` sia prima del commit sia nel pre-commit, mai aggirato.

| Punto | Correzione/verifica | Commit | Evidenza automatica |
|---|---|---|---|
| 1 | Un solo timer di recupero, invalidazione della generazione, nessun secondo `_down` durante l'attesa; subscribe precedente raccolto | `bbf17c7` | `test_audio_recovery.py::test_single_retry_full_backoff_and_no_orphan`: timer precedente rimosso, ritardi esatti 1→2→4→8→16→30→30, reset a 1 dopo recupero, un solo figlio finale e PID precedenti assenti da /proc |
| 2 | Target persistente conservato senza istantanea o con backend disabilitato/fallimento del comando | `bbf17c7` | `test_restore_preserves_target_without_snapshot[snapshot_failed/disabled]`: memoria e byte del file invariati, ripristino successivo riuscito; `test_audio_respects_default` verifica anche scelta utente, sink sparito e fallimento comando |
| 3 | `try/finally` completa ogni operazione anche dopo eccezioni; deadline dei comandi `[backend].command_timeout_seconds` (default 10 s) | `bbf17c7` | `test_routing_exception_always_finishes_and_drains_queue` (indice assente, lancio, done, salvataggio); `test_command_deadline_reaps_child_and_finishes_queue` (tre comandi di istantanea, set-default, move); `test_command_deadline_configuration` |
| 4 | UTF-8 con sostituzione, framing incrementale, JSON completo corrotto e qualsiasi eccezione di lettura causano `_down` | `bbf17c7` | `test_json_invalid_utf8_and_complete_malformed_object`, `test_subscription_read_exception_recovers` (garbage, JSON malformato, tipo di evento errato); JSON spezzato già coperto da `test_json_stream` |
| 5 | `Error.detail` contiene una descrizione tecnica inglese distinta dal codice | `19db613` | `test_service.py::test_error_signal_technical_detail`: sette codici prodotti dalla policy, payload esatto osservato sul bus privato |
| 6 | C7 emette l'errore dopo INGRESSO e conserva `last_error == "sink_timeout"` | `19db613` | `test_policy.py::test_rules[C7]`: contesto e ordine esatti; test del segnale `sink_timeout`: Transition prima di Error e LastError persistente |
| 7 | Nessuna scrittura di state.json senza target da ripristinare | `bbf17c7` | `test_empty_restore_never_writes_state`: save sostituito da un errore di test, file ancora assente, done eseguito |
| 8 | Nessuna nuova acquisizione mentre sleeping; fd di risposte tardive chiusi | `00f58b7` | `test_session_recovery.py::test_logind_restart_and_display_change_during_sleep`, `test_inhibitor_reply_arriving_during_sleep_is_closed`: logind privato, nessuna Inhibit durante sleep, una sola dopo wake |
| 9 | Uninstall idempotente con unit assente o già rimossa | `00f58b7` | `test_install_user.py::test_uninstall_is_idempotent_without_systemctl[False/True]`: due chiamate consecutive, Path.home temporaneo, subprocess interamente sostituito |
| 10 | Confronti esatti, rami mancanti, backoff completo e snapshot fallita | `19db613`, `bbf17c7` | `test_rules` (65 casi), `test_sleeping_exits_release_inhibitor`, `test_obsolete_results_and_timers`, `test_late_connect_result_after_c4`; test audio dei punti 1–2 |
| 11 | `connect_timeout` già coerente con decisione 32 e ora con §3.2.1; nessuna correzione del reason necessaria | `19db613` | `test_rules[C5]` controlla reason, LastError e tuple della transizione; `test_error_signal_technical_detail` controlla il codice pubblico `connect_timeout` |

I rami aggiunti al punto 10 includono R2 priorità/blocco, R5 sink pronto,
R6 bloccato/sospeso, C4 collegato, C8 esterno, L1 da scollegamento e pending grab
bloccato, tutte le varianti L4, U1 solo collegato, contesto G7/G9 completo,
risultati e timer obsoleti G12, ConnectResult successivo a C4 e chiusura
inibitore nelle uscite C4/C8/O8/U1 con sleeping. Le liste verificano anche
assenza di azioni extra e ordine di cancellazioni, timer, effetti e segnali.

### Esecuzioni e limiti dell'evidenza

- Audio: test mirati **38 passed in 20.86 s**; gate `bbf17c7` **150 passed in
  25.31 s**.
- Policy/servizio: test mirati **132 passed in 6.26 s**; gate `19db613`
  **188 passed in 26.78 s**.
- Sessione/installatore: test mirati **4 passed in 0.68 s**; gate `00f58b7`
  **192 passed in 27.99 s**, nessuno saltato. Ruff format su 27 file, lint
  verde, mypy senza errori su 14 file sorgente.
- Prova negativa su copia temporanea dei sorgenti `938f8a5` con i nuovi test:
  **14 failed in 3.01 s**, exit 1 atteso, nessun errore di raccolta. I casi sono
  i due ripristini senza snapshot, C7, i sette segnali Error, i due casi logind
  e le due disinstallazioni. Gli stessi casi sono verdi nella suite corrente:
  intercettano i difetti precedenti. Copia e bus privati rimossi al termine;
  nessun checkout o modifica della branch per questa prova.
- `git diff 938f8a5 -- AGENTS.md design docs/context docs/specs
  docs/hardware-lab.md`: vuoto. I file protetti sono intatti.
- Nuovi sorgenti/test limitati a config, audio, policy, service, session,
  install_user, fake_pactl, test_adapters, test_audio_recovery, test_policy,
  test_service, test_session_recovery, test_install_user. Documenti modificati:
  decisioni 39–43, questo report e idle.json. Gli artefatti graphify preesistenti
  e rigenerati dagli hook restano fuori dai commit.
- Nessun nuovo polling: la nuova deadline riguarda esclusivamente i figli
  pactl finiti. Il test idle verifica anche assenza di chiamate senza eventi.
  La configurazione valida interi positivi e il modello espone la nuova chiave.
- Nessun bus reale, Bluetooth reale, pactl reale, install-user o systemctl
  eseguito; nessun push. Uninstall è esercitato solo tramite funzione importata,
  con tutte le chiamate esterne intercettate.

**Evidenza e assunzioni:** i risultati sopra provano gli scenari simulati,
non tempi e reazioni dell'hardware. La prova reale GM 1–18 resta interamente
pendente, inclusa CPU/RSS al punto 18. Nessun punto dell'audit è lasciato senza
correzione o verifica; il riesame architetturale di Claude non è simulato.
Le decisioni tecniche 39–43 sono reversibili; la 41 supera esplicitamente la
precedente cancellazione dello stato in errore della voce 35. Nessun nuovo
contratto D-Bus, dipendenza runtime, testo UI o comportamento fuori scope.

## Msgid CLI

- `Switch Bluetooth audio between PC and phone`
- `Run the daemon`
- `Enable debug logging`
- `Show daemon status`
- `Output JSON`
- `Switch the device destination`
- `Show or change iPhone priority`
- `Scambio is not running; run systemctl --user start scambio`
- `D-Bus error: %(error)s`

## File toccati

- `.githooks/post-checkout`
- `.githooks/post-commit`
- `.githooks/pre-commit`
- `Makefile`
- `README.md`
- `docs/decisions.md`
- `packaging/systemd/scambio.service`
- `pyproject.toml`
- `src/scambio/__init__.py`
- `src/scambio/__main__.py`
- `src/scambio/api.py`
- `src/scambio/cli.py`
- `src/scambio/config.py`
- `src/scambio/core/__init__.py`
- `src/scambio/core/audio.py`
- `src/scambio/core/bluez.py`
- `src/scambio/core/dbus/app.scambio.Scambio1.xml`
- `src/scambio/core/policy.py`
- `src/scambio/core/ports.py`
- `src/scambio/core/service.py`
- `src/scambio/core/session.py`
- `src/scambio/core/transport.py`
- `src/scambio/state.py`
- `tests/conftest.py`
- `tests/fixtures/fake_pactl.py`
- `tests/fixtures/run_daemon.py`
- `tests/helpers.py`
- `tests/test_adapters.py`
- `tests/test_audio_recovery.py`
- `tests/test_install_user.py`
- `tests/test_session_recovery.py`
- `tests/test_config_state.py`
- `tests/test_policy.py`
- `tests/test_service.py`
- `tools/install_user.py`
- `tools/measure_idle.py`
- `docs/verification/01/report.md`
- `docs/verification/01/idle.json`

## Checklist reale per GM: NON ESEGUITA

Comandi copiati dalla spec, **non lanciati** durante questa sessione. La venv
fornisce `scambio` in `.venv/bin`: GM può usare `source .venv/bin/activate` prima
dei comandi. Alla prima installazione, il modello viene creato dal primo avvio;
configurare l'indirizzo e riavviare prima del punto 1. La voce 3 contiene ancora
l'annotazione storica «non misurata finora», superata da M7.

Firma GM: **pendente** · data: **pendente** · punti 1–18: **da eseguire**.

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
