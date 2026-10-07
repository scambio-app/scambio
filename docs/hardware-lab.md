# Hardware lab — misure sul campo

Solo misure, datate, con ambiente e metodo. È l'autorità sul comportamento dell'hardware
(`AGENTS.md`). Una misura superata non si cancella: si aggiunge la nuova e si marca la vecchia.

## Ambiente di riferimento

PC `casa`: Kubuntu 24.04.5, KDE Plasma 5.27.12, xdg-desktop-portal-kde 5.27.11, BlueZ 5.72,
PipeWire con pipewire-pulse, Python 3.12.3, PyGObject presente. Dispositivo: Oakley Meta 002Z,
già accoppiato e `Trusted=yes`; profili A2DP (SBC, SBC-XQ), HFP/HSP (CVSD, mSBC), AVRCP.
Telefono: iPhone di GM.

> **Cambio di ambiente — 2026-10-07 11:43 (misurato dall'orchestratore alle 13:45):** `casa` è stata
> aggiornata a **Ubuntu 26.04.1 LTS, KDE Plasma 6.6.6, BlueZ 5.85, pactl 17.0, Python 3.14.4**
> (`/etc/os-release`, `plasmashell --version`, `bluetoothctl --version`, `pactl --version`, log in
> `/var/log/dist-upgrade/`). Tutte le misure precedenti (M1–M19) sono state fatte su Ubuntu 24.04 /
> Plasma 5.27 / BlueZ 5.72 / Python 3.12: dove dipendono da Plasma, dal portal o da BlueZ (in
> particolare M13 portal, M14 clic sinistro del tray e decisione 85, comportamento di
> Disconnect/Connected della decisione 68) vanno **rivalidate** su questo ambiente. La `.venv` è stata
> ricreata con Python 3.14 alle 11:48 senza i console script di sviluppo: l'orchestratore ha
> reinstallato `pytest` nella venv; `make check` di nuovo verde (731 test).
>
> **Rivalidazioni su questo ambiente (Claude, 2026-10-07 sera):** M13/M16 per il portal → **M20**;
> M14 (clic sul tray) e M11 (icone) → **M21**; decisione 68 → **M22**. Sessione **Wayland**; GTK 4.22,
> libadwaita 1.9, kglobalacceld 6.6.5 (i metodi a interi di KGlobalAccel misurati in M16/M18
> funzionano anche qui: Scambio registra Meta+G).

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

- ~~Q5: portal GlobalShortcuts su Plasma 5.27~~ — misurato in M16 (2026-10-07): non utilizzabile, si usa KGlobalAccel.
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

## 2026-10-06 — M14: clic sull'icona del tray su Plasma 5.27 (GM + Claude)

Metodo: Scambio a `f4082a5` (spec 03 consegnata) riavviato alle 11:01; `dbus-monitor` filtrato sul
nome unico del demone mentre GM clicca sull'icona con il tasto sinistro e con il destro;
sorgente QML del systemtray (`plasma-workspace` 5.27.12,
`org.kde.plasma.private.systemtray/contents/ui/items/StatusNotifierItem.qml`).

| Osservazione | Esito |
|---|---|
| Clic sinistro | `plasmashell` chiama `ProvideXdgActivationToken` (risposta `UnknownMethod`) e poi `Activate(x, y)`; Scambio risponde con successo e **non si apre nulla**: `ItemIsMenu = true` è ignorato |
| QML del systemtray | `onActivated` apre il menu contestuale **solo se** il job `Activate` fallisce (`if (!job.result) openContextMenu`) |
| Clic destro | `AboutToShow(0)`, poi `Event(0, "opened")`; menu mostrato; `Event(0, "closed")` e `Event(5, "clicked")` → `SetPriority` dal demone stesso: funziona |
| Icone con Breeze scuro | «occhiali + telefono» ricolorata dal tema (conferma M11) |
| Prese e rilasci reali | GM: icona corretta sia con gli occhiali sul PC sia sull'iPhone |

Conseguenza: decisione 85 (`Activate` risponde con un errore). Non misurati: tema chiaro, GNOME.

## 2026-10-06 — M15: presa subito dopo un rilascio verso l'iPhone (GM + Claude, prova reale spec 03)

Metodo: journal di Scambio (`d33afa1`) e di `bluetoothd` durante il passo 5 della prova reale
(`scambio switch` dal PC, poi «Annulla» nella notifica).

| Momento | Fatto |
|---|---|
| 11:49:11,56 | `on_pc → releasing (switch)` |
| 11:49:13,80 | rilascio finito; «Annulla» premuto ≈ 2 s dopo lo switch → `releasing → connecting (switch)`; bluetoothd: «No matching connection for device» |
| 11:49:23,70 | `connect_timeout` dopo 10 s, notifica d'errore |
| 11:49:32–11:49:54 | tre `Switch` di GM: `connect_failed` in 0,1–1,2 s; bluetoothd: AVDTP «Connection reset by peer (104)», poi «Operation already in progress (114)», SDP HFP non leggibile |
| 11:50:33 | `Switch` di Claude: `on_pc` in 1,9 s, normale |

Conclusione: per ≈ 30–40 s dopo il rilascio (mentre gli occhiali passano all'iPhone) il PC può
essere rifiutato; il recupero è spontaneo. In M12 un doppio switch con ≈ 2 s fra i due comandi era
riuscito: il comportamento non è sistematico. Non è un difetto del tray (il pulsante ha chiamato
`Switch` come da contratto). Ripetizione (2026-10-07 00:14): «Annulla» ≈ 6,5 s dopo lo switch →
`on_pc` in 4,3 s. Il rifiuto si presenta solo con una presa nei primissimi secondi dopo il
rilascio; nessuna modifica per ora (se dà fastidio nell'uso: ritardo minimo prima di una presa
che segue un rilascio, da decidere con GM).

## 2026-10-07 — M16: scorciatoia globale su Plasma 5.27 — portal e KGlobalAccel (Claude, senza GM)

Metodo: script usa e getta fuori dalla repo (`~/Scrivania/Claude/scambio-misure/portal_probe.py`,
`kglobalaccel_probe.py`, `kga_conflict.py`, `xtest_key.py`); journal di
`xdg-desktop-portal-kde` (debug già attivo); sorgente di `globalshortcuts.cpp` di
xdg-desktop-portal-kde **v5.27.11**; pressione dei tasti simulata con XTest (sessione X11: passa dal
server X come un tasto fisico); copia di `~/.config/kglobalshortcutsrc` prima delle prove e
confronto finale (identico: nessun residuo). Scambio attivo con gli occhiali sul PC; Meta+G non è
mai stato premuto (è il binding khotkeys della decisione 99).

**Portal `org.freedesktop.portal.GlobalShortcuts` (v1, frontend 1.18.4, backend KDE 5.27.11)**

| Passo | Esito |
|---|---|
| `CreateSession` | riesce subito (`Response` 0); `app_id` ricavato dallo scope systemd del processo chiamante (qui `com.anthropic.Claude`) |
| `BindShortcuts` con `preferred_trigger` | `Response` 0 con `shortcuts = []`: il backend 5.27 **ignora le scorciatoie passate** e si limita ad aprire `systemsettings://kcm_keys/<app_id>` |
| Dove il backend 5.27 legge le scorciatoie | solo dall'opzione `shortcuts` di `CreateSession` (bozza vecchia dell'API); il frontend 1.18 **la filtra** (log del backend: «Wrong global shortcuts type … instead of ""»), quindi la sessione resta vuota |
| `ListShortcuts` | nessuna `Response` entro 25 s |
| `Activated` | mai emesso (nessuna scorciatoia legata) |
| Dialogo KDE | nessuno in primo piano (screenshot) |

Conclusione: su Plasma 5.27 + xdg-desktop-portal 1.18 (Kubuntu 24.04) il portal **non permette di
legare una scorciatoia**; il backend KDE implementa `BindShortcuts` per davvero solo da Plasma 6.

**KGlobalAccel su D-Bus (`org.kde.kglobalaccel`, `/kglobalaccel`, `org.kde.KGlobalAccel`)**

| Prova | Esito |
|---|---|
| `doRegister([comp, azione, nome comp, nome azione])` + `setShortcut(id, [Meta+F9], 2 = SetPresent)` | restituisce `[Meta+F9]` (interi Qt); voce scritta in `kglobalshortcutsrc` (`switch=Meta+F9,none,…`) |
| Oggetto del componente | `getComponent(comp)` → `/component/<comp con «.» → «_»>`, interfaccia `org.kde.kglobalaccel.Component` |
| Tasto premuto (XTest) | segnali `globalShortcutPressed(comp, azione, ts)` e `globalShortcutReleased` in ≈ 30 ms |
| `invokeShortcut(azione, "default")` sul componente | emette `globalShortcutPressed` (utile per provare senza tastiera) |
| Tasto già usato (Meta+G di khotkeys) | `setShortcut` → `[0]` (rifiutato); `action(tasto)` restituisce il proprietario (`khotkeys`, «Connetti Oakley») |
| Dopo un rifiuto | la voce resta `switch=,none,…`: quando il tasto si libera, `setShortcut` **con** autoload restituisce ancora `[0]` (ricorda il «nessun tasto»); con il flag 4 (`NoAutoloading`) lo prende |
| `setInactive(id)` + `unregister(comp, azione)` | voce rimossa dal file |

Conseguenze per la spec 04: su Plasma (5 e 6) la scorciatoia si registra con KGlobalAccel su D-Bus,
senza dipendenze nuove; il portal resta la via per i desktop senza `org.kde.kglobalaccel` (GNOME ≥ 48,
non misurato). Per il portal conta l'`app_id` ricavato dall'unità systemd: con l'unità attuale
`scambio.service` sarebbe vuoto (da verificare su GNOME prima della fase 5).

Ambiente (stessa data): su `casa` mancano `gir1.2-gtk-4.0` (GTK 4.14), `gir1.2-adw-1` (libadwaita
1.5) e `blueprint-compiler` (0.12), tutti disponibili nei repository di Ubuntu 24.04: prerequisiti
della finestra della spec 04.

## 2026-10-07 — M17: icona del tray dopo `ui.tray = false` (Claude, senza GM)

Metodo: Scambio a `38ac33f` (nome unico `:1.3389`); copia di `config.toml`, aggiunta di
`tray = false` in `[ui]`, `systemctl --user reload scambio`, lettura di
`RegisteredStatusNotifierItems` del watcher (`kded5`) e screenshot del pannello; ripristino del file e
nuovo reload (file identico all'originale). Poi script usa e getta
`~/Scrivania/Claude/scambio-misure/sni_release_probe.py`: registrazione con un nome noto
`org.kde.StatusNotifierItem-<pid>-1`, poi `ReleaseName` con la connessione ancora aperta.

| Prova | Esito |
|---|---|
| `ui.tray = false` + reload (registrazione col nome unico, oggetto ritirato) | l'item `:1.3389/StatusNotifierItem` **resta** nel watcher e l'icona resta nel pannello |
| Registrazione con nome noto, poi `ReleaseName` | l'item sparisce dal watcher entro 1 s, senza chiudere la connessione |

Conseguenza: debito della spec 03 confermato; correzione con la decisione 108.

## 2026-10-07 — M18: KGlobalAccel (cambio dall'esterno, nomi) e riavvio di un servizio `Type=dbus` (Claude, senza GM)

Metodo: script usa e getta in `~/Scrivania/Claude/scambio-misure/` (`kga_foreign.py`,
`exit75_probe.py`, `restartunit_probe.py`); unità transitorie `systemd-run --user -p Type=dbus
-p BusName=… -p Restart=on-failure -p RestartSec=1|2` con un nome di prova; `kglobalshortcutsrc`
confrontato con la copia di M16 alla fine (identico).

**KGlobalAccel (Plasma 5.27, KF5)**

| Prova | Esito |
|---|---|
| Un secondo client (come la KCM delle scorciatoie) chiama `setForeignShortcut(actionId, [Meta+F10])` | il proprietario riceve **`yourShortcutsChanged(as actionId, a(ai) keys)`** su `/kglobalaccel` (`org.kde.KGlobalAccel`); `keys` = `[[285212729, 0, 0, 0]]` (una sequenza = 4 interi). Il nome `yourShortcutGotChanged` non compare |
| Nuova `doRegister` con un nome leggibile diverso, poi `setShortcut(…, 2)` | il file mostra il nome nuovo (`switch=Meta+F10,none,Nome due`) e il tasto scelto dall'altro client resta |

**Riavvio di un servizio `Type=dbus` voluto dal servizio stesso**

| Prova | Esito |
|---|---|
| `ReleaseName`, poi uscita con 75 (`Restart=on-failure`, con e senza `RestartForceExitStatus=75`) | systemd vede sparire il nome e **ferma** l'unità (`SIGTERM` prima dell'uscita 75): `Result=success`, nessun riavvio |
| Uscita con 75 tenendo il nome | nessun riavvio (`Result=success`, `NRestarts=0`): la sparizione del nome vince anche qui |
| Il servizio chiama `RestartUnit("<propria unità>", "replace")` sul gestore utente di systemd (unità letta dall'ultimo segmento di `/proc/self/cgroup`) | risposta con il job, poi `SIGTERM` (arresto ordinato) e nuovo avvio **50 ms** dopo l'uscita, nella stessa unità |

Conseguenza per la spec 04: il cambio di dispositivo usa `RestartUnit` sulla propria unità, non
l'uscita con un codice (corregge la decisione 105 prima del `/goal`).

## 2026-10-07 — M19: Meta+G dopo la rimozione dell'azione khotkeys (GM + Claude)

Metodo: GM elimina l'azione khotkeys «Connetti Oakley» (backup del 7 ottobre in
`~/.config/khotkeysrc.bak-20261007-scambio`); Claude interroga `action(Meta+G)` di KGlobalAccel,
lancia `reread_configuration` del modulo khotkeys di `kded5` e, con copia di
`~/.config/kglobalshortcutsrc` (`.bak-20261007-spec04`), chiama
`unregister("khotkeys", "{4bc38507-…}")`.

| Prova | Esito |
|---|---|
| Azione assente da `khotkeysrc`, anche dopo `reread_configuration` | Meta+G **resta** a khotkeys in KGlobalAccel (voce `{4bc38507-…}=Meta+G,none,Connetti Oakley`) |
| `unregister` della voce | `true`; `action(Meta+G)` vuoto, voce tolta dal file: Meta+G libero |

Conseguenza: togliere un'azione khotkeys non libera il tasto in KGlobalAccel; serve `unregister`
della voce. Fino all'installazione della spec 04 Meta+G non fa nulla su `casa`.

## 2026-10-07 — M20: portal GlobalShortcuts su Plasma 6 (rifà M13/M16 per il portal; Claude + GM)

Ambiente: Ubuntu 26.04.1, Plasma 6.6.6 **Wayland**, xdg-desktop-portal 1.21.1, xdg-desktop-portal-kde
6.6.6, kglobalacceld 6.6.5. Metodo: lo stesso script usa e getta di M16
(`~/Scrivania/Claude/scambio-misure/portal_probe.py LOGO+F9 240`), log in
`~/Scrivania/Claude/scambio-misure/p6/portal-M20.log`; GM preme Meta+F9 due volte.

| Passo | Esito |
|---|---|
| Interfaccia | `org.freedesktop.portal.GlobalShortcuts` **versione 2** |
| `CreateSession` | `Response` 0 subito; `app_id` = `com.anthropic.Claude` (scope systemd del chiamante, come in M16) |
| `BindShortcuts` con `preferred_trigger = LOGO+F9` | `Response` 0 dopo **12,2 s**, `shortcuts = [("switch", {description, trigger_description: "Meta+F9"})]`; GM non ha visto nessun dialogo (accettazione automatica di KDE) |
| Tasto premuto | `Activated(session, "switch", 0, {})` e `Deactivated` ≈ 80 ms dopo, due volte su due |
| `kglobalshortcutsrc` | la voce va nel componente dell'`app_id` (`[com.anthropic.Claude]`, `switch=Meta+F9,Meta+F9,…`) |

Conclusione: su Plasma 6 il portal **lega davvero** la scorciatoia (su 5.27 no, M16). Scambio resta su
KGlobalAccel quando c'è KDE (decisione 102, confermata dalla 142); il portal è verificato funzionante
su un backend reale, utile per GNOME.

**Effetto collaterale da non ripetere:** il componente KGlobalAccel del portal è quello dell'`app_id`.
Lo script girava nello scope dell'app Claude, quindi ha condiviso il componente `com.anthropic.Claude`
con la scorciatoia dell'app Claude (Ctrl+Alt+Space). Alla chiusura della sessione di prova e
all'`unregister` della voce `switch`, KGlobalAccel ha tolto **tutto il componente**, anche
Ctrl+Alt+Space. Ripristinata la voce con `doRegister` + `setShortcut` (flag 4) alle 21:38
(`kglobalshortcutsrc` di nuovo con `Ctrl+Alt+Space`; predefinito `none` invece di `Ctrl+Alt+Space`);
il collegamento vivo con l'app Claude torna al suo prossimo riavvio. Le prove future del portal vanno
lanciate in uno scope proprio (`systemd-run --user --scope --unit=app-<id-di-prova>-<n>.scope`).

## 2026-10-07 — M21: tray su Plasma 6 Wayland (rifà M14 e M11; Claude + GM)

Metodo: Scambio a `0ef473b` (venv Python 3.14), `dbus-monitor` sul nome del demone
(`~/Scrivania/Claude/scambio-misure/p6/session-mon.log`) mentre GM clicca l'icona e usa il menu; tema
cambiato da Claude per 5 s (BreezeLight → BreezeDark) per gli screenshot con `spectacle -b -n`.

| Osservazione | Esito |
|---|---|
| Clic sinistro | `plasmashell` chiama `ProvideXdgActivationToken` (risposta `UnknownMethod`), poi direttamente `AboutToShow(0)` ed `Event(0, "opened")`: **nessuna chiamata ad `Activate`**, il menu si apre (GM). Plasma 6 rispetta `ItemIsMenu`; la decisione 85 resta per Plasma 5.27 e qui è innocua |
| «Impostazioni…» | `Event(7, "clicked")` → il demone chiama `org.freedesktop.Application.Activate` su `app.scambio.Scambio.Settings`, attivazione D-Bus in ≈ 0,32 s; finestra in primo piano su Wayland (GM) |
| `ui.tray` falso / vero | l'icona sparisce subito e ritorna una sola (GM; conferma M17 su Plasma 6) |
| Icona `on-pc` con Breeze chiaro e scuro | ricolorata dal tema in entrambi (screenshot) |

## 2026-10-07 — M22: doppio switch su BlueZ 5.85 (rifà la verifica della decisione 68; Claude + GM)

Metodo: (a) GM preme Meta+G due volte in meno di un secondo con un video negli occhiali (21:22:04);
(b) Claude lancia `scambio switch; scambio switch` (21:24:59,974 e 21:25:00,141); journal di Scambio
e `gdbus monitor --system --dest org.bluez` sul dispositivo (`p6/bluez-signals.log`).
`dbus-monitor --system` non vede più le chiamate degli altri senza root su 26.04: si osservano solo
i segnali di BlueZ.

| Prova | Esito |
|---|---|
| (a) Meta+G ×2 | `on_pc → releasing` 21:22:04,17 · `releasing → connecting` 06,40 · `on_pc` 08,19 · ripresa negli occhiali 10,25; nessun `connect_failed`; GM: «torna immediatamente agli occhiali» |
| (b) CLI ×2 | `releasing` 00,04 · `ServicesResolved=false` 02,396 e `Connected=false` 02,405 (orologio del monitor) · `releasing → connecting` 02,398 · `Connected=true` 03,101 · `on_pc` 03,72 · ripresa 06,25 |

Conclusione: la correzione 68 regge su BlueZ 5.85: la presa riparte solo a scollegamento avvenuto,
nessuna presa letta come fallita. L'ordine `DisconnectResult`/`Connected=false` al millisecondo non
è osservabile senza root (la transizione e il segnale distano 7 ms su due processi diversi).

## 2026-10-07 — M30: contenuto del runtime Flatpak `org.gnome.Platform//51` (Claude, senza GM)

Metodo: Flatpak 1.16.6 e flatpak-builder 1.4.8 installati da GM con apt; runtime e SDK GNOME 51
da Flathub (remote `--user`); `flatpak run --command=sh org.gnome.Platform//51` e `…Sdk//51`.
Prove e log in `~/Scrivania/Claude/scambio-misure/fase5/`.

| Componente | Platform 51 | Sdk 51 |
|---|---|---|
| Python / PyGObject | 3.14.7 / 3.58.0 | idem |
| GTK / libadwaita / GLib | 4.24 / 1.10 / 2.90 | idem |
| `pactl` | **presente** (17.0), `libpulse.so.0` | presente |
| `blueprint-compiler`, `msgfmt`, `appstreamcli` | — | **presenti** |
| `pip` / `setuptools` | — | 26.2.1 / 83.0.0 (build offline di `pyproject.toml` possibile) |

Conclusione: nessun modulo aggiuntivo serve per eseguire Scambio; per costruirlo basta l'SDK.

## 2026-10-07 — M31: demone Scambio dentro un Flatpak di prova (Claude, senza GM)

Metodo: Flatpak **di laboratorio** fuori dal repo (`fase5/app.scambio.Scambio.yml`, copia di
`src/ design/ build/` a `cc5fdd9`, avvio con `PYTHONPATH`), permessi: `--socket=pulseaudio`,
`--system-talk-name=org.bluez`, `--system-talk-name=org.freedesktop.login1`,
`--talk-name=org.mpris.MediaPlayer2.*`, `org.kde.kglobalaccel`, `org.kde.StatusNotifierWatcher`,
`org.freedesktop.Notifications`, `org.freedesktop.ScreenSaver`, `--share=ipc`, `--socket=wayland`,
`--socket=fallback-x11`. Servizio utente di casa fermato durante la prova (21:59–22:05) e poi riavviato;
per la prova il demone vedeva `~/.config/scambio` e `~/.local/share/scambio` con `--filesystem`
(solo laboratorio). Occhiali collegati al PC con audio in corso.

| Prova | Esito |
|---|---|
| BlueZ (sistema): `GetManagedObjects`, proprietà del dispositivo | ok (dispositivo trovato, `Connected=True`) |
| BlueZ: `scambio switch` ×2 dalla CLI dell'host | `on_pc → releasing → released` e `released → connecting → on_pc`, nessun errore: **Connect/Disconnect funzionano** dal sandbox |
| logind `ListSessions`, ScreenSaver `GetActive` | ok; `Lock source logind: False` |
| `pactl -f json info` / `subscribe` | ok via `unix:/run/flatpak/pulse/native` (PulseAudio su PipeWire 1.6.2) |
| KGlobalAccel | `ShortcutState: active`, `ShortcutBackend: kglobalaccel` (pressione di Meta+G **non** provata) |
| Nomi non concessi (`org.freedesktop.UPower`, `org.freedesktop.systemd1`) | `ServiceUnknown`: **systemd utente non raggiungibile** dal sandbox |
| Configurazione | dentro il sandbox `HOME=~` ma `XDG_CONFIG_HOME=~/.var/app/app.scambio.Scambio/config`: il codice che usa `Path.home()/.config` non vede la configurazione senza `--filesystem` |
| CPU a riposo | 0 tick in 30 s |
| Memoria | RSS 38–41 MB (contro ≈ 24,5 MB della venv di casa) + `xdg-dbus-proxy` 2,3 MB |

## 2026-10-07 — M32: avvio automatico tramite portal Background su Plasma 6.6.6 (Claude, senza GM)

Metodo: `bgprobe` (fase5/bgprobe.py) nel Flatpak di prova chiama
`org.freedesktop.portal.Background.RequestBackground` con `autostart=true`,
`commandline=["scambio","daemon"]`; xdg-desktop-portal 1.21.1, xdg-desktop-portal-kde 6.6.6.

| Prova | Esito |
|---|---|
| `autostart=true` | risposta `0 {'background': True, 'autostart': True}`, **nessun dialogo**; creato `~/.config/autostart/app.scambio.Scambio.desktop` con `Exec=flatpak run --command=scambio app.scambio.Scambio daemon` e `X-XDP-Autostart` |
| `autostart=false` | risposta `0 {…'autostart': False}`, file rimosso |
| Avvio reale al login | **non provato** (serve un nuovo accesso): va nella prova di installazione pulita |

## 2026-10-07 — M33: icona del tray da Flatpak su Plasma 6.6.6 Wayland (Claude, senza GM)

Metodo: demone nel Flatpak di prova; `RegisteredStatusNotifierItems` del watcher; screenshot del
pannello con `spectacle -b -n -f` (fase5/bottom*.png). Le varianti 2 e 3 sono **patch di laboratorio**
alla copia in `fase5/`, non al repo.

| Variante | Esito |
|---|---|
| Codice attuale (nome `org.kde.StatusNotifierItem-<pid>-1`, `IconThemePath=/app/…`) | nome non concesso dal sandbox: **item non registrato**, nessuna icona |
| `--own-name=org.kde.StatusNotifierItem-2-1` (nel sandbox il demone ha PID 2) | registrato, ma **posto vuoto**: `IconThemePath` è un percorso del sandbox che Plasma non vede |
| + `IconThemePath` tradotto nel percorso dell'host (`app-path` di `/.flatpak-info` + resto del percorso) | **icona visibile** (occhiali + monitor) |
| Registrazione col solo percorso (`RegisterStatusNotifierItem("/StatusNotifierItem")`, nome unico del mittente), senza `--own-name` | **registrato e icona visibile** (`:1.2698/StatusNotifierItem`) |

## 2026-10-07 — M34: portal e attivazione D-Bus da Flatpak (Claude, senza GM)

| Prova | Esito |
|---|---|
| `Gio.AppInfo.launch_default_for_uri("systemsettings://kcm_keys/app.scambio.Scambio")` dal sandbox | passa dal portal OpenURI e apre `systemsettings kcm_keys --args app.scambio.Scambio` |
| `Notify` con `--talk-name=org.freedesktop.Notifications` | ok (id 80) |
| `flatpak run … settings` | la finestra GTK4 si apre su Wayland ed è identica a quella della venv; senza `--device=dri` Mesa avvisa e ripiega sul rendering software |
| File di servizio D-Bus in `/app/share/dbus-1/services/` | Flatpak esporta **sia** `app.scambio.Scambio.service` **sia** `app.scambio.Scambio.Settings.service` (Exec riscritto in `flatpak run --command=/app/bin/scambio …`) |
| Attivazione di `app.scambio.Scambio.Settings` subito dopo l'installazione | `ServiceUnknown`: le cartelle `exports` di Flatpak entrano in `XDG_DATA_DIRS` solo dopo un nuovo accesso. Con l'installazione di sviluppo presente vince il file in `~/.local/share/dbus-1/services/` (si è aperta la finestra della venv): **le due installazioni non vanno tenute insieme** |

## 2026-10-08 — M35: tray su connessione dedicata (decisione 154) e flusso audio fantasma (Claude, senza GM)

Metodo: servizio utente di casa riavviato a `b467bce` (venv editabile, quindi codice della spec 05) alle
01:12; `RegisteredStatusNotifierItems` prima e dopo `SetConfig({"ui.tray": false})` / `true`; journal di
Scambio e `pactl -f json list sink-inputs`.

| Prova | Esito |
|---|---|
| Registrazione del tray | voce `:1.3524/StatusNotifierItem` (nome unico, nessun nome ben noto) |
| `ui.tray = false` | la voce sparisce subito (connessione chiusa) |
| `ui.tray = true` | torna **una sola** voce, su una connessione nuova (`:1.3532`) |
| Avvio con occhiali non sul PC | `released → connecting (audio_started)` e poi `connect_failed` dopo 5 s (occhiali spenti o nella custodia) |
| Causa dell'`audio_started` | uno stream sempre aperto di `speech-dispatcher-dummy` (binario `sd_dummy`, attivo dalle 11:45, non in pausa): conta come audio del PC |

Conclusione: la decisione 154 funziona su Plasma 6. Lo stream silenzioso di speech-dispatcher, comune su
Ubuntu, farebbe prendere gli occhiali al PC ogni volta che tornano disponibili: va escluso di default
(correzione chiesta a Codex dopo l'audit 1).
