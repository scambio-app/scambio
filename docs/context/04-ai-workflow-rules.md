# 04 — Regole del workflow con gli agenti

Redatto da Claude il 4 ottobre 2026. Versione alleggerita del metodo «six-file context» usato in
Kuchl: stessi principi, meno burocrazia. Integra `AGENTS.md`, che resta normativo.

## 1. Ruoli

| Chi | Ruolo | Può | Non può |
|---|---|---|---|
| GM | product owner, tester | decidere il prodotto, approvare spec e mock, provare sul dispositivo reale | — |
| Claude | architetto, designer, revisore | scrivere `docs/context/`, `docs/specs/`, `docs/hardware-lab.md`, `design/`; misurare l'hardware con script usa e getta fuori dalla repo; auditare | scrivere `src/`, `tests/`, tooling |
| Codex | implementatore | scrivere codice, test, tooling, packaging, report di verifica, decisioni tecniche | modificare `design/`, contesto, spec, hardware-lab |
| Brain `scambio_brain` | memoria di lungo periodo | essere consultato dopo repo e misure | fare da autorità |

## 2. Una fonte di verità per tipo

| Informazione | Fonte | Chi scrive |
|---|---|---|
| Policy agenti, proprietà file, invarianti | `AGENTS.md` | Claude, con GM |
| Prodotto, posizionamento, comportamento | `docs/context/01-project-overview.md` | Claude |
| Architettura e confini | `docs/context/02-architecture.md` | Claude |
| Standard di codice | `docs/context/03-code-standards.md` → poi la config eseguibile | Claude / Codex |
| Contratto design ↔ codice | `docs/context/05-ui-context.md` | Claude |
| Dove siamo, domande aperte | `docs/context/06-progress-tracker.md` | Claude |
| Comportamento misurato dell'hardware | `docs/hardware-lab.md` | Claude (misure), Codex (misure nei report) |
| Decisioni numerate | `docs/decisions.md` (append-only) | Claude (prodotto, dopo il sì di GM), Codex (tecniche) |
| Unità di lavoro | `docs/specs/NN-nome.md` | Claude, approva GM |
| Evidenza di una consegna | `docs/verification/NN/report.md` + git log | Codex |
| Aspetto e testi | `design/` | Claude |

Niente `progress.md` né «stato attuale» narrativo: il presente si legge dal tracker, dalle misure
e dal git log.

## 3. Ciclo di una unità

1. **Decisione** — GM e Claude scelgono l'unità; Claude pone 1–2 domande mirate sui comportamenti.
2. **Spec** — Claude scrive `docs/specs/NN-nome.md` dal template; la rilegge e segnala a GM cosa
   correggerebbe prima della consegna. Stato `bozza` → `approvata`.
3. **Design** (se l'unità ha UI) — mock approvato da GM, poi file in `design/` prima del `/goal`.
4. **Incarico** — GM (o Claude, se autorizzato) passa a Codex il `/goal` in fondo alla spec.
5. **Implementazione** — Codex nello scope, `make check` verde, commit locali, report.
6. **Audit** — Claude legge il diff, verifica test ed evidenze, per la UI fa screenshot reali
   (chiaro/scuro, KDE; GNOME quando disponibile) e li confronta col mock. Esito nella sezione
   «Note di revisione» della spec.
7. **Prova reale** (DoD B) — GM con occhiali e iPhone, checklist firmata.
8. **Chiusura** — tracker aggiornato; alle milestone Claude scrive in `scambio_brain`.

Comando `/goal` minimo. **Regola di GM (2026-10-05):** Codex non accetta un `/goal` lungo;
si manda prima il `/goal` corto (una riga: spec da implementare + criterio di fatto) e subito
dopo, come secondo messaggio nella stessa sessione, le istruzioni operative (scope, tappe,
stop, numerazione delle decisioni). Esempio di `/goal` corto (le spec dalla 03 hanno i due
messaggi pronti in fondo):

```
/goal Implementa docs/specs/NN-nome.md seguendo AGENTS.md e docs/context/. Fatto solo quando
ogni voce della Checklist di done è soddisfatta con evidenza e `make check` è verde. Scope: solo
§3 Dettagli; §4 Fuori scope non si tocca; design/ non si modifica. Stop: se la spec contraddice
AGENTS.md o manca una decisione di prodotto, fermati e scrivilo nel report.
```

## 4. Regole per Codex

- Leggi `AGENTS.md`, i sei file, `hardware-lab.md`, la spec; poi graphify.
- Una decisione di prodotto mancante non si inventa: se la spec indica un default applicalo e
  segnalalo, altrimenti fermati. Le scelte tecniche reversibili si prendono e si registrano.
- Nessun valore personale hardcodato (MAC, nomi): tutto da configurazione.
- Test automatici mai sul Bluetooth reale; la prova reale la fa GM.

## 5. Regole per Claude

- Sola lettura su `src/`, `tests/`, tooling. Scrive solo i propri file (vedi `AGENTS.md`).
- Le misure sull'hardware si fanno con script usa e getta fuori dalla repo, con GM presente se
  serve un'azione fisica; il risultato va in `hardware-lab.md` con data e metodo.
- Mai sovrascrivere modifiche manuali di GM: rileggere l'ultima versione prima di aggiornare.
- Spec piccole: un'unità che Codex chiude in una sessione, con una prova visibile.
- Per controlli veloci (audit di layout) usare un agente economico quando possibile.

## 6. Brain AGVM (`scambio_brain`) e graphify

**Isolamento da Kuchl.** Un'unica istanza AGVM su casa (API :8010) ospita più brain, separati
per `brain_id` con archivi distinti. Il «brain attivo» del registro è globale e resta
`kuchl_brain`: nessuno lo cambia. Si accede a Scambio solo indicando il brain in modo esplicito:
- Codex: server MCP `agvm-scambio` in `~/.codex/config.toml` (`AGVM_MCP_BRAIN_ID=scambio_brain`,
  `AGVM_MCP_BRAIN_POLICY=fixed`, sola lettura). Il server `agvm-local-memory-os` resta di Kuchl.
- Chat Claude: API HTTP o MCP sempre con `brain_id="scambio_brain"`; mai `select_brain`.

**Lettura.** Ordine: graphify (codice e documenti) → brain (perché e storia) → file. Ogni
memoria del brain va datata e verificata prima di diventare un fatto. Se il brain non risponde,
repo e misure bastano.

**Scrittura.** Solo Claude, solo con preview + commit esplicito, alle milestone (chiusura di
una spec verificata, nuova misura in hardware-lab, decisione di prodotto importante). Testo
additivo, datato, con la fonte e il metodo di misura; una memoria superata si corregge con una
nota esplicita di correzione. Codex non scrive sul brain: le sue scoperte vanno nel report e
Claude le promuove.

**Checklist di chiusura di ogni chat o sessione.**
1. Tracker (06) aggiornato; decisioni nuove in `decisions.md`; misure in `hardware-lab.md`.
2. File di contesto corretti se sono diventati falsi (non affiancati).
3. Commit (il grafo si aggiorna da solo).
4. Milestone? → scrittura nel brain con preview e commit.
5. Prompt di handoff se serve (§7).

**Graphify.** Indicizza codice e markdown; hook post-commit e post-checkout in `.githooks/`
(attivi con `core.hooksPath=.githooks`, spec 01). L'intera cartella `graphify-out/` (grafo,
report, istantanee datate, etichette, cache) è un derivato locale ricostruito dopo ogni commit:
**non si versiona** ed è in `.gitignore` (decisione 52, 2026-10-05). Se manca o è vecchia:
`graphify update .`.

## 7. Chat di progetto e handoff (GM, 2026-10-04)

- Una chat **orchestratore** per decisioni di prodotto, misure e priorità; una **chat di sviluppo**
  per ogni unità (spec, mock/design, audit).
- Ogni chat, quando il contesto diventa lungo o inizia una nuova unità, propone a GM di aprire una
  nuova chat e gli fornisce il **prompt di handoff** pronto da copiare. Prima salva in repo tutto
  ciò che è stato deciso o misurato: il prompt punta ai file, non li riassume per intero.
- Struttura del prompt: progetto e ruolo · fonte di verità e ordine di lettura · stato in 3–5 righe
  con l'ultimo commit · compito e criterio di fatto · vincoli · come chiudere e cosa riportare
  all'orchestratore.
