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
| 2 | Spec 02 — pausa MPRIS durante presa e rilascio (decisioni 50–56; niente muto, M10); l'instradamento e il rilascio a tempo sono già nella spec 01 | consegnata e auditata (audit 2 ok, 390 test, 2026-10-05); in attesa della prova reale di GM, con le misure dell'annuncio e di Q4 al punto 0 |
| 3 | Mock UI approvato → design in `design/` → spec 03 tray + notifiche | mock approvato (2026-10-05, icona B; decisioni 70–84); `design/` e 05 §5 completati; spec 03 **approvata** da GM (2026-10-05, decisione 84); Codex parte dopo la chiusura della spec 02 e con `gettext` installato; misura M11 |
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
| Q4 | Conferma del comportamento con una chiamata GSM (finora solo WhatsApp) | misura | prima della spec 02 |
| Q5 | Supporto reale del portal GlobalShortcuts su Plasma 5.27 | misura | prima della spec 04 |

## 5. Prossimi passi

1. ~~Claude scrive la spec 01~~ — approvata da GM il 2026-10-04.
2. ~~Implementazione Codex e audit di Claude~~ — fatti (audit 2 ok).
3. ~~Prova reale di GM~~ — fatta il 2026-10-05: **fase 1 chiusa**.
5. Prossime unità (decisione 49, 2026-10-05): **in parallelo** chat di design (mock UI → spec 03
   tray) e chat di sviluppo (spec 02 pausa MPRIS). Avvio automatico al login attivo (decisione 48).
4. Misure aperte: Firefox in pausa (M5), Q4 prima della spec 02.
