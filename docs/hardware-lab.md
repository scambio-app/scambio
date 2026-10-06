# Hardware lab — misure sul campo

Solo misure, datate, con ambiente e metodo. È l'autorità sul comportamento dell'hardware
(`AGENTS.md`). Una misura superata non si cancella: si aggiunge la nuova e si marca la vecchia.

## Ambiente di riferimento

PC `casa`: Kubuntu 24.04.5, KDE Plasma 5.27.12, xdg-desktop-portal-kde 5.27.11, BlueZ 5.72,
PipeWire con pipewire-pulse, Python 3.12.3, PyGObject presente. Dispositivo: Oakley Meta 002Z,
già accoppiato e `Trusted=yes`; profili A2DP (SBC, SBC-XQ), HFP/HSP (CVSD, mSBC), AVRCP.
Telefono: iPhone di GM.
Aggiornamento 2026-10-05 (orchestratore): installato `gettext` 0.21 (`msgfmt`, `xgettext`) via
`apt-get`, prerequisito della spec 03.

## 2026-10-04 — M1: presa dal PC con musica sull'iPhone

Metodo: `bluetoothctl connect/disconnect` cronometrati; `pactl` interrogato ogni 0,1–0,5 s (solo
per la misura); osservazione di GM.

| Misura | Esito |
|---|---|
| Connessione dal PC mentre l'iPhone suona | riesce: il PC «ruba» il collegamento, la musica dell'iPhone si ferma |
| Tempo `connect` | 1,2 s |
| Uscita `bluez_output.*` in PipeWire | +0,5 s (totale ≈ 1,7 s) |
| Audio PC → occhiali | funziona |
| Cambio profilo A2DP ↔ HFP mSBC | < 30 ms lato PipeWire; il microfono appare come `bluez_input.*` (16 kHz mono) |
| Tempo `disconnect` | 2,4 s |
| Dopo il rilascio | l'iPhone si ricollega da solo; la musica resta in pausa |
| Riconnessione spontanea al PC nei 40 s successivi | no |

## 2026-10-04 — M2: presa dal PC durante una chiamata WhatsApp sull'iPhone

Metodo: chiamata WhatsApp con voce negli occhiali; `connect`, attesa 5 s, `disconnect`;
osservazione di GM; due ripetizioni.

| Misura | Esito |
|---|---|
| Connessione durante la chiamata | riesce (0,76 s e 1,67 s) |
| Effetto sulla chiamata | non cade; la voce passa all'iPhone |
| Profilo attivo sul PC | A2DP |
| Dopo il rilascio (`disconnect` 2,2 s) | la chiamata torna negli occhiali da sola |

## 2026-10-04 — M3: riconnessione spontanea all'accensione (Q3)

Metodo: `dbus-monitor` sui segnali `PropertiesChanged` del dispositivo sul bus di sistema +
journal di bluetoothd; GM chiude gli occhiali nella custodia (15 s), li riapre e li indossa;
osservazione per 30–50 s. Configurazione BlueZ di default (`ReconnectAttempts` non impostato).

| Prova | Partenza | Esito |
|---|---|---|
| A — iPhone con Bluetooth acceso | occhiali sul PC | alla chiusura della custodia il link cade (Connected=false); alla riapertura **si collegano all'iPhone**; il PC non tenta di riprenderli |
| B — iPhone con Bluetooth spento | occhiali scollegati | alla riapertura **non si collegano al PC** per ≥ 50 s, pur essendo in portata (connessione manuale dal PC subito dopo riuscita in 1,86 s) |

Conclusioni: gli occhiali, all'accensione, cercano solo il telefono; né loro né bluetoothd
avviano da soli una connessione col PC. Con `Trusted=yes` non si osservano prese spontanee: il
demone non deve modificare `Trusted`. Unico caso non coperto: perdita di link non volontaria
(fuori portata) mentre sono sul PC, con la logica di riconnessione di BlueZ — da osservare se
emergono problemi.

## 2026-10-04 — M4: `pactl -f json` 16.1 (software, per la spec 01)

Metodo: `pactl -f json subscribe` letto da pipe con timestamp; `paplay` con proprietà
`media.name`/`media.role` impostate; confronto fra locale `it_IT` e `LC_ALL=C`.

| Misura | Esito |
|---|---|
| Formato di `subscribe` | oggetti JSON **concatenati senza separatori** (niente a capo) |
| Bufferizzazione su pipe | nessuna: ogni evento arriva subito (scarto < 10 ms) |
| Localizzazione | con locale italiano i valori sono tradotti (`"nuovo"`, `"sorgente"`, `"scheda"`); con `LC_ALL=C` sono stabili (`new`, `change`, `remove`; `sink-input`, `sink`, `source`, `card`, `client`) |
| Stringhe non ASCII | sostituite con `"(null)"` e avviso su stderr; il JSON resta valido |
| Eventi di uno stream breve | `new` client → `new` sink-input → più `change` → `remove` sink-input (≈ 0,2 s per un suono breve) |
| Campi utili di un sink-input | `corked`, `sink`, `properties.media.role`, `properties.application.name`, `properties.application.process.binary` |
| Sink Bluetooth | `properties.api.bluez5.address` = MAC del dispositivo; nome `bluez_output.<MAC con _>.1` |

## 2026-10-04 — M5: stream dei browser in pausa e uscita predefinita

Metodo: script usa e getta che a ogni evento `sink-input` di `pactl subscribe` stampa i
sink-input (app, ruolo, `corked`); GM avvia e mette in pausa un video YouTube in **Google
Chrome**, poi chiude la scheda. Occhiali collegati al PC durante la prova.

| Misura | Esito |
|---|---|
| Ruolo degli stream di Chrome | nessuno (`media.role` assente) |
| Stream in pausa | Chrome lo segna `corked` e lo **chiude ≈ 5 s dopo** (osservato due volte) |
| Stream multipli | Chrome ha aperto un secondo stream durante la riproduzione; è rimasto non `corked` per ≈ 28 s prima di passare a `corked` e chiudersi; il momento esatto della pausa non è stato cronometrato, quindi il ritardo massimo resta incerto (≤ 30 s) |
| Uscita predefinita | in WirePlumber non è configurato un sink predefinito (`default-nodes` ha solo la sorgente): con gli occhiali collegati il predefinito diventa da solo `bluez_output.80_AA_1C_XX_XX_XX.1` |

Conclusione: con Chrome il «silenzio» basato su stream chiusi o `corked` funziona; il ritardo
(≤ 30 s nel caso peggiore osservato) è piccolo rispetto ai 120 s del rilascio. Firefox non
misurato.

## 2026-10-04 — M6: segnali di blocco schermo (KDE Plasma 5.27)

Metodo: `dbus-monitor` sul bus di sistema (`PropertiesChanged` della sessione grafica presa da
`login1.User.Display`, qui `session/_32`) e sul bus di sessione (`org.freedesktop.ScreenSaver`,
`org.kde.screensaver`); GM blocca con Meta+L e sblocca con la password; due cicli.

| Misura | Esito |
|---|---|
| Ordine al blocco | `org.kde.screensaver.AboutToLock` → dopo ≈ 0,27 s `ScreenSaver.ActiveChanged(true)` e `LockedHint = true` (stesso millisecondo) |
| Allo sblocco | `ActiveChanged(false)` e `LockedHint = false` insieme |
| Coerenza delle fonti | le due fonti concordano sempre (2 cicli su 2) |
| `ActiveChanged` | emesso due volte, su `/ScreenSaver` e su `/org/freedesktop/ScreenSaver`: va deduplicato |
| Ritardo massimo di inibizione | `InhibitDelayMaxUSec` di logind = 30 s su `casa` |

## 2026-10-04 — M7: cambio profilo A2DP ↔ HFP e scollegamento

Metodo: occhiali collegati al PC; `pactl -f json subscribe` con timestamp;
`pactl set-card-profile` da `a2dp-sink` a `headset-head-unit` e ritorno; poi
`bluetoothctl disconnect`.

| Misura | Esito |
|---|---|
| Profili della scheda | `off`, `a2dp-sink`, `a2dp-sink-sbc_xq`, `headset-head-unit`, `headset-head-unit-cvsd`, `headset-head-unit-msbc` |
| Cambio profilo | il sink viene rimosso e ricreato con **lo stesso nome** `bluez_output.80_AA_1C_XX_XX_XX.1` (nuovo indice) in < 10 ms, nello stesso blocco di eventi |
| `api.bluez5.profile` | cambia (`a2dp-sink` ↔ `headset-head-unit`); `api.bluez5.address` resta |
| Uscita predefinita durante il cambio | resta il sink Bluetooth (stesso nome) |
| Dopo lo scollegamento | il sink sparisce; WirePlumber rende predefinita da sola la Scarlett (nessun predefinito configurato) |

Conseguenza: con la coalescenza a 50 ms un cambio di profilo di norma non produce nemmeno
`DeviceSinkGone`; se lo produce, la ricomparsa arriva ben dentro `sink_timeout_seconds`.

## 2026-10-04 — M8: osservazioni di GM durante la prova reale della spec 01

Metodo: Scambio in esecuzione (spec 01, `grab_delay_ms = 500`), YouTube in Chrome sul PC, iPhone
di GM; osservazione diretta di GM con il log del demone.

| Osservazione | Esito |
|---|---|
| Presa con ritardo 0,5 s | percepita «molto più veloce», audio quasi subito |
| Annuncio vocale degli occhiali alla connessione | presente in una presa precedente, assente nelle successive (non sistematico) |
| Notifiche dell'iPhone con occhiali sul PC | si sentono negli occhiali **sovrapposte** all'audio del PC |
| Musica avviata sull'iPhone con occhiali sul PC | suona dagli altoparlanti dell'iPhone (il PC non viene «rubato») |
| Custodia chiusa con video in riproduzione sul PC | `external_disconnect` dopo ≈ 4 s; uscita tornata alla Scarlett. **Poi, 2,6 s dopo, nuova presa automatica** (fallita dopo 5,2 s perché gli occhiali erano chiusi): Chrome ha ricreato o fermato lo stream durante lo spostamento sulla Scarlett e la breve assenza di stream (> 50 ms) è stata letta come «silenzio», azzerando l'anti ping-pong (G1). Causa dedotta dai tempi, non osservata direttamente |
| Astine chiuse mentre sono sul PC (video in corso) — correzione di GM: togliendoli dal viso la connessione **non** cade, chiudendo le astine sì | si scollegano dal PC subito (`external_disconnect` alle 08:15:09 del 5 ottobre); 2,6 s dopo Scambio ritenta la presa e fallisce in 5,2 s (stesso difetto del punto 14). Rimessi, pausa e ripresa del video: **nessuna nuova presa** per 6 minuti: corretto, perché il video su Chrome ha continuato a suonare dalla Scarlett, quindi l'anti ping-pong (attivato dalla presa fallita) non è mai caduto |
| Connessione manuale dall'applet KDE con occhiali sull'iPhone (dopo astine chiuse/riaperte) | collegamento base riuscito ma audio rifiutato dagli occhiali (bluetoothd: HFP «Software caused connection abort», AVDTP «Permission denied»/timeout); scollegamento dopo 5–25 s. La `Connect()` di Scambio invece prende gli occhiali anche dall'iPhone (M1) |
| Chiamata WhatsApp: presa dal PC durante la chiamata, poi switch | la voce passa al telefono, poi torna negli occhiali da sola dopo lo switch, ma «ci mette un po'» (scollegamento del PC 2,2 s più la riconnessione dell'iPhone; tempo totale non cronometrato) |

## 2026-10-05 — M9: Firefox in pausa e controllo MPRIS (Claude, senza GM)

Metodo: Firefox 157 (snap) con un profilo temporaneo fuori dalla repo e una pagina locale con un
tono a 440 Hz in `<audio autoplay loop>`; script usa e getta su `pactl -f json subscribe` che
stampa i sink-input a ogni evento; comandi MPRIS `Pause`/`Play` con `gdbus`, lanciati sia dal
ponte di Claude sia con `systemd-run --user` (stesso contesto di un servizio utente come
Scambio). Occhiali non collegati (uscita: Scarlett).

| Misura | Esito |
|---|---|
| Nome MPRIS | `org.mpris.MediaPlayer2.firefox.instance_1_<N>`, owner = processo principale di Firefox; registrato solo dopo l'avvio della riproduzione |
| `Pause` da processo con etichetta AppArmor diversa da `unconfined` (ponte di Claude) | rifiutata: `AccessDenied` dalla policy AppArmor dello snap (anche i segnali `kill`) |
| `Pause`/`Play` da `systemd-run --user` (non confinato, come Scambio) | funzionano; risposta in ≈ 40 ms |
| Stream dopo `Pause` | `corked = true` entro ≈ 0,2 s e **resta aperto** (osservato ≥ 50 s) |
| Stream dopo `Play` | il vecchio stream viene rimosso e ne nasce uno **nuovo** sull'uscita predefinita, nello stesso blocco di eventi |
| `PlaybackStatus` subito dopo `Pause` | `Paused` (lettura ≈ 40 ms dopo) |
| Altri player MPRIS presenti su `casa` | `chromium.instance<N>` (Chrome, `Identity` = `Chrome`), `Gwenview`; entrambi `Stopped` a riposo |

Conclusione: per Firefox il «silenzio» basato su `corked` funziona subito (M5 chiuso per
Firefox); MPRIS è utilizzabile da Scambio come servizio utente. Effetto collaterale: un `Play`
di prova alle 13:01 ha fatto partire una presa automatica di Scambio, fallita in 5 s perché gli
occhiali non erano raggiungibili.

## 2026-10-05 — M10: WirePlumber ricorda il muto degli stream (Claude, senza GM)

Metodo: `pacat` di silenzio (`/dev/zero`) con `application.name=ScambioMisura`;
`pactl set-sink-input-mute <idx> 1`; lettura di `~/.local/state/wireplumber/restore-stream`;
nuovo `pacat` con lo stesso nome applicazione. WirePlumber 0.4.17.

| Misura | Esito |
|---|---|
| Dopo il muto di uno stream | `restore-stream` registra `Output/Audio:application.name:ScambioMisura:mute=true` entro 1,5 s |
| Nuovo stream della stessa applicazione | **parte già muto** |

Conseguenza: mettere in muto uno stream (per esempio Chrome) durante la presa renderebbe muti
anche gli stream successivi della stessa applicazione, e dopo un crash resterebbe muta per
sempre. La spec 02 usa solo la pausa MPRIS (decisione 51). Residuo della misura: la voce
`ScambioMisura` resta nel file di WirePlumber, innocua.

## 2026-10-05 — M11: icone del tray via `IconThemePath` su Plasma 5.27 (Claude, senza GM)

Nota (orchestratore, 2026-10-05): numero M11 assegnato due volte da due chat parallele; per distinguerle si citano come **M11-icone** e **M11-annuncio**. Prossimo numero libero: M13.

Metodo: script usa e getta fuori dalla repo (`/tmp/sniprobe`) che esporta un
`org.kde.StatusNotifierItem` minimo con `IconThemePath` = `design/icons` e cambia `IconName`
ogni 4 s sui sei stati; screenshot con `spectacle -b -n -f`, ritagliati sul tray. Tema
`BreezeDark` (non cambiato per non disturbare GM).

| Prova | Esito |
|---|---|
| Icone in `hicolor/symbolic/status/` (con `index.theme` proprio) | **non trovate**: Plasma ripiega sull'icona a colori `app.scambio.Scambio` (toglie i suffissi del nome) per tutti gli stati |
| Icone in `hicolor/scalable/status/` | trovate e **ricolorate** dal tema: occhiali chiari su pannello scuro, punto esclamativo rosso; i sei stati distinti a 22 px |
| `StatusNotifierWatcher` | servizio di `kded5` (PID dal bus); server delle notifiche = `plasmashell` |
| Ambiente utente di systemd | `LANG=it_IT.UTF-8`, nessun `LANGUAGE` |

Conseguenza: KIconLoader usa le cartelle dell'`index.theme` di sistema di hicolor (che elenca
`scalable/status` ma non `symbolic/status`). Non misurati: tema chiaro, GNOME con AppIndicator.

## 2026-10-05 — M11b: annuncio vocale degli occhiali alla connessione (GM + Claude)

Numerata M11b perché M11 è già la misura delle icone del tray (stessa data, chat di design);
la spec 02 la cita come M11b.

Metodo: script usa e getta `~/Scrivania/Claude/scambio-misure/annuncio.py` (Scambio fermo):
occhiali indossati sull'iPhone; `bluetoothctl connect`; appena compare il sink Bluetooth parte
`paplay` di un bip ogni 0,5 s sul sink; GM preme INVIO al primo bip udito (tempo di reazione
incluso, ≈ 0,2–0,3 s); 3 giri, scollegamento e ritorno all'iPhone fra un giro e l'altro.

| Giro | `Connected` | Sink | Primo bip udito (dal sink) | Annuncio |
|---|---|---|---|---|
| 1 | 1,12 s | 1,72 s | 1,26 s | sì |
| 2 | 0,27 s | 0,87 s | 1,00 s | sì |
| 3 | 1,43 s | 2,13 s | 0,95 s | sì |

Conclusione: l'annuncio c'è stato in 3 prese su 3 (in M8 sembrava non sistematico) e l'audio
del PC diventa udibile ≈ 1,0–1,3 s dopo la comparsa del sink. GM non sa dire se i bip fossero
dopo o sopra l'annuncio («era veloce»). Il ritardo di ripresa di 2000 ms (decisione 56) copre
l'annuncio con margine; alla prova reale della spec 02 GM l'ha giudicato «perfetto».

## 2026-10-05 — M12: prova reale della spec 02 (GM, log di Scambio)

Metodo: Scambio su `5aa3e70`/`7da08ef`, occhiali e iPhone di GM, journal del demone letto da
Claude dopo i passi.

| Osservazione | Esito |
|---|---|
| Presa con video YouTube in Chrome | pausa e presa nello stesso secondo; ripresa negli occhiali 2 s dopo `on_pc`; GM: «va da dio» |
| Prima riproduzione in una finestra nuova di Firefox | presa **senza pausa**: nessun player MPRIS in `Playing` al momento della presa (Firefox registra il nome MPRIS solo dopo l'inizio della riproduzione, M9). Dalle prese successive Firefox viene messo in pausa e ripreso |
| Blocco schermo, switch, astine chiuse, Bluetooth spento con video negli occhiali | rilascio con pausa, nessuna ripresa (decisione 50) |
| Riapertura delle astine con il video ripreso a mano | nuova presa solo dopo 11 s di silenzio (anti ping-pong) |
| `paplay` (senza MPRIS) | presa senza pausa (decisione 51) |
| **Doppio switch** (`scambio switch; scambio switch`) con video negli occhiali | **difetto**: `DisconnectResult(ok)` arriva **prima** di `Connected=false`; L1 riparte subito con la presa, il `Connected=false` ritardato viene letto come presa fallita (C8, `connect_failed` nello stesso millisecondo), Firefox riprende **sulla Scarlett**; 3,5 s dopo la `Connect` ancora in corso riesce e Scambio adotta gli occhiali come presa esterna (R5), quindi il video passa negli occhiali senza pausa |
| Doppio switch dopo la correzione 68 (`545da48`) | `DisconnectResult(ok)` ignorato finché `Connected=false`; presa 1,9 s dopo il rilascio, ripresa negli occhiali: ok |
| Chiamata GSM (Q4) | non misurata: GM la considera equivalente a WhatsApp (M2) e a casa non ha rete (decisione 67) |

## Conseguenze per il design

- Il PC non può sapere prima di connettersi se il telefono usa il dispositivo: «non prendere se
  occupato» non è realizzabile.
- Una presa durante una chiamata è reversibile (switch → la chiamata torna da sola).
- La pausa durante la presa dura ≈ 2 s: sostenibile.

## Da misurare

- Q5: portal GlobalShortcuts su Plasma 5.27.
- Latenza della prima uscita audio in HFP (apertura del link SCO).
- Passaggio automatico a HFP quando un'app apre il microfono (autoswitch di WirePlumber).
- Se l'annuncio vocale si può disattivare dall'app Meta AI (durata misurata in M11b).

## 2026-10-05 — M13: portal GlobalShortcuts su casa (Q5, orchestratore, senza GM)

Metodo: `busctl --user introspect org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop`,
proprietà `version`, file `/usr/share/xdg-desktop-portal/portals/*.portal`.

| Misura | Esito |
|---|---|
| Interfaccia `org.freedesktop.portal.GlobalShortcuts` esposta | sì, `version` = 1 |
| Backend che la implementa | `kde.portal` (xdg-desktop-portal-kde 5.27.11) |
| Frontend | xdg-desktop-portal 1.18.4 |

Conclusione: la via portal per la scorciatoia della spec 04 è disponibile su casa. Resta da provare
nel funzionamento reale (CreateSession → BindShortcuts → dialogo KDE → segnale `Activated`): va
nella spec 04 come prima prova, con riserva CLI se fallisce. GNOME non misurato.

