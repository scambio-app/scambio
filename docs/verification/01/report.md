# Spec 01 — Report di verifica: STOP prima dell'implementazione

Data: 2026-10-04 · Autore: Codex · Branch: `main` · Base: `2824948`.

## Obiettivo ed esito

Implementare esclusivamente §3 della spec 01 nelle tre tappe richieste, con test
isolati e un commit verde per tappa. **Obiettivo non raggiunto**: applicata la
condizione di stop documentale prima della tappa (a). Questo è un report di blocco,
non una consegna del demone e non una dichiarazione di done.

## Evidenza del blocco

`AGENTS.md`, «Prima di pianificare», punto 2, prescrive:

> se una spec dipende da un comportamento non misurato in `hardware-lab.md`,
> fermati e segnalalo.

La spec §3.1.4 richiede il rilascio Bluetooth al blocco tramite l'OR di
`LockedHint` e `ScreenSaver.Active`, ma dichiara esplicitamente:

> il loro comportamento al blocco non è misurato: lo verifica il punto 6 della prova reale

Anche §8, punto 4, conferma il blocco schermo non misurato e la ricreazione del
sink al cambio A2DP/HFP non misurata. `hardware-lab.md` contiene M1–M5, senza una
misura datata dei segnali di blocco. M1 misura il cambio profilo, ma non documenta
la sequenza di scomparsa/ricomparsa del sink prevista da O9–O11.

La decisione 29 approva eccezioni per installazione della unit e testi inglesi,
e conferma comportamenti di prodotto. Non deroga esplicitamente al requisito
«misura prima». L'approvazione generale della spec non risolve il conflitto con
la regola di precedenza di AGENTS.md e con lo stop ribadito nell'incarico.

**Interpretazione applicata:** rimandare queste misure a dopo l'implementazione
contrasta con il prerequisito di AGENTS.md. Non è una scelta tecnica reversibile
che Codex possa registrare autonomamente dalla decisione 30. L'autorizzazione
alla misura CPU/RSS su finti riguarda quella misura specifica e non è stata
estesa a una deroga generale sul comportamento hardware.

Non sono state eseguite misure reali né sostituite con risultati dbusmock.

## Consultazioni e verifiche

- Letti AGENTS.md, docs/context/01–06, hardware-lab, decisioni, spec nell'ordine
  richiesto; completata separatamente la lettura delle porzioni troncate nell'output.
- `graphify query` sul conflitto misure/spec; `graphify affected` sulla spec
  (nessun nodo interessato) e sul nuovo report (nessun nodo univoco, file nuovo).
- `graphify path` tra AGENTS.md e spec: nessun percorso diretto trovato.
- Consultato esclusivamente MCP `agvm-scambio`, sola lettura, brain restituito
  `scambio_brain`: guida, retrieve_context e inspect_context_package, ricerca
  `5a6725a3-094a-4a5e-9823-4e1406d304ff`. Il materiale restituito riguarda la
  milestone 0 e non documenta la deroga cercata; non costituisce prova della
  sua inesistenza. La conclusione sopra si fonda sui file del repository.
- Nessuna ricerca con grep/rg; nessuna operazione sul registro brain o scrittura
  di memoria.
- `make check` eseguito: **exit 2**, `make: *** No rule to make target 'check'.  Stop.`
  Il Makefile e il pre-commit non esistono ancora nella base della spec 01.
- Nessun test unitario o di integrazione eseguito: il codice non esiste.
  Non ci sono test verdi o saltati da dichiarare.
- Nessun demone avviato, bus reale utilizzato, comando Bluetooth/audio reale,
  `make install-user` o `systemctl --user` eseguito.

## Checklist §6: fatte e non fatte

| Voce | Esito ed evidenza |
|---|---|
| Tooling, venv, hooks, blocco commit rosso | Non fatta; tappa (a) non iniziata |
| Test di tutte le regole e adattatori | Non fatta; nessun codice implementato |
| make check verde, zero skip | Non fatta; make check termina con exit 2 |
| Nessun polling e misura CPU/RSS 10 min | Nessun polling introdotto; misura non fatta, demone e finto pactl non esistono |
| Configurazione completa, nessun valore personale hardcodato | Configurazione non implementata; nessun codice con valori personali introdotto |
| Testi e msgid CLI | Nessuna CLI implementata; elenco msgid vuoto |
| design/ intatto, richieste elencate | Fatta; nessuna modifica o richiesta di design |
| Report e decisioni tecniche | Report scritto; nessuna decisione tecnica presa, numero 30 lasciato disponibile |
| Checklist reale copiata con comandi | Fatta; copia integrale sotto, non eseguita |
| Prova reale e firma GM | Non fatta; tutti i punti 1–18 pendenti |

La misura CPU/RSS reale sarà eseguita da GM al punto 18. Anche la misura su
bus privati con finti richiesta per questa sessione resta non eseguita a causa
dello stop. Non viene attribuito alcun valore CPU/RSS al demone o a pactl.

## Cambiamenti, commit e scostamenti

Unico file aggiunto intenzionalmente: `docs/verification/01/report.md`.
Nessuna modifica a src/, tests/, tooling, packaging, design/, docs/context/,
docs/specs/, hardware-lab o decisions.md. Le tre tappe (a), (b), (c) e i loro
commit non sono stati eseguiti, per la condizione di stop.

Il commit documentale di questo report è identificabile con:

```sh
git log -1 --format=fuller -- docs/verification/01/report.md
```

Messaggio previsto: `Document spec 01 measurement blocker`, con trailer
`Co-Authored-By: Codex <noreply@openai.com>`. È il commit del report di stop
richiesto dall'incarico, non un commit di tappa con gate verde. Nessun
`--no-verify`, nessuna modifica o disabilitazione degli hook, nessun push.
L'hook post-commit graphify già presente può aggiornare i propri artefatti.

All'ispezione iniziale risultavano già modificati nove file in `graphify-out/`
(labels e firma; GRAPH_REPORT, graph.json, manifest della directory datata;
GRAPH_REPORT, graph.html, graph.json, manifest principali). Non sono stati
ripristinati né inclusi nel commit del report.

## Questioni aperte e handoff

Per riprendere occorre risolvere il prerequisito: misure datate registrate da
Claude in hardware-lab per i comportamenti richiesti, oppure una deroga GM
esplicita alla regola «misura prima» per implementarli su finti e verificarli
successivamente. Questa sessione non interattiva non richiede risposte e non
introduce autonomamente la deroga.

Tracker, contesto, spec, hardware-lab e brain restano ai rispettivi proprietari.
Nessuna richiesta per design/. Nessuna assunzione sul funzionamento reale di
lock, sospensione o ricreazione del sink viene presentata come evidenza.

## Prova reale futura: copia di §6.1, NON ESEGUITA

I comandi seguenti sono riportati per GM e richiedono prima l'implementazione.
Non sono stati lanciati in questa sessione. L'indirizzo presente è copiato dalla
checklist autorizzata, non inserito nel codice. Firma GM e data: **pendenti**.

### 6.1 Checklist di prova reale per GM (occhiali + iPhone)

Preparazione: `make venv && make install-user`; in `~/.config/scambio/config.toml` mettere
`device.address = "80:AA:1C:XX:XX:XX"`; `systemctl --user start scambio`; in un terminale
`journalctl --user -u scambio -f`. Non usare la vecchia scorciatoia Ctrl+Shift+O durante la
prova. Per accorciare l'attesa si può mettere temporaneamente `release_idle_seconds = 30` e
ricaricare con `systemctl --user reload scambio` (rimettere 120 alla fine).

| # | Azione | Atteso |
|---|---|---|
| 1 | Occhiali sull'iPhone con musica; `scambio status` | `released`, `AudioActive false` |
| 2 | Avvia un video su YouTube nel PC | entro ≈ 3 s audio negli occhiali; musica iPhone ferma; `on_pc`; `pactl get-default-sink` = `bluez_output…` |
| 3 | Pausa del video, attendi `release_idle_seconds` | rilascio; iPhone si ricollega (musica in pausa, atteso); `released`; `pactl get-default-sink` = Scarlett (scelta di WirePlumber, non misurata finora: annotare) |
| 4 | Da occhiali sull'iPhone: `paplay /usr/share/sounds/freedesktop/stereo/bell.oga` | nessuna presa (suono < 1 s) |
| 5 | Notifica di sistema con suono (es. messaggio Telegram/KDE) | nessuna presa |
| 6 | Musica sul PC con occhiali sul PC → blocca lo schermo | rilascio immediato; l'audio continua dagli altoparlanti (atteso in questa spec); nel journal si vede quale fonte ha segnalato il blocco |
| 7 | Sblocca con l'audio ancora attivo | nuova presa dopo ≈ 1 s |
| 8 | Occhiali sul PC, nessun audio → sospendi il PC, poi riattiva | scollegati prima della sospensione (journal); dopo la ripresa nessuna presa finché non parte audio |
| 9 | `scambio switch` con occhiali sul PC, poi avvia audio sul PC | rilascio + `IphonePriority true`; nessuna presa |
| 10 | `scambio switch` di nuovo | presa + `IphonePriority false` |
| 11 | `scambio priority on` con occhiali sul PC | rilascio immediato |
| 12 | `systemctl --user restart scambio`; `scambio priority` | priorità conservata |
| 13 | Chiamata WhatsApp sull'iPhone, poi audio sul PC | presa; la chiamata passa al telefono; `scambio switch` → la chiamata torna negli occhiali |
| 14 | Occhiali sul PC con musica → chiudili nella custodia, riaprili | `released` (`external_disconnect`); nessun ciclo di riprese; uscita predefinita ripristinata |
| 15 | Collega gli occhiali dall'applet Bluetooth di KDE | adozione `on_pc`, audio negli occhiali |
| 16 | Spegni il Bluetooth dal tray di KDE, poi riaccendilo | `unavailable`, poi `released` |
| 17 | `systemctl --user restart pipewire pipewire-pulse wireplumber` | nessun rilascio; il demone si riaggancia (journal); una nuova presa funziona |
| 18 | Dopo 10 min di inattività: `ps -o rss,pcpu -p $(pgrep -f 'scambio daemon') $(pgrep -f 'pactl -f json subscribe')` | CPU ≈ 0 %, RSS annotato |
