# Decisioni

Append-only. Una riga per decisione: numero, data, autore, decisione, motivo breve. Una decisione
superata non si cancella: se ne aggiunge una nuova che la cita («supera n. X»).

## 2026-10-04 — Fase 0 (decise da GM con Claude)

1. GM — Nome del prodotto: **Scambio** (lo scambio ferroviario). Verificati conflitti e dominio
   `scambio.app` libero il 4 ottobre 2026.
2. GM — Posizionamento ibrido: marchio e marketing sugli smart glasses; core indipendente dal
   dispositivo; funzioni glasses avanzate premium.
3. GM — Modello open-core: core open source gratuito, moduli premium in pacchetto separato.
4. GM — Presa automatica quando parte audio sul PC, anche se il telefono usa il dispositivo, con
   pausa/muto automatico dello stream durante la connessione.
5. GM — Rilascio dopo 120 s di silenzio (`release_idle_seconds`, configurabile); immediato con
   blocco schermo e sospensione.
6. GM — Interruttore «Priorità iPhone» nel tray; si spegne solo a mano.
7. GM — Scorciatoia globale «switch intelligente»: dispositivo sul PC → rilascio + priorità on;
   altrimenti presa + priorità off.
8. GM — Scorciatoia di default **Meta+G** (scartata Ctrl+Shift+S: è «Salva con nome» in molte app).
9. GM — Interfacce: una sola app (demone + client sottili via D-Bus); v1 tray + notifiche +
   finestra GTK4/libadwaita; dopo, widget Plasma e Impostazioni rapide GNOME.
10. GM — Design di proprietà di Claude (`design/`); Codex scrive tutto il codice.
11. GM — Metodo «Kuchl-lite»: sei file di contesto, spec piccole, audit, hardware-lab al posto
    dello stato narrativo.
12. GM — Brain AGVM dedicato `scambio_brain`, consultivo, scritto alle milestone.
13. GM — Repository solo su `casa`: nessun remote, nessuna GitHub Actions; gate locali con
    `make check` e hook pre-commit.
14. GM — Lingue it, en, de dal primo giorno.

## 2026-10-04 — Fase 0 (tecniche, Claude)

15. Claude — Un solo main loop GLib, D-Bus via Gio, nessun polling; dipendenze runtime limitate a
    PyGObject/GTK4/libadwaita.
16. Claude — Scorciatoia via XDG Desktop Portal GlobalShortcuts con riserva CLI (`scambio switch`);
    la vecchia scorciatoia khotkeys di GM (Ctrl+Shift+O) va disattivata all'installazione.

## 2026-10-04 — Dominio e identificativi

17. GM — Dominio **scambio.app** acquistato (account Cloudflare personale di GM). Ne derivano
    l'app-id `app.scambio.Scambio` (Flatpak, file .desktop, icone) e il nome D-Bus del demone
    `app.scambio.Scambio` (oggetto `/app/scambio/Scambio`): Flatpak consente di possedere solo nomi
    D-Bus sotto il proprio app-id.
