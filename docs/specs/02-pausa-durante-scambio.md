# Spec 02 — Pausa durante lo scambio

Stato: approvata (GM, 2026-10-05) · Autore: Claude · Data: 2026-10-05

## 1. Obiettivo

Quando Scambio prende il dispositivo perché sul PC è partito un audio, i player del PC vanno
in **pausa** per tutta la presa e ripartono **negli occhiali** quando sono pronti, dopo
l'annuncio vocale degli occhiali. Niente più video che suona dalle casse per 2–3 s e poi salta
negli occhiali, e nessun pezzo perso sotto l'annuncio. Quando Scambio **rilascia** il
dispositivo con l'audio in corso (blocco schermo, switch, Priorità iPhone, astine chiuse o
custodia, Bluetooth spento), i player del PC vanno in pausa e restano in pausa, come quando si
tolgono le cuffie a un telefono.

**Prova visibile.** Occhiali sull'iPhone. GM avvia un video YouTube sul PC: dopo ≈ 0,5 s il
video si ferma, gli occhiali passano al PC, l'eventuale annuncio «connessione stabilita» si
sente da solo, poi il video riparte negli occhiali dal punto in cui si era fermato. GM blocca
lo schermo: gli occhiali tornano all'iPhone e il video è in pausa, non suona dalle casse.

## 2. Decisioni applicabili

- Prodotto: 4 (presa automatica con pausa/muto durante la connessione), 5 (rilascio per
  silenzio, blocco e sospensione), 44 (la pausa copre anche l'annuncio vocale degli occhiali),
  **50** (pausa senza ripresa al rilascio con audio in corso, esclusi gli errori),
  **51** (l'audio senza MPRIS resta sulle casse durante la presa; nessun muto).
- Architettura: `02-architecture.md` §6 «un errore non deve mai lasciare l'audio del PC muto o
  in pausa»; policy pura (decisione 25); anti ping-pong (decisione 45).
- Misure: M1 (presa ≈ 1,7 s fino al sink), M5 e **M9** (Chrome e Firefox: stream `corked` in
  pausa; alla ripresa Firefox apre uno stream nuovo sull'uscita predefinita; MPRIS di Firefox
  snap raggiungibile da un servizio utente), **M10** (WirePlumber memorizza il muto per
  applicazione: il muto di uno stream non si usa) in `docs/hardware-lab.md`.
- **Non ancora misurati** (GM fuori casa il 2026-10-05): la durata dell'annuncio vocale degli
  occhiali (M8: non sistematico) e la presa durante una chiamata GSM (Q4). Nessuno dei due
  cambia la logica: l'annuncio decide solo il **default** di `resume_delay_ms` per il profilo
  `meta_glasses`, qui **provvisorio a 2000 ms**; Q4 riguarda la spec 01 (presa durante una
  chiamata). Entrambi si misurano all'inizio della prova reale (§6.1, punto 0); se l'annuncio
  misurato chiede un default diverso, la correzione è una riga in `config.py` (decisione 56).
- Decisioni di questa spec: **53–56** in `docs/decisions.md` (Claude), approvazione **57** (GM).
  Codex, se gli servono voci tecniche, usa i numeri liberi dalla 58 alla 69.

## 3. Dettagli

### 3.1 Comportamento

#### 3.1.1 Moduli

Si aggiunge `src/scambio/core/players.py` (adattatore MPRIS, Protocol `PlayersPort` in
`core/ports.py`). Cambiano `core/policy.py`, `core/service.py` (esecutore e ciclo di vita),
`config.py`, `state.py`. Nessun nuovo processo, nessuna nuova dipendenza: tutto via Gio sul bus
di sessione, in modo asincrono.

#### 3.1.2 Adattatore MPRIS (`players.py`, decisione 53)

Lavora **solo su richiesta** dell'esecutore: nessuna sottoscrizione a segnali, nessun timer
proprio, nessun costo a riposo.

- **Candidati**: nomi sul bus di sessione che iniziano con `org.mpris.MediaPlayer2.`
  (`ListNames`), esclusi quelli il cui **primo segmento** dopo il prefisso è in
  `audio.ignore_players` (confronto senza maiuscole). Esempi reali: Chrome si presenta come
  `chromium.instance<N>` (segmento `chromium`), Firefox come `firefox.instance_<…>`, poi
  `vlc`, `spotify`, `elisa`, `Gwenview`. Il default di `ignore_players` esclude i proxy che non
  sono player del PC: `kdeconnect` (player del **telefono**), `plasma-browser-integration`
  (duplica le schede del browser) e `playerctld`.
- **Insieme tenuto**: voci `(nome, owner unico, kind)` con `kind` ∈ {`grab`, `release`}.
  Le voci `grab` stanno anche in `state.json` (§3.2.3), le `release` no.
- **`pause(kind)`**:
  1. tutte le voci già tenute prendono `kind` (un rilascio trasforma in `release` la pausa di
     una presa ancora in corso; una presa dopo un rilascio trasforma in `grab`);
  2. per ogni candidato, in parallelo: `GetNameOwner` e
     `Properties.Get(org.mpris.MediaPlayer2.Player, PlaybackStatus)`; se vale `Playing`,
     `Player.Pause()`; se riesce, il player entra nell'insieme con `kind` (senza duplicati);
  3. aggiorna `state.json` (scrive le voci `grab`, toglie quelle diventate `release`).
- **`resume()`**: per ogni voce, in parallelo: se l'owner attuale del nome è ancora quello
  registrato e `PlaybackStatus` è `Paused` **o** `Playing` → `Player.Play()` (su un player che
  sta già suonando non cambia nulla; serve perché lo stato dopo `Pause()` si aggiorna in modo
  asincrono). Si salta con nome sparito, owner cambiato o `Stopped`. Poi svuota l'insieme e la
  voce in `state.json`.
- **`forget()`**: svuota l'insieme e `state.json` senza toccare i player.
- Ogni chiamata ha timeout `backend.player_timeout_ms`; un player che non risponde o dà errore
  si salta con log `warning`. Un'operazione è conclusa quando tutte le sue chiamate hanno
  risposto o sono scadute (quindi dura al massimo ≈ 2 × `player_timeout_ms`: lettura +
  comando).
- Log `info` con i nomi del bus messi in pausa e ripresi (mai titoli o URL: dati personali).
- Vietati: `playerctl` o altri programmi esterni; chiamate diverse da `Pause`/`Play` (mai
  `Stop`, `PlayPause`, `Seek`); qualsiasi muto o cambio di volume (M10, decisione 51).

Nota (M9): Firefox snap accetta le chiamate MPRIS da processi non confinati, come un servizio
utente systemd, cioè Scambio. Il futuro Flatpak dovrà dichiarare
`--talk-name=org.mpris.MediaPlayer2.*` (fase 5, non qui).

#### 3.1.3 Esecutore e ciclo di vita (`service.py`)

- **Coda dei player**: le operazioni `pause`/`resume`/`forget` passano da una coda FIFO
  propria, una alla volta, nell'ordine delle azioni.
- **Presa**: `PausePlayers(grab)` parte subito e **non ritarda** `Connect`.
- **Rilascio con pausa**: se un'azione `PausePlayers(release)` precede `RestoreRouting` nella
  stessa lista di azioni, `RestoreRouting` (e quindi `Disconnect`, che già lo aspetta) parte
  solo quando la coda dei player ha finito **tutte** le operazioni accodate fino a quella
  pausa compresa. Il ritardo massimo è la somma delle operazioni in coda (in pratica una o due,
  ≤ 2 × `player_timeout_ms` ciascuna); con la sospensione il budget è `SLEEP` (4 s) contro
  ≈ 2,4 s di `Disconnect` (M1): con il default di 1000 ms ci sta, e se scade decide il timer
  `SLEEP` come oggi.
- **Ripresa**: `ResumePlayers` parte solo dopo che tutte le operazioni di instradamento
  (`RouteToDevice`, `RestoreRouting`) emesse **prima** di essa sono concluse.
- **Avvio**: dopo aver preso il nome D-Bus, se `state.json` contiene `resume_players` (e il bus
  è lo stesso, §3.2.3) l'esecutore avvia `resume()` **in modo asincrono** e aggancia gli
  adattatori alla sua conclusione (o allo scadere del suo timeout). Ripara un crash avvenuto a
  metà presa: un errore non lascia l'audio in pausa. Vietate chiamate sincrone in sequenza.
- **Arresto** (`SIGTERM`/`SIGINT`): se l'insieme contiene voci `grab`, l'esecutore avvia
  `resume()` e ferma il loop alla sua conclusione o dopo 2 × `player_timeout_ms`, poi
  `close()`; altrimenti si ferma subito. Le voci `release` si dimenticano (decisione 50).
- Il resto dell'esecutore è invariato.

#### 3.1.4 Macchina a stati (`core/policy.py`, decisione 54)

Si aggiunge al contesto `held` (bool): «Scambio potrebbe tenere in pausa dei player e deve
ancora decidere se riprenderli o dimenticarli». La policy non sa quali player, né se ne ha
messi in pausa davvero: lo sa l'adattatore. Con l'insieme vuoto `resume`/`forget` non fanno
nulla, quindi `held` può essere vero anche quando l'audio era solo senza MPRIS (va bene).

**Nuovo timer** (ottavo): `RESUME` (`policy.resume_delay_ms`).
**Nuove azioni**: `PausePlayers(kind)`, `ResumePlayers`, `ForgetPlayers`.

**Predicato.** *Audio in corso* = `audio_active` ∨ `held` (la pausa fatta da Scambio non è
silenzio). Sostituisce `audio_active` in tutti i punti in cui la spec 01 decide «c'è audio?»
dentro `on_pc`, `connecting` e `releasing`: avvio di `IDLE` (INGRESSO, O1, L2), anti ping-pong
(C4, C5, C6, C8, O8, O11, G8). **Non** cambia *idoneo alla presa automatica*, che resta su
`audio_active`.

**Blocco senza audio.** Ogni volta che una riga pone `blocked_until_silence = true` mentre
`audio_active` è falso (succede solo con `held`), emette anche `StartTimer(UNBLOCK)`: se i
player ripartono, G1 lo annulla; se non ripartono, il blocco cade dopo
`unblock_silence_seconds` come per un silenzio vero.

**Insieme P dei motivi con pausa** (decisione 50): `locked`, `sleep`, `switch`, `priority`.

**Procedure nuove**

- **PAUSA_RILASCIO**: se *audio in corso* → `PausePlayers(release)`, `held = true`.
  (Emessa anche con il solo `held`, per trasformare in `release` le voci della presa.)
- **ESITO_ERRORE**: se `held`: se `pending = release` → `ForgetPlayers` (l'utente aveva già
  chiesto il rilascio per un motivo di P prima dell'errore: resta in pausa; interpretazione
  della decisione 50, 55), altrimenti `ResumePlayers`; poi `held = false`.

**Procedure modificate** (il resto come nella spec 01 §3.1.5)

- **PRESA(r)**: prima di `Connect`, se `audio_active` → `PausePlayers(grab)`, `held = true`;
  se `held` era già vero (L1 con `pending = grab`) → `PausePlayers(grab)` anche senza audio, per
  riportare le voci a `grab`.
- **RILASCIO(r)**, ordine delle azioni:
  1. `CancelTimer(IDLE, GRAB_DELAY, CONNECT, SINK, RESUME)`;
  2. se `r` ∈ P → PAUSA_RILASCIO;
  3. `RestoreRouting`, `routed = false`;
  4. se `r` ∉ P (errori, `idle_timeout`) → ESITO_ERRORE (dopo `RestoreRouting`: la ripresa
     trova l'uscita già ripristinata);
  5. `Disconnect`, `StartTimer(RELEASE)`, `pending = none`, `reason = r` → `releasing`.
- **INGRESSO(instrada)**, ramo che entra in `on_pc`: dopo `RouteToDevice`: se `held` →
  `StartTimer(RESUME)`; `IDLE` parte solo se ¬(*audio in corso*). I rami che rilasciano
  (pending, `locked`, `sleeping`) passano da RILASCIO con un motivo di P.

**Regole globali modificate**

| # | Modifica |
|---|---|
| G8 | `blocked_until_silence = audio_active ∨ held` (+ UNBLOCK se serve); annulla anche `RESUME`. Poi, secondo lo stato di partenza: da `on_pc` o `releasing` → se *audio in corso* → `PausePlayers(release)` e poi `ForgetPlayers` (Bluetooth spento = rilascio voluto, decisione 50); da `connecting` → ESITO_ERRORE (la presa non è mai arrivata: l'audio riparte dalle casse, decisione 55). `held = false`. Il resto invariato |
| G12 | vale anche per `TimerFired(RESUME)` fuori da `on_pc` |

**Righe modificate o nuove** (ordine delle azioni come scritto)

| # | Stato | Evento (guardia) | Azioni → stato · reason |
|---|---|---|---|
| C4 | connecting | `ConnectResult(altro errore)` | `EmitError(connect_failed)`, `blocked_until_silence = audio_active ∨ held` (+ UNBLOCK); con dispositivo collegato → RILASCIO(`connect_failed`); altrimenti `CancelTimer(CONNECT, SINK)`, ESITO_ERRORE → released · `connect_failed` |
| C5 | connecting | `TimerFired(CONNECT)` | `EmitError(connect_timeout)`, blocco come C4, RILASCIO(`connect_timeout`) |
| C6 | connecting | `TimerFired(SINK)`, `origin = self` | `EmitError(sink_timeout)`, blocco come C4, RILASCIO(`sink_timeout`) |
| C8 | connecting | `DeviceConnected(false)` | `CancelTimer(CONNECT, SINK)`; `origin = self` → `EmitError(connect_failed)`, blocco come C4, ESITO_ERRORE → released · `connect_failed`; `origin = external` invariato (`held` è falso: le prese esterne non mettono in pausa) |
| O1 | on_pc | `AudioActive(false)` | `StartTimer(IDLE)` solo se ¬`held` |
| O8 | on_pc | `DeviceConnected(false)` | `CancelTimer(IDLE, SINK, RESUME)`, `RestoreRouting`, `routed = false`, `blocked_until_silence = audio_active ∨ held` (+ UNBLOCK); se `held` (la ripresa dopo la presa non è ancora avvenuta: gli occhiali sono caduti subito, per esempio profili rifiutati, M8) → ESITO_ERRORE; altrimenti se `audio_active` → `PausePlayers(release)`, `ForgetPlayers` → released · `external_disconnect` |
| O10 | on_pc | `DeviceSinkAppeared` con `routed = false` | come prima; in più, se `held` → `StartTimer(RESUME)` |
| O11 | on_pc | `TimerFired(SINK)` | `EmitError(sink_lost)`, blocco come C4, RILASCIO(`sink_lost`) (errore: ESITO_ERRORE, niente pausa) |
| O12 | on_pc | `TimerFired(RESUME)` | se `routed` → `ResumePlayers`, `held = false`, se ¬`audio_active` → `StartTimer(IDLE)` (nessun player è ripartito: vale il silenzio); se ¬`routed` (sink sparito, O9) → nulla: riparte da O10 |
| L1 | releasing | (come prima) | con PRESA(`switch`) (`pending = grab`) `held` resta e i player ripartiranno negli occhiali; altrimenti, se `held` → `ForgetPlayers`, `held = false`; poi come prima |
| L2 | releasing | (come prima) | dopo `RouteToDevice`: se `held`: se `locked` ∨ `sleeping` → `ForgetPlayers` (niente musica a schermo bloccato); altrimenti `ResumePlayers` (il rilascio è fallito: l'audio torna negli occhiali); `held = false`; `IDLE` se ¬`audio_active` |

Tutte le altre righe sono invariate. R5/U1 (prese esterne, adozioni) non mettono in pausa nulla;
O3 (`idle_timeout`) con la nuova O1 arriva solo senza audio e senza `held`; O4–O7 passano da
RILASCIO con un motivo di P; C9 e C10 non cambiano.

**Invarianti da provare** (test esaustivo su sequenze brevi, §3.2.4): in `released` e
`unavailable` vale ¬`held`; dopo ogni `PausePlayers(grab)` arriva prima o poi `ResumePlayers`
o `ForgetPlayers`; dopo un rilascio con motivo in P non arriva mai `ResumePlayers`, salvo
l'uscita da `releasing` verso una nuova PRESA (L1) o L2 senza blocco/sospensione.

**Conseguenze volute, da non «correggere»:**
- Il primo ≈ 0,5 s di audio (`grab_delay_ms`) si sente ancora dalle casse: serve a filtrare i
  suoni brevi (decisioni 18 e 44).
- L'audio senza MPRIS (giochi, chiamate nel browser) non si ferma mai (decisione 51).
- Una presa fallita riprende i player sulle casse (ESITO_ERRORE) **dopo** l'errore: con gli
  occhiali irraggiungibili il video resta fermo fino al fallimento di `Connect` (≈ 5 s su
  `casa`, M8) o al timer `CONNECT` (10 s). Poi l'anti ping-pong impedisce una nuova presa
  finché l'audio non tace per `unblock_silence_seconds`.
- Con O8 e G8 (dispositivo già sparito) qualche centinaio di ms di audio può uscire dalle casse
  prima della pausa: non c'è nulla da aspettare.
- Dopo un rilascio con pausa niente riparte da solo, nemmeno allo sblocco. L'utente riprende a
  mano e la presa automatica segue (R1); dopo O8 e G8 solo dopo `unblock_silence_seconds` di
  silenzio (anti ping-pong), come nella spec 01.
- Durante la presa la proprietà D-Bus `AudioActive` vale `false` (i player sono in pausa) e
  `IdleReleaseAt` resta 0: la UI della spec 03 deve leggere lo stato `connecting`, non
  `AudioActive`.
- Si mettono in pausa **tutti** i player in `Playing`, anche quelli senza audio (es. una
  presentazione di immagini di Gwenview): si escludono con `audio.ignore_players`. Abbinare
  player e stream per PID non è affidabile (Chrome suona da un processo figlio, i sandbox
  cambiano i PID). Un player avviato dall'utente durante la finestra `RESUME` resta com'è.

### 3.2 API D-Bus, configurazione, dati

#### 3.2.1 API D-Bus

**Invariata** (nessuna proprietà, metodo, segnale o `reason` nuovo): la chat di design usa in
parallelo il contratto della spec 01 §3.2.1 per la spec 03.

#### 3.2.2 Configurazione (decisione 56)

| Chiave | Tipo | Default | Vincoli |
|---|---|---|---|
| `policy.resume_delay_ms` | int | dal profilo: `generic` → 0, `meta_glasses` → **2000** (provvisorio, §2) | 0–10000 |
| `audio.ignore_players` | list[str] | `["kdeconnect", "plasma-browser-integration", "playerctld"]` | primo segmento del nome MPRIS |
| `backend.player_timeout_ms` | int | 1000 | 100–5000 |

Se `policy.resume_delay_ms` manca nel file, `config.py` lo risolve dal profilo al caricamento e
a ogni ricarica; `step()` riceve già il valore in `Policy` (un `RESUME` in corso resta com'è,
come gli altri timer). Nel modello creato dal demone la chiave compare **commentata** con la
spiegazione. `device.profile` passa così da «solo validato» al primo effetto (02 §2: il
comportamento di un modello sta nel profilo): basta una tabella di default in `config.py`,
senza il pacchetto `profiles/`.

#### 3.2.3 Stato persistente

`state.json` resta alla versione 1 con una chiave **opzionale**:

```json
{"version": 1, "iphone_priority": false, "restore_default_sink": null,
 "resume_players": {"bus_id": "<org.freedesktop.DBus.GetId>",
                    "players": [{"name": "org.mpris.MediaPlayer2.firefox.instance_1_2067",
                                 "owner": ":1.2081"}]}}
```

Assente o `null` = nessun player da riprendere. Il caricamento è tollerante **per voce**: una
`resume_players` malformata si scarta con `warning` senza invalidare priorità e sink salvato
(oggi `Store.load` scarta tutto: va cambiato solo per questa chiave). All'avvio la voce si usa
solo se `bus_id` è quello del bus di sessione attuale (gli owner `:1.N` si riusano dopo un
nuovo login); altrimenti si cancella. Scrittura atomica come prima. Un file della spec 01 si
carica senza errori.

#### 3.2.4 Test (Codex)

- Policy: un test per ogni regola o riga modificata o nuova (PRESA con e senza audio e con
  `held` già vero; RILASCIO per ogni motivo di P e per ogni motivo di errore; INGRESSO con
  `held`; ESITO_ERRORE con e senza `pending = release`; blocco con UNBLOCK; G8 da ogni stato;
  C4 nei due rami; C5; C6; C8 nei due rami; O1 con `held`; O8 con e senza `held`; O10 con
  `held`; O11; O12 con e senza `routed` e con e senza audio; L1 con e senza `pending = grab`;
  L2 con e senza blocco; `TimerFired(RESUME)` tardivo), con confronto esatto di contesto e
  azioni ordinate come nella spec 01.
- **Test esaustivo** sugli invarianti di §3.1.4: tutte le sequenze di 6 eventi presi da un
  insieme ridotto (`AudioActive(t/f)`, `TimerFired(GRAB_DELAY/CONNECT/SINK/RESUME/RELEASE/IDLE)`,
  `ConnectResult(ok/Failed)`, `DeviceConnected(t/f)`, `DeviceSinkAppeared/Gone`,
  `DisconnectResult(ok)`, `Locked(t)`, `Switch`, `Availability(f)`) partendo da `released`
  idoneo; solo libreria standard (nessuna nuova dipendenza).
- Flussi: presa riuscita con ripresa; presa fallita con ripresa e anti ping-pong; switch
  durante la presa (resta in pausa); doppio switch durante il rilascio (riprende negli
  occhiali); blocco durante la finestra `RESUME`; O9 durante `RESUME`.
- Adattatore: player MPRIS finti con python-dbusmock sul bus di sessione privato (oggetto
  `/org/mpris/MediaPlayer2` con `PlaybackStatus` e metodi `Pause`/`Play` che lo cambiano):
  pausa solo dei `Playing`; esclusione con `ignore_players`; ripresa di `Paused` e `Playing`
  con lo stesso owner, salto di `Stopped`, owner cambiato e nome sparito; player che non
  risponde (timeout) o dà errore; riclassificazione `grab` ↔ `release`; `forget`; nessuna
  chiamata a riposo.
- Esecutore e ciclo di vita: pausa → `RestoreRouting` → `Disconnect` in ordine;
  `PausePlayers(grab)` in parallelo a `Connect`; ripresa dopo l'instradamento; errore con la
  pausa ancora in corso; avvio con `resume_players` (stesso bus e bus diverso); `SIGTERM` con
  voci `grab` (ripresa prima dell'uscita) e con voci `release` (nessuna ripresa); `SIGTERM`
  durante `releasing`.
- Configurazione e stato: default dal profilo, chiave esplicita che vince, ricarica, limiti,
  file della spec 01, voce `resume_players` malformata.

### 3.3 Interfaccia

Nessuna UI. I testi nuovi sono solo log in inglese (decisione 27).

### 3.4 Errori e casi limite

- MPRIS assente o nessun player: le azioni non fanno nulla; presa e rilascio come nella
  spec 01.
- Player chiuso durante la presa: la ripresa lo salta.
- L'utente mette in pausa a mano durante la presa: viene ripreso (non si distingue da una
  pausa di Scambio). Accettato: la finestra è di pochi secondi.
- Crash del demone con player in pausa da una presa: al riavvio (systemd `Restart=on-failure`
  dopo 2 s) i player ripartono, sulle casse se il dispositivo non è collegato.
- Riavvio di bluetoothd con gli occhiali sul PC e audio in corso: G8 lo tratta come Bluetooth
  spento (pausa). Raro, accettato.
- Chrome in pausa chiude lo stream dopo ≈ 5 s (M5) e alla ripresa ne apre uno nuovo
  sull'uscita predefinita: è il comportamento atteso.
- KDE Connect con il telefono collegato espone i player del telefono: esclusi per default.

## 4. Fuori scope

- Pausa o ripresa della musica dell'**iPhone** (Scambio non controlla il telefono).
- Muto o volume di stream e uscite (M10, decisione 51).
- Abbinamento player ↔ stream per PID; controllo dell'audio senza MPRIS.
- Nuove proprietà o segnali D-Bus, notifiche, tray (spec 03); packaging Flatpak (fase 5).
- Pacchetto `profiles/` con comportamenti propri oltre al default di `resume_delay_ms`.

## 5. Dipendenze

Spec 01 verificata (237 test). Nessuna nuova dipendenza runtime o di sviluppo (python-dbusmock
c'è già).

## 6. Checklist di done

Ordine consigliato, un commit verde per tappa: (a) config, stato, policy con i test (compreso
l'esaustivo); (b) adattatore MPRIS; (c) esecutore, ciclo di vita, integrazione, report.

- [ ] Ogni regola nuova o modificata di §3.1.4 ha un test unitario con confronto esatto; test
      esaustivo sugli invarianti verde; i test della spec 01 restano verdi (cambiati solo dove
      §3.1.4 cambia il risultato atteso, elencati nel report).
- [ ] Adattatore MPRIS, esecutore e ciclo di vita provati con dbusmock come in §3.2.4.
- [ ] `make check` verde; nessun test saltato.
- [ ] Nessun polling, nessuna sottoscrizione nuova; unico timer nuovo `RESUME`; misura
      CPU/RSS a riposo (10 min, finti) nel report.
- [ ] Nessun valore personale hardcodato; chiavi di §3.2.2 nel modello di configurazione.
- [ ] API D-Bus invariata (XML di introspezione identico).
- [ ] `design/`, `docs/context/`, `docs/specs/`, `docs/hardware-lab.md` non modificati.
- [ ] `docs/verification/02/report.md` scritto con la checklist §6.1 e i comandi esatti;
      decisioni tecniche in `docs/decisions.md` solo se servono (58–69).
- [ ] Prova reale eseguita da GM: … · GM, data.

### 6.1 Checklist di prova reale per GM (occhiali + iPhone)

Preparazione (la fa Claude): `systemctl --user restart scambio`; journal aperto con
`journalctl --user -u scambio -f`. Configurazione invariata (profilo `meta_glasses`).

| # | Azione | Atteso |
|---|---|---|
| 0 | Misure: `python3 ~/Scrivania/Claude/scambio-misure/annuncio.py` (3 giri, ferma e riavvia Scambio da solo); poi una chiamata GSM vera, presa dal PC con un video e `scambio switch` (Q4) | Claude registra M11 e M12 in hardware-lab e, se serve, fa correggere il default di `resume_delay_ms` |
| 1 | Occhiali sull'iPhone; video YouTube in **Chrome** sul PC | ≈ 0,5 s dalle casse, poi il video si ferma; presa; annuncio da solo; il video riparte negli occhiali dal punto di pausa |
| 2 | Come 1 con **Firefox** | uguale |
| 3 | Come 1 con **Elisa** (musica locale) | uguale |
| 4 | Video sugli occhiali → **blocca** lo schermo | rilascio; video in pausa, niente dalle casse; allo sblocco nulla riparte |
| 5 | Avvia un video e **blocca** subito, mentre gli occhiali si stanno collegando | rilascio appena collegati; video in pausa |
| 6 | Video sugli occhiali → `scambio switch` | rilascio + Priorità iPhone; video in pausa |
| 7 | `scambio switch` due volte di fila, veloce, con video sugli occhiali | gli occhiali tornano al PC; il video riparte negli occhiali |
| 8 | Video sugli occhiali → **chiudi le astine** | `external_disconnect`; video in pausa; riaprendo nulla riparte da solo |
| 9 | Occhiali nella custodia chiusa (irraggiungibili); avvia un video | il video si ferma, la presa fallisce dopo ≈ 5–10 s, il video **riparte dalle casse**; nessuna nuova presa |
| 10 | Audio senza MPRIS: `paplay` di un file lungo | suona dalle casse fino alla presa, poi negli occhiali; nessuna pausa |
| 11 | Spegni il Bluetooth dal tray con video sugli occhiali | `unavailable`; video in pausa |
| 12 | Durante una presa con video: `systemctl --user kill -s KILL scambio` (lo lancia Claude) | systemd riavvia Scambio; il video riparte |

## 7. Note di revisione (Claude, dopo la consegna)

**Audit 1 — 2026-10-05** su `b8153c8`, `b7625d4`, `c260847` (report in
`docs/verification/02/report.md`; decisioni tecniche 58–63). Verificato da Claude su `casa`:
`make check` verde rieseguito (357 test, 0 saltati); file protetti (`AGENTS.md`, `design/`,
`docs/context/`, `docs/specs/`, `hardware-lab.md`, XML D-Bus) invariati; misura idle di Codex
sui finti: CPU 0 %, RSS 23 084 KiB, zero chiamate MPRIS e pactl in 600 s. Revisione statica
(agente di controllo) di policy, adattatore, esecutore, configurazione e stato contro §3: righe
PRESA, RILASCIO (passi 1–5), INGRESSO, ESITO_ERRORE, PAUSA_RILASCIO, G8, C4–C8, O1, O8, O10–O12,
L1, L2 conformi; test esaustivo su 18^6 sequenze con ¬`held` in `released`/`unavailable`.
Esito: **ok per la prova reale**, con correzioni chieste a Codex prima della prova:

1. Esecutore: un'eccezione dentro un'operazione accodata lasciava bloccate le code (i player
   sarebbero rimasti in pausa); completamenti non idempotenti.
2. Arresto: il limite di attesa partiva da `stop()` e non dalla ripresa delle voci `grab`.
3. Adattatore MPRIS: `closed` mai controllato dopo `close()`.
4. `GetId` fallito: `bus_id` vuoto cancellava `resume_players` validi.
5. `assert` in produzione e `Any` non ristretto in `players.py`.
6. Log d'errore MPRIS senza il nome del player.
7–8. Quattro test a sottoinsieme da rendere esatti; manca la riga PRESA da `Switch` con audio.

**Audit 2 — 2026-10-05** su `7da08ef` (decisioni 64–66). `make check` verde rieseguito da
Claude (390 test, 0 saltati); file protetti invariati. Verificati nel diff: completamento
idempotente e protetto da eccezioni per ogni operazione delle due code (anche `RestoreRouting`);
arresto con 2 × `player_timeout_ms` dall'inizio della ripresa delle voci `grab` e tetto
complessivo 4 × da `stop()`, arresto immediato senza voci `grab` né operazioni in corso;
`Players.close` e callback tardivi senza effetti; `bus_id` sconosciuto che conserva
`resume_players`; niente `assert`/`Any` nell'adattatore; log con il nome MPRIS; test resi
esatti e riga PRESA da `Switch` aggiunta. Percorso a riposo invariato: misura idle non ripetuta
(motivata nel report). Esito: **ok per la prova reale** (§6.1).

**Prove di Claude sul sistema reale — 2026-10-05 15:29–15:31** (servizio riavviato su
`5aa3e70`; occhiali fuori casa con GM, quindi irraggiungibili; tono in Firefox con il profilo
di M9, comandi MPRIS da `systemd-run --user`):
- **§6.1 punto 9 ok** (due volte): presa → `Paused player …firefox…` nello stesso secondo →
  `connect_failed` dopo 5 s → `Resumed player`; il tono riparte dalle casse; nessuna nuova presa
  (anti ping-pong).
- **§6.1 punto 12 ok**: `systemctl --user kill -s KILL scambio` 1,5 s dopo la pausa;
  `state.json` conteneva `resume_players` con `bus_id`; systemd riavvia dopo 3 s e il demone
  riprende Firefox prima di agganciare gli adattatori. Subito dopo parte una nuova presa (l'anti
  ping-pong non sopravvive al riavvio: accettato), finita con `connect_timeout` e ripresa.
- Rilievo minore, per la prossima unità che tocca `players.py`: alla prima pausa dopo l'avvio
  compare il warning «Cannot update resume_players without a session bus identity», perché
  `pause()` salva la riclassificazione prima di aver letto `GetId`. Innocuo: il salvataggio dopo
  la pausa riuscita avviene con `bus_id` (verificato in `state.json`).

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

Riletta da me e poi da un agente indipendente contro `AGENTS.md`, `02`, la spec 01 §3.1.5, le
decisioni 25, 44, 45, 50, 51, le misure e il codice attuale (`policy.py`, `service.py`,
`state.py`, `config.py`). L'agente ha trovato 24 punti (1 bloccante, 11 importanti); li ho
corretti tutti tranne il bloccante, che dipende da GM ed è gestito come sotto. I più importanti:
la pausa della presa che restava salvata e veniva ripresa dopo un rilascio con blocco
(riclassificazione `grab` → `release`); il blocco anti ping-pong che con i player in pausa non
cadeva mai (UNBLOCK avviato anche senza audio); la ripresa che saltava un player il cui stato
non era ancora `Paused`; `IDLE` che poteva scadere prima di `RESUME`; la ripresa prima del
ripristino dell'instradamento; arresto e avvio che avrebbero richiesto chiamate sincrone;
i player di KDE Connect (sono quelli del **telefono**) esclusi per default.

Cosa resta, e cosa correggerei se emergesse:

1. **Annuncio non misurato.** Il ritardo di ripresa per gli occhiali è provvisorio (2000 ms).
   Se l'annuncio dura di più, il video riparte sopra la coda dell'annuncio; se dura meno o
   manca, si aspetta un po' di più del necessario. Si sistema con una riga dopo la misura.
2. **Pausa di tutti i player in `Playing`.** Non si sa quale player suona davvero; si escludono
   i proxy noti. Se GM usa un player che non vuole fermare, va in `ignore_players`.
3. **Pausa manuale durante la presa** viene annullata dalla ripresa: finestra di pochi secondi.
4. **Decisioni tecniche mie, da confermare se GM non è d'accordo** (55): Bluetooth spento
   **durante** una presa = presa fallita, l'audio riparte dalle casse; rilascio fallito a schermo
   bloccato = i player restano in pausa; occhiali che cadono subito dopo la presa (prima della
   ripresa) = errore, l'audio riparte dalle casse.
5. **Dimensione.** Più piccola della spec 01: tre tappe, la policy è il grosso.

## 9. Domande aperte

Nessuna bloccante per il `/goal`. Q4 e la durata dell'annuncio si misurano al punto 0 della
prova reale. Resta Q1 (licenza) e Q5 (portal, spec 04).

## Comando `/goal`

```
/goal Implementa docs/specs/02-pausa-durante-scambio.md seguendo AGENTS.md e docs/context/.
Fatto solo quando ogni voce della Checklist di done (§6) è soddisfatta con evidenza e
`make check` è verde. Scope: solo §3; §4 non si tocca; design/, docs/context/, docs/specs/ e
docs/hardware-lab.md non si modificano; mai Bluetooth, pactl o player MPRIS reali nei test.
Lavora nelle tre tappe di §6, un commit verde per tappa, solo con i file del tuo scope (mai
graphify-out/, mai `git add -A`). Stop: se la spec contraddice AGENTS.md o manca una decisione
di prodotto, fermati e scrivilo nel report.
```
