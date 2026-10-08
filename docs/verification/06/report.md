# Spec 06 — verifica preliminare e stop

Data: 2026-10-08 · Codex · base esaminata: `93e76c38119ed0e5c5612e9dba2d172662f22e99`.

**Esito: implementazione non iniziata; candidata 1.0.1 non costruita.** Applicata la
condizione di stop del `/goal`: prima di procedere occorre riallineare la spec alle
misure autorevoli e avere gli asset di design richiesti per la release. Questo report
non attesta il completamento della spec né una prova reale.

## Obiettivo e perimetro

Implementare solo il §3 della spec 06 e consegnare una candidata 1.0.1 verificata,
senza modificare `design/`, senza pubblicazione, push, tag pubblico o deploy.
Scadenza richiesta: domenica 11 ottobre 2026. Decisioni tecniche riservate: 210–219.

## Evidenze e impedimenti

### 1. Obiettivo riferito all'iPhone, misura riferita al PC

La spec 06 §1 descrive il problema «quando Scambio rilascia il dispositivo e la musica
dell'iPhone riparte» e attribuisce il comportamento a M11b.

Le fonti autorevoli descrivono invece:

- `docs/hardware-lab.md`, M1: dopo il rilascio l'iPhone si ricollega, ma la musica resta
  in pausa.
- M11b: misura alla **connessione dal PC**, con bip prodotti da `paplay` sul sink
  Bluetooth; l'audio del PC diventa udibile circa 1,0–1,3 s dopo la comparsa del sink.
  Il ritardo di ripresa di 2000 ms copre questo annuncio.
- M12: il video di Chrome sul PC viene ripreso negli occhiali 2 s dopo `on_pc`.
- `docs/context/05-ui-context.md` §1: Scambio non controlla il telefono; la musica
  dell'iPhone non è di sua competenza.

`AGENTS.md` rende `hardware-lab.md` autorità sul comportamento hardware e impone di
fermarsi se la spec dipende da un comportamento non misurato. La decisione 187
richiede il profilo automatico e cita M11b, ma non introduce controllo o ripresa
della musica dell'iPhone. Il brain consultato non ha restituito una correzione
esplicita di questa discrepanza.

**Richiesta a Claude/GM:** correggere il §1 e rendere esplicito che la prova riguarda
la ripresa dell'audio del **PC dopo la presa**. Se si intende davvero intervenire
sull'audio dell'iPhone dopo il rilascio, servono una decisione di prodotto e le misure
relative prima dell'implementazione.

**Interpretazione, non fatto approvato:** il riferimento all'iPhone nel §1 potrebbe
essere un refuso, dato che §3 e decisione 187 richiamano il ritardo di ripresa già
esistente. Non viene corretto implicitamente da Codex.

### 2. Prerequisiti di design per soddisfare §3.2 e §3.5

Il §3.5 richiede AppStream 1.0.1 con note en/it/de. Il sorgente effettivo è
`design/metainfo/app.scambio.Scambio.metainfo.xml`: la prima release è ancora
`1.0.0`, con la sola nota inglese della prima pubblicazione.

`tools/release.py:check()` legge direttamente questo file e rifiuta una versione
diversa da `pyproject.toml` con `Metainfo version differs from pyproject.toml`.
Pertanto il solo aggiornamento del pacchetto a 1.0.1 non consentirebbe di costruire
la candidata con il processo richiesto. È una deduzione dalla lettura del controllo,
non una build 1.0.1 eseguita e fallita.

Inoltre `src/scambio/config.py:template()` prende il commento del profilo dalla
chiave `config-device-profile` in `design/i18n/{it,en,de}.po`. Lettura dei cataloghi
compilati con `gettext.GNUTranslations`:

| Lingua | Commento attuale |
|---|---|
| it | Profilo del dispositivo: generic oppure meta_glasses |
| en | Device profile: generic or meta_glasses |
| de | Geräteprofil: generic oder meta_glasses |

Nessuno spiega `auto`, richiesto dal §3.2. `AGENTS.md` assegna questi testi a Claude
e richiede a Codex di domandare le modifiche nel report. Non è stata introdotta una
seconda fonte di testi nel codice o nel tooling di rilascio.

**Richieste a Claude per `design/`:**

1. Aggiungere in testa ad AppStream la release 1.0.1 con note en/it/de sul profilo
   automatico, conservando la voce 1.0.0.
2. Aggiornare `config-device-profile` nelle tre lingue: una riga che spieghi `auto`
   come riconoscimento dal nome e `generic`/`meta_glasses` come scelte esplicite.

## Consultazione del progetto

Letti `AGENTS.md`, i sei file di contesto, `hardware-lab.md` e la spec 06;
successivamente consultati graphify, decisione 187, spec 05 §3.3.1 e i file indicati
dal grafo e dai riferimenti espliciti.

- `graphify query` usato per spec 06, profilo, configurazione e metainfo.
- `graphify path "check()" "version()"`: collegamento diretto di chiamata.
- `graphify affected "docs/verification/06/report.md"`: nessun nodo univoco, perché
  il report è nuovo; nessuna modifica a simboli di codice.
- Solo MCP `agvm-scambio`, in lettura sul brain `scambio_brain`; query
  `b31ec6d2-f937-4012-95e7-6ba6b215160c` e
  `0dfb5093-7c2c-4b64-960b-4ffc78296e8d`. Risposte `partial`, senza una fonte precisa
  sulla decisione 187 o una correzione della spec 06; nessuna memoria usata al posto
  dei file. Nessuna operazione sul registro o scrittura del brain.
- Nessuna ricerca con `grep`/`rg`/`find` e nessuna eccezione al metodo di ricerca.

## Verifiche e checklist di done

`make check` sulla base invariata: **verde**, exit 0; format verificato su 75 file,
ruff superato, mypy senza errori su 32 sorgenti, **804 test passati e nessun test
saltato**, 991 warning, durata pytest 91,94 s. Presenti gli avvisi preesistenti
PyGObject/asyncio e `Gtk.ShortcutLabel`, fuori scope per §4. Il controllo non prova
la funzionalità 1.0.1, che non è stata implementata. `git diff --check`: exit 0.

| Voce della checklist §6 | Stato ed evidenza |
|---|---|
| Test di tutte le regole §3.1 | Non eseguita: implementazione ferma prima delle modifiche |
| Parser, tre valori, default e template | Non eseguita |
| Proprietà D-Bus e output CLI | Non eseguita |
| `make check`, nessun test saltato, nessun polling | Base verde: 804 test passati, zero saltati; nessun codice o polling introdotto. Da ripetere sull'implementazione |
| Candidata, firme/hash, install/upgrade/rimozione Ubuntu/Debian, Flatpak | Non eseguita; asset di design mancanti |
| 1.0.0 sigillata intatta | Nessuna operazione sugli archivi; verifica crittografica non eseguita |
| Report completo, CPU/RSS, richieste e checklist GM | Parziale: presente il report di stop; CPU/RSS non misurati su una candidata |
| Decisioni tecniche 210–219 | Nessuna assunta: intervallo lasciato libero |
| Prova reale eseguita e firmata da GM | Non eseguita; nessuna firma attribuita a GM |

## Richieste per `02-architecture.md` all'audit

Come richiesto dal §3.2, aggiornamenti da inserire a cura di Claude dopo la ripresa:

- `device.profile`: `auto` come default; valori ammessi `auto`, `generic`,
  `meta_glasses`; nessuna migrazione dei valori espliciti esistenti.
- Profilo effettivo dal nome BlueZ del solo dispositivo configurato, aggiornato
  tramite eventi; ripiego `generic` quando il dispositivo è ignoto.
- `policy.resume_delay_ms` esplicito prevale; altrimenti default dal profilo
  effettivo, applicato alla ripresa successiva senza cambiare timer già programmati.
- Proprietà D-Bus di sola lettura `DeviceProfile` (`generic`/`meta_glasses`) e
  `DeviceProfileSource` (`auto`/`config`), con `PropertiesChanged` e output in
  `scambio status`.

Nessuno di questi comportamenti è attestato come già implementato.

## Checklist di prova reale per GM — da eseguire sulla candidata

La formulazione seguente riguarda l'audio del PC e resta subordinata al chiarimento
del §1. I test automatici non sostituiscono questa prova.

- [ ] Config pulita, Oakley Meta scelti, senza profilo esplicito: verificare log
  `device profile: meta_glasses (auto, from name)` e proprietà esposte da
  `scambio status`.
- [ ] Occhiali inizialmente sull'iPhone: avviare un video/player sul PC e verificare
  pausa durante la presa e ripresa dell'audio PC dopo l'annuncio negli occhiali.
- [ ] Aggiornare dalla 1.0.0 con `profile = "generic"` già scritto: resta `generic`;
  la configurazione dell'utente non viene migrata.
- [ ] Impostare `profile = "auto"` oppure eliminare la riga e ricaricare: verificare
  riconoscimento e ripresa successiva con il ritardo previsto.
- [ ] Annotare versione/candidata, ambiente, esiti e firma di GM con data.

## Modifiche, commit e ripresa

Unico file modificato da questa sessione: `docs/verification/06/report.md`.
Nessun cambiamento a codice, test, decisioni, design, spec, contesto, hardware-lab,
`scambio-site` o archivi di rilascio. Nessun asset staged sul sito: il rebase chiesto
per un futuro commit di asset in `scambio-site` non è ancora applicabile.

Commit documentale previsto sulla branch corrente, messaggio
`Document spec 06 preflight blockers`, con pre-commit `make check` attivo. L'hash
effettivo è nel report finale della sessione e nel git log.

Scostamento dalla consegna richiesta: solo verifica preliminare e report di stop;
nessuna candidata verificata. Per riprendere servono il chiarimento della semantica
PC/iPhone e i due aggiornamenti di design da Claude. La chiusura resta subordinata
anche all'audit, alle verifiche dei pacchetti e alla prova firmata da GM. Tracker e
brain saranno aggiornati da Claude quando esisterà una milestone verificata.
