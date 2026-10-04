# Graph Report - scambio  (2026-10-04)

## Corpus Check
- 13 files · ~5,404 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 96 nodes · 83 edges · 14 communities (11 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `b60db230`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- 01 — Panoramica del prodotto
- Spec NN — Titolo
- 02 — Architettura
- Scambio — policy per gli agenti
- 04 — Regole del workflow con gli agenti
- 05 — Contesto UI e contratto design ↔ codice
- Hardware lab — misure sul campo
- 03 — Standard di codice
- 06 — Tracker di avanzamento
- Decisioni
- 3. Dettagli
- CLAUDE.md
- design/README.md
- README.md

## God Nodes (most connected - your core abstractions)
1. `Spec NN — Titolo` - 11 edges
2. `01 — Panoramica del prodotto` - 10 edges
3. `02 — Architettura` - 9 edges
4. `Scambio — policy per gli agenti` - 8 edges
5. `04 — Regole del workflow con gli agenti` - 8 edges
6. `05 — Contesto UI e contratto design ↔ codice` - 7 edges
7. `Hardware lab — misure sul campo` - 7 edges
8. `03 — Standard di codice` - 6 edges
9. `06 — Tracker di avanzamento` - 6 edges
10. `3. Dettagli` - 5 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities (14 total, 3 thin omitted)

### Community 0 - "01 — Panoramica del prodotto"
Cohesion: 0.18
Nodes (10): 01 — Panoramica del prodotto, 1. Il problema, 2. Il prodotto, 3. Posizionamento (decisione 2026-10-04), 4. Modello open-core, 5. Utente di riferimento, 6. Comportamento (decisioni di prodotto, non ridiscutere), 7. Interfacce (+2 more)

### Community 1 - "Spec NN — Titolo"
Cohesion: 0.18
Nodes (10): 1. Obiettivo, 2. Decisioni applicabili, 4. Fuori scope, 5. Dipendenze, 6. Checklist di done, 7. Note di revisione (Claude, dopo la consegna), 8. Revisione preventiva di Claude (inviata a GM prima del /goal), 9. Domande aperte (+2 more)

### Community 2 - "02 — Architettura"
Cohesion: 0.20
Nodes (9): 02 — Architettura, 1. Stack, 2. Moduli (layout obiettivo), 3. Macchina a stati (bozza, da fissare nella spec 01), 4. Configurazione (chiavi iniziali), 5. Punto di estensione (open-core), 6. Invarianti, 7. Rischi tecnici aperti (+1 more)

### Community 3 - "Scambio — policy per gli agenti"
Cohesion: 0.22
Nodes (8): Ciclo di lavoro, Commit, Definizione di fatto, Invarianti (non negoziabili senza decisione di GM), Prima di pianificare, Proprietà dei file (vincolante), Report finale di Codex, Scambio — policy per gli agenti

### Community 4 - "04 — Regole del workflow con gli agenti"
Cohesion: 0.22
Nodes (8): 04 — Regole del workflow con gli agenti, 1. Ruoli, 2. Una fonte di verità per tipo, 3. Ciclo di una unità, 4. Regole per Codex, 5. Regole per Claude, 6. Brain AGVM (`scambio_brain`), 7. Chat di progetto e handoff (GM, 2026-10-04)

### Community 5 - "05 — Contesto UI e contratto design ↔ codice"
Cohesion: 0.25
Nodes (7): 05 — Contesto UI e contratto design ↔ codice, 1. Principi, 2. Superfici, 3. Stati da rappresentare (icone in `design/icons/`), 4. Menu del tray (bozza), 5. Contratto (da completare col mock), 6. Lingue

### Community 6 - "Hardware lab — misure sul campo"
Cohesion: 0.25
Nodes (7): 2026-10-04 — M1: presa dal PC con musica sull'iPhone, 2026-10-04 — M2: presa dal PC durante una chiamata WhatsApp sull'iPhone, 2026-10-04 — M3: riconnessione spontanea all'accensione (Q3), Ambiente di riferimento, Conseguenze per il design, Da misurare, Hardware lab — misure sul campo

### Community 7 - "03 — Standard di codice"
Cohesion: 0.29
Nodes (6): 03 — Standard di codice, 1. Gate (`make check`, eseguito anche dal hook pre-commit), 2. Python, 3. Struttura e confini, 4. Test: cosa ci si aspetta da una consegna, 5. Dipendenze

### Community 8 - "06 — Tracker di avanzamento"
Cohesion: 0.29
Nodes (6): 06 — Tracker di avanzamento, 1. Fase corrente, 2. Piano delle fasi, 3. Decisioni di prodotto prese (non ridiscutere), 4. Domande aperte, 5. Prossimi passi

### Community 9 - "Decisioni"
Cohesion: 0.40
Nodes (4): 2026-10-04 — Dominio e identificativi, 2026-10-04 — Fase 0 (decise da GM con Claude), 2026-10-04 — Fase 0 (tecniche, Claude), Decisioni

### Community 10 - "3. Dettagli"
Cohesion: 0.40
Nodes (5): 3.1 Comportamento, 3.2 API D-Bus, configurazione, dati, 3.3 Interfaccia (riferimenti a `design/` e al contratto di `05-ui-context.md`), 3.4 Errori e casi limite, 3. Dettagli

## Knowledge Gaps
- **72 isolated node(s):** `Prima di pianificare`, `Proprietà dei file (vincolante)`, `Invarianti (non negoziabili senza decisione di GM)`, `Ciclo di lavoro`, `Definizione di fatto` (+67 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Spec NN — Titolo` connect `Spec NN — Titolo` to `3. Dettagli`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `3. Dettagli` connect `3. Dettagli` to `Spec NN — Titolo`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **What connects `Prima di pianificare`, `Proprietà dei file (vincolante)`, `Invarianti (non negoziabili senza decisione di GM)` to the rest of the system?**
  _72 weakly-connected nodes found - possible documentation gaps or missing edges._