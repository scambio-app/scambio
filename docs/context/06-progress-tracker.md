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
| 1 | Spec 01 — demone headless: tooling, config, BlueZ, eventi audio, sessione, macchina a stati, API D-Bus, CLI `switch/status/priority` | da scrivere |
| 2 | Spec 02 — presa con pausa/ripresa (MPRIS + muto/spostamento stream) e rilascio a tempo | da scrivere |
| 3 | Mock UI approvato → design in `design/` → spec 03 tray + notifiche | da fare |
| 4 | Spec 04 — scorciatoia globale (portal) + finestra impostazioni | da fare |
| 5 | Avvio automatico, packaging (Flatpak), prima release | da fare |
| 6+ | Premium: widget Plasma/GNOME, ponte fotocamera iPhone, agenti | futuro |

## 3. Decisioni di prodotto prese (non ridiscutere)

Vedi `docs/decisions.md`, voci 1–17.

## 4. Domande aperte

| # | Domanda | Per chi | Quando serve |
|---|---|---|---|
| Q1 | Licenza del core (es. GPL-3.0 vs MIT/Apache-2.0) | GM | prima della prima release |
| ~~Q2~~ | ~~Dominio `scambio.app`~~ — **chiusa 2026-10-04**: acquistato da GM (decisione 17) | — | — |
| Q3 | Il dispositivo si ricollega da solo al PC all'accensione / uscita dalla custodia? | misura | prima della spec 01 |
| Q4 | Conferma del comportamento con una chiamata GSM (finora solo WhatsApp) | misura | prima della spec 02 |
| Q5 | Supporto reale del portal GlobalShortcuts su Plasma 5.27 | misura | prima della spec 04 |

## 5. Prossimi passi

1. Misura Q3 con GM.
2. Claude scrive la spec 01 e la sottopone a GM con la propria revisione.
3. `/goal` a Codex.
