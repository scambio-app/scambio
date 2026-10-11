# Vettori policy v1 — riferimento dalla chat Mac

Copia su casa dei file di `scambio-mac` (commit 191545b29f7e2df9755b4954981b4ab6ca6ccc61, spec
`docs/specs/M01-core.md` §5 e §6.3), portata dall'orchestratore il 2026-10-11. Documento completo
con semantica (§5.1–§5.3), richiesta (§5.5) e impronte (§6.3 punto 5): doc di progetto
`claude/vettori-policy-v1.md`; qui sotto le parti normative per Codex.

## Semantica (M01 §5.3)

1. Partenza: contesto = `defaults.context` sovrascritto da `initial.context`; configurazione =
   `defaults.config` sovrascritta da `config`.
2. Passo: `(c′, A) = step(c, e, config)`; supera se A = `expect.actions` (stessa lunghezza, stesso
   ordine, campo per campo) e c′ = c sovrascritto da `expect.changes` su tutti i campi.
3. `clock` = `none`: `t_ms` facoltativo e ignorato; `TimerFired` si applica così com'è anche per un
   timer non attivo (G12); `initial.timers` vietato.
4. `clock` = `virtual`: `t_ms` obbligatorio, intero ≥ 0, non decrescente. Tabella T (timer →
   scadenza assoluta ms) da `initial.timers` o vuota. Prima di un passo al tempo t nessun timer di
   T può scadere prima di t. `TimerFired(X)` valido solo se T[X] = t; X si toglie da T prima di
   `step` (come `service.py:368-375`). Dopo il passo, nell'ordine delle azioni: `StartTimer(X, ms)`
   → T[X] = t + ms; `CancelTimer(X)` → X si toglie. A parità di tempo vale l'ordine del file.
5. File malformato (fallisce, non si salta): `format`/`version`/`platform` sconosciuti; chiavi o
   valori fuori schema; `id` ripetuti; configurazione fuori limiti; voce di `changes` uguale al
   valore precedente; contesto con `pending` = `release` e `pending_reason` vuoto; violazioni del
   punto 4.
6. `automations`, `SetAutomations` e `source` di `Switch` solo nei file `"platform": "mac"`; i file
   condivisi si eseguono con `automations` = true e `Switch` = `menu`.
7. `detail`, `rules`, `origin` e `note` non entrano nel confronto.

## Impronte da verificare sul codice Linux (M01 §6.3 punto 5)

Alfabeto di base, 23 eventi: `AudioActive` t/f, `DeviceConnected` t/f, `DeviceSinkAppeared`,
`DeviceSinkGone`, `Locked` t/f, `Sleep` t/f, `SetPriority` t/f, `Switch`, `Availability` t/f,
`AudioBackend` t/f, `ConnectResult` nei quattro esiti, `DisconnectResult` ok/failed. Partenza: i
default con `priority` false e true. Configurazione di default. «Contesti» = contesti distinti
raggiungibili; «transizioni» = coppie (chiave, evento) esplorate, cappi compresi; «azioni» = somma
delle lunghezze delle liste.

| Modello | Esplorazione | Coppie | Contesti | Transizioni | Azioni | released | connecting | on_pc | releasing | unavailable |
|---|---|---|---|---|---|---|---|---|---|---|
| U | contesti; base più `TimerFired` degli otto timer | — | 81 844 | 2 537 164 | — | 24 032 | 6 372 | 2 560 | 38 640 | 10 240 |
| T | coppie contesto + timer attivi, partendo senza timer; base più `TimerFired(X)` per i soli X attivi, tolto prima di `step`; poi `StartTimer` aggiunge e `CancelTimer` toglie, nell'ordine | 151 236 | 80 404 | 3 683 354 | 5 419 116 | 23 392 | 6 372 | 2 560 | 37 840 | 10 240 |

Un'impronta diversa significa un comportamento diverso: fermarsi e riportarlo.
