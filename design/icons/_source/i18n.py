# key: (it, en, de, nota per i traduttori)
K = [
("tray-device-fallback", "il dispositivo", "the device", "das Gerät", "Al posto di {device} quando BlueZ non dà un nome. Minuscolo: il codice rende maiuscola la prima lettera della frase."),
("tray-header-released", "{device} — libero per il telefono", "{device} — free for the phone", "{device} — frei für das Handy", "Prima riga del menu e del tooltip."),
("tray-header-priority", "{device} — riservato al telefono", "{device} — reserved for the phone", "{device} — für das Handy reserviert", None),
("tray-header-connecting", "{device} — passaggio al PC…", "{device} — moving to the PC…", "{device} — wechselt zum PC…", None),
("tray-header-on-pc", "{device} — sul PC", "{device} — on the PC", "{device} — am PC", None),
("tray-header-releasing", "{device} — ritorno al telefono…", "{device} — going back to the phone…", "{device} — zurück zum Handy…", None),
("tray-header-unavailable", "{device} — non disponibile", "{device} — unavailable", "{device} — nicht verfügbar", None),
("tray-header-not-configured", "Nessun dispositivo configurato", "No device configured", "Kein Gerät eingerichtet", None),
("tray-detail-released", "Passa al PC quando parte un audio", "Moves to the PC when audio starts", "Wechselt zum PC, sobald Audio startet", "Seconda riga del menu e del tooltip."),
("tray-detail-priority", "Il PC non lo prende in automatico", "The PC won’t take it automatically", "Der PC übernimmt es nicht automatisch", None),
("tray-detail-busy", "Qualche secondo…", "A few seconds…", "Einen Moment…", None),
("tray-detail-playing", "Audio del PC in riproduzione", "PC audio playing", "PC-Audio läuft", None),
("tray-detail-idle", "Torna al telefono tra {minutes} min", "Back to the phone in {minutes} min", "In {minutes} Min. zurück zum Handy", "Menu: minuti arrotondati per eccesso, calcolati all’apertura."),
("tray-detail-idle-soon", "Torna al telefono tra meno di un minuto", "Back to the phone in under a minute", "In weniger als einer Minute zurück zum Handy", None),
("tray-detail-idle-at", "Torna al telefono alle {time}", "Back to the phone at {time}", "Um {time} zurück zum Handy", "Tooltip: ora assoluta HH:MM, così non invecchia."),
("tray-detail-on-pc", "Audio del PC sul dispositivo", "PC audio on the device", "PC-Audio über das Gerät", None),
("tray-detail-unavailable", "Bluetooth spento o dispositivo fuori portata", "Bluetooth off or device out of range", "Bluetooth aus oder Gerät außer Reichweite", None),
("tray-detail-not-configured", "Sceglilo nelle Impostazioni", "Choose it in Settings", "In den Einstellungen auswählen", "Spec 05: la finestra sceglie il dispositivo; il percorso del file cambia nel Flatpak."),
("tray-detail-error-connect", "Ultimo passaggio non riuscito: è acceso e vicino?", "Last switch failed: is it on and nearby?", "Letzter Wechsel fehlgeschlagen: eingeschaltet und in der Nähe?", "Mostrato finché l’errore non è visto (05 §5.4)."),
("tray-detail-error-sink", "Audio perso: è tornato sugli altoparlanti del PC", "Audio lost: back on the PC speakers", "Audio verloren: wieder über die PC-Lautsprecher", None),
("tray-detail-error-release", "Rilascio non riuscito: resta sul PC", "Hand-back failed: it stays on the PC", "Rückgabe fehlgeschlagen: bleibt am PC", None),
("tray-detail-error-config", "Configurazione non valida: in uso la precedente", "Invalid configuration: using the previous one", "Ungültige Konfiguration: vorherige wird verwendet", None),
("tray-action-to-pc", "Passa al PC", "Move to PC", "Zum PC holen", None),
("tray-action-to-phone", "Lascia al telefono", "Hand back to the phone", "Dem Handy überlassen", None),
("tray-action-priority", "Priorità telefono", "Phone priority", "Handy-Vorrang", None),
("tray-action-settings", "Impostazioni…", "Settings…", "Einstellungen…", None),
("tray-action-quit", "Esci da Scambio", "Quit Scambio", "Scambio beenden", None),
("notify-grab-failed-title", "{device} non raggiungibile", "{device} not reachable", "{device} nicht erreichbar", None),
("notify-grab-failed-body", "Non sono riuscito a portarlo sul PC. È acceso e vicino?", "Couldn’t move it to the PC. Is it on and nearby?", "Wechsel zum PC fehlgeschlagen. Ist es eingeschaltet und in der Nähe?", None),
("notify-sink-lost-title", "{device}: audio non disponibile", "{device}: audio unavailable", "{device}: Audio nicht verfügbar", None),
("notify-sink-lost-body", "L’audio è tornato sugli altoparlanti del PC.", "Audio is back on the PC speakers.", "Der Ton läuft wieder über die PC-Lautsprecher.", None),
("notify-release-failed-title", "{device} resta sul PC", "{device} stays on the PC", "{device} bleibt am PC", None),
("notify-release-failed-body", "Non sono riuscito a lasciarlo al telefono.", "Couldn’t hand it back to the phone.", "Rückgabe an das Handy fehlgeschlagen.", None),
("notify-unavailable-title", "{device} non disponibile", "{device} unavailable", "{device} nicht verfügbar", None),
("notify-unavailable-body", "Bluetooth spento o dispositivo fuori portata.", "Bluetooth off or device out of range.", "Bluetooth aus oder Gerät außer Reichweite.", None),
("notify-not-configured-title", "Scambio non ha un dispositivo", "Scambio has no device", "Scambio hat kein Gerät", None),
("notify-not-configured-body", "Indica l’indirizzo Bluetooth nel file di configurazione.", "Set the Bluetooth address in the configuration file.", "Bluetooth-Adresse in der Konfigurationsdatei eintragen.", None),
("notify-config-invalid-title", "Configurazione non valida", "Invalid configuration", "Ungültige Konfiguration", None),
("notify-config-invalid-body", "Scambio continua con quella precedente. Dettagli nel registro di sistema.", "Scambio keeps using the previous one. Details in the system log.", "Scambio verwendet weiter die vorherige. Details im Systemprotokoll.", None),
("notify-audio-down-title", "Scambio non sente l’audio del PC", "Scambio can’t detect PC audio", "Scambio erkennt kein PC-Audio", None),
("notify-audio-down-body", "Senza, niente passaggio automatico; lo switch funziona. Controlla pactl (pacchetto pulseaudio-utils).", "Without it there is no automatic switching; the manual switch works. Check pactl (package pulseaudio-utils).", "Ohne sie kein automatischer Wechsel; der manuelle Wechsel funktioniert. pactl prüfen (Paket pulseaudio-utils).", None),
("notify-switch-to-phone-title", "{device} lasciato al telefono", "{device} handed back to the phone", "{device} dem Handy überlassen", "Switch partito fuori dal tray (scorciatoia, CLI)."),
("notify-switch-to-phone-body", "Priorità telefono attiva: il PC non lo riprenderà da solo.", "Phone priority on: the PC won’t take it back by itself.", "Handy-Vorrang an: Der PC holt es nicht selbst zurück.", None),
("notify-switch-to-pc-title", "{device} sul PC", "{device} on the PC", "{device} am PC", None),
("notify-switch-to-pc-body", "Priorità telefono disattivata.", "Phone priority off.", "Handy-Vorrang aus.", None),
("notify-priority-on-title", "Priorità telefono attiva", "Phone priority on", "Handy-Vorrang an", "Priorità cambiata fuori dal tray senza switch (es. scambio priority on)."),
("notify-priority-on-body", "Il PC non prenderà {device} in automatico.", "The PC won’t take {device} automatically.", "Der PC übernimmt {device} nicht automatisch.", None),
("notify-priority-off-title", "Priorità telefono disattivata", "Phone priority off", "Handy-Vorrang aus", None),
("notify-priority-off-body", "Il PC prende {device} quando parte un audio.", "The PC takes {device} when audio starts.", "Der PC übernimmt {device}, sobald Audio startet.", None),
("notify-action-retry", "Riprova", "Try again", "Erneut versuchen", None),
("notify-action-undo", "Annulla", "Undo", "Rückgängig", None),
("notify-action-open-config", "Apri il file", "Open file", "Datei öffnen", None),
("settings-window-title", "Scambio", "Scambio", "Scambio", "Finestra impostazioni (spec 04). Titolo della finestra."),
("settings-daemon-down", "Scambio non è in esecuzione", "Scambio isn’t running", "Scambio läuft nicht", "Banner in cima quando il demone non è sul bus."),
("settings-daemon-start", "Avvia", "Start", "Starten", None),
("settings-status-unknown", "Stato non disponibile", "Status unavailable", "Status nicht verfügbar", "Riga di stato quando il demone non è in esecuzione."),
("settings-priority-subtitle", "Il PC non prende il dispositivo in automatico", "The PC won’t take the device automatically", "Der PC übernimmt das Gerät nicht automatisch", None),
("settings-group-device", "Dispositivo", "Device", "Gerät", None),
("settings-device-title", "Occhiali o cuffie Bluetooth", "Bluetooth glasses or headphones", "Bluetooth-Brille oder -Kopfhörer", None),
("settings-device-none", "Nessuno", "None", "Keines", "Voce dell’elenco quando non è configurato alcun dispositivo."),
("settings-device-busy", "Per cambiarlo, prima lascialo al telefono", "To change it, hand it back to the phone first", "Zum Wechseln zuerst dem Handy überlassen", "Sottotitolo: elenco bloccato mentre il dispositivo è sul PC o in passaggio."),
("settings-device-empty", "Nessun dispositivo audio accoppiato: accoppialo nelle impostazioni Bluetooth", "No paired audio device: pair one in the Bluetooth settings", "Kein gekoppeltes Audiogerät: in den Bluetooth-Einstellungen koppeln", None),
("settings-device-restarting", "Scambio si riavvia con il nuovo dispositivo", "Scambio is restarting with the new device", "Scambio startet mit dem neuen Gerät neu", "Avviso breve (toast)."),
("settings-release-title", "Torna al telefono dopo (minuti)", "Back to the phone after (minutes)", "Zurück zum Handy nach (Minuten)", None),
("settings-release-subtitle", "Di silenzio sul PC. Subito al blocco dello schermo e in sospensione", "Of silence on the PC. Right away on screen lock and suspend", "Stille am PC. Sofort bei Bildschirmsperre und Standby", None),
("settings-group-shortcut", "Scorciatoia", "Shortcut", "Tastenkürzel", None),
("settings-shortcut-title", "Switch intelligente", "Smart switch", "Intelligenter Wechsel", None),
("settings-shortcut-subtitle", "Sposta il dispositivo e attiva o toglie la Priorità telefono", "Moves the device and turns phone priority on or off", "Wechselt das Gerät und schaltet den Handy-Vorrang ein oder aus", None),
("settings-shortcut-unbound", "Nessun tasto", "No key", "Keine Taste", "Al posto del tasto quando la scorciatoia non ha un tasto."),
("settings-shortcut-conflict", "{shortcut} è già usata da «{owner}»", "{shortcut} is already used by “{owner}”", "{shortcut} wird bereits von „{owner}“ verwendet", "Sottotitolo in caso di conflitto. {shortcut} = tasto leggibile (es. Meta+G), {owner} = nome dell’azione che lo usa."),
("settings-shortcut-unsupported", "Questo desktop non offre scorciatoie globali: assegna un tasto al comando «scambio switch»", "This desktop has no global shortcuts: bind a key to the command “scambio switch”", "Dieser Desktop bietet keine globalen Tastenkürzel: eine Taste dem Befehl „scambio switch“ zuweisen", None),
("settings-shortcut-change", "Cambia…", "Change…", "Ändern…", "Apre Impostazioni di sistema → Scorciatoie (KDE)."),
("settings-group-general", "Generale", "General", "Allgemein", None),
("settings-tray", "Icona nella barra di sistema", "Icon in the system tray", "Symbol im Systembereich", None),
("settings-tray-subtitle", "Su GNOME serve l’estensione AppIndicator", "On GNOME this needs the AppIndicator extension", "Unter GNOME ist die AppIndicator-Erweiterung nötig", None),
("settings-notifications", "Notifiche", "Notifications", "Benachrichtigungen", None),
("settings-notifications-subtitle", "Solo errori e cambi della Priorità telefono fatti da fuori", "Only errors and phone priority changes made elsewhere", "Nur Fehler und von außen geänderter Handy-Vorrang", None),
("settings-language", "Lingua", "Language", "Sprache", None),
("settings-language-auto", "Automatica", "Automatic", "Automatisch", "Le altre voci restano nella propria lingua: Italiano, English, Deutsch."),
("settings-language-next-open", "La finestra cambierà lingua alla prossima apertura", "The window will switch language next time it opens", "Das Fenster wechselt beim nächsten Öffnen die Sprache", "Avviso breve (toast)."),
("settings-config-title", "File di configurazione", "Configuration file", "Konfigurationsdatei", None),
("settings-config-subtitle", "Ritardo di presa, app ignorate e altri dettagli", "Grab delay, ignored apps and other details", "Übernahmeverzögerung, ignorierte Apps und weitere Details", None),
("settings-config-open", "Apri", "Open", "Öffnen", None),
("settings-version", "Scambio {version}", "Scambio {version}", "Scambio {version}", "Piè di pagina."),
("settings-error-invalid", "Valore non accettato", "Value not accepted", "Wert nicht übernommen", "Avviso breve (toast) per ConfigInvalid."),
("settings-error-restart-required", "Salvato: vale dal prossimo avvio di Scambio", "Saved: takes effect when Scambio next starts", "Gespeichert: gilt ab dem nächsten Start von Scambio", "Avviso breve (toast) per RestartRequired (Scambio non avviato da systemd)."),
("settings-error-generic", "Non riuscito ({error})", "Failed ({error})", "Fehlgeschlagen ({error})", "Avviso breve (toast); {error} = nome dell’errore D-Bus."),
("shortcut-component-name", "Scambio", "Scambio", "Scambio", "Nome del gruppo in Impostazioni di sistema → Scorciatoie (KDE)."),
("shortcut-switch-name", "Switch intelligente (PC ↔ telefono)", "Smart switch (PC ↔ phone)", "Intelligenter Wechsel (PC ↔ Handy)", "Nome dell’azione nelle impostazioni delle scorciatoie del desktop (KDE e portal)."),
("cli-error-gtk-missing", "La finestra richiede GTK 4 e libadwaita 1.4 o successiva (pacchetti gir1.2-gtk-4.0 e gir1.2-adw-1)", "The window needs GTK 4 and libadwaita 1.4 or later (packages gir1.2-gtk-4.0 and gir1.2-adw-1)", "Das Fenster benötigt GTK 4 und libadwaita 1.4 oder neuer (Pakete gir1.2-gtk-4.0 und gir1.2-adw-1)", "scambio settings senza GTK 4/libadwaita (spec 04)."),
("cli-description", "Sposta l’audio Bluetooth fra PC e telefono", "Switch Bluetooth audio between PC and phone", "Bluetooth-Audio zwischen PC und Telefon wechseln", "Riga di comando (decisioni 27 e 29b). Stati e codici restano stringhe stabili non tradotte."),
("cli-daemon-help", "Avvia il demone", "Run the daemon", "Dienst starten", None),
("cli-settings-help", "Apri la finestra delle impostazioni", "Open the settings window", "Einstellungsfenster öffnen", None),
("cli-debug-help", "Registro dettagliato (debug)", "Enable debug logging", "Ausführliches Protokoll (Debug)", None),
("cli-status-help", "Mostra lo stato del demone", "Show daemon status", "Status des Dienstes anzeigen", None),
("cli-json-help", "Uscita in JSON", "Output JSON", "Ausgabe als JSON", None),
("cli-switch-help", "Sposta il dispositivo fra PC e telefono", "Move the device between PC and phone", "Gerät zwischen PC und Handy wechseln", None),
("cli-priority-help", "Mostra o cambia la Priorità telefono", "Show or change phone priority", "Handy-Vorrang anzeigen oder ändern", None),
("cli-not-running", "Scambio non è in esecuzione: avvialo con systemctl --user start scambio", "Scambio is not running; start it with systemctl --user start scambio", "Scambio läuft nicht: mit systemctl --user start scambio starten", None),
("cli-dbus-error", "Errore D-Bus: {error}", "D-Bus error: {error}", "D-Bus-Fehler: {error}", "Solo per errori D-Bus non previsti; {error} è il nome tecnico dell’errore."),
("cli-error-device-unavailable", "Dispositivo non disponibile: Bluetooth spento o fuori portata", "Device unavailable: Bluetooth off or out of range", "Gerät nicht verfügbar: Bluetooth aus oder außer Reichweite", None),
("cli-error-config-invalid", "Configurazione non valida: in uso la precedente", "Invalid configuration: using the previous one", "Ungültige Konfiguration: vorherige wird verwendet", None),
("cli-error-restart-required", "Indirizzo del dispositivo cambiato: riavvia con systemctl --user restart scambio", "Device address changed: restart with systemctl --user restart scambio", "Geräteadresse geändert: mit systemctl --user restart scambio neu starten", None),
("cli-help-help", "Mostra questo aiuto ed esce", "Show this help and exit", "Diese Hilfe anzeigen und beenden", None),
("session-inhibit-reason", "Lascia il dispositivo al telefono prima della sospensione", "Hand the device back to the phone before suspend", "Gerät vor dem Standby an das Telefon zurückgeben", "Motivo dell’inibitore di logind (systemd-inhibit --list)."),
("config-header", "Configurazione di Scambio. Solo dispositivi già accoppiati. Dopo una modifica: esci da Scambio e riaprilo dal menu", "Scambio configuration. Paired devices only. After a change: quit Scambio and open it again from the menu", "Scambio-Konfiguration. Nur bereits gekoppelte Geräte. Nach einer Änderung: Scambio beenden und über das Menü neu öffnen", "Commenti del modello di config.toml (decisione 84), nella lingua del momento in cui il file viene creato."),
("config-device-address", "Indirizzo Bluetooth del dispositivo (XX:XX:XX:XX:XX:XX)", "Bluetooth address of the device (XX:XX:XX:XX:XX:XX)", "Bluetooth-Adresse des Geräts (XX:XX:XX:XX:XX:XX)", None),
("config-device-profile", "Profilo del dispositivo: generic oppure meta_glasses", "Device profile: generic or meta_glasses", "Geräteprofil: generic oder meta_glasses", None),
("config-policy-grab-delay", "Millisecondi di audio prima di prendere il dispositivo", "Milliseconds of audio before taking the device", "Millisekunden Audio, bevor das Gerät übernommen wird", None),
("config-policy-release-idle", "Secondi di silenzio prima di lasciarlo al telefono", "Seconds of silence before handing it back to the phone", "Sekunden Stille, bevor es an das Telefon zurückgeht", None),
("config-policy-connect-timeout", "Secondi massimi per collegarlo o scollegarlo", "Maximum seconds to connect or disconnect it", "Maximale Sekunden zum Verbinden oder Trennen", None),
("config-policy-sink-timeout", "Secondi massimi perché compaia la sua uscita audio", "Maximum seconds for its audio output to appear", "Maximale Sekunden, bis sein Audioausgang erscheint", None),
("config-policy-sleep-timeout", "Secondi concessi al rilascio prima della sospensione", "Seconds allowed for the hand-back before suspend", "Sekunden für die Rückgabe vor dem Standby", None),
("config-policy-unblock", "Secondi di silenzio dopo un errore prima di riprovare da solo", "Seconds of silence after an error before trying again by itself", "Sekunden Stille nach einem Fehler, bevor es selbst erneut versucht", None),
("config-policy-resume-delay", "Attesa prima di riprendere la riproduzione dopo la presa; il default dipende dal profilo (generic 0, meta_glasses 2000)", "Wait before resuming playback after taking the device; the default depends on the profile (generic 0, meta_glasses 2000)", "Wartezeit vor dem Fortsetzen der Wiedergabe nach der Übernahme; der Standard hängt vom Profil ab (generic 0, meta_glasses 2000)", None),
("config-audio-ignore-roles", "Ruoli audio che non fanno passare il dispositivo al PC", "Audio roles that don’t move the device to the PC", "Audio-Rollen, die das Gerät nicht zum PC holen", None),
("config-audio-ignore-apps", "App (nome o binario) che non fanno passare il dispositivo al PC", "Apps (name or binary) that don’t move the device to the PC", "Apps (Name oder Programmdatei), die das Gerät nicht zum PC holen", None),
("config-audio-ignore-players", "Player MPRIS da non mettere mai in pausa", "MPRIS players never to pause", "MPRIS-Player, die nie pausiert werden", None),
("config-shortcut-preferred", "Scorciatoia dello switch intelligente", "Smart switch shortcut", "Tastenkürzel für den intelligenten Wechsel", None),
("config-ui-language", "Lingua: auto, it, en oppure de", "Language: auto, it, en or de", "Sprache: auto, it, en oder de", None),
("config-ui-tray", "Icona nella barra di sistema", "Icon in the system tray", "Symbol im Systembereich", None),
("config-ui-notifications", "Notifiche del desktop", "Desktop notifications", "Desktop-Benachrichtigungen", None),
("config-backend-header", "Tempi tecnici facoltativi; i default vengono dalle misure", "Optional technical timings; defaults come from measurements", "Optionale technische Zeiten; die Standardwerte stammen aus Messungen", None),
("background-reason", "Scambio si avvia all’accesso per passare l’audio fra i tuoi dispositivi", "Scambio starts when you log in so it can hand your audio between your devices", "Scambio startet bei der Anmeldung, damit es dein Audio zwischen deinen Geräten weitergeben kann", "Motivo mostrato dal portal Background (Flatpak, spec 05)."),
("daemon-already-running", "Scambio è già in esecuzione da un’altra installazione: questa si ferma", "Scambio is already running from another installation; this one is stopping", "Scambio läuft bereits aus einer anderen Installation; diese hier wird beendet", "Secondo demone che non ottiene il nome (spec 05)."),
("cli-version-help", "Mostra la versione ed esce", "Show the version and exit", "Version anzeigen und beenden", "scambio --version (spec 05)."),
]
def esc(s): return s.replace('\\','\\\\').replace('"','\\"')
HDR = '''# Scambio — testi dell'interfaccia ({lang}).
# Proprietà di Claude (design/). Chiavi simboliche: msgid = chiave del contratto
# in docs/context/05-ui-context.md; en.po è obbligatorio come gli altri.
# Segnaposto: {{device}}, {{minutes}}, {{time}}, {{error}}, {{shortcut}}, {{owner}}, {{version}} (str.format).
msgid ""
msgstr ""
"Project-Id-Version: scambio 0.1\\n"
"PO-Revision-Date: 2026-10-07 01:00+0200\\n"
"Last-Translator: Claude (design di Scambio)\\n"
"Language-Team: Scambio\\n"
"Language: {code}\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"

'''
def write(path, lang, code, idx):
    out = [HDR.format(lang=lang, code=code)]
    for row in K:
        key, note = row[0], row[4]
        if note: out.append(f'#. {note}\n')
        import re
        ph = sorted(set(re.findall(r'\{(\w+)\}', row[2])))
        if ph: out.append('#. segnaposto: ' + ', '.join('{'+p+'}' for p in ph) + '\n')
        out.append(f'msgid "{key}"\nmsgstr "{esc(row[idx]) if idx else ""}"\n\n')
    open(path,'w').write(''.join(out))
import os; d=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'i18n') + '/'
write(d+'scambio.pot','modello','', 0)
write(d+'it.po','italiano','it',1)
write(d+'en.po','english','en',2)
write(d+'de.po','deutsch','de',3)
open(d+'LINGUAS','w').write('it en de\n')
print(len(K))
