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

## 2026-10-05 — Mock UI e spec 03 (chat di design; numeri 70–89 riservati)

70. GM — Notifiche solo per l'essenziale: errori e Priorità iPhone cambiata da fuori dalla UI
    (scorciatoia, CLI). Prese e rilasci automatici restano silenziosi: lo stato lo dice l'icona.
71. GM — Clic sinistro sull'icona del tray = apre lo stesso menu del destro (`ItemIsMenu`); lo
    switch rapido resta la scorciatoia.
72. GM — Icone del tray, variante B del mock: occhiali + emblema di dove sono (telefono, monitor,
    lucchetto per la Priorità iPhone); lenti piene quando sono sul PC.
73. GM — Nei testi resta «iPhone» (anche «Priorità iPhone»); il passaggio a «telefono» per gli
    utenti Android si fa prima della release pubblica, cambiando solo i cataloghi.
74. Claude — Tray e notifiche girano nel processo del demone, solo con Gio (nessun GTK), e parlano
    col servizio tramite un proxy D-Bus sul suo stesso nome, con chiamate solo asincrone. La
    configurazione della UI arriva con `apply_config` dopo un `Reload` riuscito (stesso processo,
    non è stato del demone). La finestra (spec 04) è un processo separato su richiesta. Motivo:
    zero processi e memoria in più per la parte sempre attiva.
75. Claude — La presentazione è dati di design: `design/ui/tray.json` (regole stato → icona e
    testi, voci del menu, notifiche) caricato e validato a runtime; testi con chiavi gettext
    simboliche (`msgid` = chiave), `en.po` obbligatorio. Motivo: il design resta di Claude senza
    toccare il codice.
76. Claude — Icone con il prefisso dell'app-id (`app.scambio.Scambio-<stato>-symbolic`, pronte
    per l'export Flatpak) in `design/icons/hicolor/scalable/status/`, passate al tray con
    `IconThemePath`; icona delle notifiche per percorso assoluto. Nessun file installato fuori
    da `~/.config/scambio/` e `~/.local/share/scambio/`. La cartella è quella misurata in M11.
77. Claude — Nessun timer nella UI: niente animazioni; minuti al rilascio calcolati all'apertura
    del menu, ora assoluta nel tooltip; correlazioni delle notifiche per ordine dei messaggi
    D-Bus (il servizio emette `Transition` prima di `PropertiesChanged` e `PropertiesChanged`
    prima della risposta ai metodi).
78. Claude — Riga di stato del menu senza icona (dbusmenu cerca le icone nel tema di sistema);
    errore «attivo» con icona d'errore e `NeedsAttention` finché l'utente non lo vede (menu
    aperto o notifica) o finché `LastError` torna vuoto.
79. Claude — «Esci da Scambio» chiama il nuovo metodo `Quit()`: arresto ordinato come `SIGTERM`,
    uscita 0, systemd non lo riavvia fino al prossimo login.
80. Claude — Nuove chiavi `ui.tray` e `ui.notifications` (default `true`); `ui.language` ha
    effetto su tray, notifiche, CLI e motivo dell'inibitore.
81. Claude — «Impostazioni…» resta nascosta nel menu fino alla spec 04. «Riprova» non c'è dopo
    un rilascio fallito (uno switch accenderebbe la Priorità iPhone); `audio_backend_down` si
    notifica solo all'avvio (a runtime è un riavvio di PipeWire, che si recupera da solo).
82. Claude (da approvare da GM) — I commenti del modello di `config.toml` restano in inglese:
    file tecnico come il codice (precisa la 29b).
83. Claude (da approvare da GM) — Nella CLI restano in inglese solo le parole proprie di
    `argparse` («usage:», «options:», errori di sintassi); tutti gli altri testi hanno chiavi
    it/en/de (precisa la 29b).
84. GM — All'approvazione della spec 03 (2026-10-05): approvata la 83 (parole di `argparse` in
    inglese); **respinta la 82**: i commenti del modello di `config.toml` si traducono, con le
    chiavi `config-*` di `design/i18n/` nella lingua del momento in cui il file viene creato.
    Le decisioni tecniche di Codex per la spec 03 partono da 90.

## 2026-10-05 — Spec 02, prova reale (chat di sviluppo; numeri 67–69 riservati alla spec 02)

67. GM — Q4 chiusa senza misura: la presa durante una chiamata GSM si considera uguale a
    WhatsApp (M2); a casa non c'è rete per provarla.
68. Claude — Correzione di L1 dopo la prova reale (M12): `DisconnectResult(ok)` con
    `device_connected` ancora vero non chiude il rilascio; si aspetta `DeviceConnected(false)`
    (o la scadenza di `RELEASE`, che con il dispositivo ancora collegato vale L2). BlueZ può
    rispondere a `Disconnect()` prima di emettere `Connected=false`: ripartire subito con la
    presa (doppio switch) faceva leggere quel segnale ritardato come presa fallita. Il default
    `resume_delay_ms = 2000` per `meta_glasses` resta definitivo (M11).

## 2026-10-06 — Spec 03, implementazione (Codex)

90. Codex — Cataloghi compilati in `build/locale`, ignorata da git; risoluzione
    della lingua pura condivisa da CLI, commenti e inibitore. Il modello TOML
    conserva una base senza prosa per gli harness e genera i commenti solo alla
    creazione del file. I file esistenti non vengono riscritti. La UI richiede
    cataloghi validi; CLI e inibitore possono ripiegare su inglese o chiavi.
91. Codex — Presentazione pura con validazione chiusa del vocabolario JSON;
    adattatori Gio separati. Il proxy mantiene il numero di chiamate proprie in
    corso e inoltra i segnali in ordine. Le notifiche serializzano le richieste
    Notify per conoscere l'id di sostituzione anche nelle raffiche; generazioni
    dell'errore impediscono che una vecchia notifica cancelli un errore più recente.
    Nessun timer o dipendenza runtime aggiunta.
92. Codex — Il servizio avvia sempre la UI alla fine della prima inizializzazione
    degli adattatori, dopo nome e oggetto API: la prima lettura asincrona include
    anche `audio_backend_down` iniziale. La UI usa solo il proxy per lo stato;
    `apply_config` resta l'aggancio diretto previsto. Gli import Gio del lifecycle
    sono differiti, così importare `ui.presentation` non carica `gi` indirettamente.
93. Codex — `Quit` restituisce la risposta e percorre lo stesso stop dei segnali;
    `run` chiude il main loop dopo il completamento di `Gio.DBusConnection.flush`.
    SNI/dbusmenu si ritirano nel cleanup. XML SNI/dbusmenu nel pacchetto accanto
    all'XML pubblico; nessuna nuova dipendenza, processo o timer della UI.
94. Codex — Misura spec 03 con due campioni `/proc` distanti 600 s, come la 38:
    baseline prima delle modifiche, poi UI attiva con watcher e notifiche dbusmock.
    Si contano anche le chiamate ai due server durante l'intervallo e si salvano
    gli hash dei sorgenti UI. Il campione conclusivo viene ripetuto dopo gli
    ultimi cambi runtime; test umani e verifica visiva restano separati.

## 2026-10-06 — Spec 03, audit (chat di audit; numeri 85–89)

85. Claude — `Activate` del tray risponde con l'errore `org.freedesktop.DBus.Error.NotSupported`
    invece di riuscire senza effetti. Motivo (M14): Plasma 5.27 non guarda `ItemIsMenu`; al clic
    sinistro chiama `Activate` e apre il menu solo se la chiamata fallisce, quindi con la versione
    consegnata il clic sinistro non faceva nulla e la decisione 71 non era rispettata. È lo stesso
    comportamento delle app basate su libappindicator, che `Activate` non lo implementano.

## 2026-10-07 — Orchestratore (dopo la chiusura della fase 3)

99. Claude — La vecchia scorciatoia khotkeys di GM «Connetti Oakley» era stata spostata da GM su
    **Meta+G** e chiamava `bluetoothctl` direttamente, scavalcando il demone. Il comando è stato
    sostituito con `~/development/scambio/.venv/bin/scambio switch` (backup
    `~/.config/khotkeysrc.bak-20261007-scambio`): stesso tasto, ora passa dalla policy (Priorità
    iPhone compresa). La spec 04 deve **rimuovere** questa azione khotkeys quando registra Meta+G
    via portal, altrimenti i due binding si contendono il tasto. Fasce: spec 04 usa 100–119.

## 2026-10-07 — Spec 04, scorciatoia e finestra (chat di sviluppo: 100–109; Codex: 110–119)

100. GM — Finestra impostazioni «essenziale»: in cima stato + switch + Priorità iPhone; poi
     dispositivo (scelto fra quelli accoppiati), minuti di silenzio prima del ritorno all'iPhone,
     scorciatoia, icona nel tray, notifiche, lingua e un collegamento al file di configurazione.
     Ritardo di presa, app ignorate, tempi e profilo restano solo nel file. L'avvio all'accesso va
     con il packaging (fase 5). Mock approvato da GM il 2026-10-07 (chiaro e scuro, su `casa`).
101. GM — La finestra si apre da «Impostazioni…» nel tray **e** da un'icona «Scambio» nel menu delle
     applicazioni (file `.desktop`); se il demone è fermo, la finestra lo dice con un banner e il
     pulsante «Avvia».
102. Claude — Scorciatoia: su Plasma si registra con **KGlobalAccel su D-Bus**
     (`org.kde.kglobalaccel`), perché su Plasma 5.27 il portal GlobalShortcuts non lega nessuna
     scorciatoia (M16); sugli altri desktop si usa il portal GlobalShortcuts v1; senza nessuno dei
     due la finestra spiega come legare un tasto a `scambio switch`. KGlobalAccel si sceglie solo se
     il nome ha già un proprietario o se `XDG_CURRENT_DESKTOP` contiene `KDE` (il solo file di
     attivazione, installato anche su GNOME dalle librerie KDE, non basta). Plasma 6 non è
     misurato: se i metodi a interi falliscono si ripiega sul portal. Nessuna dipendenza nuova.
     Supera la decisione 16 nella parte «via portal»; la riserva CLI resta. Registra il demone;
     la pressione passa dall'API pubblica (`Switch()`, come tray e CLI: invariante di `AGENTS.md`);
     il file `kglobalshortcutsrc` lo scrive il servizio del desktop, non Scambio.
     Precisa la 99: l'azione khotkeys la rimuove Claude a mano, con backup, prima della prova
     reale; il codice di Scambio non tocca mai i binding dell'utente.
103. Claude — Regole di registrazione con KGlobalAccel (M16, M18): componente
     `app.scambio.Scambio`, azione `switch`; il tasto preferito (`shortcut.preferred`) si impone
     senza autoload solo la prima volta o quando cambia (memoria in `state.json`), poi vale quello
     del desktop; un tasto scelto dall'utente (`yourShortcutsChanged`) conta come «imposto», così
     non viene mai sovrascritto; tasto occupato → stato `conflict` con il nome di chi lo usa, nuovo
     tentativo all'apertura e al ritorno del focus della finestra, a `Reload` e su richiesta;
     all'arresto `setInactive` (il tasto resta all'utente).
104. Claude — Il demone scrive `config.toml`, ma solo su richiesta della finestra (`SetConfig`) e solo
     per le chiavi esposte: modifica riga per riga che conserva commenti (anche in coda alla riga)
     e chiavi non toccate, verifica rileggendo il risultato, scrittura atomica; forme TOML fuori
     dalla grammatica supportata → rifiuto senza toccare il file. Precisa la spec 01 §3.2.3 («non
     la riscrive mai»): resta vero per tutto il resto.
105. Claude — Cambio di dispositivo dalla finestra: permesso solo se il dispositivo non è sul PC né in
     passaggio (altrimenti errore `DeviceBusy`); il demone scrive il file, risponde e chiede a
     systemd `RestartUnit` della propria unità (arresto ordinato e nuovo avvio, M18: un'uscita con
     codice non riavvia un servizio `Type=dbus`). Solo se l'ultimo segmento di `/proc/self/cgroup`
     è `scambio.service`; altrimenti risponde `RestartRequired` (file già scritto).
106. Claude (parte sui file fuori dalle cartelle di Scambio approvata da GM il 2026-10-07) — Finestra in un
     processo separato `scambio settings` (GTK4 + libadwaita ≥ 1.4, unica istanza
     `app.scambio.Scambio.Settings`); il tray la apre con `org.freedesktop.Application.Activate`
     tramite attivazione D-Bus, così non vive nel gruppo di processi del demone. `make install-user`
     installa anche il file `.desktop` e il file di servizio D-Bus in `~/.local/share` (strumento di
     installazione, come l'unità systemd già in `~/.config/systemd/user`; il demone continua a non
     scrivere fuori dalle sue cartelle). `blueprint-compiler` (0.12) è una dipendenza di sviluppo:
     il `.blp` si compila in `build/`.
107. Claude — Modifiche applicate subito, senza pulsante «Salva» (convenzione libadwaita); la lingua
     della finestra cambia alla riapertura (tray, notifiche e CLI subito). Mentre la finestra è **in
     primo piano** (possiede il nome `app.scambio.Scambio.Settings.Active` solo finché è attiva) le
     notifiche della famiglia `priority` non partono: lo stato si vede già lì. Finestra aperta ma
     dietro o ridotta → notifiche normali (es. Meta+G mostra «Annulla»).
108. Claude — Icona del tray che restava visibile dopo `ui.tray = false` + `Reload` (M17): il tray
     possiede il nome `org.kde.StatusNotifierItem-<pid>-1` e si registra con quello; spegnendo il
     tray lo rilascia e il watcher lo toglie. Chiude il debito annotato nell'audit della spec 03.
109. Claude — I testi del `.ui` compilato si traducono con lo stesso `Translator` della UI (proprietà
     `translatable` sostituite prima del caricamento), non con il gettext di libc di GtkBuilder:
     così valgono `ui.language` e i cataloghi in `build/locale` anche con `LANG=C`.

## 2026-10-07 — Spec 04, implementazione (Codex: 110–119)

110. Codex — Conversione GTK/Qt/XDG in `core/shortcut_keys.py`, modulo puro;
     `core/shortcuts.py` possiede le chiamate Gio e le sottoscrizioni, con
     generazioni per scartare risposte obsolete dopo reload, perdita del nome
     o chiusura. Nessun timer aggiunto. Le richieste portal sottoscrivono il
     percorso determinato dal token prima dell'invio; le richieste pendenti
     e la sessione vengono chiuse alla sostituzione o all'arresto. Un errore
     di aggiornamento KGlobalAccel conserva anche le sottoscrizioni del tasto
     già attivo, oltre alle proprietà. Il client pubblico separato della
     scorciatoia non sopprime le notifiche come una chiamata propria del tray.
111. Codex — Il warning MPRIS senza identità del bus resta per dati di recupero
     o player effettivi; il caso vuoto non salva nulla e non avverte. Causa:
     `recover()` senza stato termina prima di chiedere `GetId`, mentre
     `forget()` e il primo `pause()` possono già chiamare `_save()`. Non si
     cancella uno stato da recuperare quando l'identità è sconosciuta.

112. Codex — `SetConfig` prepara un `ConfigEdit` prima della scrittura: legge
     i byte preservando CRLF, unisce e valida i valori del file, localizza
     gli statement con tomllib per non confondere intestazioni dentro stringhe
     multilinea, sostituisce solo scalari ammessi e verifica il dizionario
     finale. Il servizio controlla DeviceBusy prima del commit atomico con
     permessi conservati. Il cgroup è una funzione iniettabile nei test;
     RestartUnit parte dopo la risposta di successo e non applica il nuovo
     dispositivo al processo uscente. Nessuna cache aggiunta a ListDevices.
113. Codex — La finestra usa un modello puro con un valore inviato e l'ultimo
     valore desiderato per chiave: i cambi rapidi si serializzano e i segnali
     intermedi non fanno arretrare i widget. Il client condiviso conserva
     le callback del tray, osserva il proprietario e rilegge GetAll alla
     ricomparsa, scartando risposte di generazioni precedenti. Nessun timer.
     Il template viene tradotto come XML prima di Gtk.Template; sono accettati
     `yes`, `true` e `1`, perché Blueprint 0.12 emette `true`.
114. Codex — L'installatore distingue valori stringa di Desktop Entry
     (`TryExec`, `Icon`) dalla riga di comando (`Exec`): prima quota gli
     argomenti, poi applica l'escape del valore. Il servizio D-Bus segue il
     quoting richiesto da spec 04 §3.1.6. Nessuna shell e nessun database del
     desktop modificato; installazione e rimozione limitate ai tre file.
     Il limite osservato di Gio con `%` nel percorso è documentato nel report,
     senza introdurre wrapper o ulteriori file installati.
115. Codex — I test GTK partono sotto Xvfb/dbus-run-session, poi creano
     due bus dbusmock senza servizi installati attivabili prima dell'import
     GTK, con HOME e directory XDG temporanee. Questo impedisce anche
     l'autoattivazione di portal reali sul bus privato. La misura RSS della
     finestra riusa lo stesso harness e dichiara il suo overhead; la misura
     di riposo del demone conta anche le chiamate al KGlobalAccel finto.
116. Codex — Audit 1, scelta del desktop: anche la rimozione esplicita del
     tasto tramite `yourShortcutsChanged` memorizza il preferito corrente in
     state.json, inclusa la rimozione dopo un conflitto senza preferito già
     salvato. Il riavvio usa quindi autoload (flag 2) e rispetta la rimozione.
     Comportamento già presente, accettato nell'audit di Claude del 2026-10-07
     e ora fissato da un test che parte da conflict.
117. Codex — Audit 1, errori delle impostazioni: una risposta d'errore scarta
     anche l'ultimo valore in attesa per la chiave; non si reinvia e si torna
     al valore in vigore, salvo la selezione già salvata di RestartRequired.
     Precisa la serializzazione della 113. I launcher ignorano annullamento
     e chiusura del dialogo; per errori locali mostrano il messaggio GLib,
     preservandolo anche se contiene punti. Il controllo del display precede
     Application.run e produce la diagnostica CLI tradotta con uscita 1.
     Chiarimento Claude trasmesso da GM: la prima scomparsa dopo un cambio
     dispositivo riuscito consuma `restarting` e resta senza banner fino al
     ritorno del nome o alla riapertura della finestra; le successive mostrano
     il banner. Vale anche per RestartUnit fallito seguito più tardi da Quit,
     limite accettato senza timer o segnali nuovi.
118. Codex — Audit 1, corregge la 114 per i servizi D-Bus secondo spec 04
     §3.1.6 aggiornata in `0c84d9a`: Exec del `.service` quota il percorso e
     applica una sola volta l'escape di virgolette, backslash, dollaro e
     backtick; `%` resta letterale. L'escape aggiuntivo Desktop Entry e `%%`
     restano esclusivamente nel `.desktop`. Test con esecuzione reale del
     programma finto da dbus-daemon privato in un percorso con `%` e backslash.
119. Codex — Audit 1, ConfigEdit risolve il percorso con `resolve()` al momento
     della scrittura: temporaneo e sostituzione atomica sono nella directory
     del file puntato, con permessi conservati; il symlink resta invariato.
     SetConfig diagnostica le eccezioni inattese con traceback nel log e
     risponde Failed; se la risposta è già partita prima di RestartUnit,
     registra il problema senza inviare una seconda risposta.

## 2026-10-07 — Orchestratore: piattaforme e modello di business (fascia orchestratore 120–129)

120. GM — **Versione macOS** di Scambio: sì, **dopo Linux v1** (spec 04 + fase 5 packaging).
     App nativa in Swift (barra dei menu), non Python; adattatori IOBluetooth, CoreAudio,
     notifiche di sistema per il blocco, hotkey globale. Windows escluso per ora.
121. Claude — Comportamento unico fra piattaforme: la macchina a stati resta la specifica; i suoi
     casi di test vanno esportati in un file di vettori condiviso (eventi → azioni) che le due
     implementazioni (Python e Swift) devono superare. Da preparare prima della fase Mac.
122. GM — Modello di business (aggiorna le decisioni 2–3): **Linux gratuito e open source**;
     **Mac a pagamento**, vendita diretta (Developer ID + notarizzazione, pagamenti tipo
     Paddle/Lemon Squeezy, eventuale Setapp) con funzioni complete; App Store eventualmente in
     versione ridotta (la pausa dei player di altre app non è fattibile nel sandbox). Le funzioni
     premium future (ponte fotocamera, agenti) a pagamento su entrambe le piattaforme.
     Da decidere prima della fase Mac: titolare del prodotto e dell'account Apple Developer
     (Fermich o GM personale).

123. Claude — Con Plasma 6 (aggiornamento di casa del 2026-10-07) `khotkeys` non esiste più: la
     scorciatoia «Connetti Oakley» di GM è sparita insieme al servizio e la decisione 99 è superata
     da sola. Meta+G resta solo a Scambio (gruppo `[app.scambio.Scambio]` in
     `kglobalshortcutsrc`). Su casa la «verifica di Plasma 6» del Q6 si fa ora in locale, non in VM.

124. GM — Il **core Linux sarà pubblicato** su un repository pubblico (senza GitHub Actions o altri
     costi; quando e dove lo definisce lo studio di prodotto), con un **requisito vincolante**:
     nessuno deve poter prendere il lavoro e **venderlo su Mac o Windows**; l'uso e la
     redistribuzione su Linux sono liberi. La licenza (Q1) la sceglie la chat di studio di prodotto
     con un approfondimento, partendo da due candidate: **PolyForm Shield 1.0.0** (source-available,
     vieta prodotti concorrenti: soddisfa il requisito alla lettera, ma non è «open source» OSI) e
     **GPL-3.0 + CLA** (open source, deterrente ma non divieto). In entrambi i casi: CLA dei
     contributori a favore del titolare (per poter riusare il codice nell'app Mac chiusa) e
     registrazione del marchio «Scambio». Consigliato un parere legale prima della pubblicazione.

## 2026-10-07 — Studio di prodotto e go-to-market (fascia 130–149)

Fonte: documento «Scambio — Studio di prodotto e go-to-market» (https://claude.ai/code/artifact/870bc3cb-6c81-4d8a-88ea-7c84be0fd901), con fonti e scenari.
Registrate dall'orchestratore perché la chat di studio non raggiungeva casa.

130. GM — **Mac in abbonamento: €2,49/mese o €12,99/anno**, prova di 7 giorni con carta inserita
     all'inizio e rinnovo automatico; vendita diretta con Stripe Managed Payments (o Paddle); App
     Store solo se un prototipo nel sandbox regge; Setapp dopo le prime recensioni. Precisa la
     dec. 122 (proposta iniziale scartata: €12,99 una tantum con prova di 14 giorni).
131. GM — **Titolare del prodotto: Fermich srl** (venditore aziendale; account Apple Developer come
     organizzazione con D-U-N-S, con delega dell'amministratore).
132. GM — **Core Linux con licenza GPL-3.0 + CLA**, pubblicato al rilascio di Linux v1. Chiude Q1.
     Rispetto al requisito della dec. 124 la GPL è un **deterrente, non un divieto**: chi porta il
     codice su Mac/Windows deve pubblicare tutto sotto GPL e non può usare il nome; il CLA consente
     a Fermich di riusare il codice nell'app Mac chiusa.
133. GM — **Marchio UE figurativo «Scambio» (nome + logo), classi 9 e 42, a nome Fermich**, dopo
     ricerca completa su TMview e WIPO Brand Database. Motivo: in italiano «scambio» è parola
     comune (rischio di marchio descrittivo); il figurativo è più facile da registrare.
134. Claude — Vincoli emersi dallo studio, validi da subito:
     (a) **Flathub**: il manifest va scritto a mano da GM e va dichiarato l'uso di codice generato
     con IA (requisiti Flathub); alternative AUR, .deb, AppImage;
     (b) **Meta**: solo «Works with Ray-Ban Meta and Oakley Meta glasses» nel testo descrittivo,
     mai in nome, icona, dominio o titolo dello store; nessun logo Meta; disclaimer di non
     affiliazione;
     (c) **marchio**: ricerca TMview/WIPO prima del deposito; rischio percepito «scam» in inglese
     da tenere presente nel naming del messaggio.
     Messaggio proposto (non ancora deciso): «L'audio ti segue» / «Your audio follows you».

135. GM — **Supera la 132 sulla licenza.** Obiettivo esplicito di GM: guadagnare con Scambio;
     gratuito su Linux, **a pagamento su Mac, e nessun altro deve poterlo vendere**. La GPL non lo
     garantisce (è solo un deterrente), quindi il core Linux pubblicato userà **PolyForm Shield
     1.0.0**: codice pubblico, uso, modifica e redistribuzione gratuiti su Linux, ma vietato usarlo
     per prodotti che fanno concorrenza a Scambio (porting commerciali su Mac/Windows compresi).
     Restano: **CLA** per i contributi (Fermich titolare dei diritti), **marchio** (dec. 133),
     pubblicazione al rilascio di Linux v1. Comunicazione: «codice pubblico e gratuito su Linux»,
     **mai «open source»** (PolyForm Shield non è una licenza approvata OSI). Su Flathub l'app va
     dichiarata non libera. Prima della pubblicazione: verifica con un legale del testo della
     licenza e del CLA rispetto all'obiettivo.
136. GM — Un eventuale **porting Windows** (oggi escluso, dec. 120) sarà **a pagamento** come il Mac.
     Solo Linux è gratuito.

137. GM — **Supera la 135: si torna a GPL-3.0 + CLA** (come la 132), core Linux open source
     completo, pubblicato al rilascio di v1. Motivo: il guadagno sta su Mac/Windows a pagamento;
     nessuno riscrive l'app per risparmiare €2,49 al mese, e un concorrente commerciale non può
     inglobare codice GPL in un'app chiusa senza pubblicarla tutta. PolyForm Shield aggiungeva poca
     protezione in più e toglieva i vantaggi dell'open source (fiducia, contributi, visibilità).
     Restano: CLA (Fermich titolare, per riusare il codice nell'app Mac chiusa) e marchio (dec. 133).
138. GM — **Deposito del marchio rinviato**: per ora nessuna spesa per la registrazione (stima
     700–900 €); la 133 resta l'obiettivo, da eseguire quando c'è budget. Nel frattempo: niente ® o ™,
     marchi Meta solo descrittivi (dec. 134).
139. GM — **Lista d'attesa su scambio.app** prima del lancio, per misurare la domanda per
     piattaforma (Mac/Windows/Linux e iPhone/Android). Pagina unica in EN/IT/DE, lingua dal browser
     con inglese come predefinita. Anteprima: https://claude.ai/artifact/44UmbRNbQZMbayNU8HYmov.
     Prima della messa online servono: backend del modulo, informativa privacy completata (sede,
     P. IVA, fornitore email) e doppio opt-in. Account social più avanti.
140. Claude — **scambio.app online dal 2026-10-07** (approvato da GM): Worker Cloudflare
     `scambio-site` sull'account personale di GM (stesso account di kuchl.app, che non è stato
     toccato), con asset statici e `POST /api/waitlist` su D1 `scambio-waitlist` (regione weur).
     Codice in `~/development/scambio-site` (git locale, nessun remote). `www` → 301 su apex.
     `privacy@scambio.app` inoltrato a [indirizzo di GM] (Cloudflare Email Routing).
     Informativa completata con i dati di Fermich e Cloudflare come responsabile. Il campo
     «Quali occhiali» suggerisce i modelli Meta in vendita al 2026-10-07 (lista da aggiornare:
     `<datalist id="device-models">`). Doppio opt-in e invio email: non ancora.

## 2026-10-07 — Spec 04 su Ubuntu 26.04 / Plasma 6 (chat di sviluppo; numeri 141–144)

141. Claude — La decisione 85 (`Activate` del tray risponde con un errore) **resta**: su Plasma 6 il
     clic sinistro non chiama più `Activate` e apre il menu da sé (M21), quindi la regola è innocua
     qui e serve ancora su Plasma 5.27 (Kubuntu 24.04 LTS, ancora diffusa).
142. Claude — Conferma la 102 su Plasma 6: anche se ora il portal GlobalShortcuts lega le scorciatoie
     (M20), con KDE Scambio continua a usare KGlobalAccel (funziona su 5.27 e 6, nessun dialogo, il
     tasto preferito si impone, nome del componente `app.scambio.Scambio` e non dipendente
     dall'`app_id` dell'unità). Il portal resta per i desktop senza KGlobalAccel.
143. Claude — La correzione 68 è confermata su BlueZ 5.85 (M22): nessuna modifica.
144. Claude — Q6 chiusa per la parte **Plasma 6**: spec 04 provata da GM su Plasma 6.6.6 Wayland
     (casa dopo l'aggiornamento a Ubuntu 26.04), tray, notifiche, scorciatoia e finestra ok. Resta
     aperta solo la parte **GNOME** (portal con `app_id` dell'unità systemd, tray assente), da
     provare in una VM prima della fase 5.

## 2026-10-07 — Fase 5: packaging e prima release (chat di rilascio; numeri 150–169)

150. GM — **Codice pubblico su GitHub, senza Actions** né altra CI remota: build, test, pacchetti e
     firma restano su `casa`. Account o organizzazione proprietaria: domanda Q7.
151. GM — **Formati della v1: Flatpak + apt «come Chrome».** Flatpak da un repository proprio su
     scambio.app, poi Flathub con il manifest scritto a mano da GM (dec. 134a). Per Ubuntu/Debian un
     repository apt firmato su scambio.app e un `.deb` scaricabile che installa Scambio **e** aggiunge
     sorgente e chiave, così gli aggiornamenti arrivano con apt. PPA, AUR e AppImage non nella v1.
152. GM — **Prima release pubblica: 1.0.0**, a condizione che passi la prova di installazione pulita
     (casa + VM con un'altra distro e GNOME). Da 1.0.0 l'API D-Bus `app.scambio.Scambio1` e il
     formato di `config.toml` seguono SemVer.
     **Aggiornamento 2026-10-08 (GM):** niente prova di installazione pulita prima della pubblicazione;
     le prove si fanno in produzione («il software funziona, l'abbiamo provato e straprovato»). La 1.0.0 è
     uscita il 2026-10-08 dopo le verifiche automatiche in contenitori e l'audit di Claude.
153. Claude — **Flatpak fattibile** (M30–M34): runtime `org.gnome.Platform` 51 senza moduli aggiuntivi
     (`pactl` incluso), permessi statici minimi: `--share=ipc`, `--socket=wayland`,
     `--socket=fallback-x11`, `--device=dri`, `--socket=pulseaudio`, `--system-talk-name=org.bluez`,
     `--system-talk-name=org.freedesktop.login1`, `--talk-name=org.mpris.MediaPlayer2.*`,
     `--talk-name=org.kde.kglobalaccel`, `--talk-name=org.kde.StatusNotifierWatcher`,
     `--talk-name=org.freedesktop.Notifications`, `--talk-name=org.freedesktop.ScreenSaver`.
     Niente `--own-name`, niente `--filesystem`, niente systemd: le parti che li richiedevano cambiano
     (dec. 154–156).
154. Claude — **Tray senza nome ben noto** (M33): l'icona si registra col solo percorso
     `/StatusNotifierItem` su una **connessione di sessione dedicata** al tray; nasconderla
     (`ui.tray = false`) chiude quella connessione, mostrarla ne apre una nuova (stesso effetto
     visibile della 108 senza `--own-name`). Vale per tutti i formati. Nel Flatpak `IconThemePath`
     è tradotto nel percorso dell'host con `app-path` di `/.flatpak-info`.
155. Claude — **Avvio e riavvio senza dipendere da systemd.** Il demone è attivabile via D-Bus in
     tutti i formati (file `app.scambio.Scambio.service`; nel `.deb` con `SystemdService=scambio.service`).
     «Avvia» della finestra e l'apertura dal menu usano l'attivazione D-Bus al posto di `StartUnit`.
     Avvio al login (dec. 48): nel `.deb` il servizio utente abilitato per tutti gli utenti; nel Flatpak
     il demone chiede al portal Background `autostart=true` a ogni avvio (idempotente, M32). Riavvio
     dopo il cambio di dispositivo: `RestartUnit` se il demone gira sotto systemd, altrimenti
     ri-esecuzione del processo dopo l'arresto ordinato.
156. Claude — **Percorsi da pacchetto.** `design/`, cataloghi compilati e `.ui` si leggono dal checkout
     quando si sviluppa e da `<prefix>/share/scambio/` quando Scambio è installato; configurazione e
     stato in `GLib.get_user_config_dir()/scambio` e `GLib.get_user_data_dir()/scambio` (sull'host
     sono gli stessi `~/.config/scambio` e `~/.local/share/scambio` di oggi; nel Flatpak finiscono in
     `~/.var/app/app.scambio.Scambio/`). Versione unica in `pyproject.toml`.
157. Claude — **Pacchetto `.deb`**: `Architecture: all`, per **Ubuntu 24.04+ e Debian 13+** (libadwaita ≥ 1.4,
     `pactl -f json` ≥ 16); Debian 12 e Ubuntu 22.04 esclusi dalle dipendenze. Sorgente apt in formato
     deb822 (`/etc/apt/sources.list.d/scambio.sources`) e chiave in
     `/usr/share/keyrings/scambio-archive-keyring.gpg` come **file del pacchetto** (nessuna modifica
     in `postinst` alle sorgenti). Repository apt (`stable main`, `all`) e repository Flatpak (OSTree)
     generati su casa e pubblicati come asset statici del Worker `scambio-site` in
     `https://scambio.app/apt/` e `https://scambio.app/flatpak/`.
158. Claude — **Chiave di firma** dedicata «Scambio Release Signing Key» (Ed25519, per apt e Flatpak),
     generata su casa in un keyring separato `~/.local/share/scambio-release/gnupg`; GM ne conserva
     una copia offline (perderla significa non poter più aggiornare chi ha già installato).
159. Claude — **Flathub è un tentativo, non il canale principale.** Requisiti Flathub letti il
     2026-10-07: dichiarare il materiale generato con IA con parti ed estensione; i manifest Flathub
     non possono contenere contenuto generato o assistito da IA; l'IA non può aprire né scrivere PR,
     descrizioni, messaggi di commit o risposte ai revisori; i revisori possono rifiutare in base
     all'estensione del codice generato. Storia (git di flathub-infra/documentation): divieto totale
     del codice IA da fine maggio 2026, **sostituito il 2026-09-04 dalla politica a dichiarazione**
     (#641), divieto per i soli manifest ripristinato il 2026-09-21; nessuna soglia numerica, la
     valutazione è dei revisori (maturità, manutenzione, cura del progetto). Scambio è scritto quasi
     tutto da Codex, ma con spec, misure, audit e prove reali documentati: domanda possibile, esito
     incerto. Il repository Flatpak proprio resta il canale per le altre distro; per Flathub Claude
     prepara a GM solo una guida passo passo.
160. GM — **Repository su una nuova organizzazione GitHub** (proposta: `scambio-app`, libera al
     2026-10-07), creata da GM con l'account `VAX90` come proprietario. Chiude Q7.
161. GM — **Licenza `GPL-3.0-or-later`** (precisa la 137). Chiude Q8.
162. GM — **CLA pubblicato con la 1.0.0, parere legale dopo**: prima di accettare la prima PR esterna
     il testo va rivisto da un legale. Chiude Q9.
163. GM — **Indirizzo pubblico dedicato `hello@scambio.app`** (pacchetto, metainfo, README) e
     `release@scambio.app` nella chiave di firma; **tutti** gli indirizzi `@scambio.app` inoltrati per
     ora a [indirizzo di GM] (regola catch-all di Cloudflare Email Routing).
164. GM — **Storia git pubblicata intera, con l'autore riscritto** prima del primo push: autore e
     committente `Fermich srl <hello@scambio.app>` al posto dell'email personale; i trailer
     (`Co-Authored-By`, `Claude-Session`) restano. Lo fa Claude con `git filter-repo --mailmap` subito
     prima del push, salvando la tabella hash vecchio → nuovo in `docs/verification/05/commit-map.txt`;
     da lì in poi il repository usa quell'identità (`git config user.*` locale). Chiude Q11.
165. GM — **«Telefono» al posto di «iPhone» in tutta l'interfaccia** (it «telefono», en «phone», de
     «Handy»): «Priorità telefono», «Lascia al telefono», «Switch intelligente (PC ↔ telefono)».
     Cambiano solo i testi di `design/i18n/` (fatto da Claude il 2026-10-07); chiavi, nomi dell'API
     D-Bus (`IphonePriority`, `SetPriority`) e configurazione restano. Chiude Q12.
166. GM — **Dalla storia pubblicata si tolgono anche i dati personali**, nella stessa riscrittura della
     164: MAC degli occhiali → `80:AA:1C:XX:XX:XX`, `~` → `~`, l'indirizzo di inoltro Fermich →
     «l'indirizzo di GM». Dopo la riscrittura Claude ripete la scansione di segreti e dati personali
     su tutta la storia di entrambi i repository (audit S14).
167. GM — **Doppio opt-in della lista d'attesa con la release** (completa la 139–140): conta solo chi
     conferma dal link ricevuto da `hello@scambio.app`; invio con Cloudflare Email Sending dal Worker.
     **Aggiornamento 2026-10-08:** Email Sending richiede il piano Workers Paid (≈5 $/mese), non attivo
     sull'account. In produzione `DOUBLE_OPT_IN = "false"`: le iscrizioni si salvano come `unconfirmed`
     (consenso registrato, nessuna email). Per attivare il doppio opt-in: GM acquista Workers Paid,
     Claude abilita il dominio in Email Service, ripristina `[[send_email]]` e mette il flag a `"true"`;
     prima di scrivere alla lista, chiedere conferma alle voci `unconfirmed`/`legacy_unconfirmed`.
168. Claude — **Esito dell'audit di sicurezza** (`docs/verification/05/security-audit.md`, Codex con
     Daybreak Blue, 14 punti, nessuno critico). Si correggono prima della 1.0.0: S2–S6, S8, S10–S14 e
     in parte S7 e S9 (spec 05 §3.1.10). Rischi accettati:
     (a) S1 — chiave: primaria **offline** (backup di GM, poi tolta da casa), sulla macchina di build
     solo una sottochiave di firma Ed25519 senza passphrase che **scade il 2028-10-06**, unica per apt e
     Flatpak; revoca pronta nel backup. Chiavi separate per apt e Flatpak non danno protezione reale
     con un solo build host. **Stato al 2026-10-08:** la primaria è ancora nel keyring di casa (la
     rimozione automatica è stata bloccata dal sistema di permessi); il backup è nella cartella
     `scambio-chiave-BACKUP-OFFLINE` sulla Scrivania, coperta dal backup notturno sul NAS (GM). Da fare a
     mano: togliere la primaria dal keyring e spostare la cartella offline;
     (b) S3 — niente `Valid-Until` nel `Release`: obbligherebbe a rifirmare il repository a scadenza fissa,
     e un ritardo bloccherebbe `apt update` a tutti; il rischio «freeze» richiede comunque il sito
     compromesso;
     (c) S7 — l'API D-Bus non distingue i chiamanti: il bus di sessione è il confine di fiducia
     (stesso utente); si mettono solo limiti di dimensione e si evitano scritture ripetute;
     (d) S9 — `config.toml` può restare un collegamento simbolico (dotfile gestiti dall'utente);
     `state.json` e le cartelle invece no.
169. Codex — **Implementazione tecnica della spec 05** (2026-10-08).
     (a) Percorsi XDG letti da GLib; dati installati cercati in `/app`, `sys.prefix`, `/usr`.
     La versione proviene dai metadati Python; `build_py` genera la riserva dal solo
     `pyproject.toml`. Il target offline `make install` serve sia Debian sia Flatpak.
     (b) Il tray possiede una connessione dedicata e si registra col percorso; chiuderla
     rimuove l'icona. La finestra usa `StartServiceByName`. Background è una richiesta per
     avvio; la ri-esecuzione usa interprete assoluto, `-I`, argv fisso, dopo flush e chiusura.
     (c) Letture limitate e scritture atomiche con directory aperta, `O_NOFOLLOW`, file 0600,
     fsync del file e della directory. Resta consentito il symlink del solo config (168d).
     Limiti backend richiesti da §3.1.10.5: snapshot 4 MiB, subscribe 64 KiB, 256 stream,
     quattro comandi oltre al subscribe, latenza massima 2000 ms; massimo 16 player.
     Questo requisito specifico precisa «nessuna chiave nuova» del riepilogo §3.2.
     (d) Il `.deb` abilita globalmente il servizio con `systemctl --global`, senza avviarlo;
     l'installer di sviluppo mantiene i tre file della decisione 106. Due override lintian
     documentano la sorgente apt inclusa e non-conffile, entrambe imposte dalla decisione 157:
     il pacchetto upstream non è destinato all'archivio Debian. Permessi normalizzati in build.
     (e) Il repository apt usa SHA256/by-hash e firme della sottochiave fissata; niente download
     di vecchi binari. Archivio locale verificato contro manifest firmato, senza sostituzione
     di versioni esistenti; conservati anche commit e oggetti OSTree. La copia nel sito segue
     le verifiche degli artefatti e delle installazioni temporanee.
     (f) Il manifest concede letteralmente i soli permessi della 153. `flatpak info` rappresenta
     `fallback-x11` anche con il bit `x11`: il golden test confronta quella rappresentazione,
     mentre un test separato confronta l'elenco letterale del manifest. Prove negative su bus
     privati con nomi presenti; runtime condiviso in lettura nelle installazioni temporanee.
     (g) Per GLib recenti si usano `register_object_with_closures2`, `GLibUnix.signal_add` e,
     nei test, `GioUnix.DesktopAppInfo`; restano fallback per Ubuntu 24.04. I warning interni
     di PyGObject sono separati dai punti di chiamata del progetto nel report.
     (h) Le misure dei pacchetti usano il codice installato, bus privati e pactl simulato stabile,
     senza dispositivo configurato: due campioni `/proc/self/stat` a distanza di dieci minuti,
     senza ciclo di campionamento. Non sostituiscono la prova Bluetooth/desktop di GM.
     (i) Il Worker usa il binding nativo Email Sending; `remote = false` mantiene simulato
     l'invio durante `wrangler dev`. La disponibilità nell'account richiede verifica separata:
     il comando di sola lettura ha restituito Unauthorized (2036), non una prova di disponibilità.
     La migrazione D1 risiede in `packaging/site/`, richiamata da `migrations_dir`, per rispettare
     le proprietà dei file autorizzate. Il contatore giornaliero è atomico in D1; il rate limiter
     Cloudflare per IP resta il primo filtro. Nessuna migrazione remota o email reale nella prova.
     (j) CSS, JavaScript, font e Three.js sono asset locali; CSP senza `unsafe-inline`.
     Le copie tradotte entrano nel DOM come testo; solo geometrie SVG costanti usano `innerHTML`.
     `make verify` verifica senza congelare; `make stage-site` ripete le verifiche, controlla
     l'albero pulito, sigilla l'archivio firmato e copia gli asset nel checkout del sito.
     Non pubblica, non crea tag e non modifica servizi o installazioni reali dell'utente.
     (k) Audit 1, M35: `sd_dummy` e `speech-dispatcher-dummy` entrano nei default
     `audio.ignore_apps` e nel modello generato. Una lista esplicita, anche vuota, resta
     una scelta dell'utente: nessuna riscrittura automatica delle configurazioni esistenti.
     (l) Gli script Debian chiamano `systemctl --global` solo se l'eseguibile è presente.
     `verify` prova install/upgrade/remove/purge su Ubuntu 24.04 e Debian 13 sia con systemd
     sia senza il suo pacchetto, controllando l'assenza effettiva di `/usr/bin/systemctl`.
     (m) Con l'autorizzazione dell'audit 1, la migrazione passa in `scambio-site/migrations/`;
     questo supera il percorso provvisorio del punto (i). Il binding EMAIL limita il mittente
     a `hello@scambio.app` e non imposta `remote`; le prove usano `wrangler dev --local`.
     L'onboarding del dominio resta di Claude, senza invii reali nelle prove di Codex.
     (n) L'archivio 1.0.0 già sigillato resta intatto. `SCAMBIO_RELEASE_CANDIDATE=audit-1`
     separa sia gli output (`dist/candidates/audit-1/`) sia l'archivio firmato della candidata
     (`~/.local/share/scambio-release/candidates/audit-1/1.0.0/`). Identificatori limitati,
     stessa verifica di firme/hash e stesso rifiuto di sovrascrivere una versione sigillata.
     Il sito locale riceve solo la candidata verificata. Nessuna promozione automatica,
     mescolanza fra archivi o sostituzione di versioni pubblicate: il rilascio resta a Claude/GM.

## 2026-10-08 — Dopo la 1.0.0 (orchestratore, decise da GM con Claude)

170. GM — Si attiva Cloudflare Workers Paid (~5 $/mese) sull'account personale per l'invio
     email del doppio opt-in della waitlist (Email Sending richiede il piano Paid). Il pagamento
     lo fa GM; poi Claude fa l'onboarding di `scambio.app` in Email Sending, ripristina il
     binding `EMAIL`, imposta `DOUBLE_OPT_IN = "true"` e prova il giro completo.
171. GM — Prossimo fronte: lancio e promozione della 1.0.0 Linux, in una chat dedicata
     (decisioni 180–199). Niente recensioni false né account fittizi; Meta solo come «Works
     with», con disclaimer di non affiliazione.

## 2026-10-08 — Lancio e promozione della 1.0.0 Linux (chat di lancio; numeri 180–199)

Materiale operativo (brief del sito, scalette, calendario, bilanci) nel repo del sito, che non ha remote:
`~/development/scambio-site/docs/lancio/`.

180. GM — **I testi di lancio li scrive GM a mano**, in inglese e con la sua voce; Claude prepara per ogni
     canale regole, scaletta, fatti e risposte alle obiezioni e poi controlla solo fatti e regole sulle
     bozze. Motivo: Hacker News («Please don't put generated text in HN posts»), r/gnome, This Week in
     GNOME e altri vietano testi generati o ritoccati con l'IA. GM pubblica a suo nome, dichiara di esserne
     l'autore; niente account fittizi, voti chiesti o commenti su richiesta.
181. Claude — **Pagina di lancio** (brief alla chat «Sito ed email»): download Linux come pulsante primario
     ovunque tranne su Mac e Windows desktop, dove è primaria la lista d'attesa; video demo muto in loop con
     sottotitoli per lingua, senza player esterni; mock di «How it works» in versione Linux (Super+G, «— on
     the PC»); `og:image`; sezione `#compat`; deploy solo dopo il sì di GM sull'anteprima.
182. Claude — **Compatibilità dichiarata a quattro livelli**: provato (Oakley Meta HSTN + iPhone su Kubuntu /
     KDE Plasma), dovrebbe funzionare (altri occhiali Meta, Android), potrebbe funzionare (Ray-Ban Stories,
     Ray-Ban Meta Audio, cuffie di altre marche), non serve (cuffie con multipoint). Mai più «any Bluetooth
     headphones»; le chiamate si descrivono come misurate: WhatsApp su iPhone (M2), GSM e Android non
     provati. Allineati README e sito.
183. Claude — **Misura del lancio senza dati personali**: nessun analytics, cookie o parametro di
     tracciamento; contatori nel Worker per file e per giorno (UTC) sui download e sui controlli degli
     aggiornamenti apt/Flatpak, senza IP, user agent, referrer o paese, dichiarati in una riga
     dell'informativa; per la domanda Mac/Windows contano solo gli iscritti `confirmed`.
184. GM — **Lancio lunedì 12 ottobre 2026** (GM libero fino al 15; il 14 esce Plasma 6.8 e il 15 Ubuntu
     26.10): un canale importante al giorno — r/linux (12), r/kde e KDE Discuss (13, r/kde col sì dei
     moderatori), Lemmy (14), r/RaybanMeta col sì dei moderatori (15), poi canali minori, Fedora (19).
     **Show HN rinviato** a non prima dell'8 novembre: GM non ha un account HN con storia e dal marzo 2026
     HN blocca gli Show HN degli account nuovi. r/gnome non prima del 5 novembre (quattro settimane di
     storia pubblica per i progetti con IA) e solo dopo una prova reale su GNOME. Saltati r/opensource e
     GNOME Discourse (regole contro i progetti scritti con l'IA). Condizioni per partire: prova reale dei
     pacchetti pubblicati installati dal sito e primaria della chiave tolta da casa (168a); se la prova
     trova un problema serio, il lancio slitta al 19.
185. GM — Account: Reddit personale già esistente; nuovi account **a nome di GM** su Hacker News, KDE
     Identity, Fedora, Ubuntu One e Lemmy. Li crea GM.
186. GM — **Dichiarazione esatta dei ruoli** nel README, sul sito e nei post: GM dirige, prende le decisioni
     di prodotto e prova ogni giorno su hardware reale; specifiche, revisioni, design e molte misure con
     Claude; codice, test e pacchetti con Codex; tutto pubblico in `docs/`. Supera la formulazione del README
     dell'8 ottobre mattina («Designed, reviewed and tested by a human»), che il repo stesso smentiva.
187. GM — **1.0.1 prima del lancio**: il profilo `meta_glasses` (ritardo di ripresa che copre l'annuncio
     vocale, M11b) si sceglie da solo quando il nome del dispositivo contiene Meta, Ray-Ban od Oakley; oggi
     il default è `generic` e un nuovo utente Meta sente l'annuncio sopra l'audio. Lo smista
     l'orchestratore a Codex; se non è pronta per domenica 11 si parte con una nota nel README.
188. GM — **Conservazione dei dati della lista d'attesa**: fino a 12 mesi dopo che Scambio è disponibile per
     tutti i computer scelti (scelta multipla; Linux è già disponibile), mai oltre 24 mesi dall'iscrizione,
     o fino alla cancellazione. Sostituisce «until Scambio launches plus 12 months». Il tetto dei 24 mesi è
     una precisazione di Claude, da confermare da GM.
189. GM — **Social**: account Mastodon del progetto solo con pubblicazione programmata (Buffer); i post li
     prepara Claude, li approva GM, e la bio dichiara che sono scritti con l'aiuto dell'IA; le risposte alle
     persone le scrive GM. Instagram al lancio Mac, con uno strumento di programmazione (tipo Metricool).
172. GM — Conferma il tetto della decisione 188: i dati della lista d'attesa si cancellano comunque
     dopo 24 mesi dall'iscrizione. Approva la spec 06 (1.0.1, profilo automatico) e il suo avvio a
     Codex; decisioni tecniche di Codex per la spec 06 nell'intervallo 210–219.
173. GM — **Mac App Store come canale principale** (supera in parte le dec. 122 e 130): la vendita
     diretta dal sito ha troppo attrito e poca visibilità; il pubblico arriva da Instagram e
     l'abbonamento con prova si fa nell'App Store. L'app Mac si progetta **sandbox-first**; la
     vendita diretta resta solo come riserva per le funzioni che il sandbox non consente, da
     valutare dopo le prove di fattibilità sul Mac della chat Mac (fase 6, decisioni 220–259).

## 2026-10-08 — Spec 06, profilo automatico (Codex, decisioni tecniche 210–219)

210. Codex — **Configurazione dichiarata e policy effettiva separate.** Il parser conserva
     `device.profile = "auto"` e la presenza di `policy.resume_delay_ms` con il flag interno
     `Config.resume_delay_explicit` (non è una nuova chiave TOML). Il servizio risolve il profilo
     con la regex della spec e passa alla macchina a stati una copia della policy con il ritardo
     effettivo. Uno zero esplicito prevale come qualsiasi altro valore; la configurazione su
     disco non viene riscritta. Il ricalcolo non invia azioni ai timer già programmati.
211. Codex — **Nome completo per il riconoscimento, testo limitato per UI e log.** BlueZ emette
     l'evento già esistente `DeviceName` con `Alias`, oppure `Name` solo se `Alias` manca; un alias
     vuoto non ripiega sul nome. Il servizio riconosce dal nome completo, poi espone e registra
     il testo sanificato e limitato della decisione 168/S10. Rimozione del dispositivo o perdita
     di BlueZ azzerano il nome usato dall'automatico. Nessuna nuova sottoscrizione o polling.
     Si registra una riga per cambio della coppia (profilo effettivo, origine), anche se cambia
     soltanto l'origine; rinomine equivalenti e reload identici non duplicano il log.
212. Codex — **API additiva e cambio dispositivo invariato.** `DeviceProfile` e
     `DeviceProfileSource` sono proprietà di sola lettura pubblicate tramite il confronto già
     usato da `PropertiesChanged`; la CLI le stampa tramite il suo `GetAll` esistente, senza
     importare logica dal core. Il cambio di indirizzo continua a usare il riavvio della
     decisione 155: la nuova istanza risolve solo il nuovo dispositivo, inizialmente `generic`
     quando automatico e ignoto. Reload del solo profilo e rinomina non richiedono riavvio.
213. Codex — **Candidata 1.0.1 con storia pubblicata e upgrade reale.** Gli strumenti leggono
     l'archivio pubblico firmato anche quando `SCAMBIO_RELEASE_CANDIDATE` separa output e
     destinazione di sigillatura. Verificano firme, inventario e hash di entrambe le fonti e
     rifiutano una versione duplicata fra archivio pubblico e candidata; `seal()` scrive solo
     nell'archivio della candidata. apt conserva i pacchetti pubblicati e Flatpak i commit
     precedenti. La verifica usa la più recente versione sigillata inferiore alla candidata,
     senza fabbricare una vecchia versione dal nuovo pacchetto: qui 1.0.0 → 1.0.1. La prova
     Debian/Ubuntu aggiorna tramite il repository apt locale firmato e controlla che il profilo
     `generic` scritto rimanga identico; Flatpak installa il vecchio commit firmato, aggiorna
     dal nuovo repository, rimuove e reinstalla in un'installazione temporanea.
