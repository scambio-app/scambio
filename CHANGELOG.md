# Changelog

All notable changes to Scambio are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/): from 1.0.0 the D-Bus API `app.scambio.Scambio1`
and the `config.toml` format are stable.

## [1.0.0] - 2026-10-08

First public release for Linux.

### Added

- Background daemon that hands a Bluetooth headset or smart glasses to the computer when it plays
  audio, pausing MPRIS players during the switch and resuming them on the device.
- Automatic hand-back to the phone after a configurable silence (2 minutes by default), on screen
  lock and before suspend.
- Phone priority: keeps the computer from taking the device automatically.
- Global shortcut Super+G for a smart manual switch (KGlobalAccel on KDE Plasma, XDG Desktop
  Portal GlobalShortcuts elsewhere).
- System tray icon with menu and desktop notifications.
- Settings window (GTK 4 / libadwaita): device, silence timeout, shortcut, tray, notifications,
  language.
- Command line: `scambio status`, `switch`, `priority`, `settings`.
- English, Italian and German.
- Packages: `.deb` with an APT repository for Ubuntu 24.04+ and Debian 13+, and Flatpak.

[1.0.0]: https://github.com/scambio-app/scambio/releases/tag/v1.0.0
