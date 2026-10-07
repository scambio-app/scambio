# Spec 05 — Packaging e prima release pubblica (Linux 1.0.0)

Stato: approvata (GM, 2026-10-07, dopo l'audit di sicurezza e le decisioni 166–168) · Autore: Claude (chat di rilascio) · Data: 2026-10-07

## 1. Obiettivo

Scambio diventa installabile da chiunque, senza checkout né venv, e il codice diventa pubblico
sotto GPL-3.0 con CLA.

**Prova visibile.** Su un Ubuntu 24.04+ o Debian 13+ pulito l'utente scarica `scambio_1.0.0_all.deb`
da scambio.app, lo apre con un doppio clic, e dopo l'installazione: Scambio è nel menu, al prossimo
accesso parte da solo (icona nel tray), e da quel momento `sudo apt update && sudo apt upgrade`
porta le nuove versioni. Su qualunque altra distro con Flatpak (prova: VM Fedora con GNOME) l'utente
clicca «Install» sul file `.flatpakref` o lancia
`flatpak install https://scambio.app/flatpak/scambio.flatpakref`: Scambio parte, chiede al desktop di
avviarsi al login e funziona come su casa. Su GitHub c'è il repository pubblico con README inglese,
screenshot reali, LICENSE, CLA, CHANGELOG e la release 1.0.0 con i file allegati. La pagina
scambio.app dice «Linux: available» e porta ai download.

## 2. Decisioni applicabili

- Prodotto: 2–3 e 122 (Linux gratuito), 17 (nome D-Bus e app-id `app.scambio.Scambio`), 48 (avvio
  al login), 106 (cosa installa `make install-user`), 131 (titolare Fermich), 134 (Flathub, Meta
  solo «Works with», disclaimer), 137 (GPL-3.0 + CLA), 138 (niente ® né ™), 139–140 (scambio.app).
- Di questa spec: **150–168** (150–152, 160–167 di GM; 153–159 e 168 di Claude) e la **169** di Codex (una sola voce con sottopunti per le sue scelte tecniche).
- Misure: **M30–M34** (Flatpak), M17 (tray nascosto), M20 (portal su Plasma 6), M21 (tray Plasma 6).

## 3. Dettagli

### 3.1 Comportamento

#### 3.1.1 Percorsi e versione (decisione 156)

1. `paths.py` distingue due casi: **checkout** (esiste `ROOT/pyproject.toml` accanto a `src/`) →
   comportamento di oggi; **installato** → dati in `<prefix>/share/scambio/` (`design/` copiata così
   com'è, `locale/` con i `.mo`, `ui/settings-window.ui`), dove `<prefix>` è il primo fra `/app`,
   `sys.prefix` e `/usr` che contiene `share/scambio` (nel Flatpak Python ha `sys.prefix=/usr` ma i
   dati sono in `/app`). Nuova variabile `SCAMBIO_DATA_DIR` che la sostituisce; `SCAMBIO_DESIGN_DIR` e
   `SCAMBIO_LOCALE_DIR` restano (test). Nessun percorso assoluto di casa nel pacchetto.
2. Configurazione in `GLib.get_user_config_dir()/scambio/config.toml`, stato in
   `GLib.get_user_data_dir()/scambio/state.json`. Sull'host i percorsi non cambiano; nessuna
   migrazione.
3. Versione unica: `pyproject.toml` → `1.0.0`; `Version` dell'API e `scambio --version` la leggono da
   `importlib.metadata` (riserva: la costante generata in build). Nessun'altra copia del numero, a
   parte metainfo e CHANGELOG che la riportano (un test le confronta).

#### 3.1.2 Avvio, attivazione e riavvio (decisione 155)

1. File di attivazione D-Bus del demone `app.scambio.Scambio.service` in tutti i formati:
   `Exec=<bindir>/scambio daemon`; nel `.deb` anche `SystemdService=scambio.service`.
2. Il servizio utente systemd del `.deb` (`/usr/lib/systemd/user/scambio.service`, `ExecStart=/usr/bin/scambio daemon`,
   `Type=dbus`) è **abilitato per tutti gli utenti** dal pacchetto (preset o `deb-systemd-helper --user`/
   `systemctl --global enable`, scelta di Codex); l'installazione non lo **avvia** nelle sessioni già
   aperte (parte al prossimo accesso o all'apertura della finestra, punto 3). La rimozione lo
   disabilita.
3. La finestra, all'avvio dal menu, se il demone non c'è lo attiva con
   `org.freedesktop.DBus.StartServiceByName("app.scambio.Scambio")`; «Avvia» del banner (spec 04) fa
   lo stesso al posto di `StartUnit`. Il banner con «Avvia» resta per il caso in cui il demone si ferma
   a finestra aperta.
4. Nel Flatpak (presenza di `/.flatpak-info`) il demone, a ogni avvio, chiede al portal Background
   `RequestBackground` con `autostart=true`, `commandline=["scambio","daemon"]`,
   `dbus-activatable=false` e il motivo dalla chiave di testo `background-reason` (it/en/de). Una
   risposta negativa si registra nel log (una riga) e non si ripete nella stessa esecuzione; nessuna
   notifica. Fuori dal Flatpak il portal non si chiama.
5. Cambio di dispositivo (decisione 105): se il demone gira sotto systemd (cgroup come oggi) resta
   `RestartUnit`; altrimenti, dopo l'arresto ordinato di oggi (ripresa player, stato salvato), il
   processo si ri-esegue con gli stessi argomenti (`os.execv`). Nessun accesso a systemd dal Flatpak.
6. Due installazioni contemporanee (`.deb` + Flatpak, o pacchetto + `make install-user`): il secondo
   demone non ottiene il nome, scrive una riga chiara («Scambio è già in esecuzione da un'altra
   installazione») ed esce con codice ≠ 0 senza toccare il dispositivo. `make install-user` avvisa e
   si ferma se trova `/usr/bin/scambio` o l'app Flatpak installata (opzione `--force` per sviluppo).

#### 3.1.3 Tray senza nome ben noto (decisione 154, M33)

1. Il tray apre una **propria connessione** al bus di sessione, vi esporta `/StatusNotifierItem` e
   `/MenuBar` e si registra con `RegisterStatusNotifierItem("/StatusNotifierItem")`. Non possiede più
   `org.kde.StatusNotifierItem-<pid>-1`.
2. `ui.tray = false` chiude quella connessione (l'icona sparisce, come M17); `true` ne apre una nuova
   e si registra di nuovo; il riavvio del watcher (M21) continua a funzionare.
3. `IconThemePath`: la cartella delle icone dei dati (§3.1.1); nel Flatpak tradotta nel percorso
   dell'host sostituendo il prefisso `/app` con `app-path` letto da `/.flatpak-info`.
4. Il contratto di `05-ui-context.md` §5.3 cambia solo nel nome del servizio: Claude lo aggiorna.

#### 3.1.3b Installazione generica `make install`

`make install PREFIX=/usr DESTDIR=…` (e `make uninstall`) installa **tutto** ciò che serve a un
pacchetto sotto `$(DESTDIR)$(PREFIX)`: modulo Python (`pip install --no-deps --no-build-isolation
--prefix`, senza rete), `bin/scambio`, `share/scambio/` con `.mo` e `.ui` compilati, desktop, metainfo,
icone, servizi D-Bus (Exec con `$(PREFIX)/bin/scambio`), licenza in `share/licenses/scambio/`;
`SYSTEMD_USER_UNIT=1` aggiunge `lib/systemd/user/scambio.service`. Il `.deb` e il manifest Flatpak
del repository proprio usano **solo** questo target, così anche il manifest Flathub di GM resta un
modulo di poche righe (`make install PREFIX=/app`). Richiede solo Python, gettext e
blueprint-compiler; niente rete durante la build.

#### 3.1.4 Pacchetto `.deb` e repository apt (decisioni 151, 157, 158)

1. `make deb` produce `dist/scambio_<versione>_all.deb` con `dpkg-deb` (niente debhelper
   obbligatorio), costruito da un albero pulito (`git archive` del commit corrente). Contenuto:
   - `/usr/bin/scambio`; il pacchetto Python in `/usr/lib/python3/dist-packages/scambio/`;
   - `/usr/share/scambio/` (§3.1.1), compilando `.mo` e `.ui` in build;
   - `/usr/share/applications/app.scambio.Scambio.desktop` (da `design/desktop/`, con
     `Exec=scambio settings`, `Icon=app.scambio.Scambio`);
   - `/usr/share/metainfo/app.scambio.Scambio.metainfo.xml` (da `design/metainfo/`);
   - icone in `/usr/share/icons/hicolor/` (app scalabile e simbolica, più le icone di stato);
   - `/usr/share/dbus-1/services/app.scambio.Scambio.service` e `…Scambio.Settings.service`;
   - `/usr/lib/systemd/user/scambio.service`;
   - `/etc/apt/sources.list.d/scambio.sources` (deb822: `Types: deb`, `URIs: https://scambio.app/apt`,
     `Suites: stable`, `Components: main`, `Architectures: all`,
     `Signed-By: /usr/share/keyrings/scambio-archive-keyring.gpg`) e la chiave pubblica binaria in
     `/usr/share/keyrings/scambio-archive-keyring.gpg`. Il file delle sorgenti **non** è un conffile
     (la rimozione del pacchetto lo toglie);
   - `/usr/share/doc/scambio/copyright` (formato DEP-5, GPL-3.0-or-later, © Fermich srl) e changelog
     Debian compresso.
2. `Depends`: `python3 (>= 3.11)`, `python3-gi (>= 3.42)`, `gir1.2-glib-2.0`, `gir1.2-gtk-4.0`,
   `gir1.2-adw-1 (>= 1.4)`, `pulseaudio-utils (>= 16)`; `Recommends`: `bluez`, `xdg-desktop-portal`.
   `Section: sound`, `Priority: optional`, `Maintainer: Fermich srl <hello@scambio.app>` (dec. 163),
   `Homepage: https://scambio.app`.
3. `postinst` / `prerm` / `postrm`: solo abilitazione/disabilitazione del servizio utente (§3.1.2),
   aggiornamento della cache delle icone se presente; nessun'altra azione, nessun avvio.
4. `lintian` senza errori (gli avvisi rimasti motivati nel report).
5. `make apt-repo` costruisce da `dist/*.deb` il repository statico in `dist/site/apt/`
   (`pool/main/s/scambio/`, `dists/stable/{Release,InRelease,Release.gpg}`,
   `dists/stable/main/binary-all/Packages{,.gz}`) con `apt-ftparchive` e firma con la chiave di
   §3.1.7. Mantiene le versioni precedenti già pubblicate (le legge dal sito, non le cancella).

#### 3.1.5 Flatpak e repository Flatpak (decisioni 151, 153, M30–M34)

1. `packaging/flatpak/app.scambio.Scambio.yml` (manifest **del repository proprio**, scritto da
   Codex; non è il manifest Flathub e GM non lo copia, decisione 159): runtime
   `org.gnome.Platform`/`org.gnome.Sdk` 51, `command: scambio`, permessi **esattamente** quelli della
   decisione 153, un solo modulo che installa come §3.1.4 sotto `/app` (dati, desktop, metainfo,
   icone, servizi D-Bus del demone e della finestra, licenza in `/app/share/licenses/app.scambio.Scambio/`),
   sorgente = archivio del commit (`git archive`) con sha256.
2. `make flatpak` costruisce con `flatpak-builder` nel repository OSTree locale `dist/flatpak-repo`
   firmato (`--gpg-sign`), con `flatpak build-update-repo --generate-static-deltas --prune`;
   `make flatpak-site` lo copia in `dist/site/flatpak/repo/` e genera:
   - `dist/site/flatpak/scambio.flatpakrepo` (Title, Url, Homepage, GPGKey in base64);
   - `dist/site/flatpak/scambio.flatpakref` (Name, Branch `stable`, Url, `RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo`, GPGKey, IsRuntime=false).
   Branch del ramo pubblico: `stable`.
3. `flatpak-builder --show-manifest`/lint (`flatpak-builder-lint manifest` e `repo` se installabile
   in venv; altrimenti motivato nel report) e `appstreamcli validate --pedantic` sul metainfo.

#### 3.1.6 Pagina scambio.app (repository `~/development/scambio-site`, decisioni 139–140)

1. Il Worker serve `dist/site/apt/**` e `dist/site/flatpak/**` copiati in `public/apt/` e
   `public/flatpak/` (asset statici; `run_worker_first` lascia passare tutto ciò che non è
   `/api/waitlist`). Tipi: `.flatpakref` → `application/vnd.flatpak.ref`, `.flatpakrepo` →
   `application/vnd.flatpak.repo`, `.deb` → `application/vnd.debian.binary-package`; `summary`,
   `InRelease`, `Release*`, `Packages*`, `*.flatpakre*` con `Cache-Control: no-cache`.
2. `public/scambio_<versione>_all.deb` (copia del `.deb` corrente) e un indirizzo stabile
   `/download/scambio.deb` che il Worker reindirizza (302) alla versione corrente, letta da un file
   `public/download/latest.json` generato da `make flatpak-site`/`apt-repo`; e
   `public/.well-known/` pronto per il file di verifica Flathub (lo aggiunge GM più avanti).
3. Testi della pagina: **solo quelli di §3.3.3**, nelle tre lingue, nello stesso JSON `copy`; stile e
   struttura della pagina invariati salvo la nuova sezione «Download» descritta lì.
4. Il deploy (`wrangler deploy`) **non** lo fa Codex: lo fa Claude dopo il sì di GM.

#### 3.1.7 Firma e strumenti di release (decisione 158)

1. `tools/release.py` (o target del Makefile) con i passi: `check` (albero pulito, tag assente,
   versione coerente in pyproject/metainfo/CHANGELOG), `dist` (tarball sorgente
   `dist/scambio-<versione>.tar.gz` da `git archive` + `SHA256SUMS`), `deb`, `apt-repo`, `flatpak`,
   `flatpak-site`, `verify` (installazione del `.deb` in un contenitore Docker `ubuntu:24.04` e
   `debian:13` con `apt install ./scambio_*.deb` e `scambio --version`; `flatpak install` dal repo
   locale in `--user` di un'installazione Flatpak temporanea, `flatpak run --command=scambio
   app.scambio.Scambio --version`). Nessun passo pubblica nulla, fa push o tocca la rete in scrittura.
2. Chiave (decisioni 158 e 168a, creata da Claude): keyring GnuPG in
   `~/.local/share/scambio-release/gnupg` (700); primaria `24A30DBED8973273A486CC7386C8855E1251E7E2`
   tenuta offline, sottochiave di firma `4C23A6729A5750DDFC8745E305499CD6ECB01DE7` (scade
   2028-10-06). Pubblica in `packaging/keys/scambio-archive-keyring.gpg` e `.asc` (file di Claude). Gli
   strumenti usano `SCAMBIO_GNUPGHOME`, firmano **sempre** con `--local-user` sulla sottochiave e
   verificano prima l'impronta attesa (costante nel codice, confrontata con il keyring del pacchetto);
   se non corrisponde o la sottochiave scade entro 90 giorni, si fermano con un messaggio chiaro.
3. Il tag `v1.0.0` (annotato, non firmato) lo crea Claude dopo la prova di GM.

#### 3.1.10 Correzioni dell'audit di sicurezza (decisione 168)

Riferimenti: `docs/verification/05/security-audit.md`. Ogni punto ha test o evidenza nel report.

1. **S2 — archivio immutabile**: gli artefatti pubblicati (`.deb`, tarball, firme, commit del repo
   OSTree) si conservano in `~/.local/share/scambio-release/archive/<versione>/` (mai sovrascritti,
   SHA256 in un manifest locale firmato). `make apt-repo` e `make flatpak-site` costruiscono **solo**
   da quell'archivio + la versione nuova; non scaricano mai binari dal sito. Il punto 5 di §3.1.4 è
   sostituito da questo.
2. **S3 — repository**: `Release` con `Date`, `Acquire-By-Hash: yes`, soli SHA256 (niente MD5/SHA1),
   **senza** `Valid-Until` (168b); `dists/stable/main/binary-all/by-hash/SHA256/…`. `SHA256SUMS` della
   release firmato (`SHA256SUMS.asc`) e firme distaccate `.asc` per `.deb` e tarball. Il README spiega
   come verificare il `.deb` scaricato a mano (Claude). `latest.json`: schema
   `{"version":"X.Y.Z","deb":"scambio_X.Y.Z_all.deb","sha256":"…"}` con regex stretta; il Worker fa
   redirect **relativo** solo verso un nome che rispetta la regex, solo GET/HEAD.
   Pubblicazione: `dist/site/` si prepara completa, si verifica (firme, hash, `apt update` in
   contenitore che punta a un server HTTP locale su quella cartella) e solo dopo si copia in
   `public/`.
3. **S4/S5/S6/167 — sito** (`~/development/scambio-site`):
   - `POST /api/waitlist`: solo `Content-Type: application/json`, corpo ≤ 4 KiB, `Origin` obbligatorio e
     uguale **esattamente** a `https://scambio.app` (o `http://localhost:8787` solo con la variabile di
     sviluppo), `Sec-Fetch-Site` `same-origin` se presente; rate limit con il binding Cloudflare
     `ratelimit` (per IP: 5/minuto; globale: quota giornaliera configurabile) e risposte non
     enumerabili.
   - **Doppio opt-in**: nuova tabella o colonne `status` (`pending`/`confirmed`), `token_hash`
     (SHA-256 di un token casuale da 32 byte), `token_expires` (48 h), `confirmed_at`, `ip_hash` facoltativo.
     L'iscrizione crea/aggiorna solo una voce `pending` e invia l'email di conferma
     (`GET /api/confirm?t=…` → pagina di conferma statica nelle tre lingue); una voce `confirmed` **non**
     si modifica da un nuovo POST (risposta identica, nessuna email). Email inviata dal binding Cloudflare
     Email Sending (`send_email`) da `hello@scambio.app`, testo semplice in en/it/de (testi di §3.3.4).
     Se il binding non è disponibile sull'account, fermati e scrivilo nel report: lo configura Claude.
     Migrazione D1 nuova; le voci esistenti diventano `legacy_unconfirmed` (non si cancellano).
   - Header su tutte le risposte: CSP senza `unsafe-inline` per gli script (`script-src 'self'`,
     `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`, `form-action 'self'`),
     `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
     `Permissions-Policy` restrittiva, `Strict-Transport-Security: max-age=31536000`. Gli script e lo
     stile inline della pagina passano in file statici (`/app.js`, `/app.css`); Three.js e i font
     **vendorizzati** in `public/vendor/` con versione fissata e licenze; nessuna richiesta a CDN
     esterni. Il JSON dei testi diventa `public/copy.json` (fetch) e nessun testo va in `innerHTML`
     (link del consenso costruito via DOM). Aspetto della pagina invariato (screenshot prima/dopo nel
     report).
   - Test Worker con `vitest` + `@cloudflare/vitest-pool-workers` (o `wrangler dev` + script) per:
     origin, content type, dimensione, rate limit, doppio opt-in, token scaduto/riusato, voce
     confermata non modificabile, header.
4. **S7 — API D-Bus**: limiti su dimensioni di array/dizionari in ingresso (`SetConfig`,
   `EventGroup` del menu ≤ 32 voci), `SetPriority` uguale allo stato attuale non scrive
   `state.json`; documentare in `05-ui-context.md` (Claude) che il bus di sessione è il confine di fiducia.
5. **S8 — pactl**: limiti configurabili in `[backend]` con default prudenti (output di uno snapshot
   ≤ 4 MiB, riga di subscribe ≤ 64 KiB, ≤ 256 stream spostati per evento, ≤ 4 sottoprocessi `pactl`
   contemporanei oltre al subscribe); oltre soglia il figlio si termina, si registra una riga di log e si
   riprova con backoff; debounce con **latenza massima** (un refresh entro 2 s anche con eventi
   continui), senza polling.
6. **S9 — file**: cartelle `~/.config/scambio` e `~/.local/share/scambio` create 0700, file 0600;
   `state.json`: niente symlink (né file né cartella genitore, `O_NOFOLLOW`), ≤ 64 KiB, temp nella
   stessa cartella, `fsync` del file e della cartella; `config.toml`: resta permesso il symlink (168d),
   letto con limite di 256 KiB.
7. **S10 — testi esterni**: alias BlueZ, nomi dei player e ogni stringa esterna mostrata in tray,
   notifiche, finestra, CLI e log: rimozione dei caratteri di controllo C0/C1 e dei controlli
   bidirezionali, lunghezza ≤ 64 caratteri con «…»; MPRIS: al massimo 16 player gestiti per volta,
   salvataggio dello stato una volta per operazione.
8. **S11 — installazione**: `tools/install_user.py` rifiuta percorsi con CR/LF/NUL, scrive in modo
   atomico senza seguire symlink e chiama `systemctl` con percorso assoluto. Script del `.deb` in
   `sh` con `set -eu`, idempotenti, senza rete né `HOME` né servizi utente avviati; provati in
   contenitore per install, upgrade da una versione fittizia 0.9.0, remove e purge. Unità systemd
   utente con `NoNewPrivileges=yes` e `LockPersonality=yes` (verificate su casa con il `.deb` nella prova A e
   nei contenitori); niente altre direttive di sandbox che richiedono namespace (misura in contenitore).
9. **S12 — Flatpak**: test «golden» che confronta `flatpak info --show-permissions` dell'app
   costruita con l'elenco esatto della decisione 153; test negativi (UPower, systemd1,
   `org.freedesktop.Flatpak` non raggiungibili). Il portal Background si chiede una volta per avvio,
   senza argomenti variabili.
10. **S13 — esecuzione**: `/usr/bin/scambio` del `.deb` e `/app/bin/scambio` sono wrapper che
    eseguono `python3 -I -m scambio` (niente `PYTHONPATH`/user site); `pactl` cercato una volta
    all'avvio in `/usr/bin:/bin` (nel Flatpak `/usr/bin`) e usato col percorso assoluto; la
    ri-esecuzione (§3.1.2.5) usa lo stesso eseguibile assoluto e argv fisso. Nessun caricamento di
    estensioni nella 1.0.0 (il punto di estensione resta non attivo).
11. **S14 — repository**: via il percorso personale dagli hook in `.githooks/` (usa la radice del
    repo); dati personali in `src/`, `tests/`, `tools/`, `packaging/` sostituiti come §3.1.9. La
    pulizia della storia la fa Claude (dec. 164, 166).

#### 3.1.8 File pubblici del repository (scritti da Claude prima del goal, §8)

`LICENSE` (testo ufficiale GPL-3.0), `CLA.md`, `CONTRIBUTING.md`, `README.md` (inglese, con
screenshot reali in `design/screenshots/`), `CHANGELOG.md` (Keep a Changelog), `NOTICE.md`
(marchi e disclaimer Meta), metainfo e desktop in `design/`. Codex li **installa** e li valida, non li
modifica; se una validazione fallisce lo scrive nel report.

Intestazione SPDX `# SPDX-License-Identifier: GPL-3.0-or-later` e
`# SPDX-FileCopyrightText: 2026 Fermich srl` in testa a ogni file di `src/`, `tests/`, `tools/`
(Codex); un test verifica che non manchi.

#### 3.1.9 Pulizia prima della pubblicazione

1. Nessun dato personale nel repository pubblico: il MAC degli occhiali di GM, nomi di dispositivi,
   percorsi `~` e simili restano solo dove sono **misure** (`docs/hardware-lab.md`,
   `docs/verification/`) o vanno sostituiti da valori di esempio nei test e negli esempi. Codex
   produce l'elenco delle occorrenze (`git grep`, ammesso qui perché è un controllo testuale) e
   sostituisce quelle in `src/`, `tests/`, `tools/`, `packaging/`; per `docs/` e `design/` le elenca
   nel report e decide Claude.
2. La storia git si pubblica **intera**, con l'autore riscritto da Claude subito prima del push
   (decisione 164; Codex **non** riscrive la storia). Codex controlla la storia (`git log -p`) per
   segreti (token, chiavi, password) e riporta il risultato; se ne trova, si ferma.
3. Avvisi di deprecazione con Python 3.14 (936 nei test, debito della fase 4): Codex li classifica;
   quelli che nascono da `src/` o `tests/` si correggono senza cambiare comportamento; gli altri si
   elencano con la libreria d'origine.

### 3.2 API D-Bus, configurazione, dati

- API: nessun metodo né proprietà nuovi; `Version` = `1.0.0`. Il nome del servizio del tray
  diventa il nome unico della connessione del tray (§3.1.3).
- Configurazione: nessuna chiave nuova; percorsi da §3.1.1.
- Testi nuovi (Claude in `design/i18n/`, già fatti): `background-reason`, `daemon-already-running`,
  `cli-version-help` (`scambio --version`); cambiati `tray-detail-not-configured` e `config-header`.

### 3.3 Interfaccia e testi (di Claude)

#### 3.3.1 Desktop e metainfo

`design/desktop/app.scambio.Scambio.desktop.in` aggiornato (commento pubblico, non più «iPhone»
solo) e `design/metainfo/app.scambio.Scambio.metainfo.xml` nuovo: id `app.scambio.Scambio`,
`metadata_license` CC0-1.0, `project_license` GPL-3.0-or-later, developer `app.scambio`
«Fermich srl», nome, sommario e descrizione in en/it/de con «Works with Ray-Ban Meta and Oakley Meta
glasses» solo nella descrizione (dec. 134b) e il disclaimer di non affiliazione, screenshot da
`https://scambio.app/screenshots/…`, URL (homepage, bugtracker, vcs-browser, contribute), OARS
`oars-1.1` vuoto, `<release version="1.0.0" date="…">`, `<launchable>`, `<provides><dbus>`,
`<requires><display_length>`, `<supports><control>keyboard/pointer`.

#### 3.3.2 README

Inglese, per due pubblici: chi installa (prima parte, niente gergo) e chi contribuisce (seconda).
Sezioni: cosa fa (con GIF/screenshot reali), «Works with», installazione (Ubuntu/Debian `.deb`;
Flatpak; da sorgente), primo avvio (scegliere il dispositivo), GNOME senza tray (estensione
AppIndicator), FAQ brevi, privacy (nessuna rete, nessuna telemetria), sviluppo (`make venv check`,
AGENTS.md, codice scritto con agenti IA dichiarato in chiaro), contributi (CLA), licenza, marchi e
disclaimer, Mac (a pagamento, lista d'attesa).

#### 3.3.3 Testi della pagina scambio.app (Codex li inserisce così come sono)

Stato Linux (`platform_status[0]`, `status_labels.ready`):
- en: «Linux: available now. Free and open source (GPL-3.0).» · etichetta «Available»
- it: «Linux: disponibile ora. Gratis e open source (GPL-3.0).» · «Disponibile»
- de: «Linux: jetzt verfügbar. Kostenlos und Open Source (GPL-3.0).» · «Verfügbar»

Nuova sezione «Download» (titolo `headings.download`) sopra il modulo, tre blocchi:
- **Ubuntu & Debian** (Ubuntu 24.04+, Debian 13+): pulsante «Download .deb» → `scambio_<versione>_all.deb`;
  sotto, riga piccola «Updates arrive with your system updates.» / «Gli aggiornamenti arrivano con
  quelli di sistema.» / «Updates kommen mit deinen System-Updates.»
- **Other distributions (Flatpak)**: pulsante «Install with Flatpak» → `flatpak/scambio.flatpakref`
  e riga copiabile `flatpak install https://scambio.app/flatpak/scambio.flatpakref`.
- **Source code**: link «GitHub» al repository.
Titoli: en «Download for Linux» · it «Scarica per Linux» · de «Für Linux herunterladen». Pulsanti:
it «Scarica il .deb», «Installa con Flatpak»; de «.deb herunterladen», «Mit Flatpak installieren».
FAQ «Is it free?» e «When does it launch?»: Claude fornisce i testi definitivi nel commit dei testi
(§8) prima del goal.

#### 3.3.4 Email di conferma della lista d'attesa (testo semplice)

Oggetto en «Confirm your Scambio waitlist sign-up» · it «Conferma l'iscrizione alla lista d'attesa di
Scambio» · de «Bestätige deine Anmeldung zur Scambio-Warteliste».

Corpo en: «Hi! Someone (hopefully you) asked to join the Scambio waitlist with this address.
Confirm here: {link}
The link works for 48 hours. If it wasn't you, just ignore this email and we won't write again.
— Scambio, by Fermich srl · scambio.app»

Corpo it: «Ciao! Qualcuno (speriamo tu) ha chiesto di entrare nella lista d'attesa di Scambio con
questo indirizzo. Conferma qui: {link}
Il link vale 48 ore. Se non sei stato tu, ignora questa email e non ti scriveremo più.
— Scambio, di Fermich srl · scambio.app»

Corpo de: «Hallo! Jemand (hoffentlich du) möchte sich mit dieser Adresse auf die Scambio-Warteliste
setzen. Hier bestätigen: {link}
Der Link gilt 48 Stunden. Warst du das nicht, ignoriere diese E-Mail einfach – wir schreiben dir
dann nicht mehr.
— Scambio, von Fermich srl · scambio.app»

Pagina di conferma (testi nel `copy.json`): en «You're on the list. We'll write when Scambio is ready
for your platform.» / «This link has expired or was already used.»; it «Sei nella lista. Ti
scriviamo quando Scambio è pronto per la tua piattaforma.» / «Questo link è scaduto o è già stato
usato.»; de «Du stehst auf der Liste. Wir melden uns, wenn Scambio für deine Plattform bereit ist.» /
«Dieser Link ist abgelaufen oder wurde schon benutzt.» Dopo l'invio del modulo il messaggio di
successo diventa: en «Almost there: check your inbox and confirm.» · it «Ci siamo quasi: controlla la
posta e conferma.» · de «Fast geschafft: Schau in dein Postfach und bestätige.»

### 3.4 Errori e casi limite

- Distro con libadwaita < 1.4 o PulseAudio < 16: apt rifiuta l'installazione per dipendenze.
- Flatpak senza BlueZ sull'host o senza adattatore: stato `unavailable` come oggi.
- Portal Background assente (desktop senza portal): log di una riga, Scambio funziona finché la
  sessione è aperta; README spiega l'avvio manuale.
- GNOME senza estensione AppIndicator: nessuna icona (già gestito); la finestra dal menu basta.
- Aggiornamento del Flatpak col demone in esecuzione: il demone vecchio continua finché non riparte
  (`IconThemePath` punta al deploy in uso, che Flatpak conserva finché il processo vive).
- Rimozione del `.deb`: servizio disabilitato, sorgente apt rimossa; configurazione e stato
  dell'utente restano (come ogni app).

## 4. Fuori scope

Manifest Flathub e invio a Flathub (GM, guida di Claude); PPA, AUR, AppImage; versione Mac; invio
email alla lista d'attesa; aggiornamento automatico dentro l'app; firma dei tag git; registrazione
del marchio; nuove funzioni o cambi di comportamento non elencati in §3; `Gtk.ShortcutLabel`
deprecato (resta debito di design).

## 5. Dipendenze

- Già su casa: flatpak 1.16.6, flatpak-builder 1.4.8, lintian, apt-ftparchive, dpkg-deb, gpg,
  appstreamcli, desktop-file-validate, blueprint-compiler, Docker (gruppo `docker`), runtime/SDK GNOME 51.
- Prima del goal (Claude): chiave di firma (§3.1.7), file pubblici e testi (§3.1.8, §3.3), screenshot.
- Da GM: risposte alle domande di §9.

## 6. Checklist di done

- [ ] §3.1.1–3.1.3: ogni regola ha un test (percorsi checkout/installato, `StartServiceByName`,
      Background solo in Flatpak e risposta negativa, re-exec senza systemd, demone duplicato, tray su
      connessione dedicata con nascondi/mostra e riavvio del watcher, traduzione di `IconThemePath`).
- [ ] `make deb`, `make apt-repo`, `make flatpak`, `make flatpak-site`, `make dist` funzionano da un
      albero pulito; `lintian` senza errori; `appstreamcli validate --pedantic` e
      `desktop-file-validate` verdi.
- [ ] `verify` (§3.1.7): installazione del `.deb` in `ubuntu:24.04` e `debian:13` e del Flatpak dal
      repo locale riuscite, log nel report.
- [ ] Repository apt firmato: `apt update` da un contenitore che usa `scambio.sources` + keyring
      puntati al repo locale (via `file:` o server HTTP locale) senza errori di firma.
- [ ] Sito: anteprima locale (`wrangler dev`) con `/apt/dists/stable/InRelease`,
      `/flatpak/scambio.flatpakref` e la sezione Download nelle tre lingue (screenshot nel report).
- [ ] Pulizia §3.1.9 fatta e riportata; nessun segreto nella storia.
- [ ] Intestazioni SPDX presenti; test che lo verifica.
- [ ] `make check` verde; nessun test saltato; avvisi di deprecazione classificati.
- [ ] Nessun polling; CPU/RSS a riposo misurati dal `.deb` installato in venv di prova e dal Flatpak.
- [ ] `design/`, `docs/context/`, `docs/specs/`, `docs/hardware-lab.md`, `README.md`, `CLA.md`,
      `CHANGELOG.md`, `LICENSE`, `NOTICE.md`, `CONTRIBUTING.md` non modificati da Codex.
- [ ] `docs/verification/05/report.md` scritto; decisioni tecniche in `docs/decisions.md` (voce 169, con sottopunti).
- [ ] Nessun push, nessun deploy, nessun tag.
- [ ] Prova di installazione pulita di GM (§6.1) eseguita · Firma: GM, data.

### 6.1 Prova di installazione pulita (traccia; Claude la completa dopo l'audit)

A. **casa (.deb, Plasma 6)**: `make uninstall-user`, servizio di sviluppo disinstallato; doppio clic
   sul `.deb` scaricato da un'anteprima locale del sito; Scambio nel menu; nuovo accesso → icona nel
   tray e stato corretto; Meta+G; finestra; `apt policy scambio` mostra `https://scambio.app/apt`;
   rimozione e reinstallazione; ritorno alla versione di sviluppo a fine prova.
B. **VM Proxmox Fedora (GNOME, Flatpak)**: installazione dal `.flatpakref`; primo avvio dal menu;
   dialogo del portal Background (annotare testo e scelta); nuovo accesso → demone avviato;
   finestra; scorciatoia via portal GlobalShortcuts (chiude Q6 per GNOME); tray assente senza
   estensione e presente con AppIndicator; nessun Bluetooth nella VM → stato `unavailable` corretto.
C. (facoltativa) **VM Ubuntu 24.04 GNOME, .deb**: installazione e avvio.

## 7. Note di revisione (Claude, dopo la consegna)

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

Riletta il 2026-10-07 prima della consegna. Cosa correggerei o terrei d'occhio:

1. **Flathub può rifiutarci** (dec. 159): il codice è quasi tutto di Codex. Per questo il
   repository Flatpak proprio è il canale vero e Flathub resta fuori da questa spec.
2. **Il tray cambia meccanismo** (§3.1.3) per stare nel sandbox: tocca il comportamento verificato
   nelle spec 03–04 (M17, M21). L'audit lo rimisura su Plasma 6 e la prova A di GM lo ripete.
3. **GNOME è ancora senza misure reali** (Q6): portal GlobalShortcuts con l'`app_id` del Flatpak,
   dialogo del portal Background, tray assente. Si scopre solo nella prova B; se lì qualcosa non
   va, la 1.0.0 aspetta (dec. 152).
4. **Avvio per tutti gli utenti** nel `.deb` (§3.1.2.2): su un PC condiviso il demone parte anche
   per chi non usa Scambio (resta in `unavailable`, CPU 0). Alternativa più prudente ma meno
   semplice: abilitarlo alla prima apertura della finestra. Tengo la versione semplice.
5. **Chiave di firma senza passphrase su casa** (§3.1.7.2): comoda, ma chi entra in casa può
   firmare aggiornamenti. Copia offline indispensabile (dec. 158). Impronta:
   `24A3 0DBE D897 3273 A486  CC73 86C8 855E 1251 E7E2`.
6. **Storia git pubblicata intera** (§3.1.9.2): i commit portavano l'email personale di GM; GM ha
   scelto di riscrivere l'autore (dec. 164). Restano pubblici i link alle sessioni Claude nei
   trailer, il MAC degli occhiali e i percorsi di casa nelle misure: accettabile (un indirizzo
   Bluetooth è già trasmesso in chiaro dal dispositivo).
7. **Testi con «iPhone»**: sostituiti da «telefono» (dec. 165). I test che confrontano testi inglesi
   con «iPhone» vanno aggiornati da Codex.
8. Già corretti in questa bozza: ordine di ricerca dei dati nel Flatpak (§3.1.1, Python ha
   `sys.prefix=/usr`), indirizzo stabile del `.deb` fatto dal Worker (§3.1.6.2), numerazione delle
   decisioni di Codex (169), testi `background-reason`, `daemon-already-running`,
   `cli-version-help`, `tray-detail-not-configured` e `config-header` senza `systemctl`.

## 9. Domande aperte

| # | Domanda | Per chi |
|---|---|---|
| ~~Q7~~ | ~~Proprietario del repository~~ — chiusa: organizzazione nuova `scambio-app` (dec. 160) | — |
| ~~Q8~~ | ~~Variante della licenza~~ — chiusa: GPL-3.0-or-later (dec. 161) | — |
| ~~Q9~~ | ~~CLA e parere legale~~ — chiusa: pubblicato ora, legale prima della prima PR (dec. 162) | — |
| ~~Q10~~ | ~~Email pubblica~~ — chiusa: `hello@scambio.app`, catch-all verso GM (dec. 163) | — |
| ~~Q11~~ | ~~Storia git~~ — chiusa: intera, autore riscritto (dec. 164) | — |
| ~~Q12~~ | ~~«iPhone» nei testi~~ — chiusa: «telefono» (dec. 165) | — |

## Comando `/goal`

```
/goal Implementa docs/specs/05-packaging-e-release.md seguendo AGENTS.md. Fatto quando la checklist §6 (tranne la prova di GM) è soddisfatta con evidenza e make check è verde. Nessun push, deploy o tag.
```
