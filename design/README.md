# design/ — di proprietà di Claude

Tutto ciò che determina come Scambio appare e cosa dice. Codex non modifica questi file: li
carica e collega la logica secondo il contratto in `docs/context/05-ui-context.md` §5.

| Percorso | Cosa | Usato da |
|---|---|---|
| `icons/hicolor/` | albero di icone da passare come `IconThemePath`: stati del tray (`scalable/status/app.scambio.Scambio-<stato>-symbolic.svg`, cartella misurata in M11), icona simbolica e a colori dell'app, `index.theme` | spec 03 |
| `icons/_source/` | generatori delle icone e dei cataloghi (solo design, non pacchettizzati) | — |
| `ui/tray.json` | presentazione del tray: regole stato → icona e testi, voci del menu, notifiche | spec 03 |
| `ui/settings-window.blp` | finestra impostazioni in Blueprint (compilata in `build/ui/` con `make ui`) | spec 04 |
| `style/scambio.css` | CSS GTK della finestra | spec 04 |
| `desktop/app.scambio.Scambio.desktop.in` | lanciatore nel menu delle applicazioni (`@EXEC@`, `@ICON@` sostituiti da `make install-user`) | spec 04 |
| `i18n/{it,en,de}.po`, `scambio.pot`, `LINGUAS` | testi; `msgid` = chiave simbolica del contratto, `en.po` obbligatorio | spec 03–04 |

Mock approvato da GM il 2026-10-05: tela «Scambio — mock UI» (Artifact Design su claude.ai), con
il menu interattivo in tutti gli stati, le tre varianti d'icona (scelta la **B**), le notifiche e
l'anteprima della finestra. Finestra impostazioni approvata da GM il 2026-10-07 (screenshot reali
GTK4/libadwaita su `casa`, chiaro e scuro: stato sul PC, scorciatoia in conflitto, demone fermo).

Flusso: mock approvato da GM → file qui → Codex collega → audit visivo di Claude con screenshot
reali, chiaro e scuro, su KDE e GNOME.
