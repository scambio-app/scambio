# Prova di installazione pulita di Scambio 1.0.0 (per GM)

Redatta da Claude il 2026-10-08 (spec 05 §6.1). Tempo: circa 45 minuti in tutto. Claude prepara
tutto prima di ogni parte e ti scrive quando puoi partire; tu fai solo i passi qui sotto e mi dici
cosa vedi (anche solo «ok» / «no, succede X»). Se qualcosa non va, fermati e scrivimelo.

## Parte A — casa, pacchetto `.deb` (Plasma 6)

Preparazione di Claude: ferma e rimuove l'installazione di sviluppo (`make uninstall-user`), avvia
un'anteprima del sito su casa e ti dà il link.

1. Apri il link dell'anteprima nel browser, sezione **Download** → «Download .deb».
2. Apri il file scaricato con un doppio clic → **Installa** (Discover o il gestore pacchetti chiede
   la password: è normale, installa per tutto il sistema).
3. Cerca **Scambio** nel menu delle applicazioni: c'è, con l'icona degli occhiali? Aprilo.
4. Nella finestra: il dispositivo è già quello dei tuoi occhiali (la configurazione resta), lo stato
   è corretto?
5. **Esci e rientra** nella sessione (o riavvia). Dopo l'accesso: l'icona di Scambio c'è nel tray,
   senza che tu abbia aperto niente?
6. Prova normale: video sul PC → gli occhiali passano al PC; Meta+G → tornano al telefono; di nuovo
   Meta+G → tornano al PC; blocca lo schermo → tornano al telefono.
7. Nel tray: le scritte dicono **telefono** (non più «iPhone»).
8. Fino alla pubblicazione il repository `https://scambio.app/apt` non esiste ancora: se Discover o
   `apt update` mostrano un errore per scambio.app, è normale. Dopo il deploy Claude verifica che gli
   aggiornamenti arrivino da lì.

## Parte B — VM con Fedora (GNOME), Flatpak

Preparazione di Claude: una macchina virtuale con Fedora 44 Workstation (GNOME 50) già installata,
con Flatpak e il link al repository di prova. Niente Bluetooth nella VM: Scambio mostrerà
«dispositivo non disponibile», ed è giusto così.

1. Nella VM apri il link **Install with Flatpak** dall'anteprima: si apre Software di GNOME →
   **Installa**.
2. Apri **Scambio** dalla griglia delle app. Compare una richiesta di GNOME per farlo partire in
   background/all'accesso? Scrivimi il testo e rispondi **Consenti**.
3. Nella finestra: si vede bene, chiaro e scuro (cambia tema da Impostazioni → Aspetto)?
4. **Esci e rientra**: Scambio è partito da solo? (Claude lo verifica anche da remoto.)
5. Scorciatoia: GNOME chiede di confermare **Super+G** per Scambio? Accetta e premila: deve comparire
   la notifica di Scambio (senza occhiali dirà che il dispositivo non è raggiungibile).
6. Senza estensioni GNOME non mostra l'icona nel tray: è previsto. Se vuoi, installa l'estensione
   «AppIndicator and KStatusNotifierItem Support» e verifica che l'icona compaia.

## Parte C (facoltativa) — VM Ubuntu 24.04, `.deb`

Come la parte A, su un Ubuntu 24.04 pulito con GNOME.

## Dopo la prova

Claude registra l'esito nel report, chiude la Q6 per GNOME, fa gli screenshot per README e sito,
pulisce la storia git (decisioni 164/166) e ti chiede il **sì** per pubblicare: repository GitHub
pubblico, release 1.0.0 con i file, deploy del sito con i download.
