# Spec 02 — Report di implementazione

Data: 2026-10-05 · Codex · base: `892a50b` (spec approvata).

## Obiettivo ed esito

Implementare solo §3 della spec 02: pausa MPRIS durante la presa, ripresa dopo
instradamento e RESUME, pausa mantenuta al rilascio voluto, recupero sugli errori
previsti dalla policy. Nessun muto, controllo del telefono, UI o nuova API.

**Implementazione automatica consegnata; unità non chiusa.** La prova reale di GM
(ultima voce di §6) e l'audit di Claude restano da eseguire. Le prove automatiche
non costituiscono evidenza del comportamento dell'hardware.

## Commit e riproduzione

| Tappa | Commit | Contenuto | Gate |
|---|---|---|---|
| A | `b8153c8` | config, stato, policy, test esatti ed esaustivo | 320 test, make check e pre-commit verdi |
| B | `b7625d4` | adattatore MPRIS e PlayersPort, dbusmock | 334 test, make check e pre-commit verdi |
| C | `:/^Integrate player pause lifecycle and verification` | esecutore, lifecycle, integrazione, budget MPRIS, isolamento harness, evidenza | 357 test, make check e pre-commit verdi |

C è il selettore Git del commit che introduce questo report, per evitare un hash
che dipenderebbe dal contenuto stesso del commit. Si risolve con:

```sh
git rev-parse ':/^Integrate player pause lifecycle and verification'
```

Tutti e tre hanno il trailer `Co-Authored-By: Codex <noreply@openai.com>`.
Nessun push, nessun aggiramento degli hook. Staging per nomi espliciti.

Comandi di verifica, dalla radice della repo:

```sh
make check
.venv/bin/pytest tests/test_policy_players.py -q
.venv/bin/pytest tests/test_players.py tests/test_service_players.py -q
.venv/bin/python tools/measure_idle.py --output docs/verification/02/idle.json
git diff --exit-code 892a50b -- src/scambio/api.py src/scambio/core/dbus
git diff --exit-code 892a50b -- design docs/context docs/specs docs/hardware-lab.md
git diff --check
```

Il gate comprende format, lint, mypy strict e pytest. Nessun test saltato.
Output integrale del gate: [checks.txt](checks.txt).
I bus di sessione e sistema sono creati da conftest prima della raccolta;
subprocessi di demone e CLI rifiutano indirizzi non dbusmock. Nome del servizio
nei test: `app.scambio.Test`. La misura crea autonomamente due bus privati con
lo stesso isolamento. Nessun Bluetooth, pactl o player MPRIS reale contattato;
nessun comando systemctl eseguito. Il servizio utente di GM non è stato toccato.
Scostamento operativo corretto in C: i gate A/B riusavano il nome logico di
produzione degli harness della spec 01, sempre e soltanto sui bus privati;
la tappa C introduce il nome di prova dedicato anche nei subprocessi CLI.
Nessuna chiamata è stata inviata al nome del servizio sul bus reale.

## Mappa riga della spec → test → commit

Le righe sono quelle di `docs/specs/02-pausa-durante-scambio.md` alla base indicata.
I nomi senza percorso nella prima parte sono in `tests/test_policy_players.py`.
Ogni test di riga usa confronto esatto dell'intero contesto e della lista ordinata.

| Riga / regola | Test | Commit |
|---|---|---|
| 124–133, audio in corso e UNBLOCK | `test_error_outcomes`, `test_g8`, `test_o8`, `test_entry_and_o1`; regressioni UNBLOCK della spec 01 | A |
| 139–140, PAUSA_RILASCIO, audio oppure solo held oppure nessuno | `test_release_p` per locked/sleep/switch/priority | A |
| 141–143, ESITO_ERRORE | `test_error_outcomes` con pending none/release, audio true/false; casi senza held in `test_policy.py::test_rules` | A |
| 147–149, PRESA, nessun audio / audio / held | `test_grab`; `test_policy.py::test_rules[R4/R6]` | A |
| 150–156, RILASCIO per P e per errori | `test_release_p`, `test_error_outcomes`; `test_policy.py::test_rules[O3]` per idle_timeout | A |
| 157–159, INGRESSO con held | `test_entry_and_o1`; `test_release_during_resume_stays_paused` in service_players | A, C |
| 165, G8 da ogni stato | `test_g8`; `test_policy.py::test_availability_loss_sets_block_from_audio` e `test_availability_loss_preserves_existing_block_in_other_states` | A |
| 166, G12 RESUME tardivo | `test_resume_late` | A |
| 172, C4, collegato e scollegato | `test_error_outcomes[C4]` | A |
| 173, C5 CONNECT | `test_error_outcomes[C5]` | A |
| 174, C6 SINK propria presa | `test_error_outcomes[C6]` | A |
| 175, C8 propria / esterna | `test_error_outcomes[C8]`; `test_policy.py::test_rules[C8-external]` invariato | A |
| 176, O1 held e no held | `test_entry_and_o1`; `test_policy.py::test_rules[O1]` | A |
| 177, O8 held / audio / nessuno | `test_o8` (quattro combinazioni) | A |
| 178, O10 e O9 durante RESUME | `test_o9_o10_during_resume` | A |
| 179, O11 sink_lost | `test_error_outcomes[O11]` | A |
| 180, O12 routed e audio, tutte le combinazioni | `test_o12` | A |
| 181, L1 nuova presa / dimentica | `test_grab`, `test_l1_forgets` | A |
| 182, L2 locked/sleeping/audio, otto combinazioni | `test_l2` | A |
| 184–186, adozioni esterne senza pausa | `test_policy.py::test_rules[R5/U1/C7]`, `test_external_adoption_and_timeout` | A, invariati |
| 188–191, 263–267, invarianti esaustivi | `test_exhaustive_six_events` | A, C (obbligo distinto grab/release) |
| 268–270, flussi | `test_switch_during_grab_and_double_switch_release`, `test_o9_o10_during_resume`; `test_grab_parallel_connect_resume_after_route`, `test_error_while_pause_pending`, `test_release_during_resume_stays_paused` in service_players | A, C |
| 52–85, 271–276, MPRIS | `tests/test_players.py`: candidati/idle, status Paused/Playing/Stopped, riclassificazione/forget, owner sostituito/nome sparito, errori/timeout, recupero, shutdown, insieme vuoto | B |
| 78–81, limite delle operazioni | `test_discovery_shares_read_deadline`, `test_close_cancels_pending_calls` in players | C |
| 91–103, FIFO e dipendenze | `tests/test_service_players.py::test_release_waits_for_entire_player_prefix`, `test_grab_parallel_connect_resume_after_route`, `test_cross_queue_dependencies_do_not_deadlock`, `test_error_while_pause_pending` | C |
| 104–108, riparazione all'avvio | `test_startup_repair_before_adapters`, `test_startup_repair_process` (stesso bus / bus diverso); `test_players.py::test_recover` | B, C |
| 109–111, SIGTERM e chiusura | `test_sigterm_process`, `test_sigterm_process_while_releasing`, `test_stop_settles_pending_pause`, `test_stop_deadline`, `test_stop_supersedes_queued_resume`, `test_sigterm_during_releasing`; `test_players.py::test_shutdown` | B, C |
| 218–219, API invariata | diff vuoto di `src/scambio/api.py` e `src/scambio/core/dbus/` rispetto a `892a50b`; test CLI/API esistenti | C |
| 225–234, config e reload | `tests/test_config_state.py::test_player_config_profile_reload`, `test_player_config_invalid`, `test_player_config_bounds`, `test_template_and_readonly`; `test_service_players.py::test_profile_reload_keeps_current_resume_timer` | A, C |
| 238–252, stato opzionale v1 | `tests/test_config_state.py::test_resume_state`, `test_state_roundtrip_and_corruption`; recupero su dbusmock sopra | A, B, C |

L'esaustivo visita tutte le 18^6 = **34.012.224** parole di lunghezza 6 tramite
programmazione dinamica: prefissi con lo stesso contesto e obbligo vengono uniti,
ma conservano il conteggio delle sequenze. Non scarta eventi fuori stato né timer
sintetici. Controlla l'assenza di held negli stati terminali, la conservazione
dell'obbligo fino a Resume/Forget, le sole eccezioni L1/L2 alla pausa di rilascio,
e una continuazione di chiusura per ogni obbligo ancora pendente. Non pretende
di dimostrare progresso con una sequenza infinita che non consegna mai un esito.
I test dell'esecutore coprono la consegna e cancellazione effettiva dei timer.

## Aspettative della spec 01 aggiornate

- `test_policy.py`: costante RELEASE e G8 cancellano anche RESUME; R4 e il flusso
  M8 includono PausePlayers(grab) e held; O8 e G8 on_pc/releasing con audio
  includono PausePlayers(release)/ForgetPlayers. Le righe senza nuovi effetti
  mantengono le attese precedenti. `test_sleeping_exits_release_inhibitor[O8]`
  riusa le attese O8, senza cambiare l'inibitore.
- `test_service_unblock.py::test_m8_gap_and_continuous_silence` (case/bluetooth):
  aggiunto solo held=True al contesto della presa dopo 500 ms. Finestre di
  silenzio 2 s / 9,999 s / 10 s e controlli su Connect invariati.
- `test_service.py`: solo harness CLI/nome di test e confronto del nome di
  produzione nel test di rendering della unit. Nessun esito funzionale allentato.

## Misura idle sui finti

Evidenza grezza: [idle.json](idle.json). Due letture di `/proc` separate da
600 secondi monotoni, senza campionamento periodico: delta dei tick utente+sistema
per CPU, RSS ai due estremi. Demone e finto subscribe misurati separatamente.
BlueZ, logind, ScreenSaver e MPRIS sono dbusmock, pactl è il finto iniettato.

Misura definitiva iniziata alle **12:27:02 UTC** del 2026-10-05, durata
**600,099568 s**. Demone: CPU **0,0%** (0,06 s cumulativi a entrambi gli estremi),
RSS **23.084 KiB → 23.084 KiB**. Finto pactl: CPU **0,0%**, RSS
**11.612 KiB → 11.612 KiB**. **Zero RPC MPRIS e zero comandi pactl**
nell'intervallo; stato finale released. Sono valori ai due estremi e una media
CPU sull'intervallo, non una misura del picco RSS. Due misure preliminari durante
la revisione non sono usate come evidenza della versione consegnata.
Il JSON registra gli SHA-256 dei sorgenti caricati, verificati contro la versione
consegnata. L'unità dei timer e la logica attiva non sono accelerate in questa prova.
Nessuna nuova sottoscrizione runtime. L'unico timer nuovo della policy è RESUME;
il limite 2 × player_timeout_ms durante stop è il watchdog di lifecycle richiesto
esplicitamente da §3.1.3, rimosso alla conclusione. L'adattatore non crea timer.

## Checklist §6

- [x] Regole nuove/modificate con test esatti; esaustivo verde; regressioni spec 01 verdi.
- [x] Adattatore, esecutore, avvio e SIGTERM su player dbusmock privati.
- [x] make check finale verde: 357 passed in 40,64 s; nessun test saltato.
- [x] Nessun polling/sottoscrizione nuova; RESUME; misura CPU/RSS 10 minuti completata.
- [x] Nessun dato personale hardcodato; nuove chiavi nel modello, resume_delay_ms commentata.
- [x] API e XML di produzione identici alla base.
- [x] design/, docs/context/, docs/specs/, docs/hardware-lab.md non modificati.
- [x] Report, mappa, comandi e checklist reale presenti; decisioni tecniche 58–63.
- [ ] Prova reale eseguita e firmata da GM: **non eseguita in questa sessione**.

## Checklist §6.1 — da eseguire da Claude con GM

**Questi comandi sono istruzioni per la prova umana, non comandi eseguiti da Codex.**
La preparazione e gli interventi sul servizio reale spettano a Claude con GM.
Profilo meta_glasses; configurazione personale invariata. Prima di ogni presa
automatica, a riproduzione ferma, verificare che Priorità iPhone sia disattivata.

```sh
systemctl --user restart scambio
journalctl --user -u scambio -f
# In un altro terminale, solo quando si prepara una nuova presa automatica:
scambio status --json
scambio priority off
```

| # | Azione / comando esatto | Esito da verificare | Firma / data |
|---|---|---|---|
| 0a | `python3 ~/Scrivania/Claude/scambio-misure/annuncio.py` — tre giri; lo script ferma/riavvia Scambio | Claude registra M11, durata dalla comparsa del sink, e valuta default 2000 ms | pendente |
| 0b | Chiamata GSM vera sull'iPhone; avvia video sul PC, poi `scambio switch` | Claude registra M12/Q4: chiamata non cade, rientra negli occhiali al rilascio | pendente |
| 1 | Occhiali sull'iPhone; avvia YouTube in Chrome | ≈0,5 s casse, pausa, connessione/annuncio, ripresa negli occhiali dal punto di pausa | pendente |
| 2 | Ripeti 1 con Firefox | stesso esito | pendente |
| 3 | Ripeti 1 con Elisa, musica locale | stesso esito | pendente |
| 4 | Video negli occhiali; blocca con Meta+L, poi sblocca | rilascio, video fermo, nessuna ripresa allo sblocco | pendente |
| 5 | Avvia video e blocca immediatamente con Meta+L durante connecting | rilascia appena collegati, video resta fermo | pendente |
| 6 | Video negli occhiali; `scambio switch` | rilascio e Priorità iPhone, video fermo | pendente |
| 7 | Video negli occhiali; `scambio switch; scambio switch` | ritorno al PC e ripresa negli occhiali | pendente |
| 8 | Video negli occhiali; chiudi le astine, poi riaprile | external_disconnect, video in pausa, nessuna ripresa spontanea | pendente |
| 9 | Occhiali nella custodia chiusa; avvia video | pausa, fallimento entro ≈5–10 s, ripresa casse, nessun nuovo tentativo | pendente |
| 10 | Comandi sotto, scegliendo un WAV lungo | audio senza MPRIS resta sulle casse fino alla presa e poi passa negli occhiali | pendente |
| 11 | Video negli occhiali; spegni Bluetooth dal tray | unavailable e video in pausa | pendente |
| 12 | Durante connecting con video: Claude esegue `systemctl --user kill -s KILL scambio` | systemd riavvia il demone, il video riparte | pendente |

Comandi per il punto 10 (nessun file personale assunto):

```sh
read -r -p 'Percorso assoluto di un WAV lungo: ' scambio_wav
paplay --property=media.role=music "$scambio_wav"
```

Non firmare in base ai test finti. Salvare data, esito e osservazioni di ogni punto;
Claude aggiornerà hardware-lab, tracker e, alla milestone verificata, scambio_brain.

## Scostamenti, assunzioni e handoff

Nessuna decisione di prodotto inventata e nessun ampliamento a §4. Il default
meta_glasses 2000 ms è **provvisorio approvato**, decisione 57: questa implementazione
non misura l'annuncio e non conferma Q4. Nessuna richiesta a design/. Nessuna nuova
dipendenza, nessun programma esterno per MPRIS, nessun muto o volume modificato.

Scelte tecniche nelle decisioni 58–63. Se il watchdog di arresto scade durante
un'operazione ancora pendente, chiude le chiamate; le voci grab già persistite
restano recuperabili al prossimo avvio (test_stop_deadline). Errori MPRIS si
saltano con warning come da spec; questo non garantisce la ripresa di un player
che rifiuta Play o scompare. Nessun titolo o URL nei log prodotti da Scambio.

Graphify usato per query, affected e path; nessun grep/rg/find di ripiego.
Il server agvm-scambio è stato consultato in sola lettura su scambio_brain:
ha restituito contesto della milestone 0 del 2026-10-04, non evidenza delle
nuove decisioni 50–57; per queste fanno fede i file letti nella repo. Nessuna
operazione sul registro e nessuna scrittura al brain.

File di questa unità: `src/scambio/config.py`, `state.py`, `core/policy.py`,
`core/ports.py`, `core/players.py`, `core/service.py`; `tests/test_config_state.py`,
`test_policy.py`, `test_policy_players.py`, `test_players.py`, `test_service.py`,
`test_service_players.py`, `test_service_unblock.py`, `conftest.py`,
`fixtures/run_daemon.py`, `fixtures/run_cli.py`; `tools/measure_idle.py`;
`docs/decisions.md`; questo report, `checks.txt` e `idle.json`.

Restano a Claude audit, aggiornamento del tracker e promozione della milestone nel
brain; a Claude con GM la prova §6.1 e le misure M11/M12. Codex non modifica i file
riservati per soddisfare formalmente una checklist e non dichiara chiusa la spec.
