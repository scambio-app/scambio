# Spec 04 — Report di verifica

Data: 2026-10-07 · Codex · Base: `9e89ce4`.

## Stato

Tappe (a) e (b) completate; tappa (c) da iniziare.
Commit tappa (a): `881f494`.
Goal non completato.

## Lettura preliminare ed evidenza

Letti nell'ordine AGENTS.md, contesto 01–06, hardware-lab e spec; consultati
poi graphify, decisioni e brain tramite il solo MCP `agvm-scambio` in sola
lettura. Il brain ha restituito un pacchetto parziale di milestone precedenti:
nessuna sua memoria è stata assunta come requisito nuovo. Nessun grep/rg di ripiego.

Il contrasto fra 05 §5.10 (banner nascosto al riavvio voluto) e la checklist
§6.1 punto 8 ha causato lo stop preliminare richiesto dal Messaggio 2.
Durante la sessione una modifica esterna alla spec ha corretto il punto 8
in «nessun banner (05 §5.10)»: contrasto risolto, implementazione ripresa.
Codex non ha modificato la spec e non includerà la modifica esterna nei propri commit.

La copia invariata del file di Claude `tray.json.spec04` è la consegna
espressamente prevista dalla spec §3.1.6 per la tappa (b); non comporta
progettare o modificare autonomamente il design. Copia non ancora eseguita.

## Verifiche

- Baseline `make check`: verde, 569 test passati, nessun salto (65,01 s).
  Il Makefile iniziale compila i18n; `make ui` sarà aggiunto in tappa (c).
- Misura baseline di 600 s avviata con `tools/measure_idle.py --ui` su bus
  privati e fake pactl. Output previsto: `idle-before.json`.
- Nuovi test spec 04 e misura finale: da eseguire.
- GNOME e Plasma 6: non verificati.
- Prova GM e audit visivo Claude: da eseguire; checklist da completare
  nel report conclusivo. Nessuna prova umana simulata.

## Debito MPRIS

Causa letta nel codice: `recover()` termina subito quando non c'è stato da
recuperare; il primo `forget()`/`pause()` può chiamare `_save()` prima di
`GetId`, con insieme vuoto e nessun dato da salvare. Evitare l'avviso solo
in questo caso vuoto; mantenere il warning quando esistono player o dati
di recupero. Test `test_empty_startup_without_bus_identity_is_silent`: passa; verifica anche
che i dati reali senza identità restino preservati e diagnosticati.

## Chiusura ancora richiesta

Checklist §6 non soddisfatta: implementazione, test nuovi, misure finali,
checklist GM e prova reale mancanti. Decisioni tecniche 110–112 registrate; 113–119 disponibili.
Tracker, hardware-lab, contesto e spec restano di Claude; aggiornamenti e
promozione al brain saranno richiesti nel report finale.

## Consegna tappa (a)

- KGlobalAccel e portal via Gio, conversione pura dei tasti, memoria facoltativa
  `shortcut` in state.json, proprietà `Shortcut*` e `RetryShortcut`.
- Pressione tramite un `ScambioClient` separato verso `Switch()`, senza
  modifica della policy. Callback di risposta/errore aggiunte al client per
  diagnosticare `DeviceUnavailable`; il completamento del client per la
  finestra resta nella tappa (c).
- Chiusura KGlobalAccel con `setInactive`/NO_AUTO_START; mai unregister.
  Portal: sottoscrizione prima della chiamata, chiusura richieste/sessione.
- Test dedicati: 44 casi in `test_shortcuts.py`, incluso un test tabellare
  con tutte le combinazioni dei modificatori e i tasti ammessi; 37 test MPRIS.
- `make check`: **614 passati, nessuno saltato**, 73,72 s; format, lint,
  mypy (26 file) e compilazione cataloghi verdi.
- Nessuna nuova dipendenza o timer. Misura iniziale conclusa: vedi sotto.
- File della tappa: `src/scambio/core/{shortcut_keys.py,shortcuts.py,service.py,
  players.py,dbus/app.scambio.Scambio1.xml}`, `src/scambio/state.py`,
  `src/scambio/ui/client.py`, `tests/{test_shortcuts.py,test_players.py,
  test_service.py}`, `docs/decisions.md` e questo report.
- Modifiche esterne osservate: spec §6.1 punto 8 e hardware-lab M19;
  escluse dal commit di Codex. Nessun file design modificato.

## Consegna tappa (b)

- SetConfig con conservazione dei byte non modificati e permessi; Config,
  DeviceBusy, ListDevices asincrono e RestartUnit dopo la risposta.
- CLI status espone Config anche come chiave=valore nel testo.
- Tray con nome noto rilasciato quando disattivato; voce 7 visibile e
  attivazione D-Bus della finestra. Notifiche priority sospese col nome
  Settings.Active posseduto; notifiche di errore ancora attive.
- Asset `design/ui/tray.json`: copia **identica** al file consegnato da
  Claude (§3.1.6); unica differenza semantica dalla base è la rimozione
  di `visible: false` della voce 7. Nessuna modifica creativa al design.
- `make check`: **665 passati, nessun salto**, 78,13 s; lint, format,
  mypy e cataloghi verdi. Test TOML 29, API 19, tray 19, notifiche 31.
- Evidenza M17: `test_tray_name_disappears_and_returns`; l'owner sparisce,
  ricompare e il watcher riceve di nuovo lo stesso nome, su bus privato.
- Config: test del segnale prima della risposta, rifiuti senza Error/LastError,
  indirizzo modificato solo nel file, cgroup simulato, errore di RestartUnit
  con file scritto e demone invariato, filtro/disponibilità BlueZ.
- File: `src/scambio/{api.py,cli.py,config.py}`, `core/{bluez.py,ports.py,
  service.py,dbus/app.scambio.Scambio1.xml}`, `ui/{actions.py,notify.py,tray.py}`;
  test config_edit/settings_api e aggiornamenti notifications/presentation/
  service/tray; asset consegnato; decisioni e report.

## Misura iniziale di riposo

`idle-before.json`: baseline caricata prima delle modifiche, 600,09 s su
bus privati con watcher, notifiche, MPRIS e fake pactl. CPU demone 0,0%;
RSS da 23.764 a 23.892 KiB. Nessuna chiamata durante l'intervallo a pactl,
MPRIS, watcher o notifiche. La baseline non ha ancora la scorciatoia;
la misura finale dovrà includere KGlobalAccel finto attivo.
