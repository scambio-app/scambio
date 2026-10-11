# Vettori policy v1 — arresto alla verifica degli input

Data: 2026-10-11. Codice ispezionato: `e0c59d54772d94022170a8c835b32a464a8d79a8`.
Obiettivo: esportare la macchina a stati Linux per Mac secondo la decisione 121 e
`docs/specs/M01-vectors/`. **Unità non completata: generazione sospesa per il conflitto
fra i casi richiesti e la semantica normativa.**

## Evidenza del blocco

La richiesta impone sia tutti i casi di `test_rules` e dei test parametrizzati con
contesti espliciti, preservando `Context` e `Policy`, sia il rifiuto dei contesti con
`pending="release"` e `pending_reason=""`. Anche README M01, semantica §5.3 punto 5,
classifica questi contesti come malformati.

Nei test esistenti **19 casi** presentano proprio quella combinazione:

| Origine | Varianti non esportabili tali e quali |
|---|---:|
| `tests/test_policy.py::test_rules[C4]` (`CASES`, riga 352) | 1 |
| `tests/test_policy.py::test_sleeping_exits_release_inhibitor[C4]` | 1 |
| `tests/test_policy_players.py::test_error_outcomes`, `pending="release"`, 6 eventi × 2 valori di `active` | 12 |
| `tests/test_policy_players.py::test_g8`, `pending="release"`, 5 stati | 5 |
| Totale | **19** |

`Context.pending_reason` vale `""` per default. Le fixture sopra non lo impostano.
Gli eventi verificati oggi non hanno bisogno di leggerlo: i test Linux passano, ma
questo non rende i relativi input conformi al formato condiviso.

Esportarli produrrebbe vettori malformati; ometterli violerebbe la copertura richiesta;
aggiungere un motivo solo nell'esportatore violerebbe la conversione «tali e quali».
Non è stato scelto implicitamente nessuno di questi comportamenti (decisione 217).
Nessuna modifica a `src/`, ai test esistenti o agli input M01.

**Chiarimento necessario all'orchestratore:** adeguare prima le fixture Linux con
motivi espliciti ammessi, oppure restringere esplicitamente l'insieme da esportare.
Proposta: parametrizzare le fixture interessate sui quattro motivi ammessi
(`switch`, `priority`, `locked`, `sleep`), poi esportare quei contesti senza
normalizzazioni. Questa proposta non è stata applicata.

## Metodo e verifiche

Letture: AGENTS, contesto 01–06, hardware-lab, README/schema/semi M01, codice policy,
test e decisioni. Ricerche tramite `graphify query`, `affected` e `path`;
nessun grep/rg. `affected` non trova un nodo univoco per i nuovi file di questa
unità; per `docs/decisions.md` mostra i report 05/06. Il collegamento
`test_error_outcomes → exact → step` è confermato dal grafo e dal codice.
Brain consultato esclusivamente tramite MCP `agvm-scambio`, scope
`scambio_brain`, operazioni di lettura `retrieve_context` e
`inspect_context_package` (ricerca `9deb8a10-3f67-4260-9883-96181c0f634e`).
Restituisce le milestone Linux fino all'8 ottobre, non un chiarimento M01 utile
al conflitto. Repo e input restano l'autorità.

Ispezione eseguita con un plugin pytest temporaneo: intercetta il riferimento
`step` dei due moduli di test, registra contesto/evento e poi chiama la funzione
Linux originale senza modificare input o risultato. Esecuzione sul checkout
verificato tramite `policy.__file__`, con `PYTHONPATH=src`:

- `tests/test_policy.py tests/test_policy_players.py -k 'not exhaustive'`:
  **246 passed, 1 deselected**, 0,12 s (0,171 s incluso il runner).
- 245 test chiamano `step`, per **337 chiamate**; 19 chiamate in 19 test hanno
  il contesto malformato. Questi sono conteggi diagnostici dell'intera selezione,
  non conteggi di vettori prodotti.
- L'esaustivo è escluso solo dalla diagnosi mirata come richiesto; non viene
  escluso dal gate completo.
- `PYTHONPATH=src .venv/bin/pytest tests/test_i18n.py -q`: **24 passed**, 0,06 s.
- `PYTHONPATH=src make check`: **verde**, format/lint/type check e **848 passed**,
  nessun test saltato, pytest 106,64 s. Restano avvisi di deprecazione GTK/GLib/asyncio
  già presenti; nessuna modifica di questa unità li introduce.

Il primo `make check` senza `PYTHONPATH` ha caricato il pacchetto installato in
`/usr/lib/python3/dist-packages/scambio`, non `src/scambio`, pur risultando la
venv installata come editable: **847 passed, 1 failed**, 107,85 s.
`test_cli_config_readonly_and_fallback` cercava il catalogo compilato sotto
`/usr/lib/python3/build/locale/`. La verifica corretta forza `PYTHONPATH=src`,
anche per il commit e il suo hook; non salta controlli e non modifica
l'installazione di sistema. L'ispezione dei 19 casi è stata ripetuta sul checkout.

Riproduzione minima del conflitto senza plugin e senza modificare file:

```sh
PYTHONPATH=src:tests .venv/bin/python - <<'PY'
from test_policy import CASES
from scambio.core.policy import Context

_, values, event, _, _ = next(row for row in CASES if row[0] == "C4")
context = Context(**values)
assert context.pending == "release"
assert context.pending_reason == ""
print("C4 non esportabile secondo M01 §5.3 punto 5:", context, event)
PY
```

## Input conservati

I sei file di `docs/specs/M01-vectors/` vengono aggiunti al repository **senza
modificarne il contenuto**, come richiesto. Non è stato accertato un errore nei
semi: il blocco riguarda le fixture Linux; schema e replay completi non sono
stati verificati. Il documento di progetto `claude/vettori-policy-v1.md` non è
presente nel checkout; il README locale contiene il vincolo sufficiente a
dimostrare il conflitto.

SHA256 letti prima di qualunque scrittura e ricontrollati per il commit:

| File | SHA256 |
|---|---|
| README.md | `526e6fae13e933f3cf5665be9f79aaa6f82dfb28d74b8fefb03ac3a0d56228c3` |
| schema.json | `fdaee2759ab226414ec329044a4b9ee3d8591e023e1d5587bd446114a8c33de4` |
| flow.double-switch-waits-for-disconnect.json | `79c56a565133f1691f1b93bf524807e9f37520d673cbd070ea5584c17f5d25ee` |
| flow.m8-gap-keeps-block.json | `f5f2488f0e959cdcbba4e49a101721200c7a329c29ca509e144cc4001278f8fc` |
| rule.c7.external-sink-timeout.json | `34805b34ba41a76da6fdeb3b560571cc98ee4f39dcf6ce389b5dcc7f0ba12ac8` |
| rule.r4.grab-after-delay.json | `2f02d47e941feee2574e97d76e8f4f84c569f3777ef1c8a2e9b546933153d0a0` |

## Checklist e consegna alla chat Mac

| Requisito | Stato |
|---|---|
| Lettura norme, graphify, brain in sola lettura | Fatto |
| Conservazione byte degli input M01 | Fatto, hash sopra |
| Esportatore puro e `policy-v1.json` rigenerabile | Non realizzati: stop sugli input |
| Tutti i casi espliciti e flussi virtuali | Non esportati; 19 input incompatibili |
| Conversioni e rifiuto dei malformati nel generatore/harness | Non implementati |
| ≥ 2000 passeggiate × 60 passi, file separati e copertura | Non generate; nessuna copertura dichiarata |
| Replay Linux del corpus e dei quattro semi | Non implementato |
| Impronte U e T ricalcolate | Non eseguite: stop iniziale; nessuna concordanza o discrepanza dichiarata |
| `source.commit`, seme, licenza come costante unica | Non implementati; licenza dei vettori resta provvisoria da decidere da GM |
| Report e decisione tecnica 217 | Fatto |
| Gate locale | Verde: 848 test; hook pre-commit obbligatorio anche per questa consegna |

**Per la chat Mac:** nessun nuovo corpus da copiare o usare come riferimento
verificato. Comunicare questo report e la decisione 217; i sei input M01
conservati sono quelli già forniti dalla chat Mac. Dopo il chiarimento, la
consegna prevista resta `tests/vectors/policy-v1.json` e tutti i
`tests/vectors/policy-walks-v1-NN.json`, insieme allo schema e al README M01.

Non sono assunti nuovi comportamenti Bluetooth/audio né eseguite prove hardware.
Nessuna richiesta per `design/`. Tracker e brain da aggiornare da Claude con
lo stato di sospensione; nessuna nuova misura da aggiungere a hardware-lab.

File di questa consegna: i sei input M01, questo report e la voce tecnica in
`docs/decisions.md`. `design/icons/_deviatoio-v3/github/` resta fuori dal commit;
nessun push. Il commit del report è identificabile con
`git log -1 --format=%H -- docs/verification/vettori-v1/report.md`.
