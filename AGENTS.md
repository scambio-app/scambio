# Scambio — policy per gli agenti

File normativo e corto: ogni sessione agente lo legge per primo. Ordine di autorità in caso di
conflitto: `AGENTS.md` → `docs/context/02-architecture.md` → voci non superate di
`docs/decisions.md` → la spec dell'unità → gli altri file di `docs/context/` → tutto il resto.
Sul comportamento dell'hardware l'autorità è `docs/hardware-lab.md`, che contiene solo misure
datate con il metodo usato.

## Prima di pianificare

1. Leggi, in ordine: questo file → `docs/context/01…06` → `docs/hardware-lab.md` → la spec.
2. **Misura prima, leggi dopo.** Il comportamento Bluetooth/audio non si deduce dalla prosa né
   dalla memoria: se una spec dipende da un comportamento non misurato in `hardware-lab.md`,
   fermati e segnalalo.
3. Usa graphify (quando il codice esiste): `graphify query` prima di `grep`, `graphify affected`
   prima di toccare un simbolo. Un documento sbagliato si corregge, non se ne scrive uno nuovo
   accanto.
4. Il brain AGVM `scambio_brain` è solo consultivo: non vince mai su repo e misure.

## Proprietà dei file (vincolante)

| Chi | Possiede | Non tocca |
|---|---|---|
| **Codex** | `src/`, `tests/`, `packaging/`, `tools/`, `pyproject.toml`, `Makefile`, `.githooks/`, `docs/verification/`, voci tecniche di `docs/decisions.md` | `design/`, `docs/context/`, `docs/specs/`, `docs/hardware-lab.md` |
| **Claude** | `design/` (icone, layout Blueprint, stile, testi it/en/de), `docs/context/`, `docs/specs/`, `docs/hardware-lab.md`, voci di prodotto di `docs/decisions.md` | `src/`, `tests/`, `packaging/`, tooling |
| **GM** | decisioni di prodotto, approvazione di spec e mock, prova reale con occhiali e iPhone | — |

Se a Codex serve un cambio in `design/` (un widget, un'icona, un testo), lo chiede nel report
finale; non lo fa da sé. L'interfaccia fra design e codice è il contratto in
`docs/context/05-ui-context.md` (ID dei widget, azioni, segnali, chiavi dei testi).

## Invarianti (non negoziabili senza decisione di GM)

- Un solo processo demone, un solo main loop GLib; tutto il D-Bus via Gio.
- **Nessun polling.** Solo segnali ed eventi. CPU a riposo ≈ 0%, memoria residente minima.
- Mai root, mai `sudo`. Nessuna modifica di sistema fuori da `~/.config/scambio/` e
  `~/.local/share/scambio/`.
- Mai disaccoppiare (unpair) un dispositivo; agire solo sui dispositivi configurati.
- Le interfacce grafiche, la scorciatoia e la CLI parlano col demone **solo** tramite la sua API
  D-Bus. Nessuna logica nelle UI; mai `bluetoothctl` diretto.
- Dipendenze runtime: solo PyGObject e le librerie di sistema standard (GLib/Gio, GTK4,
  libadwaita). Ogni nuova dipendenza richiede una decisione registrata.
- Ogni timeout e soglia è configurabile; nessun valore personale (MAC, nomi) hardcodato.
- Ogni testo visibile ha chiavi it/en/de.
- Il core open-source non importa mai codice premium: le estensioni si agganciano tramite il
  punto di estensione definito in `02-architecture.md`.

## Ciclo di lavoro

Spec `docs/specs/NN-nome.md` (bozza → approvata da GM) → `/goal` a Codex → implementazione
dentro lo scope → audit di Claude (codice + verifica visiva per la UI) → prova reale di GM
quando prevista → chiusura nel tracker. Una unità alla volta; ciò che è fuori scope si annota come
debito e non si fa.

## Definizione di fatto

- Checklist della spec soddisfatta, con evidenza.
- `make check` verde in locale (lint, format, type check, test). **Non esiste CI remota**:
  il repository vive solo su `casa`, nessun remote, nessuna GitHub Actions. Il hook
  `.githooks/pre-commit` esegue `make check`; non si aggira (`--no-verify` vietato).
- Un test saltato non è un test verde. La prova umana (DoD B) non si simula: si prepara la
  checklist per GM.
- Evidenza in `docs/verification/<spec>/report.md`; scelte tecniche in `docs/decisions.md`.

## Report finale di Codex

Obiettivo, cosa è cambiato, commit, test eseguiti, voci della checklist fatte/non fatte,
scostamenti dalla spec, richieste per `design/`, domande aperte, file toccati. Evidenza e
assunzioni sempre distinte.

## Commit

Commit piccoli e coerenti sulla branch corrente, messaggi in inglese all'imperativo. Nessun push:
non c'è remote.
