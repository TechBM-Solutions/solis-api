PYTHON := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn

.PHONY: setup run health live decision check

setup:
	python -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi

run:
	$(UVICORN) app.main:app --host 127.0.0.1 --port 8001

health:
	curl -sS http://127.0.0.1:8001/health

live:
	curl -sS http://127.0.0.1:8001/live

decision:
	curl -sS http://127.0.0.1:8001/consumption-decision

check:
	bash scripts/public_release_check.sh
