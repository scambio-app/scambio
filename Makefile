PYTHON ?= /usr/bin/python3
VENV = .venv/bin
PREFIX ?= /usr/local
DESTDIR ?= /
SYSTEMD_USER_UNIT ?= 0
PYTHON_LIB ?=
.PHONY: venv check fmt test run hooks install-user uninstall-user
venv:
	$(PYTHON) -m venv --system-site-packages .venv
	$(VENV)/python -m pip install -e '.[dev]'
check: i18n ui
	$(VENV)/ruff format --check src tests tools
	$(VENV)/ruff check src tests tools
	$(VENV)/mypy
	$(VENV)/pytest
fmt:
	$(VENV)/ruff format src tests tools
	$(VENV)/ruff check --fix src tests tools
test:
	$(VENV)/pytest
run: i18n ui
	$(VENV)/scambio daemon --debug
hooks:
	git config core.hooksPath .githooks
install-user: i18n ui
	$(VENV)/python tools/install_user.py install
uninstall-user:
	$(VENV)/python tools/install_user.py uninstall

.PHONY: i18n
i18n:
	@command -v msgfmt >/dev/null || { echo "msgfmt missing: install gettext before make i18n" >&2; exit 1; }
	@for lang in it en de; do mkdir -p build/locale/$$lang/LC_MESSAGES; msgfmt --check design/i18n/$$lang.po -o build/locale/$$lang/LC_MESSAGES/scambio.mo || exit; done

.PHONY: ui
ui:
	@command -v blueprint-compiler >/dev/null || { echo "blueprint-compiler missing: install blueprint-compiler before make ui" >&2; exit 1; }
	@mkdir -p build/ui
	blueprint-compiler compile design/ui/settings-window.blp --output build/ui/settings-window.ui

.PHONY: install uninstall dist deb apt-repo flatpak flatpak-site release-check
install: i18n ui
	$(PYTHON) tools/install.py install --prefix "$(PREFIX)" --destdir "$(DESTDIR)" --python-lib "$(PYTHON_LIB)" $(if $(filter 1,$(SYSTEMD_USER_UNIT)),--systemd,)
uninstall:
	$(PYTHON) tools/install.py uninstall --prefix "$(PREFIX)" --destdir "$(DESTDIR)"
dist deb apt-repo flatpak flatpak-site:
	$(VENV)/python tools/release.py $@
release-check:
	$(VENV)/python tools/release.py check

.PHONY: verify
verify:
	$(VENV)/python tools/verify_release.py
