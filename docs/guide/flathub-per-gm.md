# Guida: pubblicare Scambio su Flathub (per GM)

Redatta da Claude il 2026-10-07. Questa guida dice **cosa fare e dove leggere**; il manifest, la
descrizione della PR e le risposte ai revisori li scrivi **tu, a mano**, senza IA: lo impongono i
requisiti di Flathub (decisione 159). Claude non scrive né corregge il manifest; può rispondere a
domande generali su Flatpak come farebbe la documentazione.

## 0. Quando partire

Solo dopo che la 1.0.0 è pubblica: tag `v1.0.0` su github.com/scambio-app/scambio, archivio
`.tar.gz` scaricabile dalla release, screenshot raggiungibili su scambio.app, repository Flatpak
proprio funzionante (prova B della spec 05).

## 1. Leggi (una volta, 30–40 minuti)

1. Requisiti: https://docs.flathub.org/docs/for-app-authors/requirements — in particolare
   «Generative AI policy», «Application ID», «Permissions» (finish-args) e «License».
2. Invio: https://docs.flathub.org/docs/for-app-authors/submission
3. Struttura del manifest: https://docs.flatpak.org/en/latest/manifests.html e
   https://docs.flatpak.org/en/latest/flatpak-builder-command-reference.html
4. Permessi del sandbox: https://docs.flatpak.org/en/latest/sandbox-permissions.html
5. Lint: https://docs.flathub.org/docs/for-app-authors/linter
6. Verifica del dominio: https://docs.flathub.org/docs/for-app-authors/verification

## 2. Fatti sull'app che ti servono (dal repository, non dal manifest del nostro repo)

Non copiare né guardare `packaging/flatpak/app.scambio.Scambio.yml`: è scritto da Codex e
renderebbe il tuo manifest «assistito da IA». Le informazioni che ti servono sono fatti sull'app:

- ID: `app.scambio.Scambio` (dominio scambio.app, tuo).
- Runtime: GNOME 51 (`org.gnome.Platform` / `org.gnome.Sdk`), misura M30 in `docs/hardware-lab.md`.
- Installazione: il progetto ha `make install PREFIX=… DESTDIR=…` (spec 05 §3.1.3b); non serve rete.
- Comando: `scambio`; il lanciatore apre `scambio settings`.
- Cosa usa l'app sul sistema (per scegliere i permessi leggendo la pagina «sandbox permissions»):
  le misure **M31–M34** in `docs/hardware-lab.md` elencano quali servizi D-Bus di sistema e di
  sessione, audio e portal servono e cosa succede senza. Decidi tu ogni permesso e preparati a
  motivarlo ai revisori.

## 3. Prepara il manifest in locale

1. Crea una cartella fuori dal repository Scambio, per esempio `~/flathub-scambio/`.
2. Scrivi a mano `app.scambio.Scambio.yml` (o `.json`) seguendo la documentazione del punto 1.3:
   sorgente = archivio della release su GitHub con il suo `sha256` (calcolalo tu con `sha256sum`).
3. Prova: `flatpak-builder --user --force-clean --install build app.scambio.Scambio.yml`, poi
   `flatpak run app.scambio.Scambio`.
4. Lint: `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest app.scambio.Scambio.yml`
   e, dopo una build con `--repo=repo`, `… repo repo` (installa prima `org.flatpak.Builder` da
   Flathub). Correggi finché non ci sono errori.
5. **Disinstalla** la versione del nostro repository prima della prova, per non averne due.

## 4. Apri la PR su Flathub

1. Fai un fork di https://github.com/flathub/flathub con il tuo account e parti dal ramo
   `new-pr` (come indicato nella pagina «submission»).
2. Aggiungi il tuo manifest, fai commit (messaggio scritto da te) e apri la PR verso `new-pr`.
3. Nel modulo della PR, nella parte sull'IA, scrivi tu la **dichiarazione**: quali parti sono
   generate (il codice in `src/` e `tests/` e il packaging del repository proprio, da Codex; spec,
   documenti, testi e icone, da Claude) e in che misura (quasi tutto il codice), e cosa hai fatto tu
   (decisioni di prodotto, revisione delle spec, prove sul tuo hardware documentate in
   `docs/hardware-lab.md` e `docs/verification/`). Il manifest: scritto da te senza IA.
4. Rispondi tu ai revisori. Non chiedere revisioni a un agente e non incollare risposte generate.

## 5. Dopo l'accettazione

1. Flathub crea il repository `flathub/app.scambio.Scambio`: gli aggiornamenti sono PR lì
   (nuovo tag e nuovo `sha256`), sempre scritte da te.
2. Verifica del dominio: dal portale sviluppatori di Flathub copi il token; Claude lo pubblica in
   `https://scambio.app/.well-known/org.flathub.VerifiedApps.txt` (la cartella è già prevista).
3. Il sito passa da «Install with Flatpak» al pulsante Flathub; il nostro repository resta per chi
   l'ha già installato.

## Se la rifiutano

Nessun problema per gli utenti: il repository Flatpak su scambio.app continua a funzionare e
riceve gli aggiornamenti. Si può riprovare più avanti, quando il progetto avrà storia e utenti.
