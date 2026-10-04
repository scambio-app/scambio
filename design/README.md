# design/ — di proprietà di Claude

Tutto ciò che determina come Scambio appare e cosa dice. Codex non modifica questi file: li
carica e collega la logica secondo il contratto in `docs/context/05-ui-context.md`.

- `icons/` — icone SVG (stati del tray in versione simbolica, icona dell'app).
- `ui/` — layout delle finestre in Blueprint (`.blp`); i `.ui` compilati non si versionano.
- `style/` — CSS GTK dell'app.
- `i18n/` — traduzioni gettext (`it`, `en`, `de`) dei testi definiti nel contratto.

Flusso: mock approvato da GM → file qui → Codex collega → audit visivo di Claude con screenshot
reali, chiaro e scuro, su KDE e GNOME.
