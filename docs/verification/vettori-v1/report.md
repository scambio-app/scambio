# Vettori policy v1 — verifica e consegna Linux → Mac

Data: 2026-10-11. Decisione 121; riferimento normativo:
`docs/specs/M01-vectors/README.md` (§5.3 e tabella U/T) e `schema.json`.
Il commit `c98cd4b` ha conservato i sei input M01 e documentato lo stop iniziale.
La risposta dell'orchestratore ha risolto il conflitto con l'espansione esplicita
registrata nella decisione 217, senza modificare `src/` né i test Linux esistenti.
Decisioni tecniche aggiuntive: 218–219.

## Risultato e conteggi

- `tests/vectors/policy-v1.json`: **399 vettori, 427 passi**, 776.862 byte.
  Comprende **394 vettori clock none**: tutte le 337 chiamate esplicite a `step()`
  dei due moduli, escluse le tracce esaustive, con i 19 casi incompleti sostituiti
  da 76 espansioni (337 − 19 + 76). Incluse tutte le **68 righe di test_rules**,
  tutti i casi parametrizzati e, in aggiunta, le chiamate dei test non parametrizzati.
- **5 flussi clock virtual, 33 passi**: M8, Bluetooth spento/riacceso (due rami,
  con cache Connected aggiornata oppure ancora vera), switch durante la presa,
  doppio switch che attende DeviceConnected(false).
- `policy-walks-v1-00.json` … `policy-walks-v1-09.json`: **2.000 passeggiate ×
  60 passi = 120.000 passi**, 200 passeggiate per file, **21.060.885 byte** totali.
  Ogni file misura 2,07–2,14 MB decimali; JSON non compresso, un vettore per riga.
  1.000 partenze da `Context(priority=False)` e 1.000 da `Context(priority=True)`.
- Totale consegnato: **2.399 vettori, 120.427 passi, 21.837.747 byte**.
  Il replay aggiunge i **4 semi M01, 19 passi**: **2.403 vettori e 120.446 passi**
  verificati sul codice Linux.

Nessun campo `platform` nei file esportati. `Context` e `Policy` sono convertiti
integralmente, con `resume_delay_ms` già risolto (0 nei default; 2000 nei casi
player che lo prevedono). L'unica trasformazione del contesto è quella esplicita
approvata per i 19 casi elencati nell'appendice.

## Copertura e orologio

Seme pubblico **121217** in `source.seed`; generatore Python `random.Random`
inizializzato separatamente con `"121217:<indice>"` per ogni passeggiata. Gli
indici pari iniziano con priority false, i dispari con true. Gli intervalli
simulati sono estratti da 0, 1, 50, 200, 500, 2000, 10000, 120000 ms; quando una
scadenza precede il prossimo evento viene emesso il TimerFired corrispondente,
consumato prima di `step()`. Nessun timer scaduto viene saltato.

Copertura **65/65 coppie (stato, tipo di evento)**: cinque stati × tredici tipi,
con TimerFired come tipo. Tutti gli otto timer sono effettivamente esercitati;
sono osservate anche 17 coppie stato/nome del timer (dettaglio distinto, senza
asserire la copertura di tutte le possibili combinazioni sintattiche).
`source.coverage` di ciascun file contiene conteggi di passeggiate, passi,
coppie stato/evento e coppie stato/timer. I test ricalcolano tutti questi dati.

| Stato prima dell'evento | Passi nelle passeggiate |
|---|---:|
| released | 23.371 |
| connecting | 4.904 |
| on_pc | 9.222 |
| releasing | 11.334 |
| unavailable | 71.169 |

Il medesimo `VirtualClock` implementa §5.3.4 nel generatore e nel replay: scadenze
assolute, sostituzione con StartTimer, cancellazione idempotente, timer consumato
prima della policy, ordine delle azioni e del file a parità di tempo. I flussi
M8 e doppio switch riprendono i tempi illustrativi dei semi; quello durante la
presa dichiara GRAB_DELAY iniziale a 500 ms. I TimerFired obsoleti dei test unitari
restano nei vettori clock none: non vengono inventati timer virtuali per renderli
validi. Le due varianti Bluetooth sono rami separati dello stesso test.

**Assunzioni:** i tempi dei flussi e delle passeggiate sono simulati, non misure
hardware; gli eventi casuali sondano la policy anche con osservazioni insolite.
Non attestano la frequenza o la plausibilità fisica di una sequenza Bluetooth.
Le misure M8/M12/M22 già presenti motivano i flussi; nessuna nuova misura è richiesta
per questa esportazione della funzione pura.

## Impronte e raggiungibilità

Esplorazione fino all'esaurimento della frontiera, dalla configurazione di default
e dai due Context di default (priority false/true). Alfabeto di base: 23 eventi.
U aggiunge sempre gli otto timer; T aggiunge solo i timer attivi, tolti prima di
`step()`, e aggiorna l'insieme nell'ordine delle azioni. T usa la chiave
(Context completo, insieme dei timer), come richiesto dalla tabella: non elimina
campi, non filtra contesti e non introduce scadenze temporali nel modello T.

| Modello | Coppie | Contesti | Transizioni | Azioni | released | connecting | on_pc | releasing | unavailable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| U | — | 81.844 | 2.537.164 | — | 24.032 | 6.372 | 2.560 | 38.640 | 10.240 |
| T | 151.236 | 80.404 | 3.683.354 | 5.419.116 | 23.392 | 6.372 | 2.560 | 37.840 | 10.240 |

**Tutte le celle normative coincidono.** Il test legge le attese direttamente
dalla tabella del README invariato. Il conteggio aggiuntivo delle azioni U è
2.912.172, informativo perché non compare tra le attese normative.

**Evidenza richiesta dall'orchestratore:** in tutti gli **80.404 contesti di T**,
raggiunti nelle **151.236 coppie**, il numero di contesti con `pending="release"`
e `pending_reason=""` è **zero**. La combinazione è **IRRAGGIUNGIBILE** dai default
nel modello T. Anche U ne trova zero. Non è un'inferenza dalle passeggiate: è il
risultato dell'esplorazione finita completa. La regola M01 resta invariata.

## Provenienza e riproducibilità

`source.repo = "scambio-linux"`; `source.commit` di tutti gli undici file è
**`c98cd4b82191609748df7a4d33f4da70c45a47ae`**. È il commit della policy, della
configurazione e dei test Linux usati come sorgente, ottenuto con
`git rev-parse --verify HEAD^{commit}` al momento della generazione. Lo strumento
confronta quei quattro file con `git show <commit>:<path>` e rifiuta un checkout
sorgente diverso; rifiuta anche l'importazione del core dal pacchetto di sistema.
Il generatore aggiunto da questa unità è identificato dal percorso e dalla versione
in `source.generator`; il commit sorgente non pretende di contenerlo già.

Per evitare auto-riferimenti e instabilità a ogni commit, la rigenerazione nei test
riusa il commit registrato nel JSON, controllandone contenuto e metadati. Non
ricalcola HEAD per sostituirlo nelle attese. `generated_at` è convenzionalmente la
data del commit sorgente (`git show -s --format=%cI`), **non** l'ora del processo.
Questo rende riproducibili anche i byte; non è un'attestazione dell'ora di esportazione.

`source.license = "GPL-3.0-or-later"` deriva da **un'unica costante
`VECTOR_LICENSE`**. È provvisoria, come richiesto: la licenza finale dei vettori
resta da decidere da GM. Licenza e copyright SPDX sono anche nella stringa libera
`source.generator`, nelle prime cinque righe, per rispettare il test di packaging
esistente senza commenti JSON, nuove proprietà fuori schema o modifiche ai test.

## Implementazione e validazione

`tools/export_policy_vectors.py` esegue copie isolate dei moduli di test,
intercettando `step()` senza cambiare i loro assert, input o file. Non invoca
pytest come runner, conftest, bus o hardware; usa pytest solo tramite i decoratori
già presenti nelle fixture, una dipendenza di sviluppo esistente. Il test di
isolamento blocca esplicitamente ogni import di gi nel sottoprocesso.

`tools/policy_vector_format.py` contiene conversioni, interprete dei costrutti
usati dallo schema locale e controllo semantico. Non è un validatore JSON Schema
generico; rifiuta costrutti di schema non supportati. Non ci sono dipendenze nuove.
Valori numerici JSON equivalenti sono confrontati come valori, senza confondere
booleani e interi. La semantica aggiunge ai vincoli strutturali: ID unici, changes
non ridondanti, contesti completi validi, divieto dei campi Mac nel condiviso,
assenza di initial.timers con clock none e correttezza del tempo virtuale.

Le conversioni scartano value per Switch/DeviceSinkAppeared/DeviceSinkGone,
lo conservano solo per i sette eventi booleani, traducono gli esiti Connect e
Disconnect come richiesto e conservano gli errori grezzi in detail. Nel replay
**detail non cambia l'esito**, anche se contiene una stringa simile a un successo.
Le azioni usano timer/ms, value, code, from/to/reason, kind secondo lo schema;
changes include solo i campi realmente cambiati.

`tests/policy_vector_replay.py` applica gli override dei default, rigioca ogni passo
sulla policy Linux e confronta contesto completo e azioni ordinate per valore JSON.
Aggiorna l'orologio con le azioni effettive della policy. I test coprono anche
input malformati, scadenze saltate/anticipate/inattive, tempi non monotoni, timer
zero, scadenze uguali, sostituzione e cancellazione di timer, errori ignorati come
diagnostica, campi sconosciuti, numeri fuori limiti e chiavi JSON duplicate.

## Comandi, tempi e gate

Ambiente: Python 3.14.4, pytest 9.1.1, venv locale. Make e pytest danno precedenza
al checkout, risolvendo l'importazione del pacchetto omonimo in `/usr/lib` osservata
nel preflight. Nessuna modifica all'installazione di sistema.

```sh
make policy-vectors           # genera da HEAD, dopo avere committato i sorgenti Linux
make check                    # include rigenerazione COMPLETA e replay del corpus
make policy-fingerprints      # esplorazioni U/T complete, confronto con README
```

Riproduzione dei byte consegnati anche dopo altri commit (i quattro sorgenti devono
ancora coincidere con il commit indicato):

```sh
PYTHONPATH=src:. .venv/bin/python tools/export_policy_vectors.py \
  --source-commit c98cd4b82191609748df7a4d33f4da70c45a47ae
```

- Generazione integrale con validazione prima della scrittura: **9,333 s** misurati
  con `time make policy-vectors` (prima della sola aggiunta dei metadati SPDX).
- Prima suite vettori: **73 passed, 2 deselected**, 11,88 s. La rigenerazione di
  **tutte** le passeggiate resta in make check, senza campionamento.
- Gate U/T iniziale: **2 passed**, 49,95 s (U 19,132 s; T 30,751 s).
  Escluso dal gate ordinario con marker esplicito perché aggiunge circa 50 s;
  il comando dedicato è stato eseguito integralmente. Nessun test è marcato skip.
- **Gate finale `make check`: verde**, format/lint/type check e **921 passed,
  2 deselected**, pytest 118,98 s. I due test esclusi sono esattamente le impronte
  eseguite integralmente nel comando seguente; zero skip.
- **Gate finale `make policy-fingerprints`: verde**, **2 passed**, 52,13 s
  (U 19,435 s; T 32,630 s). Complessivamente **923 test eseguiti e passati**
  nei due gate complementari.
- Durante lo sviluppo, il primo gate ha rilevato la mancanza delle dichiarazioni
  SPDX nei JSON; risolta nel serializzatore/metadati, senza modificare il test.
  Il controllo packaging successivo passa (3 test). Gli avvisi di deprecazione
  GTK/GLib/asyncio già presenti restano fuori scope.

## Input normativi conservati

Gli input M01 sono già versionati in `c98cd4b` e restano identici ai byte ricevuti;
nessun errore rilevato nei quattro semi, tutti rigiocati con successo. Hash SHA256
ricontrollati rispetto al report iniziale:

| File | SHA256 |
|---|---|
| README.md | `526e6fae13e933f3cf5665be9f79aaa6f82dfb28d74b8fefb03ac3a0d56228c3` |
| flow.double-switch-waits-for-disconnect.json | `79c56a565133f1691f1b93bf524807e9f37520d673cbd070ea5584c17f5d25ee` |
| flow.m8-gap-keeps-block.json | `f5f2488f0e959cdcbba4e49a101721200c7a329c29ca509e144cc4001278f8fc` |
| rule.c7.external-sink-timeout.json | `34805b34ba41a76da6fdeb3b560571cc98ee4f39dcf6ce389b5dcc7f0ba12ac8` |
| rule.r4.grab-after-delay.json | `2f02d47e941feee2574e97d76e8f4f84c569f3777ef1c8a2e9b546933153d0a0` |
| schema.json | `fdaee2759ab226414ec329044a4b9ee3d8591e023e1d5587bd446114a8c33de4` |

## Istruzioni per la chat Mac

Copiare integralmente:

1. `tests/vectors/policy-v1.json`.
2. I dieci `tests/vectors/policy-walks-v1-00.json` … `policy-walks-v1-09.json`.
3. Se non già identici nel repo Mac, i sei file di `docs/specs/M01-vectors/`
   (README, schema, quattro semi), verificando gli hash sopra.
4. Questo report come evidenza e mappa delle espansioni.

Nessuna dipendenza Python/gi è necessaria nel replay Swift. Eseguire i file come
condivisi (automations true, Switch menu), con la semantica §5.3 e confronto per
valori JSON, azioni in ordine. I 76 vettori espansi sono **attese ricavate dal
Linux sul contesto completato**, non una richiesta di cambiare la policy Mac.
Non importare i vecchi 19 contesti incompleti come vettori validi.

## Checklist, scostamenti e consegna

| Requisito | Evidenza |
|---|---|
| Esportatore senza gi e rigenerazione principale | Test isolato + confronto valori e byte |
| Tutti i casi richiesti | 68 test_rules; 337 chiamate esplicite, espansione 19 → 76 |
| Cinque flussi virtuali | 33 passi controllati dall'orologio prima della scrittura |
| Passeggiate e copertura | 2000 × 60, 65/65 coppie, dieci file, seme/contatori nei metadati |
| Rigenerazione passeggiate | Completa nel gate ordinario; nessun campione sostitutivo |
| Replay corpus e quattro semi | 120.446 passi sul codice Linux |
| Impronte U/T e raggiungibilità | Tutte le celle coincidono; contesto vietato irraggiungibile |
| Provenienza e licenza | Commit sorgente verificato, timestamp stabile, costante unica provvisoria |
| Input M01 immutati | Sei SHA256 uguali al preflight, già committati in c98cd4b |
| Test Linux e src invariati | Diff vuoto rispetto a c98cd4b |
| Report e decisioni | Questo report; 217 aggiornata, 218–219 aggiunte |
| Gate finali e commit locali | 921 + 2 test verdi; hook pre-commit attivo, nessun push |

Scostamenti: solo l'espansione autorizzata dall'orchestratore. Nessuna decisione
di prodotto inventata. Nessuna richiesta per design/, nessuna prova umana
simulata; hardware-lab invariato perché non sono state eseguite nuove misure.
Resta a GM la scelta della licenza finale dei vettori; resta a Claude l'audit,
l'aggiornamento del tracker e la promozione della milestone nel brain.

Ricerca con graphify (query/affected/path e update locale); brain consultato solo
via MCP agvm-scambio in sola lettura, senza usare memoria come autorità rispetto
al repo. Nessun grep/rg. Il grafo aggiornato segnala alcuni JSON senza nodi:
l'evidenza del corpus viene dalla lettura dei file e dai test, non dal grafo.

File toccati in questa ripresa: `Makefile`, `pyproject.toml`, i tre strumenti
`tools/export_policy_vectors.py`, `tools/policy_vector_format.py`,
`tools/policy_fingerprints.py`, i due nuovi file di test
`tests/policy_vector_replay.py`, `tests/test_policy_vectors.py`, gli undici JSON
in `tests/vectors/`, questo report e `docs/decisions.md`.
`design/icons/_deviatoio-v3/github/` resta non tracciato ed escluso dai commit.
Commit di consegna identificabile con
`git log -1 --format=%H -- tools/export_policy_vectors.py`.

## Appendice — 19 origini e 76 vettori espansi

Per ogni origine sono elencati tutti e quattro gli ID, senza abbreviazioni.
Ogni vettore porta inoltre l'origin originale seguito dalla nota
` (pending_reason espanso: <motivo>)`.

```json
{
  "tests/test_policy.py::test_rules[C4]": [
    "case.test_policy.test_rules.033.step-00.reason-switch",
    "case.test_policy.test_rules.033.step-00.reason-priority",
    "case.test_policy.test_rules.033.step-00.reason-locked",
    "case.test_policy.test_rules.033.step-00.reason-sleep"
  ],
  "tests/test_policy.py::test_sleeping_exits_release_inhibitor[C4]": [
    "case.test_policy.test_sleeping_exits_release_inhibitor.000.step-00.reason-switch",
    "case.test_policy.test_sleeping_exits_release_inhibitor.000.step-00.reason-priority",
    "case.test_policy.test_sleeping_exits_release_inhibitor.000.step-00.reason-locked",
    "case.test_policy.test_sleeping_exits_release_inhibitor.000.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-C4-event0-False-released-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.006.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.006.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.006.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.006.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-C4-event1-True-releasing-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.007.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.007.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.007.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.007.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-C5-event2-False-releasing-connect_timeout]": [
    "case.test_policy_players.test_error_outcomes.008.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.008.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.008.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.008.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-C6-event3-True-releasing-sink_timeout]": [
    "case.test_policy_players.test_error_outcomes.009.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.009.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.009.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.009.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-C8-event4-False-released-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.010.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.010.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.010.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.010.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[False-release-O11-event5-True-releasing-sink_lost]": [
    "case.test_policy_players.test_error_outcomes.011.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.011.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.011.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.011.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-C4-event0-False-released-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.018.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.018.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.018.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.018.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-C4-event1-True-releasing-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.019.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.019.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.019.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.019.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-C5-event2-False-releasing-connect_timeout]": [
    "case.test_policy_players.test_error_outcomes.020.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.020.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.020.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.020.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-C6-event3-True-releasing-sink_timeout]": [
    "case.test_policy_players.test_error_outcomes.021.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.021.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.021.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.021.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-C8-event4-False-released-connect_failed]": [
    "case.test_policy_players.test_error_outcomes.022.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.022.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.022.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.022.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_error_outcomes[True-release-O11-event5-True-releasing-sink_lost]": [
    "case.test_policy_players.test_error_outcomes.023.step-00.reason-switch",
    "case.test_policy_players.test_error_outcomes.023.step-00.reason-priority",
    "case.test_policy_players.test_error_outcomes.023.step-00.reason-locked",
    "case.test_policy_players.test_error_outcomes.023.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_g8[release-released]": [
    "case.test_policy_players.test_g8.005.step-00.reason-switch",
    "case.test_policy_players.test_g8.005.step-00.reason-priority",
    "case.test_policy_players.test_g8.005.step-00.reason-locked",
    "case.test_policy_players.test_g8.005.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_g8[release-unavailable]": [
    "case.test_policy_players.test_g8.006.step-00.reason-switch",
    "case.test_policy_players.test_g8.006.step-00.reason-priority",
    "case.test_policy_players.test_g8.006.step-00.reason-locked",
    "case.test_policy_players.test_g8.006.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_g8[release-connecting]": [
    "case.test_policy_players.test_g8.007.step-00.reason-switch",
    "case.test_policy_players.test_g8.007.step-00.reason-priority",
    "case.test_policy_players.test_g8.007.step-00.reason-locked",
    "case.test_policy_players.test_g8.007.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_g8[release-on_pc]": [
    "case.test_policy_players.test_g8.008.step-00.reason-switch",
    "case.test_policy_players.test_g8.008.step-00.reason-priority",
    "case.test_policy_players.test_g8.008.step-00.reason-locked",
    "case.test_policy_players.test_g8.008.step-00.reason-sleep"
  ],
  "tests/test_policy_players.py::test_g8[release-releasing]": [
    "case.test_policy_players.test_g8.009.step-00.reason-switch",
    "case.test_policy_players.test_g8.009.step-00.reason-priority",
    "case.test_policy_players.test_g8.009.step-00.reason-locked",
    "case.test_policy_players.test_g8.009.step-00.reason-sleep"
  ]
}
```
