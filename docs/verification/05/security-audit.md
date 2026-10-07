# Audit di sicurezza pre-release Linux 1.0.0

Data: 2026-10-07. Perimetro: checkout Scambio, design di packaging della spec 05,
`~/development/scambio-site` e storia Git completa di entrambi i repository. L'audit è solo
statico/dinamico locale: nessun accesso al Bluetooth reale, al bus di sessione di GM o a
`scambio.service`; nessuna scrittura di rete.

## Esito e riepilogo

**Esito: non pubblicare ancora la 1.0.0.** S1 e S2 sono rischi alti di supply chain; le correzioni
marcate «sì» vanno implementate o accettate esplicitamente da GM con una decisione prima della
pubblicazione. Non risultano vulnerabilità critiche né esecuzione di comandi tramite shell/SQL.

| ID | Gravità | Base | Area | Prima di 1.0.0 | Sintesi |
|---|---|---|---|---|---|
| S1 | alta | design + verifica locale | firma | sì | chiave di release senza passphrase, senza scadenza e unica per apt/Flatpak |
| S2 | alta | design | apt | sì | pacchetti letti dal sito possono essere rifirmati senza una catena di fiducia imposta |
| S3 | media | design | distribuzione | sì | replay/freeze apt, download `.deb` e pubblicazione statica non sufficientemente vincolati |
| S4 | media | verificata | sito/waitlist | sì | abuso, consenso non verificato, body illimitato e aggiornamento di email altrui |
| S5 | media | verificata | sito/waitlist | sì | controllo Origin aggirabile e richieste senza Origin accettate |
| S6 | media | verificata | sito/frontend | sì | JavaScript terzo senza SRI, header assenti e due sink XSS nel copy |
| S7 | bassa | verificata | D-Bus/tray | sì | ogni client autorizzato sul bus può comandare/floodare il demone e il menu |
| S8 | media | verificata | pactl/PipeWire | sì | output, JSON, eventi e numero di sottoprocessi senza limiti |
| S9 | bassa | verificata | file locali | sì | symlink, permessi e atomicità non garantiscono il confine XDG dichiarato |
| S10 | bassa | verificata | MPRIS/BlueZ/UI | sì | fan-out illimitato e stringhe esterne non normalizzate |
| S11 | media | verificata + design | installer/.deb/systemd | sì | escaping/scritture fragili oggi; script root e hardening non specificati |
| S12 | bassa | design | Flatpak | sì | permessi D-Bus necessari ma larghi a livello di servizio, senza test negativo imposto |
| S13 | bassa | verificata + design | esecuzione Python | sì | PATH/import/re-exec ed estensioni non hanno ancora un confine di fiducia imposto |
| S14 | media | verificata | storia Git/privacy | sì | indirizzi, MAC e percorsi personali resteranno nella storia pubblicata |

`Base = verificata` indica codice o comportamento osservato; `design` indica un rischio della spec
non ancora implementata. Gli scenari di design non sono presentati come exploit già presenti.

### Confini di fiducia osservati

| Canale | Chi può fornire input/comandi | Effetto sul demone |
|---|---|---|
| `app.scambio.Scambio1`, session bus | qualunque client host sullo stesso bus; Flatpak solo se il proxy gli concede il nome | tutti i metodi pubblici, proprietà inclusi MAC/nome configurati, segnali e `ListDevices` |
| dbusmenu/tray, connessione dedicata | client del session bus che scopre il nome unico tramite il watcher | apertura menu e azioni Switch/priority/settings/Quit |
| BlueZ e logind, system bus | servizi di sistema proprietari dei nomi; un utente normale non può normalmente impersonarli | inventario/alias/stato Bluetooth, Connect/Disconnect del solo device configurato, sleep/lock |
| MPRIS, Notifications, KGlobalAccel, watcher, ScreenSaver | servizi/app dello stesso utente autorizzati sul session bus | pause/resume player, azioni notifica, shortcut, tray e stato sessione |
| socket PulseAudio/PipeWire | client audio dell'utente, spesso anche sandboxati con relativo socket | snapshot/eventi pactl e routing degli stream |

Non è emerso alcun percorso `Unpair`/`RemoveDevice`; l'API agisce soltanto sul dispositivo
configurato, salvo `ListDevices`, che enumera i dispositivi audio già accoppiati.

## Problemi

### S1 — Chiave di release non protetta e senza piano di revoca — alta

- **Evidenza verificata:** la spec impone Ed25519, nessuna scadenza e nessuna passphrase
  (`docs/specs/05-packaging-e-release.md:158-173`); decisione 158 usa la stessa identità per apt e
  Flatpak (`docs/decisions.md:675-677`). `stat` ha confermato 0700 sul GNUPGHOME e 0600 sul file
  segreto; `gpg --list-packets/--show-keys` ha confermato che i due file versionati in
  `packaging/keys/` contengono solo la chiave pubblica.
- **Scenario:** malware o furto dell'account utente su `casa` copia la chiave non cifrata e firma
  aggiornamenti validi per tutti gli utenti, potenzialmente per un tempo indefinito. Il backup
  offline risolve solo la perdita, non la compromissione.
- **Correzione (spec 05):** primaria offline e certificato di revoca; sottochiavi di firma con
  scadenza/rotazione, preferibilmente su token hardware, altrimenti cifrate e sbloccate via agent;
  usare chiavi distinte per apt e Flatpak; verifica automatica del fingerprint atteso e
  procedura documentata di revoca/rotazione. **Prima della 1.0.0: sì.**

### S2 — Il repository apt può “lavare” un pacchetto ostile — alta

- **Evidenza di design:** `make apt-repo` deve leggere dal sito le versioni già pubblicate e poi
  firmare il nuovo indice (`docs/specs/05-packaging-e-release.md:121-124`), ma la spec non impone di
  autenticarle né limita versioni, nomi, hash, symlink o dimensioni.
- **Scenario:** dopo una compromissione del sito/CDN, un file con versione artificiosamente alta
  viene scaricato al rilascio successivo, incluso in `Packages` e quindi firmato legittimamente da
  `casa`; apt lo considera un aggiornamento autentico.
- **Correzione (spec 05/release tool):** non importare binari dalla rete: conservare un archivio
  locale immutabile degli artefatti pubblicati. Se il recupero è indispensabile, verificare prima
  `InRelease` con fingerprint fissato, poi ogni hash/dimensione/versione contro un manifest locale;
  rifiutare percorsi, symlink, duplicati e versioni non attese. **Prima della 1.0.0: sì.**

### S3 — Freschezza, bootstrap e atomicità dei repository statici — media

- **Evidenza di design:** la spec elenca `Release/InRelease` ma non `Date`, `Valid-Until` o
  `Acquire-By-Hash` (`docs/specs/05-packaging-e-release.md:121-124`); il `.deb` diretto è solo una
  copia (`:145-153`), il tag è annotato ma non firmato (`:173`). Le nuove rotte dipendono da
  `latest.json`, senza regole su nome/redirect/cache. Non è stato provato il deploy, quindi
  atomicità e trasformazioni Cloudflare sono ipotesi da verificare.
- **Scenario:** un mirror/CDN compromesso serve per mesi metadati vecchi ancora validamente
  firmati; oppure sostituisce il `.deb` scaricato direttamente, che `apt install ./file.deb` non
  autentica tramite `InRelease`. Un `latest.json` manomesso può diventare open redirect o path
  traversal se usato senza allowlist.
- **Correzione (spec 05 + sito):** `Date`, `Valid-Until` con procedura di rinnovo,
  `Acquire-By-Hash: yes`, solo SHA-256; staging e verifica end-to-end prima di uno switch atomico;
  asset immutabili e metadata `no-cache`, nessuna trasformazione dei byte firmati; nome/versione
  di `latest.json` con regex stretta e redirect relativo same-origin; GET/HEAD soltanto. Pubblicare
  `SHA256SUMS` firmato e firma distaccata anche per tarball/`.deb`, e firmare tag/commit di release.
  **Prima della 1.0.0: sì.**

### S4 — Waitlist abusabile e consenso non dimostrato — media

- **Evidenza verificata:** nessun rate limit, Turnstile, limite del body o verifica email in
  `../scambio-site/src/worker.js:22-47`; l'`UPSERT` aggiorna preferenze e `consent_at` di una email
  esistente (`:41-46`). `package.json:6-8` non ha test. D1 usa placeholder bindati: non è emersa SQL
  injection.
- **Scenario:** un bot riempie D1/costi con indirizzi di vittime o modifica una voce nota e rinnova
  falsamente il timestamp di consenso; al lancio le vittime ricevono posta non richiesta. Un body
  molto grande consuma memoria prima della validazione.
- **Correzione (sito):** limite stretto del body e `Content-Type: application/json`; rate limit
  Cloudflare per IP/email, cooldown e quota globale; challenge anti-bot; double opt-in con token
  monouso prima di rendere attivo il consenso; non sovrascrivere una voce verificata senza prova di
  possesso. Risposta sempre non enumerabile e test locali Worker/D1. **Prima della 1.0.0: sì.**

### S5 — Controllo Origin aggirabile — media

- **Evidenza verificata:** `origin.startsWith("http://localhost")` in
  `../scambio-site/src/worker.js:24-27` accetta, per esempio, l'origine ostile
  `http://localhost.attacker.example`; un test Node locale lo ha confermato. Origin assente è
  accettato e `request.json()` non richiede content type, quindi un POST browser “simple” in
  `text/plain` può evitare il preflight.
- **Scenario:** una pagina sotto un dominio col prefisso ammesso invia iscrizioni arbitrarie dai
  browser dei visitatori. Origin non ferma bot diretti, perciò va abbinato a S4.
- **Correzione (sito):** parsing URL e allowlist esatta di `https://scambio.app` e
  `https://www.scambio.app`; localhost solo con flag di sviluppo e host/porta esatti; in produzione
  richiedere Origin e verificare anche `Sec-Fetch-Site`; rifiutare content type diversi da JSON.
  **Prima della 1.0.0: sì.**

### S6 — Supply chain web, header e sink XSS — media

- **Evidenza verificata:** Three.js viene caricato dinamicamente da cdnjs senza SRI
  (`../scambio-site/public/index.html:1110-1122`); Google Fonts è remoto (`:15-18`). Il Worker non
  aggiunge CSP, `nosniff`, frame policy, referrer policy o permissions policy (`worker.js:15-19,58`).
  Il JSON copy è inserito letteralmente dentro `<script>` (`index.html:522`) e `consent_text` passa a
  `innerHTML` (`:562-570`). Un test locale ha mostrato che una traduzione contenente `</script>`
  chiude anticipatamente l'elemento. Il copy corrente è statico e fidato: non è stato verificato un
  XSS remoto attuale.
- **Scenario:** compromissione CDN esegue JavaScript nel dominio Scambio; oppure una futura modifica
  al copy introduce accidentalmente markup/event handler attivo. I provider dei font ricevono
  inoltre metadati dei visitatori, non menzionati chiaramente nell'informativa.
- **Correzione (sito):** vendorizzare e fissare JS/font; se resta una CDN, SRI + `crossorigin`;
  eliminare `innerHTML` per il copy (creare il link via DOM) ed eseguire escape di `<` nella
  serializzazione JSON. Imporre CSP senza `unsafe-inline` tramite file JS/CSS o nonce/hash,
  `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'none'`, `nosniff`, referrer/permissions
  policy e HSTS; test con payload malevoli. **Prima della 1.0.0: sì.**

### S7 — Superficie D-Bus e tray senza controllo d'abuso — bassa

- **Evidenza verificata:** `_method` non usa `sender` e consente Switch, SetPriority, Quit, Reload,
  RetryShortcut, ListDevices e SetConfig (`src/scambio/core/service.py:450-512`). `ListDevices`
  restituisce alias/MAC dei dispositivi audio accoppiati (`src/scambio/core/bluez.py:164-181`). Il
  menu esportato accetta Event/EventGroup e attiva azioni, incluso Quit, senza controllo del mittente
  o limite dell'array (`src/scambio/ui/tray.py:247-338`). SetPriority/Switch causa un `fsync` dello
  stato anche se ripetuto (`src/scambio/core/policy.py:196-208`, `service.py:369-374`).
- **Scenario:** un processo con accesso al bus di sessione fa thrashing Bluetooth, modifica la
  configurazione, enumera dispositivi, termina il demone o genera scritture e callback senza limite.
  Su un desktop monoutente un processo host ha già lo stesso UID e può uccidere/modificare i file;
  un Flatpak estraneo è normalmente filtrato dal proxy D-Bus. Per questo la gravità non è alta e il
  bus va documentato come confine di fiducia, non come autenticazione.
- **Correzione (codice + spec):** rate limit per sender e globale, una sola operazione/invocazione
  lunga per tipo, cap su dizionari/array e EventGroup, coalescing delle scritture uguali, timeout e
  cancellazione alla scomparsa del sender. Documentare metodi/proprietà e dati visibili; non
  concedere `--talk-name=app.scambio.Scambio` ad app terze. **Prima della 1.0.0: sì.**

### S8 — Dati pactl/PipeWire senza limiti — media

- **Evidenza verificata:** `communicate_utf8_async` accumula tutto stdout
  (`src/scambio/core/audio.py:123-158`); il buffer del subscribe non ha cap (`:21-56`) e una prova
  locale ha mantenuto 1.048.582 byte di JSON parziale. Snapshot e liste sono caricati integralmente
  (`:257-317`); ogni stream può generare un `move-sink-input` (`:422-445`). Un flusso continuo di
  eventi riprogramma sempre il debounce (`:245-255`), rimandando indefinitamente il refresh.
  `spawnv` usa argv separati: nomi/indici non diventano shell injection.
- **Scenario:** un client PulseAudio/PipeWire non fidato crea moltissimi stream/proprietà o un
  subscribe patologico, causando crescita di memoria, storm di processi, CPU o stato audio fermo.
  L'accesso al socket Pulse è comune anche per app sandboxate.
- **Correzione (codice):** massimi configurabili per byte, record, profondità/lunghezze e comandi;
  lettura streaming con terminazione del figlio oltre soglia; validazione strutturale prima dell'uso;
  coda/fan-out limitati e debounce con latenza massima (event-driven, non polling); backoff dopo
  violazioni. **Prima della 1.0.0: sì.**

### S9 — Scritture locali non confinate in presenza di symlink — bassa

- **Evidenza verificata:** la creazione iniziale di config usa umask e segue i componenti symlink
  (`src/scambio/config.py:158-175`). `ConfigEdit.write()` risolve e segue esplicitamente il symlink,
  separa read/stat/write e non fsynca la directory (`:365-410`); il test attuale richiede proprio di
  preservare il target del symlink. `state.json` ha temp 0600 e replace atomico, ma segue una directory
  parent symlink, non fsynca la directory e legge senza size cap (`src/scambio/state.py:66-111`).
- **Scenario:** un altro processo dello stesso UID cambia symlink tra i passi o fa uscire la
  destinazione dagli alberi XDG; un client D-Bus sandboxato con accesso al servizio può sfruttare il
  demone come writer solo se riesce anche a predisporre quel path. L'impatto è limitato dallo stesso
  UID, ma viola l'invariante “non scrive fuori” e riduce la durabilità dopo crash.
- **Correzione (codice):** directory 0700 e file 0600; rifiutare symlink e componenti non posseduti
  usando `lstat`/`openat` + `O_NOFOLLOW` e verifica inode, oppure registrare esplicitamente una diversa
  decisione di prodotto; cap di dimensione; temp nello stesso parent, `fsync` file, replace e `fsync`
  directory. **Prima della 1.0.0: sì.**

### S10 — Fan-out MPRIS e testo esterno non normalizzato — bassa

- **Evidenza verificata:** ogni nome MPRIS scoperto genera letture/chiamate concorrenti senza cap e
  ogni pausa riuscita salva lo stato (`src/scambio/core/players.py:219-298`). BlueZ inoltra Alias
  senza cap/normalizzazione (`src/scambio/core/bluez.py:108-122,164-181`). Tooltip e body notifica
  sono correttamente escapati (`src/scambio/ui/presentation.py:307-371`,
  `src/scambio/ui/notify.py:143-151`); l'XML GTK è serializzato con ElementTree
  (`src/scambio/ui/window.py:54-67`). Non sono emersi `set_markup` o input usato come URI: le URI
  aperte sono fisse (`window.py:210-226`, `notify.py:250-257`).
- **Scenario:** un processo registra molti player MPRIS e moltiplica D-Bus/fsync; un alias con escape,
  newline o caratteri bidi falsifica visivamente notifica/menu/log o l'output raw di `scambio status`
  (`src/scambio/cli.py:86-100`). Non è stata verificata esecuzione di markup Pango.
- **Correzione (codice):** cap e concorrenza limitata per player, un solo salvataggio batch; limite
  di lunghezza e rimozione C0/C1 per testi UI/log, gestione bidi esplicita, mantenendo l'escaping
  contestuale. **Prima della 1.0.0: sì.**

### S11 — Installer fragile e requisiti insufficienti per script root/systemd — media

- **Evidenza verificata:** l'installer developer segue symlink, scrive non atomicamente e invoca
  `systemctl` via PATH (`tools/install_user.py:69-95`). L'escaping systemd/D-Bus non rifiuta newline
  nel path (`:8-18,56-65`); il desktop tratta invece CR/LF/tab (`:21-53`). L'unità corrente non ha
  direttive di hardening (`packaging/systemd/scambio.service:1-15`). Gli script `.deb` sono solo
  descritti (`docs/specs/05-packaging-e-release.md:118-120`), quindi il rischio root è di design.
- **Scenario:** un checkout con newline inietta una direttiva nel file generato; un symlink locale
  devia una scrittura. Più importante, un futuro maintainer script eseguito da root potrebbe usare
  PATH/variabili/home o rete in modo non previsto. Non esiste oggi tale exploit nel `.deb`, perché il
  pacchetto non è implementato.
- **Correzione (codice + spec 05):** rifiuto di CR/LF/NUL, renderer strutturato, scritture atomiche
  no-follow e binari assoluti. Maintainer script `set -eu`, idempotenti, solo path package-owned,
  senza rete, input utente, HOME o `systemctl --user`; usare helper Debian e non avviare il servizio.
  Provare in container install/upgrade/remove/purge. Aggiungere e testare un set compatibile di
  `NoNewPrivileges`, protezioni filesystem/home con sole directory Scambio scrivibili,
  `PrivateTmp`, `RestrictSUIDSGID` e limiti risorse. **Prima della 1.0.0: sì.**

### S12 — Permessi Flatpak larghi a livello di nome D-Bus — bassa

- **Evidenza di design:** decisione 153 concede talk all'intero `org.bluez`, `login1`, wildcard MPRIS,
  KGlobalAccel, watcher, Notifications e ScreenSaver (`docs/decisions.md:643-650`); la spec richiede
  esattamente tali permessi (`docs/specs/05-packaging-e-release.md:126-141`). Sono coerenti con le
  misure M30–M34 e non risultano filesystem, session-bus/system-bus completi o own-name aggiuntivi.
- **Scenario:** se il processo Scambio viene compromesso, il proxy consente potenzialmente metodi
  del servizio oltre a quelli usati dal programma; il manifest Flatpak filtra per nome, non per
  singolo metodo. È riduzione di sandbox, non un bypass già verificato.
- **Correzione (spec 05):** allowlist letterale e divieto esplicito di `--socket=session-bus`,
  `--socket=system-bus`, filesystem e nomi ulteriori; `flatpak info --show-permissions` come golden
  test e prove negative verso UPower/systemd/altri nomi, oltre alle positive M30–M34. Riesaminare ogni
  permesso a ogni release. La richiesta portal Background deve essere idempotente, gestire il rifiuto
  senza retry storm e non ricevere comandi/URI variabili. **Prima della 1.0.0: sì
  (verifica/accettazione del rischio).**

### S13 — PATH, import Python, re-exec ed estensioni — bassa

- **Evidenza verificata:** il demone lancia `pactl` per nome (`src/scambio/core/service.py:691-712`)
  e l'installer `systemctl` per nome; non usa shell. `pyproject.toml:5-21` non ha dipendenze runtime e
  nel codice corrente non sono emersi import dinamici né caricamento di `scambio.extensions`.
  L'estensione è futura; anche il re-exec non è ancora implementato (decisione 155).
- **Scenario:** ambiente systemd/PYTHONPATH/user-site alterato fa caricare un modulo o eseguibile
  inatteso; un entry point di terzi diventa esecuzione di codice nel demone. È stesso UID, ma compromette
  integrità e persistenza dell'app.
- **Correzione (codice + spec 05):** entry point assoluto e interprete isolato (`python3 -I` o
  equivalente verificato), ambiente/PATH minimo e `/usr/bin/pactl`; re-exec solo dell'eseguibile
  assoluto già avviato, argv costruito senza shell, dopo rilascio bus/risorse e flush dello stato.
  Caricare estensioni solo da origini esplicitamente fidate, con API/versione verificata e failure
  isolation; nessun discovery implicito dal user-site per il pacchetto di sistema. **Prima della
  1.0.0: sì.**

### S14 — Dati personali nella storia che verrà pubblicata — media

- **Evidenza verificata:** `git log -p --all` ha coperto 75 commit Scambio e 3 commit sito. Tutti gli
  autori usano l'indirizzo personale `ferr…`; la storia contiene un MAC reale `80:A…` (tra gli altri,
  commit `2824948`, `7a22ab`), percorsi personali `/hom…` in report storici e l'indirizzo di inoltro
  `gian…` in decisioni. Nel tree corrente restano inoltre il path personale negli hook
  (`.githooks/post-commit:59`, `post-checkout:63`), il MAC fuori dal solo hardware lab
  (`docs/specs/01-demone-headless.md:496`) e l'inoltro (`docs/decisions.md:612,696`). Nel sito i dati
  societari e `privacy@…` sono pubblicazione intenzionale dell'informativa.
- **Scenario:** il primo push rende permanenti e indicizzabili identità privata, identificatore
  hardware e layout locale. Pulire solo il tree non li rimuove dalla storia che la spec vuole
  pubblicare integralmente.
- **Correzione (repo/spec 05, proprietà Claude/GM):** prima del primo push decidere cosa è davvero
  pubblico; riscrivere autore **e** blob storici per MAC, inoltro e path non necessari, poi ricreare
  tag e rieseguire la scansione. Le misure che GM decide di lasciare pubbliche vanno elencate come
  accettazione consapevole. Rimuovere comunque il path hardcoded dagli hook. **Prima della 1.0.0:
  sì.**

## Controlli con esito positivo

- `SetConfig` accetta solo cinque chiavi e tipi D-Bus esatti (`service.py:491-507`); il parser valida
  MAC, profilo, enum, booleani e range numerici (`config.py:178-267`). Restano i limiti di volume di
  S7/S9, non una type confusion osservata.
- Le chiamate `pactl` usano `Gio.SubprocessLauncher.spawnv` con argv separati; non sono emersi
  `shell=True`, `os.system`, `eval` o interpolazioni di comandi. Nomi sink e indici non diventano
  opzioni shell.
- SQL D1 usa statement preparato e `.bind`; nessun valore utente viene concatenato alla query.
- Il sorgente apt previsto usa deb822 con `Signed-By` verso un keyring package-owned
  (`docs/specs/05-packaging-e-release.md:107-111`); non usa `apt-key` né modifica la sorgente nel
  `postinst`.
- Tooltip e body notifica sono escapati; i widget GTK ricevono testo/proprietà e l'XML tradotto viene
  serializzato. Le sole aperture osservate sono il file config e la URI fissa
  `systemsettings://kcm_keys/app.scambio.Scambio`.
- Nessun `Unpair`/`RemoveDevice`, nessuna telemetria/rete nel demone e nessun import premium sono
  emersi dalla ricerca.
- Scansione completa delle patch Git con pattern per private-key header, token GitHub/OpenAI/
  Anthropic/AWS, JWT, bearer, password/secret e `.env`: **nessun segreto candidato** nei due repo.
  Gli unici file dal nome “key” sono le chiavi pubbliche apt, confermate tali. Questa è evidenza a
  pattern, non garanzia matematica di assenza.

## Metodo, prove e limiti

- Letti nell'ordine prescritto `AGENTS.md`, contesti 01–06, `hardware-lab.md` e spec 05; per il
  contesto è stato usato soltanto MCP `agvm-scambio` sul brain read-only `scambio_brain` e ogni fatto
  è stato verificato nel repo.
- Codice/documenti cercati prima con `graphify query/path/affected`. Nel repo sito Graphify ha
  risposto `graph file not found`; lì sono stati letti direttamente i file. `git grep`/grep è stato
  usato dichiaratamente come controllo testuale di sicurezza per sink, subprocess, markup, segreti e
  dati personali, e per la storia, dopo Graphify o dove il grafo non era disponibile.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/pytest -q`:
  **727 passati, 4 falliti, 0 saltati, 936 warning**. I quattro fallimenti sono tutti dovuti ai file
  `design/i18n/*` e layout/cataloghi compilati già non allineati nel worktree; i test D-Bus e adapter
  di sicurezza sono passati su bus/display privati. Nessun test ha usato il bus reale di GM.
- `make check` non è stato lanciato perché rigenera artefatti UI/locale nel workspace e avrebbe
  violato il vincolo “nessun file salvo il report”. Nessun `npm audit` o deploy: richiederebbe rete o
  tool non predisposti. Nessun container è stato necessario per confermare i finding; le prove di
  pacchetto restano obbligatorie dopo l'implementazione.
- Prove isolate: il controllo Origin ha accettato `http://localhost.attacker.example`; JSONStream ha
  trattenuto 1.048.582 byte incompleti; una stringa copy con `</script>` ha prodotto una chiusura
  anticipata. Sono test di proprietà locali, non traffico verso il sito pubblico.

## Correzioni da aggiungere alla spec 05

1. Politica della chiave: primaria offline, revoca, sottochiavi cifrate/hardware con scadenza,
   rotazione e chiavi distinte per apt/Flatpak.
2. Divieto di rifirmare artefatti recuperati dal sito senza verifica `InRelease` + manifest locale;
   preferire archivio locale immutabile.
3. `Date`, `Valid-Until`, `Acquire-By-Hash`, soli hash SHA-256, staging atomico e verifica byte/hash
   dopo la copia negli asset Cloudflare.
4. Firma di tag/commit e di `SHA256SUMS`; verifica documentata del `.deb` scaricato direttamente.
5. Contratto sicuro per `latest.json`: schema/nome/versione stretti, redirect relativo same-origin,
   GET/HEAD soltanto, cache e MIME espliciti.
6. Waitlist con body/content-type limitati, rate limit/quota/challenge, double opt-in e update solo con
   prova di possesso; test Worker/D1 obbligatori.
7. Asset web vendorizzati o SRI, CSP e security header; nessun `innerHTML` da copy e JSON sicuro per
   embedding HTML.
8. Budget di risorse configurabili per D-Bus/tray, pactl/PipeWire, MPRIS e stringhe esterne; debounce
   con latenza massima senza introdurre polling.
9. Contratto filesystem: directory 0700, file 0600, niente symlink/TOCTOU, size cap, replace atomico e
   fsync della directory negli alberi XDG.
10. Maintainer script root minimali/idempotenti/offline, niente HOME o servizio utente reale, binari
    assoluti; matrice container install/upgrade/remove/purge e unità systemd hardenizzata verificata.
11. Golden test e test negativi dei permessi Flatpak; divieto esplicito di bus/filesystem/own-name
    ulteriori.
12. PATH/ambiente/import isolati, `pactl` assoluto, re-exec sicuro ed estensioni solo da origini
    fidate con API versionata.
13. Gate pre-push che riesegue scansione segreti/dati personali sulla storia riscritta di entrambi i
    repository e registra le sole eccezioni approvate da GM.
