# 01 — Panoramica del prodotto

Redatto da Claude il 4 ottobre 2026 con le decisioni di GM della stessa data. Le decisioni
numerate stanno in `docs/decisions.md`; qui c'è il quadro.

## 1. Il problema

Molti dispositivi audio Bluetooth — tra cui gli occhiali smart Meta (Ray-Ban Meta, Oakley Meta) —
non supportano il multipoint: possono essere collegati a un solo dispositivo alla volta. Chi li
usa sia con il PC Linux sia con il telefono deve collegarli e scollegarli a mano, e i due
dispositivi si contendono il collegamento.

## 2. Il prodotto

**Scambio** è un demone leggero per Linux, con icona nel tray, che fa da «multipoint software»:
prende il dispositivo quando il PC ha bisogno dell'audio e lo restituisce al telefono quando il
PC non lo usa più, senza interventi manuali. Il nome viene dallo scambio ferroviario, che devia il
treno da un binario all'altro.

## 3. Posizionamento (decisione 2026-10-04)

- **Marchio e marketing: «l'app Linux per gli smart glasses».** Gli occhiali Meta sono il caso di
  punta e il profilo meglio testato.
- **Il core è indipendente dal dispositivo**: lo switch funziona con qualsiasi dispositivo audio
  Bluetooth. Il comportamento specifico di un modello sta in un *profilo dispositivo*.
- Nessun concorrente diretto su Linux (verificato il 4 ottobre 2026: solo script e guide).
- I marchi Meta, Ray-Ban e Oakley non entrano nel nome né nel logo; si citano solo in modo
  descrittivo («compatibile con occhiali Meta»).

## 4. Modello open-core

| Livello | Contenuto | Licenza |
|---|---|---|
| Core (gratuito) | demone, switch automatico, Priorità iPhone, scorciatoia, tray, finestra impostazioni, profilo generico e profilo occhiali Meta | open source (licenza da decidere, vedi tracker) |
| Premium (futuro) | funzioni per smart glasses oltre l'audio: ponte fotocamera/foto tramite app companion iPhone, collegamento ad agenti locali/Claude, widget nativi (Plasma, Impostazioni rapide GNOME) | proprietaria, pacchetto separato |

Vincolo tecnico verificato (4 ottobre 2026): il Wearables Device Access Toolkit di Meta (fotocamera,
microfono, foto) esiste solo per iOS e Android tramite l'app Meta AI, ed è in developer preview
senza pubblicazione pubblica. Le funzioni camera richiederanno quindi un'app ponte su iPhone.

## 5. Utente di riferimento

Chi usa Linux al lavoro e porta occhiali smart o cuffie BT usati anche col telefono. Primo utente
e tester: GM (Kubuntu, KDE Plasma, iPhone, Oakley Meta 002Z).

## 6. Comportamento (decisioni di prodotto, non ridiscutere)

1. **Presa automatica**: quando sul PC parte un audio (non suoni di sistema/notifiche), il PC
   prende il dispositivo, anche se il telefono lo sta usando. L'audio del PC viene messo in pausa
   (o in muto) durante la connessione (~2 s misurati), poi spostato sul dispositivo e ripreso.
2. **Rilascio automatico** dopo 120 s di silenzio audio sul PC (configurabile); rilascio
   immediato con blocco schermo e sospensione.
3. **Priorità iPhone**: interruttore nel tray; quando attiva il PC non prende mai il dispositivo
   in automatico. Si spegne solo a mano.
4. **Scorciatoia globale «switch intelligente»**, default **Meta+G**: se il dispositivo è sul PC lo
   rilascia e attiva la Priorità iPhone; altrimenti lo prende e la disattiva.
5. Al rilascio il telefono si ricollega da solo ma la musica resta in pausa (misurato): la UX lo
   comunica. Una chiamata in corso sul telefono non cade e torna da sola al dispositivo.

## 7. Interfacce

Tray StatusNotifier + notifiche freedesktop (uguali su tutti i desktop) + finestra impostazioni
GTK4/libadwaita. Lingue it, en, de fin dal primo giorno. Desktop di riferimento: KDE Plasma
(GM) e GNOME (il più diffuso); distribuzione futura via Flatpak.

## 8. Fuori scope (per ora)

Accoppiamento (pairing) dei dispositivi, che resta al sistema; gestione di più dispositivi
contemporanei; Windows/macOS; funzioni premium.

## 9. Glossario

| Termine | Significato |
|---|---|
| Presa | il PC si collega al dispositivo (lo «ruba» al telefono) |
| Rilascio | il PC si scollega e lascia il dispositivo al telefono |
| Priorità iPhone | modalità in cui il PC non prende mai il dispositivo in automatico |
| Switch | azione manuale (scorciatoia, tray) che inverte lo stato |
| Profilo dispositivo | comportamento specifico di un modello (es. occhiali Meta) sopra il core generico |
