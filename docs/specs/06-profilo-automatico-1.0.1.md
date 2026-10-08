# Spec 06 — Profilo del dispositivo automatico (Linux 1.0.1)

Stato: bozza · Autore: Claude (orchestratore) · Data: 2026-10-08 · Scadenza: domenica 11 ottobre 2026

## 1. Obiettivo

Oggi il default del profilo dispositivo è `generic` (`resume_delay_ms = 0`). Così un nuovo utente
con occhiali Meta, quando Scambio rilascia il dispositivo e la musica dell'iPhone riparte, sente
l'annuncio vocale degli occhiali sovrapposto all'audio (M11b). Il profilo `meta_glasses` esiste
già e copre l'annuncio con un ritardo di ripresa di 2000 ms (dec. M11, voce 340), ma bisogna
sceglierlo a mano in configurazione.

Con la 1.0.1 il profilo si sceglie **da solo**, in base al nome del dispositivo configurato.
Esce come Linux 1.0.1, prima del lancio di lunedì 12 ottobre (dec. 187).

**Prova visibile:** su un'installazione pulita, con gli Oakley Meta configurati e senza nessuna
voce `profile` scritta a mano:

- il log del demone dice una volta `device profile: meta_glasses (auto, from name)`;
- `scambio status` mostra il profilo effettivo;
- alla ripresa la musica riparte dopo l'annuncio, non sopra.

## 2. Decisioni applicabili

- 187 (1.0.1 prima del lancio, profilo automatico dal nome).
- 182 (compatibilità a quattro livelli: i nomi che contano sono Meta, Ray-Ban e Oakley).
- M11 / M11b in `docs/hardware-lab.md` (annuncio vocale, 2000 ms definitivi).
- Precedente: decisione tecnica (l) sulle liste esplicite. Una scelta scritta dall'utente non
  si riscrive.
- Spec 05 per il processo di rilascio (archivio firmato, versioni sigillate, apt, Flatpak,
  sito).

## 3. Dettagli

### 3.1 Comportamento

1. Nuovo valore di profilo **`auto`**, che diventa il **default** (dataclass `Device`, parser e
   `TEMPLATE`). `generic` e `meta_glasses` restano validi e, se scritti, vincono sempre.
2. Con `auto`, il profilo effettivo si ricava dal **nome del dispositivo configurato**:
   - si usa `Alias` di BlueZ, oppure `Name` se `Alias` manca;
   - si confronta senza distinguere maiuscole/minuscole con l'espressione regolare
     `\bmeta\b|ray-?ban|oakley`;
   - se corrisponde → `meta_glasses`, altrimenti `generic`.
   - Esempi: «Oakley Meta 002Z», «Ray-Ban Meta 1A2B» e «RayBan Stories» danno `meta_glasses`;
     «Metallica Buds» e «WH-1000XM5» danno `generic`.
3. Il profilo si ricalcola quando:
   - il dispositivo configurato cambia (indirizzo diverso);
   - il dispositivo compare in BlueZ dopo l'avvio;
   - cambia l'`Alias` (segnale `PropertiesChanged`, già sottoscritto: **niente polling**).
   Finché il dispositivo non è noto a BlueZ, il profilo effettivo è `generic`.
4. **Ritardo di ripresa effettivo:** se `policy.resume_delay_ms` è scritto in configurazione,
   vince quello. Altrimenti vale `RESUME_DEFAULTS[profilo effettivo]`. Il cambio di profilo
   aggiorna il ritardo senza riavviare il demone, e il nuovo valore vale dalla ripresa
   successiva.
5. Il profilo effettivo e la sua origine (`auto` dal nome, oppure configurazione) vanno nel log
   **una volta** a ogni cambio. Nel log va anche il nome che ha deciso il profilo, ma mai
   indirizzi di altri dispositivi.
6. **Configurazioni esistenti:** un `profile = "generic"` già scritto resta `generic`, perché
   non si può distinguere da una scelta dell'utente. Nessuna migrazione automatica. Le note
   di rilascio dicono agli utenti Meta della 1.0.0 di mettere `profile = "auto"`, oppure di
   cancellare la riga. Gli utenti 1.0.0 sono pochissimi: il prezzo è accettabile.

### 3.2 API D-Bus, configurazione, dati

- `[device] profile`: valori ammessi `auto` | `generic` | `meta_glasses`, default `auto`.
  Il `TEMPLATE` scrive `profile = "auto"`, con un commento di una riga che spiega i tre valori.
- Proprietà D-Bus di sola lettura **`DeviceProfile`** (stringa, profilo effettivo:
  `generic` | `meta_glasses`) e **`DeviceProfileSource`** (`auto` | `config`), con
  `PropertiesChanged`. `scambio status` le stampa.
- Aggiorna `docs/context/02-architecture.md` solo tramite richiesta nel report (il file è di
  Claude): Codex elenca le chiavi nuove, Claude le inserisce all'audit.

### 3.3 Interfaccia

Nessuna UI nuova. Se la finestra impostazioni mostra già il profilo, mostra quello effettivo
con la nota «automatico»; se non lo mostra, non si aggiunge nulla. `design/` non si tocca;
eventuali testi nuovi vanno chiesti nel report.

### 3.4 Errori e casi limite

- Nome vuoto o assente → `generic`.
- `Alias` cambiato dall'utente in un nome che non corrisponde → torna `generic`.
  È voluto: chi rinomina deve poter uscire dall'automatico.
- Cambio di profilo durante un rilascio in corso: il ritardo già programmato non si modifica;
  il nuovo vale dalla ripresa successiva.
- Configurazione con `profile` sconosciuto → `ConfigInvalid`, come oggi.

### 3.5 Rilascio 1.0.1

Stesso processo della spec 05: candidata separata, verifiche, archivio firmato, nessuna
sovrascrittura della 1.0.0 sigillata.

- Versione 1.0.1 in tutti i punti in cui oggi c'è 1.0.0: pacchetto, AppStream `<release>` con
  nota in en/it/de, `NEWS`/changelog.
- Repository apt e Flatpak aggiornati; il sito riceve solo la candidata verificata.
- `README`: righe sul profilo automatico e nota per gli utenti della 1.0.0.
- **Pubblicazione fuori scope per Codex.** Push, tag pubblico, release GitHub e
  `wrangler deploy` li fanno Claude e GM, dopo il sì di GM. Codex si ferma a candidata
  verificata e pronta.
- Coordinamento col sito: la chat «Sito ed email» sta modificando `scambio-site`. Codex aggiunge
  solo gli asset della candidata nei percorsi di rilascio già esistenti, senza toccare HTML,
  CSS o JS. Prima di committare, fa rebase sull'ultimo commit di `scambio-site`.

## 4. Fuori scope

- Altri profili (cuffie di altre marche) e tabelle di modelli.
- UI per scegliere il profilo.
- Qualsiasi modifica a `design/`, al sito (oltre agli asset di rilascio), alla waitlist o al
  Worker.
- GNOME, warning dei test, `Gtk.ShortcutLabel`.

## 5. Dipendenze

Nessuna dipendenza nuova.

## 6. Checklist di done

- [ ] Ogni regola di §3.1 ha un test:
  - regex con i casi di §3.1.2;
  - precedenza `config` > `auto`;
  - `resume_delay_ms` esplicito che vince;
  - ricalcolo su cambio di `Alias` e su comparsa del dispositivo (dbusmock BlueZ);
  - `generic` finché il dispositivo è ignoto;
  - log una sola volta.
- [ ] Test del parser: default `auto`; i tre valori validi; `TEMPLATE` aggiornato e
  ri-analizzabile.
- [ ] Proprietà D-Bus `DeviceProfile` e `DeviceProfileSource` con `PropertiesChanged`;
  `scambio status` le stampa.
- [ ] `make check` verde; nessun test saltato; nessun polling introdotto.
- [ ] Candidata 1.0.1 costruita e verificata come in spec 05: firme, hash, install, upgrade da
  1.0.0 e rimozione su Ubuntu 24.04 e Debian 13; Flatpak.
- [ ] La 1.0.0 sigillata è intatta.
- [ ] `docs/verification/06/report.md` contiene:
  - le evidenze;
  - le richieste per `02-architecture.md`;
  - la misura CPU/RSS a riposo;
  - la checklist di prova reale per GM: occhiali Meta con config pulita, ripresa dopo
    l'annuncio, upgrade da 1.0.0 con `profile` già scritto.
- [ ] Decisioni tecniche in `docs/decisions.md`, nell'intervallo **210–219**.
- [ ] Prova reale eseguita da GM: … · Firma: GM, data.

## 7. Note di revisione (Claude, dopo la consegna)

## 8. Revisione preventiva di Claude (inviata a GM prima del /goal)

1. **Rischio regex «meta»:** con `\bmeta\b` un dispositivo chiamato per esempio «Meta Quest»
   (visore) prenderebbe un ritardo di 2 s inutile, ma innocuo. Accettato: sbagliare in quel
   verso costa poco, mentre l'annuncio sopra la musica è proprio il difetto da togliere.
2. **Configurazioni 1.0.0 con `generic` scritto:** restano senza automatico. Scelto di non
   migrare per coerenza con la decisione (l); copre la nota di rilascio.
3. **Tempi:** l'unità è piccola. Il collo di bottiglia è il rilascio (build, verifiche su
   container, firma). Se domenica sera non è pronta, vale il piano B della decisione 187:
   lancio con una nota nel README.

## 9. Domande aperte

Nessuna di prodotto.

## Comando `/goal`

```
/goal Implementa docs/specs/06-profilo-automatico-1.0.1.md seguendo AGENTS.md e docs/context/.
Fatto solo quando ogni voce della Checklist di done è soddisfatta con evidenza e `make check` è
verde. Scope: solo §3; §4 non si tocca; design/ non si modifica; niente push, tag pubblici,
release GitHub o deploy: ti fermi alla candidata 1.0.1 verificata. Decisioni tecniche 210–219.
Stop: se la spec contraddice AGENTS.md o manca una decisione di prodotto, fermati e scrivilo
nel report.
```
