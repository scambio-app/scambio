PYTHON ?= /usr/bin/python3
VENV = .venv/bin
.PHONY: venv check fmt test run hooks install-user uninstall-user
venv:
	$(PYTHON) -m venv --system-site-packages .venv
	$(VENV)/python -m pip install -e '.[dev]'
check:
	$(VENV)/ruff format --check src tests tools
	$(VENV)/ruff check src tests tools
	$(VENV)/mypy
	$(VENV)/pytest
fmt:
	$(VENV)/ruff format src tests tools
	$(VENV)/ruff check --fix src tests tools
test:
	$(VENV)/pytest
run:
	$(VENV)/scambio daemon --debug
hooks:
	git config core.hooksPath .githooks
install-user:
	$(VENV)/python tools/install_user.py install
uninstall-user:
	$(VENV)/python tools/install_user.py uninstall
