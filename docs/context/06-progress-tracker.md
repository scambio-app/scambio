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
| 3 | Mock UI approvato → design in `design/` → spec 03 tray + notifiche | ✅ verificata 2026-10-07 (569 test; audit 1 di Claude: codice conforme, clic sinistro su Plasma corretto con la decisione 85, d33afa1; prova reale GM passi 0–10 ok; misure M14, M15) |
| 4 | Spec 04 — scorciatoia globale (KGlobalAccel su Plasma, portal altrove; M16) + finestra impostazioni | ✅ verificata 2026-10-07 (731 test; audit 1 corretto; prova reale GM ok su Ubuntu 26.04 / Plasma 6.6.6 Wayland; misure M16–M22) |
| 5 | Spec 05 — packaging (`.deb` + repo apt «come Chrome», Flatpak da repo proprio), GitHub `scambio-app`, release 1.0.0 | ✅ **pubblicata il 2026-10-08**: github.com/scambio-app/scambio (tag firmato v1.0.0), scambio.app con download `.deb`/apt/Flatpak; verifiche dal vivo su Ubuntu 24.04, Debian 13 e Flatpak; prova umana in produzione (dec. 152) |
| 6 | **macOS** (dec. 120–122): vettori di test condivisi, app Swift da barra dei menu, firma e vendita diretta | dopo la fase 5 |
| 7+ | Premium: widget Plasma/GNOME, ponte fotocamera iPhone, agenti | futuro |

## 3. Decisioni di prodotto prese (non ridiscutere)

Vedi `docs/decisions.md`, voci 1–29.

## 4. Domande aperte

| # | Domanda | Per chi | Quando serve |
|---|---|---|---|
| ~~Q1~~ | ~~Licenza~~ — **chiusa 2026-10-07**: GPL-3.0 + CLA (dec. 137, supera la 135) | — | — |
| ~~Q2~~ | ~~Dominio `scambio.app`~~ — **chiusa 2026-10-04**: acquistato da GM (decisione 17) | — | — |
| ~~Q3~~ | ~~Riconnessione spontanea~~ — **chiusa 2026-10-04** (M3): mai verso il PC | — | — |
| ~~Q4~~ | ~~Chiamata GSM~~ — **chiusa 2026-10-05** senza misura: uguale a WhatsApp (decisione 67) | — | — |
| ~~Q5~~ | ~~Portal GlobalShortcuts su Plasma 5.27~~ — **chiusa 2026-10-07** (M16): non lega scorciatoie; si usa KGlobalAccel (decisione 102) | — | — |
| Q6 | ~~Plasma 6~~ — **chiusa la parte Plasma 6 il 2026-10-07** (decisione 144, M20–M22). Resta **GNOME** (portal con `app_id` dell'unità systemd, tray assente): VM prima della fase 5 | Claude | prima della fase 5 |

## 5. Prossimi passi

1. ~~Claude scrive la spec 01~~ — approvata da GM il 2026-10-04.
2. ~~Implementazione Codex e audit di Claude~~ — fatti (audit 2 ok).
3. ~~Prova reale di GM~~ — fatta il 2026-10-05: **fase 1 chiusa**.
5. Prossime unità (decisione 49, 2026-10-05): **in parallelo** chat di design (mock UI → spec 03
   tray) e chat di sviluppo (spec 02 pausa MPRIS). Avvio automatico al login attivo (decisione 48).
4. ~~Misure aperte: Firefox in pausa (M5), Q4~~ — chiuse il 2026-10-05 (M9, decisione 67). **Fase 2 chiusa il 2026-10-05.**
6. **Fase 3 chiusa il 2026-10-07** (spec 03 verificata). Prossima unità: spec 04 (scorciatoia globale + finestra impostazioni).
7. Spec 04 (2026-10-07): misure M16–M18, mock della finestra approvato, decisioni 100–109; spec approvata da GM, Codex al lavoro.
8. **Fase 4 chiusa il 2026-10-07** (spec 04 verificata su Plasma 6.6.6 Wayland). Debiti: `Gtk.ShortcutLabel` deprecato da GTK 4.22 (design, Claude); verifica GNOME in VM (Q6) prima della fase 5.
8. Fase 5 (2026-10-07, chat di rilascio): Flatpak misurato su casa (M30–M34), scelte di GM 150–152 e 160–165, spec 05 scritta; Flathub solo come tentativo (dec. 159).
9. Fase 5 (2026-10-08 notte): Codex ha implementato la spec 05 e le correzioni dell'audit 1 (candidata `audit-1` firmata in `~/.local/share/scambio-release/candidates/`); guida della prova in `docs/guide/prova-installazione-1.0.md`.
10. **Fase 5 chiusa il 2026-10-08**: 1.0.0 pubblica. Aperti: doppio opt-in (Workers Paid, dec. 167), CLA Assistant da collegare (GM, accesso OAuth), primaria della chiave da togliere da casa (168a), domanda a Flathub (guida in `docs/guide/flathub-per-gm.md`), GNOME mai provato dal vivo (Q6), `Gtk.ShortcutLabel` deprecato.
