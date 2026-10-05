# Sorgenti delle icone

`icons.py` genera le icone simboliche (16×16, solo `fill`, Breeze `ColorScheme-*` + classe GTK
`.error`); `appicon.py` l'icona a colori dell'app; `i18n.py` i cataloghi di `design/i18n/`.
Si rigenerano con `python3 <script>` da questa cartella (servono solo per il design; non fanno
parte del pacchetto né del gate `make check`). La variante approvata da GM è la **B**
(occhiali + emblema, 2026-10-05); A e C restano nel generatore come riferimento del mock.
