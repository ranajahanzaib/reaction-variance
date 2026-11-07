UV_CACHE_DIR ?= /tmp/reaction-variance-uv
export UV_CACHE_DIR
PYTHON = backend/.venv/bin/python
export PYTHONPATH := backend
.PHONY: install download inspect ingest rebuild backend frontend test e2e build serve format
install:
	uv sync --directory backend --locked
	pnpm --dir frontend install --frozen-lockfile
download:
	$(PYTHON) -m app.ingestion download
inspect:
	$(PYTHON) -m app.ingestion inspect
ingest rebuild:
	$(PYTHON) -m app.ingestion rebuild
backend:
	backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011 --reload
frontend:
	pnpm --dir frontend dev
test:
	$(PYTHON) -m pytest backend/tests -q
	pnpm --dir frontend test
e2e:
	pnpm --dir frontend e2e
build:
	pnpm --dir frontend build
serve:
	backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8011
format:
	backend/.venv/bin/ruff format backend scripts
	pnpm --dir frontend exec prettier --write src tests '*.ts' '*.json' '*.html'
