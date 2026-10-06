# 06 — Tracker di avanzamento

Aggiornato da Claude il 4 ottobre 2026. Dice dove siamo e cosa manca; l'evidenza tecnica sta nei
report di `docs/verification/` e nel git log.

## 1. Fase corrente

**Fase 0 — Fondazioni (chiusa il 4 ottobre 2026).** Visione, architettura, metodo, nome,
posizionamento, prime misure hardware; repository creato su `casa` (solo locale); brain
`scambio_brain` creato.

## 2. Piano delle fasi

| Fase | Contenuto | Stato |
|---|---|---|
| 0 | Fondazioni documentali e misure iniziali | ✅ chiusa |
| 1 | Spec 01 — demone headless: tooling, config, BlueZ, eventi audio, sessione, macchina a stati, instradamento, API D-Bus, CLI `switch/status/priority`, servizio utente | ✅ verificata 2026-10-05 (237 test, prova reale GM ok; sospensione n/a su casa) |
| 2 | Spec 02 — pausa MPRIS durante presa e rilascio (decisioni 50–56; niente muto, M10); l'instradamento e il rilascio a tempo sono già nella spec 01 | ✅ verificata 2026-10-05 (418 test, prova reale GM ok dopo la correzione 68; annuncio misurato M11b; Q4 chiusa senza misura, decisione 67) |
| 3 | Mock UI approvato → design in `design/` → spec 03 tray + notifiche | consegnata da Codex il 2026-10-06 (commit 52a300b, 5bfe574, 0c1aea3; 564 test, CPU 0 %, RSS 24 MB; decisioni 90–94); audit 1 di Claude fatto il 2026-10-06 (codice conforme; difetto del clic sinistro su Plasma, M14 → decisione 85, corretto da Codex in d33afa1, 569 test); prova reale di GM in corso: passi 0–4 ok, 5 da ripetere (M15), 6–10 da fare |
| 4 | Spec 04 — scorciatoia globale (portal) + finestra impostazioni | da fare |
| 5 | Avvio automatico, packaging (Flatpak), prima release | da fare |
| 6+ | Premium: widget Plasma/GNOME, ponte fotocamera iPhone, agenti | futuro |

## 3. Decisioni di prodotto prese (non ridiscutere)

Vedi `docs/decisions.md`, voci 1–29.

## 4. Domande aperte

| # | Domanda | Per chi | Quando serve |
|---|---|---|---|
| Q1 | Licenza del core (es. GPL-3.0 vs MIT/Apache-2.0) | GM | prima della prima release |
| ~~Q2~~ | ~~Dominio `scambio.app`~~ — **chiusa 2026-10-04**: acquistato da GM (decisione 17) | — | — |
| ~~Q3~~ | ~~Riconnessione spontanea~~ — **chiusa 2026-10-04** (M3): mai verso il PC | — | — |
| ~~Q4~~ | ~~Chiamata GSM~~ — **chiusa 2026-10-05** senza misura: uguale a WhatsApp (decisione 67) | — | — |
| Q5 | Portal GlobalShortcuts: **interfaccia presente v1 su casa (M13, 2026-10-05)**; resta la prova funzionale (bind + Activated) dentro la spec 04 | spec 04 | prima della spec 04 |

## 5. Prossimi passi

1. ~~Claude scrive la spec 01~~ — approvata da GM il 2026-10-04.
2. ~~Implementazione Codex e audit di Claude~~ — fatti (audit 2 ok).
3. ~~Prova reale di GM~~ — fatta il 2026-10-05: **fase 1 chiusa**.
5. Prossime unità (decisione 49, 2026-10-05): **in parallelo** chat di design (mock UI → spec 03
   tray) e chat di sviluppo (spec 02 pausa MPRIS). Avvio automatico al login attivo (decisione 48).
4. ~~Misure aperte: Firefox in pausa (M5), Q4~~ — chiuse il 2026-10-05 (M9, decisione 67). **Fase 2 chiusa il 2026-10-05.**
