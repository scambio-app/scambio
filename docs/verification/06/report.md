# Spec 06 — candidata Linux 1.0.1 verificata

Data: 2026-10-08 · Codex · branch `main` nei due repository.

**Implementazione e verifiche automatiche completate; candidata sigillata e asset del sito
committati localmente. La spec non è chiusa: manca la prova reale firmata da GM.**
`make check`: **848 test passati, zero saltati**, format/lint/type check verdi.
Nessun push, tag, release GitHub, deploy o promozione nell'archivio pubblico.

## Obiettivo e perimetro

Implementato solo §3: riconoscimento automatico del profilo dal nome BlueZ del dispositivo
configurato, ritardo effettivo, API, test e candidata 1.0.1. La ripresa riguarda l'audio del
**PC alla presa**, secondo M11b/M12; non controlla l'iPhone.

I blocchi del precedente report (`541ddff`) sono risolti: Claude ha corretto §1 in `a9d65e1`
e consegnato quattro file di design nel working tree. Su istruzione esplicita di GM sono
inclusi invariati nel commit della versione; gli [SHA256 originali](evidence/design-sha256.txt)
corrispondono ancora ai file finali. Nessun testo, widget, icona o layout riscritto da Codex.
Nessuna nuova decisione di prodotto o contraddizione normativa emersa dopo la correzione.

## Comportamento implementato

- `Device`, parser e template usano `auto`; `generic` e `meta_glasses` espliciti prevalgono.
  La regex è quella della spec, senza distinzione maiuscole/minuscole. Un file esistente
  con `generic` non viene migrato né riscritto.
- BlueZ usa `Alias`, oppure `Name` se `Alias` manca. Alias vuoto, dispositivo ignoto o
  rimosso e perdita di BlueZ portano l'automatico a `generic`. Comparsa, rinomina e ritorno
  di BlueZ ricalcolano tramite gli eventi già esistenti.
- Il riconoscimento usa il nome completo; UI/API e log conservano sanificazione e limite
  di 64 caratteri. Viene considerato soltanto il dispositivo configurato. Una riga di log
  per cambio della coppia profilo/origine, senza duplicati per rinomine equivalenti o reload.
- Il parser conserva la presenza di `policy.resume_delay_ms`: anche uno zero esplicito
  prevale. Il servizio costruisce la policy effettiva con default 0/2000 ms. I timer già
  programmati restano identici, il valore nuovo vale dalla ripresa successiva.
- `DeviceProfile` e `DeviceProfileSource` sono proprietà D-Bus readonly, con
  `PropertiesChanged`. La CLI le stampa tramite il `GetAll` esistente, anche in JSON.
  La finestra non mostrava il profilo e resta invariata; nessuna logica aggiunta alle UI.
- Il cambio di indirizzo mantiene il riavvio della decisione 155; la nuova istanza risolve
  il nuovo dispositivo. Rinomina e reload del solo profilo non richiedono riavvio.

Nessun polling, nuovo main loop, demone aggiuntivo o dipendenza runtime introdotto.
Il tooling conserva la storia pubblicata nella candidata e prova l'upgrade dalla **vera
1.0.0 sigillata**, senza fabbricare una versione precedente dal pacchetto nuovo.

## Checklist §6 ed evidenze

| Voce | Stato | Evidenza |
|---|---|---|
| Ogni regola §3.1 ha un test | FATTO | 41 casi in `tests/test_profiles.py`: regex, precedenze, ritardo esplicito, comparsa/rinomina/rimozione BlueZ, nome ignoto, log, configurazione preservata; bus privati dbusmock |
| Parser, tre valori, default e template ri-analizzabile | FATTO | `test_auto_defaults_and_localized_templates`, `test_profile_parser_preserves_explicit_timing`; cataloghi it/en/de reali; rifiuto del profilo sconosciuto nella suite esistente |
| Proprietà D-Bus, segnali e CLI | FATTO | `test_bluez_alias_api_signals_and_log_once`, `test_reload_source_signal_and_preserve_pending_resume`, `test_cli_prints_effective_profile` |
| `make check`, zero salti, nessun polling | FATTO | [Log completo](evidence/make-check.log): 848/848 passati; lettura delle modifiche e misure sotto |
| Candidata, firme/hash, install/upgrade/rimozione Ubuntu/Debian e Flatpak | FATTO | [Build](evidence/build.log), [verify](evidence/verify.log), [sigillo](evidence/seal.log), [artefatti](evidence/artifacts.json) |
| 1.0.0 sigillata intatta | FATTO | Firma verificata; [inventario precedente](evidence/archive-1.0.0-before.json) e [confronto finale](evidence/archive-integrity.json): 188 file con hash e permessi invariati |
| AppStream e `config-device-profile` di Claude usati senza duplicazione | FATTO | [Hash dei quattro originali](evidence/design-sha256.txt), validazione AppStream e test dei template localizzati |
| Report, richieste architettura, CPU/RSS, checklist GM | FATTO | Questo report e misure allegate |
| Decisioni tecniche 210–219 | FATTO | [Decisioni 210–215](../../decisions.md); 216–219 non utilizzate |
| Prova reale eseguita e firmata da GM | **NON FATTO** | Checklist sotto preparata; esiti e firma/data non ricevuti. I mock non valgono come prova umana |

La chiusura nel tracker resta subordinata anche all'audit di Claude previsto da `AGENTS.md`.

## Test e verifiche dei pacchetti

Il controllo del commit sorgente `9c6a85d` ha verificato format su 76 file, ruff, mypy su
32 sorgenti e 848 test in 104,94 s. Gli hook pre-commit hanno eseguito `make check` su ogni
commit del main, senza `--no-verify`. Nessuna CI remota usata.

Copertura aggiuntiva: Alias vuoto distinto da Alias mancante, fallback Name e invalidazione,
nomi con token oltre il 64° carattere, dispositivo estraneo, riavvio BlueZ, cambio della sola
origine, reload con timer pendente e cambio indirizzo. Tre nuovi test del tooling verificano
storia firmata, rifiuto di duplicati/manomissioni, scelta della versione precedente e copia
OSTree scrivibile senza alterare l'originale.

Comandi sui sorgenti puliti, tutti terminati con exit 0:

```sh
SCAMBIO_RELEASE_CANDIDATE=linux-1-0-1-rc1 make dist deb apt-repo flatpak flatpak-site
SCAMBIO_RELEASE_CANDIDATE=linux-1-0-1-rc1 make verify
```

I desktop file estratti dai due pacchetti sono [validi](evidence/desktop-file.log).
`make verify` controlla firme, hash e AppStream, poi:

| Ambiente | Prova | Esito |
|---|---|---|
| Ubuntu 24.04, systemd presente | Installazione 1.0.0, apt update e upgrade 1.0.1, remove/purge, reinstallazione/purge | PASS |
| Debian 13, systemd presente | Stesso ciclo, unità systemd verificata | PASS |
| Ubuntu 24.04, systemd assente | Stesso ciclo, assenza effettiva di systemctl prima/dopo | PASS |
| Debian 13, systemd assente | Stesso ciclo | PASS |
| Flatpak temporaneo, GNOME Platform 51 | Installazione commit 1.0.0, aggiornamento 1.0.1, permessi, rimozione/reinstallazione/rimozione | PASS |

apt legge il repository firmato da un server HTTP locale. La configurazione `generic`
e lo stato sentinella sopravvivono; parser e default nuovi sono verificati dal Python installato.
Sono controllate rimozione della sorgente apt e dell'abilitazione del servizio.
Nel Flatpak i permessi corrispondono alla decisione 153 e tre servizi presenti sui bus privati
risultano irraggiungibili: UPower, systemd1 e org.freedesktop.Flatpak.
Container e installazioni Flatpak/venv sono temporanei; nessuna installazione o modifica
della configurazione e del servizio reali di GM.

## Candidata, integrità e sito locale

Identificatore: **`linux-1-0-1-rc1`**, versione **1.0.1**.
Sorgente dei pacchetti: **`9c6a85d173b98407a66b909e0e69dcf69a4f3694`**.
Il commit successivo di report/evidenze non cambia i sorgenti contenuti nei pacchetti.

- Output: `dist/candidates/linux-1-0-1-rc1/`.
- Archivio immutabile: `~/.local/share/scambio-release/candidates/linux-1-0-1-rc1/1.0.1/`.
- Manifest [JSON](evidence/candidate-manifest.json) e [firma](evidence/candidate-manifest.json.asc);
  inventario verificato dopo la sigillatura, file 0444 e directory 0555.

| Artefatto | Byte | SHA256 / commit |
|---|---:|---|
| `scambio_1.0.1_all.deb` | 229580 | `37da071748767f680c304bd5e462995db5970b24315cbafffd81d63323b6d782` |
| `scambio-1.0.1.tar.gz` | 1700383 | `13e7f95979e10fa9ed5e59a697e6936ddf259119d1934b50883f34d13f2f5859` |
| Flatpak `app.scambio.Scambio/x86_64/stable` | — | `6c245a679b4270a3456a1427b7b185734521c78dc541f8e7b0e7aeb3b3d0a794` |

La baseline pubblicata è l'archivio 1.0.0 con sorgente `50e722b`, `.deb` SHA256
`32a14d35c95c533fa5c01b41e62bcc41b6ce904336969aafcbec2a4fd740b293` e OSTree
`4dfea0a65d45f83d55d85e2eebfb59b7e3ee82b8c7ca1332b14899637cc9e984`.
Verificata contro gli asset 1.0.0 del sito prima di copiarvi la candidata. L'archivio pubblico
non ha ricevuto una cartella 1.0.1 né alcuna sovrascrittura.

Nel sito, `git rebase 18318baa1d0623ebd7d79920f87cf9886c902a71` ha confermato la branch
aggiornata; verificato lo stesso HEAD immediatamente prima del commit degli asset.
Commit locale **`74604fc34528b783692e77cfeda2ca77503380af`**, padre `18318ba`.
Solo 118 percorsi di rilascio cambiati. [Verifica asset](evidence/site-assets.json): 291 file
corrispondono allo staging verificato; tutti gli altri file tracciati restano identici.
Il file non tracciato `.design-ref.tgz` dell'altra chat è intatto. Nessuna modifica a HTML,
CSS, JS, Worker, waitlist o configurazione del sito.

Anteprima `wrangler dev --local` su `127.0.0.1:8897`, poi arrestata: **15 richieste GET/HEAD
passate**, inclusi redirect relativo alla 1.0.1, deb, firme, apt e Flatpak; byte, MIME e cache
verificati. [Risultati](evidence/site-routes.json). Nessun invio email o accesso a D1 remoto.
Nessuna nuova schermata da verificare per asset binari senza variazioni dell'interfaccia.

## Misure CPU/RSS a riposo

Dieci minuti con gli strumenti esistenti: due letture dei contatori di processo, senza
ciclo di campionamento. I timer della sonda non sono timer del demone.

Il checkout usa bus privati dbusmock BlueZ/logind/ScreenSaver/MPRIS, pactl stabile simulato,
UI/SNI/notifiche e KGlobalAccel simulati attivi. Gli hash nel [JSON](evidence/idle-checkout.json)
coincidono con il codice runtime della candidata. Nell'intervallo: zero chiamate pactl,
MPRIS, watcher, notifiche e KGlobalAccel.

Il deb è estratto e caricato da una venv temporanea; il Flatpak è installato e avviato da una
`FLATPAK_USER_DIR` temporanea con runtime condiviso in lettura. Bus privati, pactl simulato,
nessun dispositivo configurato e UI abilitata. I JSON riportano hash deb e commit OSTree:
le misure valide sono quelle della build finale `9c6a85d`.

| Ambiente | Intervallo | CPU aggiuntiva | RSS iniziale/finale |
|---|---:|---:|---:|
| Checkout, UI e scorciatoia attive | 600,100 s | 0 s, 0% | 36.936 / 36.936 KiB |
| [`.deb` finale](evidence/idle-deb.json) | 600,100 s | 0 s, 0% | 38.724 / 38.724 KiB |
| [Flatpak finale](evidence/idle-flatpak.json) | 600,100 s | 0 s, 0% | 43.800 / 43.800 KiB |

Sono misure del processo negli scenari dichiarati. Non provano il comportamento Bluetooth
reale, la temporizzazione percepita dell'annuncio o il consumo dell'intero desktop.

## Decisioni, problemi risolti e limiti

Decisioni tecniche: 210 policy dichiarata/effettiva e presenza del ritardo; 211 nome completo
e testo sanificato; 212 API additiva e riavvio per indirizzo; 213 storia pubblicata e upgrade
reale; 214 permessi della copia OSTree; 215 URI locale del remote Flatpak.

Due verifiche intermedie fallite sono state corrette prima della build consegnata: la copia
dell'archivio sigillato lasciava `.lock` OSTree non scrivibile; `remote-modify` con un percorso
anziché `file://` terminava senza aggiornare il Flatpak. Il controllo della versione ha
rilevato quest'ultimo caso. Le prove finali riportate sono successive alle correzioni e
complete, senza trasformare gli insuccessi in test passati.

- 1056 warning esterni PyGObject/asyncio; deprecazione `Gtk.ShortcutLabel` già presente.
  Non corretti, come richiesto dal §4. Nessun test saltato.
- Lintian senza errori: rimangono gli override della decisione 157 e gli avvisi preesistenti
  sui percorsi assoluti degli script e sulla manpage assente. AppStream valida con il solo
  avviso pedantico sul maiuscolo nell'ID fissato. Desktop file valido.
- `flatpak-builder --show-manifest` eseguito; `flatpak-builder-lint` non eseguito perché
  mancano modulo e namespace GI AppStream/OSTree nativi, non installabili via pip.
  [Sonda locale](evidence/flatpak-lint-prerequisites.log). Omissione motivata consentita da
  spec 05 §3.1.5.3; nessun pacchetto di sistema installato sull'host.
- `git diff --check` degli asset apt segnala tre righe vuote finali nei nuovi file by-hash:
  separatori dei record Debian generati da apt-ftparchive, conservati byte per byte per
  mantenere hash e firme. Non modificati come se fossero prosa.
- Parti preesistenti del README su FAQ/Mac/ruoli AI contengono testo troncato: debito
  editoriale per Claude; questa unità cambia solo versione e note sul profilo.
- Nessuna prova hardware registrata da Codex; M11b/M12 sono evidenze preesistenti e non
  sostituiscono la prova della candidata. GNOME resta fuori scope.

## Richieste a Claude per `02-architecture.md` e chiusura

Il file è di Claude e non è stato modificato. All'audit inserire:

1. `device.profile`: valori `auto | generic | meta_glasses`, default `auto`; valori espliciti
   preservati senza migrazione. `resume_delay_explicit` è interno, non una chiave TOML.
2. Profilo del solo indirizzo configurato da `Alias`, fallback `Name` solo se Alias assente,
   regex della spec; automatico ignoto/vuoto → `generic`. Aggiornamento per eventi, anche
   dopo scomparsa/ritorno BlueZ. Nome completo interno, testo pubblico sanificato e limitato.
3. `policy.resume_delay_ms` esplicito prevale; altrimenti 0 per `generic`, 2000 per
   `meta_glasses`. Policy effettiva separata, ricalcolo senza modificare timer pendenti.
4. Proprietà D-Bus readonly tipo `s`: `DeviceProfile` (`generic | meta_glasses`) e
   `DeviceProfileSource` (`auto | config`), con `PropertiesChanged` e `scambio status`.
5. Cambio indirizzo applicato tramite riavvio esistente; profilo/alias senza riavvio.
   Log una volta per coppia profilo/origine.

Nessuna ulteriore richiesta per `design/`: gli asset consegnati sono validi e usati invariati.
Restano audit Claude, prova GM, aggiornamento contesti/tracker e, alla milestone, brain da
parte di Claude. Hardware-lab solo con misure reali e metodo. Nessuna domanda di prodotto
aperta; manca l'evidenza umana prevista.

## Checklist di prova reale per GM — da eseguire e firmare

Usare la candidata e gli hash indicati sopra. Questa checklist **non è un risultato**.
La preparazione dell'installazione reale, evitando due demoni, è di GM/Claude.

- [ ] Annotare data, ambiente/desktop, versione del pacchetto, nome del dispositivo e hash.
- [ ] Config pulita con Oakley Meta configurati, senza impostare a mano `profile` o
  `resume_delay_ms`: log una volta `device profile: meta_glasses (auto, from name)`;
  `scambio status` mostra `DeviceProfile: meta_glasses` e `DeviceProfileSource: auto`.
- [ ] Avviare un video/player sul PC con occhiali inizialmente non sul PC; alla presa
  confermare che l'audio del PC riprende **dopo** l'annuncio vocale. Annotare eventuale
  sovrapposizione; la musica dell'iPhone non è una verifica della spec.
- [ ] Upgrade dalla 1.0.0 con `profile = "generic"` scritto: file identico, profilo `generic`
  e origine `config`.
- [ ] Impostare `profile = "auto"` oppure cancellare la riga e ricaricare: `meta_glasses`,
  origine `auto`, ritardo dalla ripresa successiva senza riavvio del demone.
- [ ] Esiti e anomalie; firma **GM**, data: **non ricevute**.

La richiesta degli esiti è stata inviata a GM nella sessione. Nessuna firma attribuita
implicitamente e nessuna pubblicazione intrapresa in attesa.

## Commit, proprietà dei file e metodo

| Repository | Commit | Contenuto |
|---|---|---|
| scambio | `1f39ff9` | Profili, API/test, versione/note 1.0.1 e asset invariati di Claude |
| scambio | `c99bb14` | Storia dei repository e upgrade dalla release sigillata |
| scambio | `7c23a1e` | Permessi della copia OSTree e test di integrità |
| scambio | `9c6a85d` | URI della verifica Flatpak; sorgente finale dei pacchetti |
| scambio-site | `74604fc` | Soli asset della candidata verificata, dopo rebase |

File di implementazione: `src/scambio/config.py`, `src/scambio/core/bluez.py`,
`src/scambio/core/service.py`, `src/scambio/core/dbus/app.scambio.Scambio1.xml`;
`tests/test_profiles.py`, `tests/test_service.py`, `tests/test_service_players.py`,
`tests/test_release_tools.py`; `tools/release.py`, `tools/verify_release.py`; `pyproject.toml`,
README, CHANGELOG, sole voci 210–215 di `docs/decisions.md`. I quattro file `design/` sono
quelli ricevuti da Claude e inclusi invariati su richiesta. Report e allegati sono sotto
`docs/verification/06/`. Nel sito l'elenco è in [site-assets.json](evidence/site-assets.json).

Letti in ordine AGENTS, context 01–06, hardware-lab e spec; consultati graphify query,
affected e path prima delle modifiche. Il grafo è ricostruito dagli hook ed escluso da Git.
Nel sito manca il grafo: lettura diretta dei percorsi noti, senza ricerca testuale.
Nessun `grep`, `rg` o `find` per cercare codice/documenti.
Contesto storico solo tramite MCP `agvm-scambio` sul brain `scambio_brain`, in sola lettura:
query di ripresa `dbfc91ec-0f32-4ad0-8cbc-c28ee29939a6`, oltre alle due del preflight in
`541ddff`. Risposta parziale, verificata contro repo/spec; nessuna memoria sostituisce le
misure, nessuna scrittura o operazione sul registro.

La sola voce non soddisfatta della checklist di done è la prova reale firmata di GM.
Il goal non è dichiarato completo finché questa evidenza manca.
