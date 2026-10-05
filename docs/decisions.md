# Decisioni

Append-only. Una riga per decisione: numero, data, autore, decisione, motivo breve. Una decisione
superata non si cancella: se ne aggiunge una nuova che la cita («supera n. X»).

## 2026-10-04 — Fase 0 (decise da GM con Claude)

1. GM — Nome del prodotto: **Scambio** (lo scambio ferroviario). Verificati conflitti e dominio
   `scambio.app` libero il 4 ottobre 2026.
2. GM — Posizionamento ibrido: marchio e marketing sugli smart glasses; core indipendente dal
   dispositivo; funzioni glasses avanzate premium.
3. GM — Modello open-core: core open source gratuito, moduli premium in pacchetto separato.
4. GM — Presa automatica quando parte audio sul PC, anche se il telefono usa il dispositivo, con
   pausa/muto automatico dello stream durante la connessione.
5. GM — Rilascio dopo 120 s di silenzio (`release_idle_seconds`, configurabile); immediato con
   blocco schermo e sospensione.
6. GM — Interruttore «Priorità iPhone» nel tray; si spegne solo a mano.
7. GM — Scorciatoia globale «switch intelligente»: dispositivo sul PC → rilascio + priorità on;
   altrimenti presa + priorità off.
8. GM — Scorciatoia di default **Meta+G** (scartata Ctrl+Shift+S: è «Salva con nome» in molte app).
9. GM — Interfacce: una sola app (demone + client sottili via D-Bus); v1 tray + notifiche +
   finestra GTK4/libadwaita; dopo, widget Plasma e Impostazioni rapide GNOME.
10. GM — Design di proprietà di Claude (`design/`); Codex scrive tutto il codice.
11. GM — Metodo «Kuchl-lite»: sei file di contesto, spec piccole, audit, hardware-lab al posto
    dello stato narrativo.
12. GM — Brain AGVM dedicato `scambio_brain`, consultivo, scritto alle milestone.
13. GM — Repository solo su `casa`: nessun remote, nessuna GitHub Actions; gate locali con
    `make check` e hook pre-commit.
14. GM — Lingue it, en, de dal primo giorno.

## 2026-10-04 — Fase 0 (tecniche, Claude)

15. Claude — Un solo main loop GLib, D-Bus via Gio, nessun polling; dipendenze runtime limitate a
    PyGObject/GTK4/libadwaita.
16. Claude — Scorciatoia via XDG Desktop Portal GlobalShortcuts con riserva CLI (`scambio switch`);
    la vecchia scorciatoia khotkeys di GM (Ctrl+Shift+O) va disattivata all'installazione.

## 2026-10-04 — Dominio e identificativi

17. GM — Dominio **scambio.app** acquistato (account Cloudflare personale di GM). Ne derivano
    l'app-id `app.scambio.Scambio` (Flatpak, file .desktop, icone) e il nome D-Bus del demone
    `app.scambio.Scambio` (oggetto `/app/scambio/Scambio`): Flatpak consente di possedere solo nomi
    D-Bus sotto il proprio app-id.

## 2026-10-04 — Spec 01, demone headless

18. GM — La presa automatica parte solo se l'audio resta attivo per almeno 1 s
    (`policy.grab_delay_ms = 1000`, configurabile): filtra i suoni brevi senza ruolo.
19. GM — Attivare la Priorità iPhone mentre il dispositivo è sul PC lo rilascia subito, come lo
    switch.
20. GM — Approvata la dipendenza runtime `pactl` ≥ 16 (`pulseaudio-utils`): esclude Ubuntu
    22.04; nel Flatpak andrà inclusa.
21. Claude — Eventi audio: sottoprocesso `pactl -f json subscribe` con `LC_ALL=C`, parsing
    incrementale con `raw_decode` (M4), istantanee `pactl -f json list` coalescenti a 50 ms,
    riavvio con attesa crescente. Scartati: `pw-dump --monitor` (scarica oggetti interi a ogni
    modifica, verboso e costoso), libpulse via ctypes (strutture ABI a mano, fragile con mypy
    strict; resta possibile come backend alternativo dietro la stessa interfaccia), binding
    PipeWire nativi (nessun binding Python mantenuto). «Silenzio» = nessuno stream non `corked`
    e non escluso; nessuna misura di livello (costerebbe CPU). M5 conferma che basta per Chrome.
22. Claude — Instradamento: con il dispositivo sul PC l'uscita predefinita è il dispositivo
    (comportamento da cuffia: anche le notifiche vanno lì). Scambio la imposta solo se WirePlumber
    non l'ha già fatto, salva il predefinito precedente nello stato persistente e lo ripristina al
    rilascio, all'arresto e all'avvio dopo un crash.
23. Claude — Stato persistente (Priorità iPhone, predefinito da ripristinare) in
    `~/.local/share/scambio/state.json`, scritto in modo atomico; `config.toml` è solo letto dal
    demone (lo crea come modello se manca). `policy.iphone_priority` esce dalla configurazione.
24. Claude — Blocco schermo = `LockedHint` di logind (sessione da `User.Display`, perché un
    servizio utente non appartiene alla sessione) OR `org.freedesktop.ScreenSaver.Active`;
    sospensione con `PrepareForSleep` e inibitore `delay`.
25. Claude — `core/policy.py` è una funzione pura `step(ctx, event, config)`; i timer sono azioni
    ed eventi. Regola anti ping-pong: dopo una presa fallita o una perdita esterna con audio
    attivo, nessuna presa automatica finché l'audio non tace.
26. Claude — Interfaccia D-Bus `app.scambio.Scambio1` su `/app/scambio/Scambio` (nome del bus
    invariato, decisione 17); il suffisso 1 permette versioni future senza rompere i client.
27. Claude — Testi della CLI: msgid inglesi marcati con gettext; i cataloghi it/de arrivano con
    la spec 03. Stati e codici d'errore sono stringhe stabili non tradotte.
28. Claude — Servizio utente systemd `Type=dbus` legato a `graphical-session.target`;
    `make install-user` installa la unit senza abilitarla né avviarla.
29. GM — Approvata la spec 01 con tre eccezioni/conferme: (a) `make install-user` può scrivere
    `~/.config/systemd/user/scambio.service`, solo se lanciato a mano (il demone non scrive mai
    fuori da `~/.config/scambio/` e `~/.local/share/scambio/`); (b) fino alla spec 03 testi della
    CLI, commenti del modello di configurazione e motivo dell'inibitore di sospensione sono in
    inglese (eccezione temporanea all'invariante it/en/de); (c) confermati i comportamenti
    ricavati: nessuna presa automatica a schermo bloccato; anti ping-pong dopo prese fallite o
    perdite esterne; l'arresto di Scambio non scollega il dispositivo; con il dispositivo sul PC
    anche le notifiche vanno lì; una connessione manuale esterna viene rispettata anche con
    Priorità iPhone attiva.
## 2026-10-04 — Spec 01, implementazione (Codex)

30. Codex — Eventi e azioni immutabili e contesto copiato per `step`; `last_error` nel
    contesto rende verificabile l'azzeramento previsto da PRESA/INGRESSO senza I/O.
    I callback obsoleti e i timer cancellati saranno scartati dall'esecutore/adattatori.
31. Codex — Sezione tecnica opzionale `[backend]` per rispettare l'invariante dei tempi
    configurabili: `coalesce_ms=50`, `retry_initial_seconds=1`, `retry_max_seconds=30`,
    `dbus_margin_seconds=5`, `dbus_timeout_seconds=10`. Interi positivi fino a 60000;
    retry iniziale non superiore al massimo. Nessun nuovo timer periodico.
32. Codex — Precedenza alla procedura C5 per il reason `connect_timeout`, omesso per
    svista dall'elenco riassuntivo di §3.2.1 ma esplicitamente prescritto dalla tabella.
    Nessuna nuova proprietà/metodo/segnale D-Bus. Arresto senza ripristino secondo
    §3.1.6 e decisione 29; riparazione al successivo avvio se scollegato.
33. Codex — Stubs PyGObject fissati a 2.10.0: la versione corrente 2.17 richiede
    PyGObject >=3.55 da pip e non è compatibile con l'obbligo di usare gi di sistema.
    Venv con `/usr/bin/python3 --system-site-packages`; runtime pip vuoto.
34. Codex — Adapter Gio con generazioni per scartare callback tardivi; BlueZ accoda
    segnali durante GetManagedObjects, pubblica Connected prima di Availability(true).
    Session deduplica l'OR e invalida risposte iniziali superate da segnali; fd di
    inibizione tardivi vengono chiusi. Protocol separati senza dipendenze Gio.
35. Codex — Instradamento serializzato, con istantanea fresca prima di ogni azione;
    il ripristino termina (anche in errore) prima di cancellare lo stato salvato.
    Snapshot e azioni usano solo il comando pactl iniettato esplicitamente.
36. Codex — Il servizio attende le prime letture di tutti gli adattatori, applica
    prima lock/sleep e poi audio/connessione/disponibilità. Ripara l'instradamento
    prima dell'adozione solo se il dispositivo risulta scollegato. I comandi di
    priorità durante l'avvio sono persistiti immediatamente.
37. Codex — Ripristino asincrono prima di Disconnect, con timer RELEASE e SLEEP
    indipendenti: un backend audio lento non impedisce la scadenza dell'inibitore.
    Il backend pactl assente/vecchio resta disabilitato anche durante RestoreRouting.
38. Codex — Harness di processo e misura idle richiedono indirizzi dbusmock per
    entrambi i bus e un finto pactl esplicito. CPU misurata come delta dei tick
    /proc su 600 secondi monotoni, RSS ai due estremi; nessun campionamento periodico.
    I timer accelerati sono iniettati solo dai test; nessuna opzione di produzione.

## 2026-10-04 — Spec 01, correzioni dopo audit 1 (Codex)

39. Codex — Un solo tentativo di recupero audio pendente: un guasto invalida la
    generazione e marca il backend indisponibile fino al prossimo tentativo; ulteriori
    guasti/istantanee durante l'attesa non aumentano il backoff. Il riavvio rimuove
    esplicitamente il timer precedente. Solo un'istantanea pubblicata con successo
    ripristina il ritardo iniziale.
40. Codex — `[backend].command_timeout_seconds=10` limita tutti i figli pactl finiti
    (versione, istantanee e instradamento); il processo subscribe resta guidato da eventi.
    Alla scadenza il figlio viene terminato e raccolto, e l'operazione si conclude come
    fallita. La coda chiude ogni operazione anche in caso di eccezione nei callback.
41. Codex — Supera la cancellazione in errore della voce 35: un ripristino senza
    istantanea affidabile o con comando fallito conserva il sink salvato. Si cancella
    dopo successo oppure quando un'istantanea valida dimostra che il sink non esiste
    più o che il predefinito è già cambiato. Senza sink salvato non si scrive lo stato.
    La sottoscrizione decodifica UTF-8 con sostituzione; JSON completo malformato o
    eccezioni di lettura invalidano il backend e riavviano una sola sottoscrizione.
42. Codex — Il segnale pubblico `Error` separa codice stabile e descrizione tecnica
    inglese tramite una mappa dell'esecutore; la policy continua a produrre solo codici.
    Nessun nuovo codice o firma D-Bus. C7 conserva `sink_timeout` dopo INGRESSO come
    richiesto dalla spec corretta; `connect_timeout` resta invariato (voce 32 ora
    confermata dall'elenco dei reason di §3.2.1).
43. Codex — L'acquisizione dell'inibitore è vietata mentre `Session.sleeping` è
    vero, inclusi riaggancio del proprietario logind, cambio User.Display e risposta
    asincrona tardiva. I fd tardivi vengono chiusi; solo il segnale di risveglio
    consente una nuova acquisizione. La disinstallazione tollera gli esiti non zero
    di stop/disable (unit assente o inattiva), elimina il file se presente e conserva
    il controllo d'errore su daemon-reload. Test con destinazione temporanea e
    subprocess sostituito, senza invocare systemctl.

## 2026-10-04 — Prova reale spec 01 (GM)

44. GM — Ritardo di presa ridotto a 0,5 s (`policy.grab_delay_ms = 500`, supera la 18 sul
    valore): la presa con 1 s gli è sembrata lenta. In più la pausa durante lo scambio (spec 02)
    deve coprire anche l'annuncio vocale degli occhiali alla connessione («connessione stabilita
    su casa»), che ritarda l'audio e non serve: va misurata la sua durata prima della spec 02.
45. Claude — Anti ping-pong più robusto dopo la prova reale (M8): il blocco si azzera solo dopo
    `policy.unblock_silence_seconds` (default 10 s) di silenzio continuo, non al primo istante
    senza stream; il Bluetooth spento mentre il dispositivo è sul PC conta come perdita esterna.
    Motivo: Chrome ricrea lo stream quando cambia l'uscita, e il buco veniva letto come silenzio.

## 2026-10-05 — Correzioni dopo la prova reale spec 01 (Codex)

46. Codex — UNBLOCK usa l'esecutore dei timer già esistente: G1 avvia/riarma
    la scadenza solo con audio inattivo e blocco presente, la ripresa dell'audio
    la cancella; G1b azzera solo il blocco, senza presa immediata. RILASCIO e G8
    conservano il timer. Restano valide le guardie dell'esecutore sui callback
    cancellati o sostituiti, verificate anche con tempo controllato nei test.
    Il nuovo campo è aggiunto in coda a Policy, conservando l'ordine dei campi
    precedenti; file di configurazione esistenti e servizio in esecuzione non
    vengono modificati. Il default 500 ms vale dove manca un valore esplicito.
47. Codex — Regressioni del servizio con BlueZ dbusmock e finto pactl reali
    come processi su bus privati; solo il pianificatore della policy è iniettato.
    Il test usa ID GLib cancellabili e avanzamenti deterministici a 2 s, 9,999 s,
    10 s e 500 ms, verificando contesto intero, timer e chiamate Connect registrate
    dal mock. Nessun sonno, polling o orologio aggiunto al runtime.

## 2026-10-05 — Orchestratore (dopo la chiusura della fase 1)

48. GM — Avvio automatico di Scambio al login da subito: `systemctl --user enable
    scambio.service` (legato a `graphical-session.target`, attivo su Plasma 5.27 di casa).
    Si disattiva con `systemctl --user disable scambio.service`.
49. GM — Prossime unità in parallelo: chat di design per il mock UI (tray, menu, notifiche,
    finestra impostazioni; poi spec 03 tray) e chat di sviluppo per la spec 02 (pausa MPRIS
    durante lo scambio, annuncio vocale degli occhiali) affidata a Codex. Non si sovrappongono:
    `design/` è di Claude, il core di Codex.

## 2026-10-05 — Spec 02, pausa durante lo scambio (chat di sviluppo)

50. GM — Al rilascio con audio in corso sul PC (blocco schermo, sospensione, switch, Priorità
    iPhone, perdita esterna come astine chiuse o custodia, Bluetooth spento) Scambio mette in
    pausa i player MPRIS e **non** li riprende: come cuffie tolte su un telefono. Non vale per
    il rilascio dopo un errore (un errore non lascia mai l'audio in pausa, 02 §6).
51. GM — Durante la presa l'audio che non si può mettere in pausa (app senza MPRIS: giochi,
    chiamate nel browser) resta sulle casse finché il dispositivo è pronto; nessun muto.
52. Claude — `graphify-out/` non si versiona: tutto il contenuto (grafo, report, istantanee
    datate, etichette, cache) è derivato e si ricostruisce dopo ogni commit, quindi lasciava la
    repo sempre modificata. Rimosso dall'indice e messo in `.gitignore`; regola in `AGENTS.md` e
    `04` §6.
53. Claude — Pausa e ripresa solo via MPRIS (`Pause`/`Play`) dall'adattatore `players.py`, a
    richiesta, senza segnali né timer propri: si mettono in pausa tutti i player in `Playing`
    tranne `audio.ignore_players` (default: `kdeconnect`, `plasma-browser-integration`,
    `playerctld`). Scartati: abbinamento player ↔ stream per PID (Chrome suona da un processo
    figlio, i sandbox cambiano i PID) e il muto degli stream (M10).
54. Claude — Policy: contesto `held`, timer `RESUME`, azioni `PausePlayers(grab|release)`,
    `ResumePlayers`, `ForgetPlayers`; «audio in corso» = `audio_active ∨ held` per IDLE e anti
    ping-pong; i rilasci per `locked`/`sleep`/`switch`/`priority` tengono la pausa, quelli per
    errore riprendono (spec 02 §3.1.4).
55. Claude — Casi limite della decisione 50: Bluetooth spento durante una presa e occhiali
    caduti prima della ripresa contano come presa fallita (l'audio riparte dalle casse); un
    rilascio fallito a schermo bloccato o in sospensione lascia i player in pausa; un errore
    dopo che l'utente aveva già chiesto il rilascio (switch, priorità, blocco) li lascia in
    pausa.
56. Claude — `policy.resume_delay_ms` (0–10000) con default dal profilo: `generic` 0,
    `meta_glasses` 2000 provvisorio finché non si misura l'annuncio (prova reale spec 02).
    Primo effetto di `device.profile`, con una tabella in `config.py`.
57. GM — Approvata la spec 02 con il ritardo di ripresa provvisorio di 2 s e i casi limite della
    decisione 55; misure dell'annuncio e di Q4 al punto 0 della prova reale.

## 2026-10-05 — Spec 02, implementazione (Codex)

58. Codex — Configurazione risolta al caricamento per profilo; stato opzionale MPRIS
    tipizzato separatamente e validato senza perdere priorità o sink se malformato.
    Esplorazione esaustiva della policy con programmazione dinamica: si raggruppano
    prefissi con contesto e obbligo di ripresa uguali, conservando la molteplicità
    di tutte le 18^6 sequenze. Gli obblighi residui hanno una continuazione di
    chiusura verificata; nessuna pretesa di liveness con eventi infiniti arbitrari.
59. Codex — MPRIS: owner e PlaybackStatus letti in parallelo; comandi indirizzati
    all'owner unico verificato, senza auto-attivazione. GetId è memorizzato per la
    connessione; ListNames/GetId precedono le RPC ai player (lettura + comando,
    ciascuna con player_timeout_ms). Ogni Pause riuscita viene persistita subito,
    così un player lento non ritarda il salvataggio degli altri. Nessun segnale
    o timer dell'adattatore; cancellazione Gio alla chiusura.
60. Codex — Due code FIFO nell'esecutore (player e instradamento), con contatori di
    completamento e dipendenze solo verso operazioni precedenti: la pausa di rilascio
    sblocca RestoreRouting, la ripresa aspetta tutti gli instradamenti precedenti.
    Connect e i timer della policy restano indipendenti. All'arresto si drena il
    prefisso dei player prima di distinguere grab/release; un watchdog di ciclo di
    vita a 2 × player_timeout_ms chiude Gio e il loop se il prefisso non termina.
    È distinto dall'unico nuovo timer della policy, RESUME, ed esiste solo in stop.
61. Codex — Precisazione della 59: discovery (ListNames/GetId) e letture dei player
    condividono una scadenza monotona di player_timeout_ms; alle RPC di lettura
    successive si passa solo il budget residuo. Il comando dispone al massimo di
    un secondo player_timeout_ms. Nessun timer dell'adattatore: la scadenza si
    applica ai timeout Gio, anche nel recupero all'avvio. Le scritture atomiche e
    l'esecuzione dei callback restano soggette alla latenza del sistema.
62. Codex — Harness automatici e misura idle usano app.scambio.Test esclusivamente
    su bus dbusmock privati; CLI di prova isolata prima dell'import del client.
    Nome e XML pubblici di produzione invariati. La misura registra anche SHA-256
    dei sorgenti caricati e il numero di RPC MPRIS ai finti fra i due campioni.
63. Codex — Durante stop, le riprese ordinarie ancora accodate diventano no-op e
    non aspettano più il routing; resta shutdown a riprendere solo le voci grab.
    Le pause/forget già richieste si drenano entro il watchdog, senza avviare
    nuovi instradamenti. Evita di riprendere voci release dopo SIGTERM quando un
    ResumePlayers di L2 aspettava ancora RouteToDevice; regressione sui due kind.


## 2026-10-05 — Spec 02, correzioni audit 1 (Codex)

64. Codex — Ogni operazione delle code player/routing riceve un completamento
    idempotente. Un'eccezione sincrona viene registrata senza payload remoto e
    completa l'operazione, liberando la coda. RestoreRouting protegge anche il
    proprio contatore e la disconnessione differita: callback duplicati o tardivi
    non completano operazioni successive e non decrementano due volte il contatore.
65. Codex — Correzione del budget di arresto della 60, mantenendo il trattamento
    delle operazioni accodate della 63: il limite di 2 × player_timeout_ms parte
    dall'inizio di shutdown/ripresa, dopo il prefisso player già richiesto. Un
    limite complessivo di 4 × player_timeout_ms decorre da stop e include l'attesa
    dell'operazione in corso. Entrambi dipendono dalla configurazione e vengono
    rimossi alla conclusione; esistono solo durante l'arresto. Senza voci grab e
    senza operazioni pendenti, stop conclude nello stesso giro, senza attesa.
    Se il tetto complessivo scade, le voci grab persistite restano recuperabili
    all'avvio seguente, come prima. Nessun nuovo timer della policy.
66. Codex — Players.close cancella le RPC e completa una sola volta le operazioni
    pendenti; metodi e callback tardivi non creano client né modificano lo stato.
    Senza GetId valido, salvataggio/recupero conservano resume_players e registrano
    un warning: identità sconosciuta non equivale a bus diverso. Il confine Gio
    valida le risposte come stringa, tupla di nomi o risultato vuoto; niente Any
    né assert nell'adattatore. Gli errori ai player indicano il nome MPRIS noto,
    anche per GetNameOwner; il payload remoto non finisce nel log.
