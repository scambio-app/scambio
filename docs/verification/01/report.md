# Spec 01 — Report di consegna

Data: 2026-10-04 · Codex · branch `main` · base documentale `99927b5`.

## Obiettivo ed esito

Implementato §3 della spec 01: demone headless, policy pura, adattatori Gio,
API D-Bus, CLI e unit utente systemd. Consegnate tutte e tre le tappe tecniche,
ciascuna con `make check` verde. **DoD B e chiusura complessiva restano pendenti**:
la prova reale 1–18 e la firma sono riservate a GM e non sono state simulate.

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

Il commit successivo contiene questo report e l'evidenza della misura idle;
si identifica con `git log -1 --format=fuller -- docs/verification/01/report.md`.

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
C1–C10, O1–O11, L1–L4, U1–U2**. Ogni caso verifica stato, azioni previste,
immodificabilità dell'input e presenza della transizione quando lo stato cambia.
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

Ispezione AST del runtime: solo due siti nell'adattatore audio (coalescenza e
riaggancio) e i due rami del pianificatore (millisecondi/secondi). Il pianificatore
riceve esclusivamente i sei timer della policy, li rimuove alla cancellazione e
scarta callback non più correnti. Le chiamate D-Bus hanno timeout configurabili.
Nessun `time.sleep`, thread, asyncio o ciclo di polling nel runtime.

Eseguito `.venv/bin/python tools/measure_idle.py`: due bus privati nuovi,
bluez5, logind, ScreenSaver e finto pactl. Durata misurata **600,092 s**;
inizio **2026-10-04 08:58:10 UTC**. Artefatto: [idle.json](idle.json).

| Processo | CPU nell'intervallo | RSS iniziale | RSS dopo 10 min |
|---|---:|---:|---:|
| Demone | 0,0% | 22.788 KiB | 22.788 KiB |
| Finto pactl subscribe | 0,0% | 11.516 KiB | 11.516 KiB |

Delta CPU nullo alla risoluzione dei tick /proc; **zero chiamate pactl** durante
l'intervallo; stato finale `released`. Il campione comprende il demone reale
Python/Gio con trasporti simulati, non il Bluetooth/audio di sistema. Processi e
bus privati sono stati terminati dal cleanup dello strumento.

**GM eseguirà la misura reale al punto 18** della checklist: non è coperta da
questi numeri e non viene dichiarata fatta.

Limite del campione: il processo è stato avviato durante l'integrazione, prima
delle ultime due guardie per backend audio disabilitato e comandi di priorità
durante l'avvio. Il percorso a riposo misurato (backend disponibile, nessun
comando/evento) è invariato; non si attribuisce al campione la verifica di
quelle guardie, coperte dai test. Il finto pactl è rimasto lo stesso.

## Checklist §6

| Voce | Esito |
|---|---|
| Tooling da repo pulito e hook che rifiuta il rosso | Fatto, evidenza sopra |
| Regole della policy e adattatori con finti | Fatto, casi nominati e suite sopra |
| make check verde, nessun test saltato | Fatto, 132 test |
| Nessun polling, CPU/RSS su finti per 10 minuti | Vedi misura sopra; prova reale riservata a GM |
| Configurazione della spec, nessun dato personale hardcodato | Fatto; MAC sintetici nei test, indirizzo runtime da config |
| Nessun testo it/de nell'app, msgid CLI elencati | Fatto; lista sotto |
| design/ non modificato, richieste esplicitate | Fatto; nessuna richiesta |
| Report e decisioni tecniche dalla 30 | Fatto; decisioni 30–38 |
| Checklist reale copiata con comandi | Fatto, §6.1 sotto |
| Prova reale GM e firma | **Non fatta**, punti 1–18 pendenti |

## Scostamenti e scelte tecniche

Decisioni reversibili 30–38 in `docs/decisions.md`. Sezione `[backend]` aggiuntiva
per rendere configurabili anche i tempi tecnici fissi della prosa. Stubs fissati
alla versione compatibile col PyGObject di sistema. Moduli ausiliari `api.py`,
`core/ports.py`, `core/transport.py` isolano contratto e trasporto.

Il reason `connect_timeout` segue C5, che lo richiede esplicitamente: è assente
per svista dall'elenco riassuntivo dei reason in §3.2.1. Da riallineare da Claude;
non sono stati aggiunti metodi, segnali o proprietà API. Il ripristino all'arresto
menzionato nella vecchia decisione 22 non viene applicato: valgono §3.1.6 e la
successiva decisione 29. Nessuna pausa/muto, MPRIS, UI, profili, estensioni,
scorciatoie, pairing, attivazione D-Bus o packaging distributivo introdotti.

## Assunzioni, limiti e handoff

Le evidenze automatiche provano il comportamento con i finti, non il dispositivo
reale. CPU/RSS del finto pactl non equivalgono a pactl di sistema. M1–M7 sono
fonti documentali lette, non misure ripetute da Codex. Restano la prova reale di
GM (in particolare sospensione e punto 18), audit Claude e firma DoD B.

Nessuna domanda di prodotto bloccante emersa. Nessuna richiesta per `design/`.
Tracker, contesto, spec e hardware-lab non modificati: Claude aggiornerà tracker,
annotazione del reason e riferimenti ormai superati alla misura Scarlett in
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
