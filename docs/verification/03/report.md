# Spec 03 — Report di implementazione

Data: 2026-10-06 · Codex · branch `main` · base `995928e`.

## Obiettivo ed esito

Implementare `docs/specs/03-tray-notifiche.md` §3 e il contratto di
`docs/context/05-ui-context.md` §5. Consegnati localizzazione it/en/de,
tray SNI/dbusmenu, notifiche essenziali, `Quit()` e ricarica della UI.
**La spec non è chiusa: prova reale e firma di GM ancora pendenti, così come
l'audit visivo di Claude.** GNOME/AppIndicator non verificato.

Nessun contatto con Bluetooth, audio, notifiche o bus di sessione reali durante
le prove automatiche; nessuna installazione, modifica del tema o riavvio del
servizio utente effettuati da Codex.

## Commit e gate

| Tappa | Commit | Evidenza |
|---|---|---|
| (a) paths/i18n, CLI, inibitore, configurazione, build | `52a300b` | pre-commit `make check`: 441 passed, zero skip |
| (b) presentazione, proxy e notifiche | `5bfe574` | pre-commit `make check`: 531 passed, zero skip |
| (c) tray, Quit, lifecycle, verifiche e report | commit contenente questo report | `git log -1 --format=fuller -- docs/verification/03/report.md` |

Baseline verde: 418 test. Gate conclusivo: **564 passed in 63,69 s**,
zero skip; ruff format/lint e mypy verdi (24 sorgenti). Log: [make-check.txt](make-check.txt).
Hook pre-commit mai aggirato, nessun push. Decisioni tecniche 90–94.

## Cosa cambia

- `paths.py` individua design e cataloghi nella repo; override degli asset per i
  test. `make i18n` usa `msgfmt --check` per tutte le lingue; `check`, `run` e
  `install-user` compilano i cataloghi in `build/locale`, ignorata da git.
- `i18n.py` risolve la lingua senza Gio e gestisce fallback e maiuscola del solo
  nome dispositivo mancante. CLI e motivo dell'inibitore usano chiavi. Il
  modello TOML genera commenti tradotti solo alla creazione; i file esistenti
  restano invariati. `ui.tray`/`ui.notifications` sono booleani con default true.
- Presentazione letta e validata da `tray.json`: regole, precedenze, etichette,
  icone e parametri delle notifiche. Minuti ricalcolati aprendo il menu, tooltip
  con ora assoluta. Nessun timer né polling nella UI.
- Proxy Gio asincrono sulla stessa API pubblica; correlazione delle notifiche
  per ordine dei segnali e intervallo chiamata/risposta. Famiglie serializzate
  per usare correttamente `replaces_id`; errori visti o risolti cancellano
  l'indicatore. Azioni obsolete ignorate; apertura configurazione tramite portal.
- SNI e dbusmenu via Gio, registrazione a ogni comparsa del watcher, segnali solo
  al cambio del modello, menu e toggle con firme D-Bus corrette. `Reload` applica
  lingua e interruttori UI. `Quit` con risposta e flush prima dell'uscita 0,
  stessa gestione MPRIS di SIGTERM, senza scollegare né cambiare instradamento.
- Asset mancanti/non validi disattivano la UI con log; l'API continua a funzionare.
  Le callback hanno confini di eccezione; una richiesta menu errata riceve un
  errore D-Bus e non blocca quelle successive.

## Evidenze automatiche

| Requisiti | Prove |
|---|---|
| Tutte le 9 regole, overlay per codice/precedenze, tooltip, stato switch e toggle | `tests/test_presentation.py`: tabella regole, overlay in it/en/de, 20 combinazioni stato/configurazione/priorità |
| Confini minuti | 120000001, 120000000, 60000001, 60000000, 0 e -1 µs; ora locale nel tooltip |
| Vocabolario JSON e asset | Mutazioni invalide, icone esistenti, chiavi e azioni validate; errori API coperti dalla mappa |
| Cataloghi e modello | `tests/test_i18n.py`: PO/POT con stesse chiavi, MO compilati equivalenti, segnaposto esatti, template TOML valido nelle tre lingue, copertura commenti non-backend, file esistente intatto |
| Lingua, fallback e caratteri speciali | `LANGUAGE=de:it`, `LC_ALL=C` + `LANG=it_IT.UTF-8`, fallback inglese/chiave, catalogo troncato, dispositivo vuoto e `_&<>`, CLI tedesca senza creazione del file, quattro errori D-Bus CLI tradotti, inibitore alla nuova acquisizione |
| Notifiche | `tests/test_notifications.py`: nove errori, quattro cambi di priorità, tipi hint, sostituzione/chiusura, id estranei, azioni valide/non valide, startup-only, once-per-run, OpenURI, eccezioni e server assente |
| Correlazione senza timer | Comandi propri menu/pulsante silenziosi, C9 senza Transition, Switch senza cambio seguito da cambio esterno notificato; prese/rilasci/blocco/sospensione/connessione esterna silenziosi |
| Tray/protocollo | `tests/test_tray.py`: watcher riavviato, GetLayout/profondità/filtri/radice, toggle int32, GetProperty/GetGroupProperties, AboutToShow/Group, Event/Group, errore visto anche con opened, segnali/revisioni e nessun segnale su modello uguale |
| Lifecycle reale del processo su finti | `tests/test_ui_service.py`: tray/menu → API vera `app.scambio.Test`, Reload lingua/interruttori, entrambi false, setup/audio mancanti all'avvio, design/cataloghi assenti con API funzionante, Quit esterno e da menu |
| Arresto | Quit in pausa grab/release: risposta ricevuta, exit 0, ripresa solo grab, stato MPRIS pulito e instradamento conservato; suite SIGTERM preesistente ancora verde |
| Confini architetturali | AST senza import core/timer/GTK nella UI; import di `i18n` e `ui.presentation` in nuovo processo senza caricare `gi`; mypy strict sui moduli puri |

Gli errori tecnici pubblici del demone restano codici/descrizioni API stabili;
le superfici utente traducono mediante le chiavi del design. I valori wire
(State, nomi proprietà, codici) e le parole proprie di argparse non si traducono.

## Misura CPU/RSS (10 minuti)

Metodo della spec 01/decisione 38: `/proc/<pid>/stat` ai due estremi, delta tick
CPU su intervallo monotono di 600 s, RSS ai due estremi; nessun campionamento
periodico. Harness con bus privati nuovi, BlueZ/logind/ScreenSaver/MPRIS finti e
pactl finto bloccato su FIFO. La seconda prova aggiunge watcher SNI e server
notifiche finti; la registrazione del tray è attesa prima del campione iniziale.

- Baseline: `.venv/bin/python tools/measure_idle.py --output docs/verification/03/idle-before.json`.
- Dopo: `.venv/bin/python tools/measure_idle.py --ui --output docs/verification/03/idle-after.json`.
- [idle-before.json](idle-before.json): 600,086 s dal 2026-10-06 07:02:01 UTC,
  CPU 0,0%, RSS 22876 → 23004 KiB; zero chiamate pactl/MPRIS durante l'intervallo.
- [idle-after.json](idle-after.json): 600,099 s dal 2026-10-06 07:17:16 UTC,
  CPU 0,0%, RSS **23976 → 24104 KiB** (≈24,7 MB decimali, sotto 40 MB).
  Zero chiamate pactl, MPRIS, watcher e notifiche nell'intervallo. Stato finale
  `released`. Hash di tutti i sorgenti elencati confrontati con la working copy:
  corrispondono; processi misurati terminati dopo cleanup.

Il delta RSS finale rispetto alla baseline è 1100 KiB. Un campione intermedio
precedente agli ultimi cambi runtime è stato sostituito dalla misura conclusiva;
non viene usato come evidenza del codice finale.

Gli hash nei JSON identificano il codice caricato. Il campo `real_measurement`
della baseline è la dicitura storica dello strumento spec 02; questo campione
è stato eseguito per la spec 03 prima delle modifiche. I numeri misurano il demone
con trasporti simulati, non le prestazioni del desktop/BlueZ/PipeWire reali.

## Checklist §6 e limiti

| Voce | Stato |
|---|---|
| Decisioni 70–84 e contesto | Già presenti nella base, letti |
| Regole coperte da test | Fatto, mappa sopra |
| make check verde, zero skip | Fatto: 564 test, log allegato |
| Nessun polling/timer UI; CPU/RSS prima/dopo ≤40 MB | Fatto: CPU 0,0% in entrambi; RSS finale 23004 / 24104 KiB |
| Valori configurabili e nuovi interruttori | Fatto; soli indirizzi sintetici nei test |
| Testi/icona/parametri da design | Fatto; parole argparse escluse come decisione 83 |
| design/ non modificato | Fatto; nessuna richiesta di design |
| Scritture runtime nei percorsi ammessi | Fatto; nessuna scrittura della UI. Repo, build e temporanei dei test secondo eccezione 29a |
| Entrambi interruttori false | Verificati con proxy e demone di processo |
| Report e decisioni da 90 | Fatto |
| Checklist GM con comandi | Preparata sotto |
| Prova reale GM e firma | **Pendente** |

Nessuno scostamento di prodotto. Precisazione tecnica: avvio UI dopo la prima
inizializzazione degli adattatori (decisione 92), per non perdere il LastError
iniziale. Sono stati aggiunti `actions.py` e `guard.py` per separare GAction e
confini delle callback. Nessuna funzione della spec 04 implementata.

Ricerca: graphify query/affected/path; aggiornamento esplicito del grafo dopo il
tratto senza commit. Brain consultato solo tramite MCP `agvm-scambio`, sola
lettura; ricordava le milestone 0 e 2, non le decisioni UI, verificate nella repo.
Nessun fallback grep/rg. Le firme SNI sono state confrontate anche con
l’[XML ufficiale KDE](https://raw.githubusercontent.com/KDE/kstatusnotifieritem/master/src/org.kde.StatusNotifierItem.xml). L'aggiornamento graphify segnala JSON senza nodi; i JSON
di design e misura sono stati letti direttamente, non trattati come memoria.

Assunzioni/limiti separati dall'evidenza: ricolorazione Plasma scuro da M11;
Plasma chiaro e comportamento del desktop reale richiedono la prova seguente.
GNOME non disponibile e non verificato. Il limite dell'etichetta durante switch
annullato a metà resta quello già accettato nel contratto 05 §4.

Claude dovrà aggiornare tracker, checklist della spec e hardware-lab dopo audit
ed esiti di GM, e promuovere la milestone al brain. Questi file protetti non
sono stati modificati da Codex.

## Prova reale per GM — da eseguire e firmare

Prerequisiti: occhiali e iPhone disponibili, dispositivo già configurato;
non cambiare indirizzo e non rifare il pairing. Eseguire dalla repo:

```sh
cd ~/development/scambio
make i18n
systemctl --user restart scambio
.venv/bin/scambio status
journalctl --user -u scambio -f
```

Il journal resta in un terminale separato. I comandi seguenti usano `.venv/bin/scambio`
e non richiedono installazioni di sistema.

| # | Azione/comando esatto | Risultato atteso | Esito GM |
|---|---|---|---|
| 1 | Occhiali sull'iPhone; verificare Breeze scuro; Impostazioni di sistema → Colori → Breeze chiaro, poi tornare allo scuro | Occhiali + telefono distinguibili, colori del tema in entrambe le varianti | Pendente |
| 2 | Avviare un video sul PC, poi metterlo in pausa; aprire menu e tooltip | Monitor, nessuna notifica; nome + «sul PC»; minuti al rilascio nel menu e ora nel tooltip | Pendente |
| 3 | Menu → «Lascia all'iPhone» | Lucchetto e priorità spuntata; nessuna notifica | Pendente |
| 4 | `.venv/bin/scambio switch` | Torna al PC e notifica con priorità disattivata | Pendente |
| 5 | `.venv/bin/scambio switch`, poi pulsante «Annulla» | Notifica di rilascio; Annulla prende dal PC senza seconda notifica | Pendente |
| 6 | Dopo rilascio, `.venv/bin/scambio priority off`; occhiali nella custodia, avviare un video (se serve, attendere silenzio continuo per l'anti ping-pong prima di riavviarlo) | Non raggiungibile + Riprova, icona errore; aprire menu la fa tornare normale | Pendente |
| 7 | Spegnere Bluetooth dall'applet KDE; poi riaccenderlo | Non disponibile, switch disabilitato | Pendente |
| 8 | Aprire `~/.config/scambio/config.toml`; in `[ui]` impostare `language = "de"`; `systemctl --user reload scambio`; `.venv/bin/scambio --help`; ripristinare `language = "auto"` e ricaricare | Menu e help tedesco, poi lingua automatica | Pendente |
| 9 | `kquitapp5 plasmashell && kstart5 plasmashell` | Icona ricompare nello stato corretto | Pendente |
| 10 | Menu → «Esci da Scambio»; `systemctl --user is-active scambio`; `systemctl --user start scambio` | inactive (exit 3 previsto dal comando), dispositivo dove era; nuovo avvio riuscito | Pendente |
| 11 | Catturare menu e notifiche con Spectacle nei due temi; consegnare le immagini a Claude per confronto col mock | Audit visivo documentato; difetti allegati senza cambiare le icone nel codice | Pendente |

Firma GM: **pendente** · Data: **pendente**.
Per chiudere: riportare i numeri dei passi, esito e anomalie; non considerare
queste righe una prova già eseguita.

## File toccati

- `Makefile`, `pyproject.toml`.
- `src/scambio/paths.py`, `src/scambio/i18n.py`, `src/scambio/cli.py`, `src/scambio/config.py`.
- `src/scambio/core/session.py`, `src/scambio/core/service.py`, i tre XML in `src/scambio/core/dbus/`.
- `src/scambio/ui/__init__.py`, `client.py`, `presentation.py`, `actions.py`, `guard.py`, `notify.py`, `tray.py`.
- `tests/test_i18n.py`, `tests/test_presentation.py`, `tests/test_notifications.py`, `tests/test_tray.py`, `tests/test_ui_service.py`.
- `tools/measure_idle.py`, `docs/decisions.md`, `docs/verification/03/{report.md,make-check.txt,idle-before.json,idle-after.json}`.

## Correzione dopo audit — decisione 85 (2026-10-06)

Scope del nuovo `/goal`: clic sinistro del tray secondo la decisione 85 e
`05-ui-context.md` §5.3. Base `43ab731`, branch `main`; commit della correzione:
quello contenente questa sezione (`git log -1 --format=fuller -- src/scambio/ui/tray.py`).
Le sezioni precedenti documentano la consegna originale della spec 03.

`Activate` su `org.kde.StatusNotifierItem` restituisce sempre
`org.freedesktop.DBus.Error.NotSupported` e termina senza altri effetti.
Applicazione diretta della decisione 85, senza nuove decisioni tecniche o
scostamenti dal contratto. `ItemIsMenu` resta vero; `SecondaryActivate`,
`ContextMenu` e `Scroll` restano senza effetti. Nessuna richiesta per `design/`.

Evidenza automatica su bus privati con Gio e dbusmock:

- Il nuovo test, prima della correzione, falliva con `DID NOT RAISE Error`:
  `.venv/bin/pytest tests/test_tray.py -k activate_not_supported --maxfail=1 -q`.
- Dopo la correzione, `.venv/bin/pytest tests/test_tray.py -q`: **17 passed**.
  Il nome remoto dell'errore è verificato in tutti e cinque gli stati, con
  chiamate ripetute e coordinate diverse. Nessuna chiamata a `Switch`,
  `SetPriority`, `Quit`, nessun menu segnato aperto, modello invariato.
- `GetLayout` e `AboutToShow` funzionano dopo l'errore. Con errore UI attivo,
  `Activate` non lo segna visto: lo fanno successivamente `AboutToShow(0)` o
  `Event(0, "opened")`. Gli altri tre metodi SNI non aprono né attivano azioni.
- `make check` verde: **569 passed in 66,14 s, zero skip**; compilazione dei
  cataloghi, formattazione, lint e mypy verdi. Log completo:
  [make-check-activate.txt](make-check-activate.txt).

Checklist della correzione: comportamento e regressione coperti; nessun
polling, timer, dipendenza, modifica di design o di configurazione introdotti.
File toccati: `src/scambio/ui/tray.py`, `tests/test_tray.py`, questo report e
`docs/verification/03/make-check-activate.txt`.

Limiti separati dall'evidenza: il comportamento dell'host Plasma deriva dalla
misura M14 già registrata, non da una nuova prova visiva. Non eseguiti riavvii
del demone reale né misure Bluetooth/audio/CPU; i campioni CPU/RSS sopra
identificano la consegna originale. GNOME resta non verificato.

Verifica manuale per GM, ancora da eseguire: dalla repo,
`systemctl --user restart scambio`; clic sinistro sull'icona → menu; chiuderlo,
clic destro → stesso menu. Annotare esito e data per Claude. Questa prova non
è inclusa nel criterio automatico di completamento del presente `/goal`.

Ricerca: graphify query/affected/path e lettura dei file; alcuni simboli non
risolti in modo univoco, impatto verificato tramite il nodo `tray.py`. Nessun
fallback grep/rg. Brain consultato in sola lettura via MCP `agvm-scambio`:
restituisce le milestone 0 e 2, nessuna evidenza sulla decisione 85, verificata
direttamente nel repository insieme a M14. Graphify si aggiorna al commit.
Nessuna domanda tecnica aperta. Handoff a Claude: aggiornare tracker ed esito
dell'audit; registrare la futura prova di GM nei file di sua proprietà.
