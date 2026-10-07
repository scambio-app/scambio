# Spec 05 — implementazione e verifiche locali

Data: 2026-10-08. Autore: Codex. Branch: `main` in entrambi i repository.

## Esito e limiti della consegna

Implementati packaging Debian/Flatpak, avvio e percorsi installati, correzioni di sicurezza
§3.1.10, sito con asset locali e doppio opt-in, strumenti di verifica e firma. Nessun push,
deploy, tag, riscrittura della storia, invio email reale o migrazione D1 remota.

**Stato della prima consegna, precedente all’audit 1:** la chiusura restava sospesa sui
prerequisiti di Claude indicati sotto. La sezione [Correzioni audit 1](#correzioni-audit-1)
aggiorna questa situazione e distingue il lavoro di Codex dalle attività rimaste a Claude/GM.
La prova reale di GM è esclusa dal goal e non è stata eseguita né simulata come prova umana.
Le prove locali del binding email sono positive, ma non dimostrano l'abilitazione nell'account.

- Email Sending: `wrangler email sending settings scambio.app` restituisce `Unauthorized [2036]`.
  Non permette di concludere né che il binding sia disponibile né che sia indisponibile.
  §3.1.10.3 dice: «Se il binding non è disponibile sull'account, fermati e scrivilo nel report:
  lo configura Claude». È stata richiesta la verifica del prerequisito, senza modificare account
  o credenziali. [Output](evidence/email-account.log).
- FAQ: §3.3.3 dice «Claude fornisce i testi definitivi nel commit dei testi (§8) prima del goal».
  I testi definitivi per “Is it free?” e “When does it launch?” non risultano consegnati nel sito;
  le FAQ precedenti restano in `copy.json`, senza nuove formulazioni inventate da Codex.
- Screenshot dell'app: il metainfo di Claude riferisce `/screenshots/settings.png` e
  `/screenshots/tray.png`, ma `git ls-files design/screenshots` è vuoto. Servono le immagini reali
  di Claude/GM e la loro copia nel sito. Gli screenshot allegati qui sono del sito locale,
  non sostituiscono quelli dell'app.

## Cosa è cambiato

Il target offline `make install` è condiviso da Debian e Flatpak. Installa wrapper Python
isolato, pacchetto, traduzioni, UI compilata, dati, icone, servizi D-Bus, desktop e metainfo;
`SYSTEMD_USER_UNIT=1` aggiunge l'unità. Non sostituisce `hicolor/index.theme`, che appartiene
al tema condiviso del sistema. `make uninstall` usa il manifest dei soli file posseduti.

Il demone usa XDG di GLib, la finestra attiva via D-Bus, il tray possiede una connessione
separata e traduce il percorso icone del sandbox nel percorso dell'host. Background è richiesto
una sola volta per avvio nel Flatpak; il riavvio senza systemd chiude ordinatamente e usa
un interprete assoluto con `-I` e argv fisso. I limiti degli input esterni, i file privati e
le stringhe mostrate/loggate sono trattati come richiesto dalla spec.

I repository locali sono firmati con la sottochiave fissata, con verifica del fingerprint e
scadenza. apt usa solo SHA256 e by-hash, conserva le versioni dell'archivio autenticato e non
importa pacchetti dalla rete o dallo staging preesistente. La versione è unica, `1.0.0`.
Il Worker serve gli asset, valida il manifest del download e gestisce pending/confirmed,
token casuali hashati con scadenza e uso singolo, rate limit e quota giornaliera atomica.
CSS, JavaScript, Three.js e font sono locali; le traduzioni vengono inserite come testo.

Le scelte tecniche sono nella sola [decisione 169](../../decisions.md).

## Checklist §6

| Voce | Stato | Evidenza |
|---|---|---|
| §3.1.1–3.1.3: test di percorsi, attivazione, Background, re-exec, duplicato, tray, IconThemePath | FATTO | `test_paths`, `test_background`, `test_ui_service`, `test_service`, `test_tray`; [make check](evidence/make-check.log) |
| Build pulite deb/apt/Flatpak/sito/dist; lintian e validazioni | FATTO | [dist](evidence/dist.log), [deb](evidence/deb.log), [apt](evidence/apt.log), [Flatpak](evidence/flatpak.log), [flatpak-site](evidence/flatpak-site.log), [AppStream](evidence/appstream.log), [desktop](evidence/desktop-file.log) |
| Installazioni Ubuntu 24.04, Debian 13 e Flatpak temporaneo | FATTO | [verify e staging](evidence/verify-stage.log) |
| apt update dal repo HTTP locale con sorgente deb822 e keyring | FATTO | Stesso log, `APT::Update::Error-Mode=any`; indice by-hash e firma verificati |
| Sito locale: InRelease, flatpakref, Download en/it/de | FATTO per le rotte e gli screenshot; prerequisiti editoriali/account aperti | [rotte](evidence/site-routes.json), [en](screenshots/download-en.png), [it](screenshots/download-it.png), [de](screenshots/download-de.png) |
| Pulizia §3.1.9, scansione segreti della storia | FATTO nel perimetro Codex | [occorrenze](evidence/personal-data.txt), [scan](evidence/history-scan.json); nessun candidato ai pattern controllati |
| Intestazioni SPDX e test | FATTO | `tests/test_packaging.py::test_spdx_headers` |
| make check, nessun salto, deprecazioni classificate | FATTO | 792 test passati, zero saltati, 991 warning esterni classificati sotto |
| Nessun polling; misure CPU/RSS dai due pacchetti | FATTO nell'ambiente dichiarato | [deb](evidence/idle-deb.json), [Flatpak](evidence/idle-flatpak.json); metodo sotto |
| File di Claude non modificati da Codex | FATTO | Eccezione autorizzata: primo commit include i file design già scritti da Claude, identici; test aggiornati da Codex |
| Report e decisione 169 | FATTO | Questo file e decisione 169 |
| Nessun push/deploy/tag | RISPETTATO | Solo commit locali e anteprima locale |
| Prova reale GM §6.1 | NON ESEGUITA, esclusa dal goal | Checklist da completare dopo audit Claude |

## Evidenza §3.1.10 / S1–S14

| Audit | Implementazione / verifica | Limite residuo |
|---|---|---|
| S1 | Fingerprint primario e sottochiave, scadenza oltre 90 giorni; test rifiuto chiave cambiata/scadenza; firme verificate con keyring pubblico | Backup offline/revoca sono di GM; nessuna esportazione o copia di segreti |
| S2 | Manifest locale firmato, hash e inventario esatto; rifiuto contenuto cambiato, file extra, symlink; test esclude pacchetto estraneo nello staging apt | Archivio locale non equivale a pubblicazione |
| S3 | InRelease/Release.gpg, SHA256SUMS.asc e firme deb/tar; Date, Acquire-By-Hash; redirect relativo GET/HEAD e schema stretto | Niente Valid-Until per decisione 168b |
| S4 | Migrazione preserva legacy; pending/confirmed, hash SHA256, 32 byte casuali, 48 ore, token sostituito/scaduto/riusato, confirmed immutabile, risposta identica e niente reinvio | Binding account da verificare; test solo email simulate |
| S5 | Origin esatto, localhost solo con flag, Sec-Fetch-Site, JSON MIME, limite body in streaming; limiter 5/60s e quota D1 | Limiter Cloudflare per posizione; contatore globale in D1 |
| S6 | Header su risposte API/statiche/redirect, CSP senza unsafe-inline, vendor con licenze/versioni/hash, niente copy in innerHTML | FAQ definitive mancanti; nessuna richiesta a CDN nelle prove browser |
| S7 | SetConfig ≤32 voci/64 KiB, EventGroup ≤32/64 KiB, priorità invariata senza scrittura | Bus di sessione confine di fiducia accettato; aggiornamento contratto UI a Claude |
| S8 | Output snapshot ≤4 MiB, record subscribe ≤64 KiB, routing ≤256, quattro comandi oltre subscribe, debounce massimo 2s; limiti configurabili, terminazione/backoff e log | Nessun polling aggiunto; prove con backend simulato |
| S9 | Directory 0700, file 0600, state no symlink e ≤64 KiB, config ≤256 KiB con symlink consentito, temp locale e fsync file/directory | Eccezione config della decisione 168d |
| S10 | Controlli C0/C1/bidi rimossi, testi limitati a 64 caratteri con ellissi; massimo 16 player, salvataggio una volta per operazione | Test `test_external_text`, `test_players`, `test_service_players` |
| S11 | Installer valida CR/LF/NUL, scrive atomicamente senza seguire symlink e usa systemctl assoluto; script sh set-eu; hardening unità | install/upgrade 0.9/remove/purge in Docker; prova desktop reale a GM |
| S12 | Manifest con elenco esatto decisione 153; golden sui permessi installati; bus privati con servizi presenti ma non raggiungibili nel sandbox | Prova GNOME e portal reale a GM |
| S13 | Wrapper Python -I, pactl assoluto cercato una volta, re-exec argv fisso, estensioni non attive | Nessuna dipendenza runtime aggiunta |
| S14 | Hook senza percorso personale; alberi Codex puliti; scansione delle patch di tutta la storia dei due repo | Riscrittura autori/dati personali demandata a Claude (164/166), non eseguita |

Test sito: `.venv/bin/python tools/test_site.py` contro `wrangler dev` locale,
D1 `--local` e `send_email remote=false`: **38 richieste HTTP controllate**, più test del
Worker con ASSETS iniettato per manifest validi/manomessi e localhost abilitato.
[Output](evidence/site-tests.log). `node --check` sui tre script frontend e
`node --input-type=module --check < src/worker.js` passano. Lo script `npm test` esistente
è il placeholder che termina sempre con “no test specified” ([output](evidence/site-npm-test.log));
non rappresenta una suite passata. `package.json` è fuori dai file assegnati e non è stato cambiato.
Il test del manifest usa asset iniettati perché il watcher
Wrangler ricarica i file in modo asincrono. Le prove del corpo troppo grande hanno evidenziato
un problema di keep-alive nel proxy locale: la risposta 413 chiude la connessione. Il rerun
completo passa; gli errori delle esecuzioni intermedie non vengono conteggiati come successi.

Il browser usa un profilo temporaneo, senza il profilo personale. [Prima](screenshots/home-before.png),
[dopo](screenshots/home-after.png), [richieste ed errori](evidence/browser.json).
Verificati anche tutti gli [hash dei vendor](evidence/vendor.log).
Eseguita anche la variante con animazione e payload copy `<img ... onerror=...>`: il payload
resta testo, nessun elemento img creato e nessuna esecuzione, zero richieste esterne/zero errori.
[Log](evidence/browser-motion.log), [sonda riproducibile](evidence/browser-probe.mjs).

## Misure CPU/RSS

`tools/measure_packages.py` estrae il `.deb` e carica il codice installato in una venv temporanea;
per Flatpak crea `FLATPAK_USER_DIR` temporanea, installa dal repository locale e avvia il modulo
sotto `/app`. I runtime esistenti sono condivisi in lettura. Nessun pacchetto installato per GM.

Due letture di `/proc/self/stat` separate da 600 secondi, dopo assestamento iniziale; nessun ciclo
di campionamento. Bus system/session privati, nessun dispositivo configurato, pactl simulato
stabile e UI abilitata. I timer della misura appartengono alla sonda, non al demone.
Valori, SHA256 del deb e commit OSTree sono nei due JSON allegati. Queste misure verificano
l'assenza di attività periodica del codice installato in questo scenario: non misurano Bluetooth
reale, portal reale o consumo complessivo del desktop.

| Pacchetto finale | Intervallo | Incremento CPU | RSS iniziale/finale |
|---|---:|---:|---:|
| deb | 600,100 s | 0 tick, 0,0% | 38.676 / 38.676 KiB (37,77 MiB) |
| Flatpak | 600,100 s | 0 tick, 0,0% | 43.752 / 43.752 KiB (42,73 MiB) |

## Avvisi e scostamenti motivati

- Python 3.14: **991 warning**, tutti interni a PyGObject di sistema: 1 da
  `gi/overrides/__init__.py` (`GLib.unix_signal_add_full`), 1 da `gi/events.py:803`
  (`asyncio.AbstractEventLoopPolicy`), 989 da `gi/events.py:890` (`get_event_loop_policy`).
  Corretti i punti diretti del progetto con compatibilità `GLibUnix`,
  `register_object_with_closures2` e `GioUnix.DesktopAppInfo`; mantenuti fallback Ubuntu 24.04.
- Blueprint: `Gtk.ShortcutLabel` deprecato in `design/ui/settings-window.blp:90`.
  Il widget appartiene a Claude e non è stato cambiato.
- Lintian: zero errori dopo due override documentati, imposti da decisione 157
  (`package-installs-apt-sources`, `file-in-etc-not-marked-as-conffile`). Sei warning sui percorsi
  assoluti negli script sono intenzionali per S11; `no-manual-page` resta, CLI con `--help`
  localizzato, nessuna manpage richiesta dalla spec.
- AppStream valida; avviso pedantico sul maiuscolo dell'ID fissato `app.scambio.Scambio`.
  `desktop-file-validate` termina con successo senza output.
- `flatpak-builder --show-manifest` eseguito. `flatpak-builder-lint` non eseguito: in venv
  mancano i namespace GI nativi AppStream 1.0 e OSTree 1.0, non installabili con pip;
  nessuna installazione di pacchetti di sistema sull'host autorizzata.
  [Sonda](evidence/flatpak-lint-prerequisites.log); prerequisiti dal
  [README ufficiale](https://github.com/flathub-infra/flatpak-builder-lint#local-environment).
- Flatpak serializza `fallback-x11` con i bit `x11` e `fallback-x11`: golden sull'output effettivo
  e test separato sull'elenco letterale del manifest, senza permessi aggiuntivi.
- I limiti `[backend]` sono richiesti da §3.1.10.5, che precisa il riepilogo «nessuna chiave nuova»
  di §3.2; decisione 169c. Non è stata introdotta una funzione di prodotto diversa.
- Migrazione D1 in `packaging/site/`, richiamata da Wrangler, per rispettare i file assegnati.
- Durante remove/purge Docker, dpkg può lasciare directory Python con cache bytecode generata
  dall'esecuzione. Non è una modifica ai dati utente; i file posseduti e l'abilitazione sono rimossi.
- Ricerca: graphify query/affected/path e brain agvm-scambio in sola lettura. Per il sito manca
  un grafo, perciò sono stati letti direttamente i file noti. `git grep` è usato per la scansione
  privacy esplicitamente autorizzata da §3.1.9 e, come ultima risorsa dopo graphify senza risultati,
  per individuare i vecchi punti di chiamata alle API deprecate. Nessun altro brain usato/scritto.

## Privacy, storia e proprietà dei file

L'elenco testuale allegato distingue il perimetro modificabile dai documenti di Claude.
Gli alberi `src/`, `tests/`, `tools/`, `packaging/` e gli hook non contengono le occorrenze
personali cercate. Restano riferimenti a device/percorsi/email in overview, decisioni pregresse,
spec e misure/report precedenti. Claude decide e applica la bonifica nelle proprie aree e nella
storia; Codex non riscrive la storia. I percorsi temporanei nei log di questa misura sono evidenza.

Lo scan applica pattern per chiavi private PEM/PGP, token GitHub/OpenAI/Anthropic/AWS,
JWT, Bearer e assegnazioni di credenziali alle patch di `git log --all -p` dei due repository.
Risultato: nessun candidato. È una ricerca per pattern, non una prova matematica di assenza;
valori sospetti non vengono stampati. Chiavi pubbliche del packaging lasciate intatte.

Il primo commit obbligatorio `bbf86db` include i cinque file di design già modificati da Claude,
senza alterarne il contenuto, e aggiorna le aspettative dei test. Tutti i successivi cambi di
Codex rispettano i confini assegnati. `.gitignore` esclude graphify-out, mai aggiunto ai commit.
Tracker, contesti, guide, README, CHANGELOG, licenze e hardware-lab non sono stati modificati.

## Commit, artefatti e file toccati

Build degli artefatti da commit pulito **`f02a9a5`**.
[Dimensioni e SHA256 degli artefatti](evidence/artifacts.json). I commit successivi di sola evidenza non
cambiano il sorgente contenuto nei pacchetti. [Commit di implementazione](evidence/commits.txt).
Sito: `dfd7738` implementa Worker e frontend; `50897c7` contiene gli asset verificati.
Archivio `~/.local/share/scambio-release/archive/1.0.0/`: 226 file coperti dal manifest
firmato, file 0444 e directory 0555; verifica e ripetizione idempotente di `seal()` riuscite
([log](evidence/archive.log)). È una conservazione locale, senza pubblicazione.
Tutti i commit hanno i trailer prescritti e gli hook non sono stati aggirati.

[File main](evidence/files-main.txt), [file sito](evidence/files-site.txt). Le modifiche diffuse
in `src/`, `tests/`, `tools/` includono le intestazioni SPDX; il report e i suoi allegati sono
aggiunte sotto `docs/verification/05/`. Nessun remote richiesto, nessun push o tag.

## Richieste a Claude / domande aperte

1. Verificare e configurare Email Sending `hello@scambio.app`, poi consentire una verifica
   dell'account con credenziali adatte. Il deploy e l'invio reale restano fuori da questa sessione.
2. Consegnare le due FAQ definitive en/it/de previste da §3.3.3; controllare i titoli brevi
   “Flatpak” e “GitHub” dei blocchi Download rispetto al testo editoriale finale.
3. Fornire screenshot reali settings/tray referenziati dal metainfo; completare la verifica
   visiva dell'app e valutare la deprecazione `Gtk.ShortcutLabel` nel design.
4. Aggiornare `05-ui-context.md` col confine di fiducia D-Bus e i limiti; tracker e guide secondo
   workflow. Registrare misure reali solo dopo GM. Riscrittura storia 164/166 a cura di Claude.
5. Audit del codice e della UI, quindi prova GM A/B; Q6 GNOME resta aperta fino alla prova B.

## Bozza checklist GM §6.1 — non eseguita

Claude completa questa traccia dopo il proprio audit. Annotare data, desktop/versioni,
artefatto/hash, esito e anomalie; nessuna casella è una prova già effettuata.

- [ ] A/casa: fermare e disinstallare volontariamente il servizio di sviluppo; installare con
  doppio clic il deb scaricato dall'anteprima; verificare menu, finestra, nuovo accesso e tray.
- [ ] A: verificare stato reale, Meta+G, passaggio audio/telefono, priorità, lock/suspend;
  annotare `apt policy scambio` e unità con hardening. Non modificare altri binding.
- [ ] A: rimuovere/reinstallare, confermare conservazione config/stato; ripristinare lo sviluppo.
- [ ] B/Fedora GNOME: installare dal flatpakref, aprire dal menu, annotare dialogo e scelta
  Background, nuovo accesso e demone, finestra e GlobalShortcuts con app_id corretto (Q6).
- [ ] B: tray assente senza estensione, presente con AppIndicator; senza Bluetooth stato
  `unavailable`; nessuna misura Bluetooth inventata nella VM.
- [ ] C facoltativa: Ubuntu 24.04 GNOME, installazione e avvio deb.
- [ ] Firma GM, data ed evidenze; chiusura tracker solo dopo audit e prove richieste.

## Correzioni audit 1

Riferimento: §7 «Audit 1», commit Claude `575f7e3`; autorizzazioni aggiuntive di GM
in questa sessione per `scambio-site/migrations/` e il modello config generato dal codice.
Le sezioni precedenti documentano la prima consegna; questa sezione ne aggiorna l'esito.

| Punto | Correzione | Evidenza |
|---|---|---|
| 1 — M35 | Default e template includono `sd_dummy` e `speech-dispatcher-dummy`. Il filtro copre nome e binario, senza distinzione maiuscole/minuscole. Liste esplicite, anche vuote, preservate; il vero `speech-dispatcher` non è escluso. | 63 test mirati config/audio; test dei default anche nel Python installato dai pacchetti. [Log](audit1/audio-tests.log) |
| 2 — Debian senza systemd | `postinst` e `prerm` eseguono `systemctl --global` solo con `/usr/bin/systemctl` eseguibile. | `verify`: Ubuntu 24.04 e Debian 13, entrambi con e senza il pacchetto systemd; installazione, upgrade fittizio da 0.9.0, remove, purge e reinstallazione. Assenza del binario controllata prima e dopo il ciclo, senza stub. [Log](audit1/verify.log) |
| 3 — Migrazione autonoma | SQL invariato spostato in `scambio-site/migrations/0003_double_opt_in.sql`; tolto `migrations_dir`, quindi directory predefinita del solo sito. Test aggiornato al percorso e all'intera sequenza delle migrazioni. | Copia temporanea del solo sito, schema iniziale con una riga, `wrangler d1 migrations apply --local` applica 0002/0003; la riga resta `legacy_unconfirmed`; seconda applicazione senza operazioni. [Log](audit1/site-migrations.log) |
| 4 — Binding email | Tolto `remote = false`; aggiunto `allowed_sender_addresses = ["hello@scambio.app"]`. Worker e testi invariati. | Config verificata dal test; `wrangler dev --local` e doppio opt-in simulato en/it/de: 38 asserzioni HTTP, token scaduti/riusati, riga confermata immutabile e nessun reinvio. [Log](audit1/site-tests.log) |

La configurazione email segue la [documentazione del binding Cloudflare](https://developers.cloudflare.com/email-service/configuration/send-bindings/).
L'esecuzione locale senza binding remoti [simula le email](https://developers.cloudflare.com/email-service/local-development/sending/);
è stato usato anche `--local` esplicito. Nessun invio reale, onboarding o migrazione D1 remota.
L'onboarding dalla dashboard resta a Claude, come stabilito dall'audit.

### Ricostruzione 1.0.0 e S2

Il contenuto dei pacchetti cambia per i punti 1 e 2: sono stati ricostruiti tarball, `.deb`,
repository apt, Flatpak e staging del sito dal commit pulito **`6685c13`**.
È stato usato un checkout detached separato, perché nel checkout principale era presente la
guida non committata di Claude `docs/guide/prova-installazione-1.0.md`, lasciata intatta.
Nessun commit o spostamento di branch nel checkout di build.

Per non violare l'immutabilità è stata aggiunta l'opzione di tooling
`SCAMBIO_RELEASE_CANDIDATE=audit-1` (decisione 169n):

- nuovi output: `dist/candidates/audit-1/`;
- nuovo archivio sigillato: `~/.local/share/scambio-release/candidates/audit-1/1.0.0/`;
- archivio precedente: `~/.local/share/scambio-release/archive/1.0.0/`, **mai modificato**.

Entrambi gli archivi mantengono manifest firmato, SHA256, file 0444 e directory 0555.
Verificato l'inventario completo del vecchio archivio prima/dopo: **228 file identici**, comprese
le firme e il manifest. Il test automatico continua a rifiutare byte diversi per una versione
già sigillata, anche nelle candidate. Nessuna eccezione “force”, nessun download di vecchi
binari, nessuna fusione dei due archivi. [Verifica](audit1/archive-check.log).

Il sito locale contiene la candidata corretta. La vecchia copia in `dist/` è evidenza della
prima consegna, **non** la candidata da provare. I percorsi sopra, gli
[hash nuovi](audit1/artifacts.json) e il manifest identificano senza ambiguità gli artefatti.
Non è stata promossa o sovrascritta una release pubblicata: scelta della candidata per il
rilascio, onboarding, push/deploy e tag restano a Claude/GM.

Comandi eseguiti nel checkout pulito, con la venv di sviluppo già disponibile:

```sh
SCAMBIO_RELEASE_CANDIDATE=audit-1 make dist deb apt-repo flatpak flatpak-site
# Verifica e sigillatura con tools/verify_release.py --stage-site
```

`stage-site` esegue prima `verify`, poi sigilla solo la candidata e copia gli asset nel sito.
Il primo tentativo senza systemd ha rilevato che apt lo introduceva tramite `dbus-user-session`.
Il verificatore corretto (`5833238`) sceglie `dbus-x11` e imposta un pin negativo per systemd:
la matrice completa è poi passata. È stato eseguito con `runpy.run_path` dal main, importando
`release` dal checkout pulito `6685c13`, così `seal()` registra il vero commit sorgente degli
artefatti. Questo cambiamento riguarda solo il verificatore: nessuna seconda ricostruzione
dei pacchetti invariati. Ora gli stessi artefatti sono disponibili nel main e si verificano con
`SCAMBIO_RELEASE_CANDIDATE=audit-1 make verify`.
[Build](audit1/build.log), [verify completo](audit1/verify.log). Verificate firme, SHA256,
apt update locale/by-hash, versione installata, hardening quando systemd è presente,
conservazione dei dati utente, permessi Flatpak esatti e tre accessi D-Bus negati.

### Controlli, commit e limiti

`make check`: **804 test passati, zero saltati**, 991 avvisi esterni PyGObject già classificati.
[Output](audit1/make-check.log). I 14 test degli strumenti di release coprono anche separazione
delle candidate, identificatori invalidi e divieto di sostituire una versione sigillata.
Lintian senza errori; restano i due override, otto avvisi sui percorsi assoluti e uno
no-manpage, motivati come nella prima consegna. AppStream valida con il solo avviso pedantico sul maiuscolo dell'ID invariato.

Sono state ripetute le misure di dieci minuti dai **nuovi** pacchetti installati in venv/Flatpak
temporanei: stesso metodo e stessi limiti della prima consegna (bus privati, pactl simulato,
nessun dispositivo configurato). [deb](audit1/idle-deb.json), [Flatpak](audit1/idle-flatpak.json).
| Candidata audit-1 | Intervallo | CPU aggiuntiva | RSS iniziale/finale |
|---|---:|---:|---:|
| deb | 600,100 s | 0 tick, 0% | 38.068 / 38.068 KiB |
| Flatpak | 600,089 s | 1 tick (10 ms), 0,0017% | 43.440 / 43.440 KiB |

I valori riguardano questo scenario; M35 resta una misura di Claude, non ripetuta da Codex sul
Bluetooth reale.

Commit main: `509f5ba` (punto 1), `63a0959` (test e rimozione della migrazione dal main),
`6685c13` (punto 2, verifiche e candidate). Commit sito: `54b0ec5` (punti 3–4);
`1340c31` contiene gli artefatti corretti; `5833238` nel main corregge il solo ambiente Docker. Il commit del presente report
raccoglie le evidenze senza cambiare il contenuto dei pacchetti.

File di implementazione toccati: `src/scambio/config.py`, `tests/test_config_state.py`,
`tests/test_adapters.py`, `tests/test_release_tools.py`, `packaging/debian/postinst`,
`packaging/debian/prerm`, `tools/test_site.py`, `tools/release.py`, `tools/verify_release.py`,
`docs/decisions.md` (solo 169); SQL rimosso da `packaging/site/` e trasferito nel sito,
`wrangler.toml`, asset generati in `public/`, report e allegati sotto `docs/verification/05/`.
Nessun cambiamento Codex a design, spec, contesti, hardware-lab, guide o configurazione di GM.
[Rotte locali e hash](audit1/site-routes.log); [scan della storia di entrambi i repo](audit1/history-scan.json),
nessun candidato ai pattern di segreti controllati.

Le configurazioni già esistenti con `ignore_apps = []` continuano a escludere zero app:
la modifica dei default non sovrascrive una scelta esplicita. Per adottare il nuovo filtro su
una configurazione esistente, GM può aggiungere i due nomi alla propria lista. Codex non ha
modificato il file reale né riavviato il servizio.

Le FAQ definitive risultano consegnate da Claude in `67d950e` del sito: la precedente richiesta
nel report è superata. Restano a Claude/GM onboarding email, screenshot reali dell'app/prova B,
audit finale, prova §6.1 e operazioni di pubblicazione. Nessun push, deploy, tag o riscrittura
della storia effettuati da Codex. La guida non committata di Claude resta fuori dai nostri commit.

Ricerca: graphify per simboli e impatto nel main; nel sito il grafo non esiste, quindi lettura
diretta dei file noti. Brain consultato solo tramite agvm-scambio, senza scritture o cambio brain.
