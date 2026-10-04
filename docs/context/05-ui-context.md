# 05 — Contesto UI e contratto design ↔ codice

Redatto da Claude il 4 ottobre 2026. Il design è di Claude (decisione di GM): i file stanno in
`design/` e Codex li collega senza modificarli. Le sezioni marcate «da definire» si completano
con il mock approvato, prima della spec che implementa la UI.

## 1. Principi

- **Invisibile quando funziona.** Lo stato normale non chiede attenzione; si notifica solo ciò che
  l'utente deve sapere (presa fallita, Priorità iPhone attivata con lo switch, musica dell'iPhone
  rimasta in pausa).
- **Lo stato si legge dall'icona** senza aprire nulla: dove sono gli occhiali e se la Priorità
  iPhone è attiva.
- **Nativo dove possibile**: icone simboliche che seguono il tema chiaro/scuro; finestra
  libadwaita con le convenzioni GNOME HIG, leggibile anche su KDE.
- **Tastiera prima del mouse**: ogni azione del tray ha un equivalente da scorciatoia o CLI.
- Testi brevi, in it/en/de; tono neutro e amichevole.

## 2. Superfici

| Superficie | Tecnologia | Note |
|---|---|---|
| Icona tray + menu | StatusNotifierItem + dbusmenu | superficie principale su KDE |
| Notifiche | freedesktop Notifications | con azioni quando servono (es. «Annulla») |
| Finestra impostazioni | GTK4 + libadwaita, Blueprint in `design/ui/` | su GNOME senza tray è il punto di ingresso |
| Scorciatoia | portal GlobalShortcuts, default Meta+G | nessuna UI propria |

## 3. Stati da rappresentare (icone in `design/icons/`)

| Stato | Significato | Icona |
|---|---|---|
| `released` | dispositivo non sul PC, automatico attivo | da definire |
| `connecting` | presa in corso | da definire |
| `on_pc` | dispositivo sul PC | da definire |
| `priority` | Priorità iPhone attiva | da definire |
| `unavailable` | Bluetooth spento o dispositivo non configurato/non trovato | da definire |
| `error` | ultima operazione fallita | da definire |

## 4. Menu del tray (bozza)

Riga di stato (non cliccabile) · «Passa al PC» / «Lascia all'iPhone» (switch) · interruttore
«Priorità iPhone» · «Impostazioni…» · «Esci». Testi e ordine definitivi col mock.

## 5. Contratto (da completare col mock)

Per ogni elemento interattivo: ID del widget in Blueprint, azione GAction (`app.switch`,
`app.toggle-priority`, `app.open-settings`, `app.quit`), proprietà dell'API D-Bus collegata,
chiave del testo. Codex usa solo questi nomi; se gliene serve uno nuovo lo chiede nel report.

API del demone usata dalle UI: proprietà, metodi e segnali di `app.scambio.Scambio1` in
`docs/specs/01-demone-headless.md` §3.2.1. `priority` ed `error` della tabella §3 si derivano da
`IphonePriority` e `LastError`.

## 6. Lingue

Chiavi gettext; cataloghi `design/i18n/{it,en,de}.po`. Lingua di sistema di default, forzabile da
configurazione.
