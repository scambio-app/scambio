# Spec 04 — Report di verifica

Data: 2026-10-07 · Codex · Base: `9e89ce4` · branch `main`, nessun remote.

## Stato e commit

Le tre tappe sono state sottoposte all’audit 1 di Claude; codice in larga
parte conforme e visivo conforme al mock, secondo la consegna GM e §7 della
spec. Correzioni audit 1 completate (vedi sezione dedicata). Il goal **non è
chiuso**: resta anche la prova reale firmata di §6.

| Tappa | Consegna | Commit | Verifica |
|---|---|---|---|
| (a) | Scorciatoia, stato, API e debito MPRIS | `881f494` | `make check`: 614 passati |
| (b) | Configurazione, dispositivi, tray e notifiche | `88ea326` | `make check`: 665 passati |
| (c) | Modello, finestra, CLI, build, installazione e misure | `5e5a3a9` | `make check`: 710 passati |

Nessun hook aggirato. Nessun push. Decisioni tecniche **110–119**,
incluse le correzioni dell’audit 1. Nessuna nuova dipendenza runtime.

## Cosa è cambiato

- Scorciatoia Gio KGlobalAccel/portal, conversione pura GTK/Qt/XDG,
  proprietà `Shortcut*`, `RetryShortcut`, memoria del preferito in state.json.
  La pressione chiama l'API pubblica `Switch()` tramite un client separato;
  non modifica la policy. Arresto con `setInactive`/NO_AUTO_START, mai unregister.
- `SetConfig` modifica solo i valori richiesti, preserva commenti, CRLF e
  permessi, verifica il TOML risultante e scrive atomicamente. Config pubblica,
  filtro ListDevices, DeviceBusy e RestartUnit dopo la risposta, con cgroup
  iniettabile nei test. Fuori dall'unità: RestartRequired col file già scritto.
- Il tray possiede e rilascia il nome noto SNI; il watcher vede sparire
  l'icona quando il tray è disattivato. La voce Impostazioni attiva la finestra
  tramite D-Bus. Le notifiche priority sono sospese solo col nome
  Settings.Active posseduto; gli errori restano.
- Modello puro e finestra GTK separata, 21 ID del contratto, traduzione XML
  prima di Gtk.Template, serializzazione dei cambi rapidi senza echi,
  recupero della connessione quando torna il demone, nome Active legato al focus.
  Una seconda CLI presenta la stessa finestra. Il demone non importa GTK.
- `scambio settings`, flag di servizio nascosto, diagnostica GTK mancante;
  `make ui` integrato in check/run/install-user. L'installatore produce e
  rimuove soltanto unità utente, lanciatore e servizio D-Bus della finestra.

## Evidenza automatica

La baseline era verde: **569 test**, nessun salto (65,01 s).
Tappa (a): **614**, 73,72 s; tappa (b): **665**, 78,13 s.
La verifica finale della tappa (c) ha dato **710 test**, 79,59 s, nessun
salto: [make-check.txt](make-check.txt). Cataloghi, Blueprint, ruff format,
ruff check e mypy (28 file) verdi. Include l'esecuzione via attivazione
D-Bus con un percorso contenente spazi.

| Requisiti | Evidenza |
|---|---|
| §3.1.1 / 05 §5.11 | `tests/test_shortcuts.py`: 44 test, inclusa tabella completa dei tasti e modificatori, autoload, conflitto, binding scelto dall'utente, segnali, errori, riavvio KGA, portal Response immediata, shutdown e ordine proprietà/risposta |
| §3.1.2–3.1.4 | `tests/test_config_edit.py` (29) e `tests/test_settings_api.py` (19): conservazione byte/permessi, rifiuti sicuri, Config prima della risposta, nessun Error/LastError su rifiuto, busy anche per indirizzo editato nel file, RestartUnit finto, filtro BlueZ |
| §3.1.5 / 05 §5.10 | `tests/test_settings_model.py` (35): stati, backend, dispositivi, minuti, lingua, azioni, tre modifiche rapide, errori e banner; import puro e chiavi catalogo |
| GTK reale | `tests/test_window.py` → `tests/fixtures/run_settings.py`: 21 ID/tipi, tedesco con LANG=C, nessuna chiave visibile, azioni, cambi priority/minuti/tray e nessun eco, Active, scomparsa/ritorno demone, seconda CLI con una sola finestra |
| CLI settings | `tests/test_settings_cli.py` (5): flag passato e nascosto, import mancante/versione non supportata con errore tradotto |
| §3.1.6 | `tests/test_install_user.py` (6): HOME temporanea, validazione desktop, avvio tramite Gio, spazio e caratteri quotati, servizio D-Bus, rimozione idempotente; `tests/test_tray.py`: Activate e warning se servizio non attivabile |
| §3.1.7 | `tests/test_notifications.py` (31): priority sospesa in foreground, errori consentiti e ripresa alla perdita del nome |
| §3.1.8 | `test_tray_name_disappears_and_returns`; `test_empty_startup_without_bus_identity_is_silent` |
| Invarianti | `tests/test_presentation.py`: modelli puri, nessun timer UI, nessun import core/GTK fuori dal confine previsto; cataloghi verificati dai test i18n; mypy strict sul modello |

I test non provano il comportamento reale di GNOME o Plasma 6: **non verificati**.
Il fallback UnknownMethod verso portal è coperto con mock. Nessuna assunzione
su una firma nuova Bluetooth/audio: gli adattatori usano le misure M16–M18.

## Misure di risorse

Metodo: due campioni di `/proc/<pid>/stat`, separati da dieci minuti;
nessun campionamento periodico. Bus di sistema/sessione dbusmock, BlueZ,
logind, ScreenSaver, MPRIS, watcher SNI e notifiche finti; fake pactl.
Il timeout del laboratorio non è un timer del demone. Gli artefatti
registrano data UTC, durata, PID, hash sorgenti e contatori delle chiamate.

- [idle-before.json](idle-before.json): baseline caricata prima delle
  modifiche, **600,09 s**, CPU demone **0,0%**, RSS **23.764 → 23.892 KiB**.
  Zero chiamate durante l'intervallo a pactl, MPRIS, watcher e notifiche.
  Non contiene la scorciatoia, non ancora implementata nella baseline.
- [idle-after.json](idle-after.json): **600,10 s**, CPU demone **0,0%**,
  RSS **24.324 → 24.452 KiB** (circa 25,04 MB, sotto 40 MB), con KGlobalAccel
  finto **active**. Zero chiamate a pactl, MPRIS, watcher, notifiche e KGA
  durante l'intervallo; RSS finale +560 KiB rispetto alla baseline.
  Hash dei sorgenti verificati contro i file consegnati.
- [window-rss.json](window-rss.json): finestra GTK 4.14.5 / libadwaita 1.5.0
  aperta, **157.496 KiB ≈ 153,8 MiB**. È il processo dell'harness GTK dopo
  i controlli d'integrazione: comprende anche import e oggetti di prova
  dbusmock. Non è una misura del solo codice della finestra. La soglia
  di 40 MB riguarda il demone, non questo processo.

Riproduzione:

```sh
.venv/bin/python tools/measure_idle.py --ui --shortcuts --output docs/verification/04/idle-after.json
.venv/bin/python tools/measure_settings.py --output docs/verification/04/window-rss.json
```

## Debiti chiusi

**MPRIS.** `recover()` senza stato termina prima di chiedere GetId; il primo
`forget()`/`pause()` poteva chiamare `_save()` con insieme vuoto e identità
ancora assente. Ora quel caso non salva e non avverte. Con player o stato
di recupero effettivi il warning rimane e i dati non vengono cancellati.

**Tray M17.** Nome `org.kde.StatusNotifierItem-<pid>-1` posseduto con
DO_NOT_QUEUE, registrato dopo l'acquisizione, rilasciato alla disattivazione
ed alla chiusura, ripreso e registrato alla riattivazione. Test sul bus privato;
la sparizione visibile nel pannello resta nel punto 6 della prova GM.

## Scostamenti, limiti e tracciabilità

- Letti AGENTS, contesto 01–06, hardware-lab, spec; ricerche con graphify,
  decisioni e brain tramite il solo MCP `agvm-scambio`, sola lettura.
  Il brain ha restituito un pacchetto parziale di milestone precedenti;
  nessuna memoria assunta come requisito nuovo. Nessun grep/rg di ripiego.
- Stop preliminare per contrasto fra §6.1 punto 8 e 05 §5.10 sul banner.
  La modifica esterna alla spec lo ha risolto in «nessun banner»; Codex ha
  ripreso, senza editare né committare spec e hardware-lab modificati da altri.
- `design/ui/tray.json` è la copia **identica** del file Claude
  `~/Scrivania/Claude/scambio-misure/tray.json.spec04`, come autorizzato da
  §3.1.6 nella tappa (b). Nessun altro file design toccato, nessuna richiesta
  di widget, testo, icona o stile.
- Blueprint emette `translatable="true"`: il traduttore XML accetta anche
  questa forma e `1` oltre a `yes`; test GTK tedesco ne prova l'effetto.
- Il quoting segue la [specifica Desktop Entry](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html).
  `desktop-file-validate` accetta il file con `%` raddoppiato in Exec, ma
  nella Gio locale `DesktopAppInfo.new_from_filename` rifiuta il lanciatore
  quando **l'eseguibile stesso** contiene `%` nel percorso (anche eliminando
  TryExec). Limitazione osservata, non aggirata con wrapper o altri file.
  Spazi, backslash, virgolette, dollaro e backtick sono provati tramite Gio;
  l'attivazione D-Bus era inizialmente provata con spazi. Le correzioni audit 1
  recepiscono §3.1.6 aggiornata e provano anche `%` e backslash nel servizio
  D-Bus (decisione 118), senza alterare il quoting del `.desktop`.
- Durante uno smoke test preliminare sotto Xvfb e bus privato, prima
  dell'isolamento aggiuntivo, GTK ha tentato di attivare i portal installati
  **su quel bus privato**. Questo non rispettava il divieto operativo sui
  portal reali. Il test è stato sostituito con bus dbusmock senza servizi
  attivabili, prima dell'import GTK; la suite finale controlla questo
  isolamento. Nessuna interazione con Bluetooth/KGlobalAccel/notifiche o
  display della sessione GM effettuata dai test finali.
- Nessuna installazione nel profilo reale e nessun binding dell'utente
  modificati da Codex. M19, arrivata come modifica esterna di hardware-lab,
  registra la preparazione khotkeys di Claude/GM, non una prova di Scambio.

## Checklist §6

- [x] Prerequisiti di prodotto/design forniti da Claude (baseline `9e89ce4`).
- [x] Correzioni audit 1 completate; implementazione e copertura di §3.1 / 05 §5.10–§5.11,
  secondo la matrice dei test sopra; limiti desktop reali dichiarati.
- [x] Verifica finale `make check`, cataloghi e Blueprint, nessun test saltato.
- [x] Nessun polling/timer nuovo; CPU/RSS prima-dopo entro soglia, RSS finestra documentato.
- [x] Nessun valore personale hardcodato in produzione, nessun testo visibile
  o valore di stile introdotto nel codice; chiavi e asset del design.
- [x] Design preservato, con la sola copia autorizzata §3.1.6, nessuna richiesta nuova.
- [x] Confini di scrittura rispettati; installatore limitato ai tre file.
- [x] Due debiti §3.1.8 corretti con test.
- [x] Report, GNOME/Plasma 6 non verificati, decisioni 110–119.
- [x] Checklist GM preparata qui sotto.
- [ ] Prova reale GM eseguita e firmata.

## Checklist di prova reale GM — da eseguire

Responsabili: Claude prepara installazione e screenshot; GM esegue le azioni
con occhiali e iPhone. Registrare esito, anomalie e data per ogni punto.
Un punto non applicabile (assenza di seconda cuffia) va motivato, non segnato
come prova riuscita. Conservare il config prima della prova e ripristinare
minuti/lingua alla fine.

- [ ] **0. Preparazione Claude:** verificare backup/rimozione khotkeys di M19,
  `make install-user`, riavviare Scambio; `scambio status` deve riportare
  `ShortcutState: active`, `ShortcutBackend: kglobalaccel`, `Shortcut: <Super>g`.
  Annotare commit provato e versioni desktop.
- [ ] **1. Tastiera:** occhiali sul PC con video; Meta+G li lascia all'iPhone,
  notifica con Annulla e lucchetto. Secondo Meta+G li riprende sul PC con
  notifica di priorità disattivata. Verificare anche Annulla con finestra chiusa.
- [ ] **2. KCM:** gruppo Scambio e azione «Switch intelligente (PC ↔ iPhone)»
  su Meta+G. Cambio tasto dal KCM conservato dopo riavvio del demone; poi
  ripristinare Meta+G. Rimozione del tasto rispettata al riavvio, poi ripristinare.
- [ ] **3. Apertura dal tray:** Impostazioni apre la finestra; annotare se viene
  in primo piano su X11. Stato/pulsante coerenti col tray. Lascia all'iPhone
  dalla finestra funziona senza notifica priority. Seconda apertura presenta
  la stessa finestra.
- [ ] **4. Priorità:** modifica nella finestra aggiorna la spunta nel tray senza
  notifica; finestra dietro/inattiva e Meta+G ripristinano le notifiche normali.
- [ ] **5. Minuti:** impostare 3, confrontare config (solo valore 180, commenti
  intatti); alla pausa successiva compare «tra 3 min». Ripristinare 2.
- [ ] **6. Tray:** disattivare l'icona, verificarne la sparizione immediata;
  riattivare, verificare una sola icona e menu funzionante.
- [ ] **7. Lingua:** Deutsch mostra avviso, tray tedesco subito; chiudere e
  riaprire la finestra, ora tedesca. Ripristinare Automatica e riaprire.
- [ ] **8. Dispositivo:** con occhiali sul PC, elenco bloccato e spiegazione.
  Se disponibile una seconda cuffia accoppiata: prima lasciare gli occhiali,
  scegliere la cuffia, avviso di riavvio **senza banner**, poi dati del nuovo
  dispositivo; ritornare agli occhiali. Annotare eventuale RestartUnit fallito.
- [ ] **9. Cambia:** apre il KCM sulle scorciatoie di Scambio.
- [ ] **10. Apri:** il file di configurazione si apre nell'editor previsto.
- [ ] **11. Arresto/ripartenza:** Esci da Scambio colla finestra aperta mostra
  il banner e disabilita i gruppi; Avvia recupera stato e controlli.
- [ ] **12. Lanciatore:** menu applicazioni → Scambio apre la finestra anche
  senza icona tray; verificare icona e identificazione della finestra.
- [ ] **13. Audit Claude:** screenshot reali chiaro/scuro, confronto col mock,
  testi e focus; registrare esito nella spec.

**Commit provato:** … · **Esiti/allegati:** … · **Firma GM e data:** …

## File e handoff

Elenco completo dei file del lavoro: `git diff --name-only 9e89ce4..HEAD`.
I commit (a)/(b) contengono core scorciatoia/API/config, stato, tray/notifiche
ed i relativi test; (c) contiene `src/scambio/ui/{settings_model,window,client}.py`,
CLI, paths, Makefile, pyproject, installatore, strumenti di misura, test
settings/model/GTK/installazione, decisioni e artefatti di questo report.

A Claude: audit codice e visivo, compilazione del tracker/spec al completamento,
promozione delle misure pertinenti in hardware-lab e, alla milestone verificata,
brain `scambio_brain` secondo §6 del workflow. Codex non modifica quei file
né scrive sul brain. GNOME e Plasma 6 restano per Q6, prima della fase 5.


## Correzioni audit 1

Base dell’audit: `881f494`, `88ea326`, `5e5a3a9`; base di questa correzione:
`0c84d9a`, che corregge §3.1.6 per il quoting del servizio D-Bus.
Scope esclusivo: i tredici punti consegnati da GM. Nessuna modifica a design,
nessuna nuova API, dipendenza o timer. Le note d’audit aggiunte da Claude alla
spec durante il lavoro sono modifiche esterne e restano fuori dal commit Codex.

### Correzioni e prove

| # | Esito / modifica | Test |
|---|---|---|
| 1 | Rimozione esplicita dopo conflict conservata, decisione 116 | `test_foreign_unbind_after_conflict_persists_desktop_choice`: stato iniziale senza preferito, rimozione, rilettura store e nuovo avvio con flag 2 |
| 2 | Errore → scarto del valore in coda, un solo avviso e riallineamento | `test_rapid_edits_are_discarded_after_error`, ConfigInvalid e DeviceBusy, tre incrementi rapidi |
| 3 | Prima perdita del nome consuma restarting; soppressione mantenuta per quella sola assenza, secondo il chiarimento Claude | `test_restart_failure_then_quit_suppresses_only_first_absence`: caso RestartUnit fallito → Quit, riapertura e perdite successive |
| 4 | Backend none → unsupported anche con preferito vuoto/non valido | `test_no_backend_is_unsupported_for_disabled_preference`, anche Retry |
| 5 | Quoting D-Bus distinto da Desktop Entry, decisione 118 | `test_dbus_activation_executes_path_with_spaces`: file esatto e argv dell’eseguibile finto, anche `%` e backslash, su dbus-daemon privato |
| 6 | Scrittura atomica sul target risolto, symlink e permessi preservati | `test_write_preserves_relative_symlink_and_target_permissions` |
| 7 | Eccezione inattesa di SetConfig → LOG.exception e risposta Failed | `test_unexpected_set_config_exception_returns_failed`: RPC sul bus e verifica del traceback nel record di log |
| 8 | Proprietario iniziale già disponibile ignorato dalla prima callback appeared | `test_audit_window_boundaries[startup-counts]`: una ListDevices e una RetryShortcut con focus simulato |
| 9 | Tutte le chiavi .pot; proprietà, disabled-text e modelli; traduzioni del layout confrontate col .po tedesco | `test_text_check_detects_any_catalog_key` in quattro superfici e `test_layout_translation_check_detects_wrong_language` con testo inglese iniettato |
| 10 | Mock completamente pronto prima della finestra; nessuna chiamata privata a appeared | `test_window_harness_uses_public_owner_lifecycle`; percorso reale di apertura, perdita/ritorno, anche apertura inizialmente senza owner |
| 11 | Flag NO_AUTO_START e chiamata prima del flush confermati | `test_shutdown_inactive_no_auto_start_before_flush`, Quit e SIGTERM in sottoprocesso, osservando le chiamate Gio effettive |
| 12 | DISMISSED/CANCELLED ignorati; altri errori locali mostrano exc.message intero | `test_audit_window_boundaries[desktop-errors]`: FileLauncher e URI, compreso messaggio contenente un punto |
| 13 | Senza display: diagnostica cli-error-gtk-missing, stderr e uscita 1, senza traceback | `test_audit_window_boundaries[no-display]`, con DISPLAY/WAYLAND_DISPLAY rimossi nel figlio sotto Xvfb e bus privati |

Prove rosso → verde: prima delle correzioni sono stati riprodotti sette
fallimenti nel gruppo core/config/API/installazione e sette nella finestra;
separatamente è fallito il controllo della traduzione inglese iniettata.
I punti 1 e 11 erano già conformi: i nuovi test passavano anche prima e non
vengono presentati come difetti corretti. Su copie temporanee del codice
sono stati verificati i controlli negativi: omettere la persistenza, togliere
NO_AUTO_START o anticipare il flush fa fallire i test corrispondenti. Il
controllo del punto 10 fallisce sul fixture originale con la chiamata privata.
Nessuna mutazione sperimentale è stata applicata al codice della working tree.

### Chiarimento del punto 3 recepito

Decisione di Claude trasmessa da GM: la prima scomparsa del nome dopo il
successo del cambio dispositivo consuma `restarting`, mantenendo nascosto
il banner per quella sola assenza. Il banner resta nascosto anche se altri
aggiornamenti fanno ridisegnare la finestra o ripetono lo stato assente.
Al ritorno del nome la soppressione finisce; ogni perdita successiva mostra
il banner. Una finestra riaperta senza demone mostra il banner normalmente.

Nel caso raro RestartUnit fallito senza perdita del nome, un Quit successivo
è quella prima scomparsa e resta quindi senza banner: limite esplicitamente
accettato, senza introdurre timer, segnali o API. Decisione 117 aggiornata.
Il test nuovo fallisce prima della modifica sul mancato consumo di
`restarting` e passa dopo, verificando anche persistenza della soppressione,
riapertura e due perdite successive.

### Verifiche e file

`make check`: **731 passati, nessuno saltato**, 85,30 s; lint, format,
mypy (28 file), cataloghi e Blueprint verdi:
[audit1-make-check.txt](audit1-make-check.txt).
Riproduzioni e controlli negativi: [audit1-regressions.txt](audit1-regressions.txt).
Tutti i tredici punti sono inclusi nel commit unico `Fix spec 04 audit findings`
contenente questo report. Le misure CPU/RSS sopra
restano evidenza dei commit dell’implementazione iniziale; non vengono
attribuite ai sorgenti modificati dall’audit.

File di produzione: `config.py`, `core/{service,shortcuts}.py`,
`ui/{client,settings_model,window}.py`, `tools/install_user.py`.
Test: config_edit, install_user, settings_api, settings_model, shortcuts,
window e fixture run_daemon/run_settings. Documenti: decisioni 116–119 e
questo report. Nessuna richiesta per design. Prova GM ancora da eseguire.
