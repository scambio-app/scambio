# Hardware lab — misure sul campo

Solo misure, datate, con ambiente e metodo. È l'autorità sul comportamento dell'hardware
(`AGENTS.md`). Una misura superata non si cancella: si aggiunge la nuova e si marca la vecchia.

## Ambiente di riferimento

PC `casa`: Kubuntu 24.04.5, KDE Plasma 5.27.12, xdg-desktop-portal-kde 5.27.11, BlueZ 5.72,
PipeWire con pipewire-pulse, Python 3.12.3, PyGObject presente. Dispositivo: Oakley Meta 002Z,
già accoppiato e `Trusted=yes`; profili A2DP (SBC, SBC-XQ), HFP/HSP (CVSD, mSBC), AVRCP.
Telefono: iPhone di GM.

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

## Conseguenze per il design

- Il PC non può sapere prima di connettersi se il telefono usa il dispositivo: «non prendere se
  occupato» non è realizzabile.
- Una presa durante una chiamata è reversibile (switch → la chiamata torna da sola).
- La pausa durante la presa dura ≈ 2 s: sostenibile.

## Da misurare

- Q3: riconnessione spontanea al PC all'accensione / uscita dalla custodia, con e senza iPhone in
  portata.
- Q4: chiamata GSM invece di WhatsApp.
- Q5: portal GlobalShortcuts su Plasma 5.27.
- Latenza della prima uscita audio in HFP (apertura del link SCO).
