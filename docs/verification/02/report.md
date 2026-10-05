# Spec 02 — Report di implementazione

Data: 2026-10-05 · Codex · base: `892a50b` (spec approvata).

## Obiettivo ed esito

Implementare solo §3 della spec 02: pausa MPRIS durante la presa, ripresa dopo
instradamento e RESUME, pausa mantenuta al rilascio voluto, recupero sugli errori
previsti dalla policy. Nessun muto, controllo del telefono, UI o nuova API.

**Correzione 68 consegnata; unità non chiusa.** Audit 2 di Claude positivo su
`7da08ef` (390 test). La prova reale di GM è positiva tranne il doppio switch
(M12, commit `b52447e`): corretto in E e verificato sui finti; resta da riprovare
sull'hardware il nuovo punto 13. Le prove automatiche non sostituiscono quella prova.

## Commit e riproduzione

| Tappa | Commit | Contenuto | Gate |
|---|---|---|---|
| A | `b8153c8` | config, stato, policy, test esatti ed esaustivo | 320 test, make check e pre-commit verdi |
| B | `b7625d4` | adattatore MPRIS e PlayersPort, dbusmock | 334 test, make check e pre-commit verdi |
| C | `c260847` | esecutore, lifecycle, integrazione, budget MPRIS, isolamento harness, evidenza | 357 test, make check e pre-commit verdi |
| D — audit 1 | `7da08ef` | completamenti, arresto, chiusura e stato MPRIS, regressioni esatte | 390 test, make check e pre-commit verdi |
| E — decisione 68 | `:/^Wait for disconnection before restarting a grab` | L1 attende Connected=false; regressioni L1/L2 e doppio switch | 418 test, make check e pre-commit verdi |

E è il selettore Git del commit che introduce la correzione e questo aggiornamento
(per evitare un hash dipendente dal proprio contenuto). Si risolve con:

```sh
git rev-parse ':/^Wait for disconnection before restarting a grab'
```

Tutti hanno il trailer `Co-Authored-By: Codex <noreply@openai.com>`.
Nessun push, nessun aggiramento degli hook. Staging per nomi espliciti.

Comandi di verifica delle tappe A–D, dalla radice della repo (basi storiche):

```sh
make check
.venv/bin/pytest tests/test_policy_players.py -q
.venv/bin/pytest tests/test_players.py tests/test_service_players.py -q
.venv/bin/python tools/measure_idle.py --output docs/verification/02/idle.json
git diff --exit-code 892a50b -- src/scambio/api.py src/scambio/core/dbus
git diff --exit-code 7c09041 -- AGENTS.md design docs/context docs/specs docs/hardware-lab.md
git diff --check
```

Il gate comprende format, lint, mypy strict e pytest. Nessun test saltato.
Output del gate iniziale: [checks.txt](checks.txt); gate audit 1: [audit-1-checks.txt](audit-1-checks.txt).
I bus di sessione e sistema sono creati da conftest prima della raccolta;
subprocessi di demone e CLI rifiutano indirizzi non dbusmock. Nome del servizio
nei test: `app.scambio.Test`. La misura crea autonomamente due bus privati con
lo stesso isolamento. Nessun Bluetooth, pactl o player MPRIS reale contattato;
nessun comando systemctl eseguito. Il servizio utente di GM non è stato toccato.
Scostamento operativo corretto in C: i gate A/B riusavano il nome logico di
produzione degli harness della spec 01, sempre e soltanto sui bus privati;
la tappa C introduce il nome di prova dedicato anche nei subprocessi CLI.
Nessuna chiamata è stata inviata al nome del servizio sul bus reale.

## Audit 1 — punto → commit → test

Base delle correzioni dell’audit 1: `7c09041` (audit di Claude). Commit D come sopra.
Nessun cambiamento alla policy, all'API D-Bus o ai file protetti; nessun ampliamento
oltre i punti richiesti. Decisioni tecniche 64–66. Le righe §3.1.3 109–111 ricevono
il budget di arresto precisato dalla richiesta di audit, senza cambiare la spec.

| Punto dell'audit | Commit | Evidenza automatica |
|---|---|---|
| 1 — eccezioni e done duplicati, player/routing | D | `test_service_players.py::test_queue_completes_once_after_adapter_failure` (entrambe le code: eccezione, doppio done, done seguito da eccezione; callback tardivo mentre il successivo è attivo); `test_error_release_resumes_after_routing_exception` (route, restore, entrambi; ramo CONNECT scaduto: Pause → Play, contatori esatti e disconnessione una sola volta) |
| 2 — SIGTERM con pausa lenta, budget ripresa separato | D | `test_sigterm_during_slow_pause`: T=400 ms, RPC finte da 330 ms, SIGTERM durante Pause; uscita dopo >800 e <1600 ms, sequenza esatta Pause → Play, PlaybackStatus Playing e stato ripulito. `test_stop_starts_resume_budget_after_current_operation`: timer complessivo 4T prima della fine del prefisso, timer ripresa 2T solo dopo, entrambi rimossi; `test_stop_without_pending_players_is_immediate`, `test_stop_deadline`, regressioni grab/release già presenti |
| 3 — nessun I/O dopo close | D | `test_players.py::test_closed_public_operations_only_complete`, `test_close_blocks_late_callbacks` (GetId, ListNames, owner, status, Pause, Play; callback consegnato due volte), `test_close_during_recovery_preserves_state`, `test_close_cancels_pending_calls`: done una sola volta, nessun client/salvataggio, stato invariato |
| 4 — GetId fallito non cancella lo stato | D | `test_unknown_bus_preserves_saved_players` (pause/resume/forget/recover): identità vuota, warning, resume_players in memoria e byte di state.json invariati |
| 5 — validazione esplicita e tipi ristretti | D | `test_invalid_transport_reply` (6 forme malformate), `test_malformed_discovery_completes`, mypy strict; nessun Any/assert in players.py |
| 6 — nome del player nei log, senza contenuti | D | `test_error_logs_player_without_remote_content`: Pause e GetNameOwner indicano il player; titolo/URL remoti esclusi; regressioni errori/timeout MPRIS |
| 7 — confronti completi | D | `test_policy_players.py::test_switch_during_grab_and_double_switch_release`: intero contesto e lista ordinata nei tre passaggi; `test_service_players.py::test_grab_parallel_connect_resume_after_route`, `test_release_during_resume_stays_paused`, `test_sigterm_process[release]`: sequenze intere; anche error/cross-queue rafforzati |
| 8 — PRESA da released con Switch e audio_active | D | `test_policy_players.py::test_switch_grab_from_released_with_audio`: contesto esatto e SavePriority(false), PausePlayers(grab), Connect, timer CONNECT, transizione, in quest'ordine (§3.1.4, 147–149) |

Gate eseguito: **390 passed in 46,47 s**, zero skip; format, lint e mypy verdi.
Comandi eseguiti per l'evidenza finale:

```sh
make check > /tmp/scambio-audit1-checks.txt 2>&1
cp /tmp/scambio-audit1-checks.txt docs/verification/02/audit-1-checks.txt
git diff --exit-code 7c09041 -- AGENTS.md design docs/context docs/specs docs/hardware-lab.md src/scambio/api.py src/scambio/core/dbus
git diff --check
```

Il confronto dei 18 SHA-256 protetti/API catturati all'inizio dell'audit non ha
rilevato cambiamenti. Il commit di Claude `7c09041`, che aggiunge l'audit alla spec,
è preservato. Tutti i test continuano a usare i soli bus privati di conftest.
Nessuna operazione sul servizio reale, sui bus reali o sui dispositivi.

**Idle non rimisurato**, secondo la condizione posta nell'audit: cambiano soltanto
operazioni richieste, callback, gestione errori e arresto. Nessun nuovo lavoro
nel percorso quiescente, nessun polling o sottoscrizione, nessun timer a riposo.
I due watchdog sono creati esclusivamente da stop e rimossi alla conclusione.
`test_pause_candidates_and_idle` resta verde. La misura di 10 minuti sotto è
l'evidenza della versione C: i suoi hash non sono presentati come hash di D.

## Mappa riga della spec → test → commit

Le righe sono quelle di `docs/specs/02-pausa-durante-scambio.md` alla base indicata.
I nomi senza percorso nella prima parte sono in `tests/test_policy_players.py`.
Ogni test di riga usa confronto esatto dell'intero contesto e della lista ordinata.

| Riga / regola | Test | Commit |
|---|---|---|
| 124–133, audio in corso e UNBLOCK | `test_error_outcomes`, `test_g8`, `test_o8`, `test_entry_and_o1`; regressioni UNBLOCK della spec 01 | A |
| 139–140, PAUSA_RILASCIO, audio oppure solo held oppure nessuno | `test_release_p` per locked/sleep/switch/priority | A |
| 141–143, ESITO_ERRORE | `test_error_outcomes` con pending none/release, audio true/false; casi senza held in `test_policy.py::test_rules` | A |
| 147–149, PRESA, nessun audio / audio / held | `test_grab`; `test_policy.py::test_rules[R4/R6]`; `test_switch_grab_from_released_with_audio` | A, D |
| 150–156, RILASCIO per P e per errori | `test_release_p`, `test_error_outcomes`; `test_policy.py::test_rules[O3]` per idle_timeout | A |
| 157–159, INGRESSO con held | `test_entry_and_o1`; `test_release_during_resume_stays_paused` in service_players | A, C, D |
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
| 181, L1 nuova presa / dimentica | `test_grab`, `test_l1_forgets` | A, E (segnale disconnesso, risposta/scadenza già disconnesso) |
| 182, L2 locked/sleeping/audio, otto combinazioni | `test_l2` | A, E (errore RPC e RELEASE scaduto) |
| 184–186, adozioni esterne senza pausa | `test_policy.py::test_rules[R5/U1/C7]`, `test_external_adoption_and_timeout` | A, invariati |
| 188–191, 263–267, invarianti esaustivi | `test_exhaustive_six_events` | A, C (obbligo distinto grab/release) |
| 268–270, flussi | `test_switch_during_grab_and_double_switch_release`, `test_o9_o10_during_resume`; `test_grab_parallel_connect_resume_after_route`, `test_error_while_pause_pending`, `test_release_during_resume_stays_paused` in service_players | A, C, D |
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

Misura della versione C iniziata alle **12:27:02 UTC** del 2026-10-05, durata
**600,099568 s**. Demone: CPU **0,0%** (0,06 s cumulativi a entrambi gli estremi),
RSS **23.084 KiB → 23.084 KiB**. Finto pactl: CPU **0,0%**, RSS
**11.612 KiB → 11.612 KiB**. **Zero RPC MPRIS e zero comandi pactl**
nell'intervallo; stato finale released. Sono valori ai due estremi e una media
CPU sull'intervallo, non una misura del picco RSS. Due misure preliminari durante
la revisione non sono usate come evidenza della versione consegnata.
Il JSON registra gli SHA-256 dei sorgenti caricati, verificati contro la versione
C misurata. L'unità dei timer e la logica attiva non sono accelerate in questa prova.
Nessuna nuova sottoscrizione runtime. L'unico timer nuovo della policy è RESUME;
il watchdog originale di C a 2 × player_timeout_ms da stop è corretto in D:
budget della ripresa 2T dal suo avvio, tetto complessivo 4T (decisione 65).
Sono watchdog di lifecycle, rimossi alla conclusione. L'adattatore non crea timer.

## Prova reale e correzione 68 — 2026-10-05

**Evidenza umana:** M12 registra Chrome, Firefox (dopo la prima riproduzione),
blocco schermo, switch singolo, astine chiuse/riaperte, paplay e Bluetooth spento
con gli esiti previsti. Alla prima riproduzione in una nuova finestra Firefox il
player MPRIS non è ancora disponibile: presa senza pausa, come osservato in M9/M12;
nessun intervento su questo comportamento. GM comunica «tutto ok tranne il doppio
switch». Elisa e blocco durante connecting non hanno dettagli separati in M12:
per questi punti si riporta la conferma complessiva di GM, non una nuova misura.
Le prove di presa fallita e recupero dopo KILL sono documentate da Claude nella
spec §7 (15:29–15:31, `5aa3e70`). Codex non ha eseguito prove sui bus reali.

M11 **annuncio vocale**: tre giri, primo bip udibile 0,95–1,26 s dal sink,
tempo di reazione incluso; GM giudica il ritardo di 2 s «perfetto».
La decisione 68 conferma il default meta_glasses a 2000 ms. Q4 è chiusa dalla
decisione 67 per equivalenza accettata da GM con WhatsApp: **GSM non misurato**.

**Difetto del punto 7 (M12):** la risposta positiva a Disconnect precede il
segnale Connected=false. La nuova presa partiva subito e il segnale ritardato
veniva interpretato da C8 come errore, con ripresa sulle casse e adozione esterna
successiva. In E, solo in releasing, risposta positiva + dispositivo ancora
collegato lascia contesto e azioni invariati. RELEASE resta attivo. Il segnale
Connected=false chiude L1; se manca e RELEASE scade ancora collegato, vale L2.
Nessun nuovo timer, stato o API; service.py, players.py e BlueZ invariati.
Nessuna decisione tecnica 69 necessaria: applicazione diretta della decisione 68.

| Spec / misura → requisito | Test | Commit |
|---|---|---|
| §3.1.4, correzione 68, righe 184–188: attesa dopo risposta anticipata | `test_policy.py::test_rules[L1-wait-connected]`; `test_policy_players.py::test_disconnect_success_waits_while_connected` (held sì/no, pending none/grab) | E |
| L1: chiusura solo quando disconnesso, con ripresa della presa o forget | `test_grab`, `test_l1_forgets`: risposta ok/errore già disconnesso, DeviceConnected(false), RELEASE scaduto già disconnesso; contesto e azioni esatti | E |
| L2: risposta positiva non chiude; RELEASE ancora collegato ripristina il routing | `test_l2`: otto combinazioni locked/sleeping/audio, errore RPC o scadenza dopo ok; `test_policy.py::test_rules[L2/L2-timeout]`, `test_release_completion_branches`, confronti esatti | E |
| M12 doppio switch, ordine reale degli eventi | `test_double_switch_waits_for_disconnect_signal`: traccia esatta dalla prima Switch a RESUME; `test_switch_during_grab_and_double_switch_release` aggiornato | E |
| M12, esecutore e adattatori su D-Bus privato | `test_service_players.py::test_double_switch_with_early_disconnect_reply`: Disconnect del mock risponde subito; PropertiesChanged(Connected=false) inviato solo dopo la verifica di releasing/pending grab e dello stesso timer RELEASE; nessuna Connect prima del segnale; Pause → Play con Play soltanto in on_pc sul sink Bluetooth finto, transizioni e azioni esatte nei rispettivi flussi | E |
| Rilascio con blocco/sospensione/switch durante RESUME | `test_release_during_resume_stays_paused`: risposta ok conserva contesto e timer, successivo Connected=false chiude senza Play | E |
| Invarianti §3.2.4 | `test_exhaustive_six_events`: tutte le 34.012.224 sequenze, invarianti invariati | A, C, E |

**Verifica della regressione:** prima di modificare policy.py, i due nuovi test
del doppio switch fallivano: la policy restituiva connecting dopo DisconnectResult;
il servizio riceveva già ConnectResult prima di Connected=false. Dopo la modifica,
281 test mirati verdi (policy, policy_players, service_players), esaustivo incluso.
Gate completo: **418 passed in 47,08 s**, zero skip; format, lint e mypy verdi.
Output: [decision-68-checks.txt](decision-68-checks.txt).

```sh
.venv/bin/pytest tests/test_policy_players.py::test_double_switch_waits_for_disconnect_signal tests/test_service_players.py::test_double_switch_with_early_disconnect_reply -q
.venv/bin/pytest tests/test_policy.py tests/test_policy_players.py tests/test_service_players.py -q
make check > /tmp/scambio-68-checks.txt 2>&1
cp /tmp/scambio-68-checks.txt docs/verification/02/decision-68-checks.txt
git diff --check
```

Solo policy.py cambia a runtime. **Idle non rimisurato**: nessuna modifica al
percorso a riposo, a service.py o players.py; resta la misura C sopra, senza
attribuirne gli hash a E. Test esclusivamente sui bus conftest, nome app.scambio.Test;
nessun Bluetooth, pactl o MPRIS reale, nessun intervento sul servizio di GM.
I file protetti sono identici agli SHA-256 catturati a inizio turno. La modifica
al workflow già in staging è stata nel frattempo committata dall'altra chat in
`055a15c` ed è preservata; il commit E include solo i file elencati nello scope.

## Checklist §6

- [x] Regole nuove/modificate con test esatti; esaustivo verde; regressioni spec 01 verdi.
- [x] Adattatore, esecutore, avvio e SIGTERM su player dbusmock privati.
- [x] make check correzione 68 verde: 418 passed in 47,08 s; nessun test saltato.
- [x] Nessun polling/sottoscrizione nuova; RESUME; misura CPU/RSS 10 minuti completata.
- [x] Nessun dato personale hardcodato; nuove chiavi nel modello, resume_delay_ms commentata.
- [x] API e XML di produzione identici alla base.
- [x] design/, docs/context/, docs/specs/, docs/hardware-lab.md non modificati.
- [x] Report, mappa, comandi e checklist reale presenti; decisioni tecniche 58–66.
- [ ] Prova reale completamente positiva: M12 e conferma di GM acquisiti; **resta il punto 13 dopo la correzione 68**, non simulato dai test.

## Checklist §6.1 — esiti e riprova con GM

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

| # | Azione / comando esatto | Esito atteso / osservazioni | Evidenza / stato (2026-10-05) |
|---|---|---|---|
| 0a | `python3 ~/Scrivania/Claude/scambio-misure/annuncio.py` — tre giri; lo script ferma/riavvia Scambio | Claude registra M11, durata dalla comparsa del sink, e valuta default 2000 ms | ok · GM + Claude, M11 annuncio; 2000 ms confermati dalla 68 |
| 0b | Chiamata GSM vera sull'iPhone; avvia video sul PC, poi `scambio switch` | Claude registra M12/Q4: chiamata non cade, rientra negli occhiali al rilascio | non misurato; chiuso per decisione 67 di GM |
| 1 | Occhiali sull'iPhone; avvia YouTube in Chrome | ≈0,5 s casse, pausa, connessione/annuncio, ripresa negli occhiali dal punto di pausa | ok · GM, M12 |
| 2 | Ripeti 1 con Firefox | stesso esito | ok dalle prese successive · GM, M12; prima finestra senza MPRIS |
| 3 | Ripeti 1 con Elisa, musica locale | stesso esito | ok nella conferma complessiva di GM; non dettagliato in M12 |
| 4 | Video negli occhiali; blocca con Meta+L, poi sblocca | rilascio, video fermo, nessuna ripresa allo sblocco | ok · GM, M12 |
| 5 | Avvia video e blocca immediatamente con Meta+L durante connecting | rilascia appena collegati, video resta fermo | ok nella conferma complessiva di GM; non dettagliato in M12 |
| 6 | Video negli occhiali; `scambio switch` | rilascio e Priorità iPhone, video fermo | ok · GM, M12 |
| 7 | Video negli occhiali; `scambio switch; scambio switch` | ritorno al PC e ripresa negli occhiali | difetto M12; corretto in E, riprova al punto 13 |
| 8 | Video negli occhiali; chiudi le astine, poi riaprile | external_disconnect, video in pausa, nessuna ripresa spontanea | ok · GM, M12; nuova presa dopo 11 s di silenzio |
| 9 | Occhiali nella custodia chiusa; avvia video | pausa, fallimento entro ≈5–10 s, ripresa casse, nessun nuovo tentativo | ok · Claude, spec §7 (due prove) |
| 10 | Comandi sotto, scegliendo un WAV lungo | audio senza MPRIS resta sulle casse fino alla presa e poi passa negli occhiali | ok · GM, M12 |
| 11 | Video negli occhiali; spegni Bluetooth dal tray | unavailable e video in pausa | ok · GM, M12 |
| 12 | Durante connecting con video: Claude esegue `systemctl --user kill -s KILL scambio` | systemd riavvia il demone, il video riparte | ok · Claude, spec §7 |
| 13 | Dopo la correzione 68: video Firefox negli occhiali, `scambio switch; scambio switch` | pausa, ritorno al PC e ripresa negli occhiali; mai dalle casse; nel journal nessun connect_failed né adozione external_connect intermedia | **pendente · GM con Claude** |

Comandi per il punto 10 (nessun file personale assunto):

```sh
read -r -p 'Percorso assoluto di un WAV lungo: ' scambio_wav
paplay --property=media.role=music "$scambio_wav"
```

Non firmare in base ai test finti. Salvare data, esito e osservazioni di ogni punto;
Claude aggiornerà hardware-lab, tracker e, alla milestone verificata, scambio_brain.

## Scostamenti, assunzioni e handoff

Nessuna decisione di prodotto inventata e nessun ampliamento a §4. Il default
meta_glasses 2000 ms è **confermato dalla decisione 68 e M11**; Q4 chiusa dalla
decisione 67 senza misura GSM. Le osservazioni reali sono attribuite a GM/Claude.
Nessuna richiesta a design/. Nessuna nuova dipendenza, nessun programma esterno per MPRIS, nessun muto o volume modificato.

Scelte tecniche nelle decisioni 58–66. Se il watchdog di arresto scade durante
un'operazione ancora pendente, chiude le chiamate; le voci grab già persistite
restano recuperabili al prossimo avvio (test_stop_deadline). Errori MPRIS si
saltano con warning come da spec; questo non garantisce la ripresa di un player
che rifiuta Play o scompare. Nessun titolo o URL nei log prodotti da Scambio.

Graphify usato per query, affected e path; nessun grep/rg/find di ripiego.
Il server agvm-scambio è stato consultato in sola lettura su scambio_brain:
ha restituito contesto della milestone 0 del 2026-10-04, non evidenza delle
decisioni 50–57 e 68; per queste fanno fede i file letti nella repo. Nessuna
operazione sul registro e nessuna scrittura al brain.

File di questa unità: `src/scambio/config.py`, `state.py`, `core/policy.py`,
`core/ports.py`, `core/players.py`, `core/service.py`; `tests/test_config_state.py`,
`test_policy.py`, `test_policy_players.py`, `test_players.py`, `test_service.py`,
`test_service_players.py`, `test_service_unblock.py`, `conftest.py`,
`fixtures/run_daemon.py`, `fixtures/run_cli.py`; `tools/measure_idle.py`;
`docs/decisions.md`; questo report, `checks.txt`, `audit-1-checks.txt` e `idle.json`.
Per l'audit 1: solo `core/players.py`, `core/service.py`, `test_players.py`,
`test_service_players.py`, `test_policy_players.py`, decisioni, report e log audit.

Restano a Claude la verifica delle correzioni, l'aggiornamento del tracker e la
promozione della milestone nel brain; a Claude con GM la riprova del punto 13.
Codex non modifica i file riservati per soddisfare formalmente una checklist
e non dichiara chiusa la spec prima della riprova.

File della sola correzione 68: `src/scambio/core/policy.py`, `tests/test_policy.py`,
`tests/test_policy_players.py`, `tests/test_service_players.py`, questo report e
`docs/verification/02/decision-68-checks.txt`. Nessuna richiesta a design/;
nessuno scostamento ulteriore o decisione di prodotto mancante.
