SHELL := /bin/bash
MIGRATION_DATABASE:=./migrate.db

# Test environment variables — used by pytest in CI and local runs.
# The JWT_SECRET value here is intentionally weak and for testing only.
export JWT_SECRET ?= ci-test-secret-not-for-production-use-only

PACKAGE_SLUG=oscilla
PYTHON_VERSION := $(shell cat .python-version)
PYTHON_SHORT_VERSION := $(shell echo $(PYTHON_VERSION) | grep -o '[0-9].[0-9]*')

ifeq ($(USE_SYSTEM_PYTHON), true)
	PYTHON_PACKAGE_PATH:=$(shell python -c "import sys; print(sys.path[-1])")
	PYTHON_ENV :=
	PYTHON := python
	PYTHON_VENV :=
	UV := uv
else
	PYTHON_PACKAGE_PATH:=.venv/lib/python$(PYTHON_SHORT_VERSION)/site-packages
	PYTHON_ENV :=  . .venv/bin/activate &&
	PYTHON := . .venv/bin/activate && python
	PYTHON_VENV := .venv
	UV := uv
endif

# Used to confirm that uv has run at least once
PACKAGE_CHECK:=$(PYTHON_PACKAGE_PATH)/build
PYTHON_DEPS := $(PACKAGE_CHECK)


.PHONY: all
all: $(PACKAGE_CHECK)

.PHONY: install
install: uv $(PYTHON_VENV) sync frontend_install

.venv:
	$(UV) venv --python $(PYTHON_VERSION)

.PHONY: uv
uv:
	@command -v uv >/dev/null 2>&1 || { echo >&2 "uv is not installed. Installing via pip..."; pip install uv; }

.PHONY: sync
sync: $(PYTHON_VENV) uv.lock
	$(UV) sync --group dev

$(PACKAGE_CHECK): $(PYTHON_VENV) uv.lock
	$(UV) sync --group dev

uv.lock: pyproject.toml
	$(UV) lock

.PHONY: pre-commit
pre-commit:
	pre-commit install

#
# Formatting
#
.PHONY: chores
chores: ruff_fixes black_fixes prettier_fixes tomlsort_fixes frontend_format_fix document_schema

.PHONY: ruff_fixes
ruff_fixes:
	$(UV) run ruff check . --fix

.PHONY: black_fixes
black_fixes:
	$(UV) run ruff format .

.PHONY: prettier_fixes
prettier_fixes:
	npx --yes prettier --write . --log-level warn
	cd frontend && npx prettier --write . --log-level warn

.PHONY: tomlsort_fixes
tomlsort_fixes:
	$(PYTHON_ENV) tombi format $$(find . -not -path "./.venv/*" -name "*.toml")

#
# Testing
#
.PHONY: tests
tests: install pytest ruff_check black_check mypy_check prettier_check tomlsort_check paracelsus_check check_ungenerated_migrations validate frontend_check frontend_test frontend_playwright_lint

.PHONY: pytest
pytest:
	$(UV) run pytest --cov=./${PACKAGE_SLUG} --cov-report=term-missing tests

#
# Frontend
#
.PHONY: frontend_install
frontend_install:
	cd frontend && npm ci

.PHONY: frontend_build
frontend_build:
	cd frontend && npm run build

.PHONY: frontend_dev
frontend_dev:
	cd frontend && npm run dev

.PHONY: frontend_check
frontend_check:
	cd frontend && npx svelte-check --tsconfig ./tsconfig.json

.PHONY: frontend_test
frontend_test:
	cd frontend && npx vitest run

# Validate Playwright test structure (duplicate titles, config errors) without
# running tests or requiring a live server. Uses --list to parse all test files.
.PHONY: frontend_playwright_lint
frontend_playwright_lint: frontend_playwright_install
	cd frontend && npx playwright test --config playwright.e2e.config.ts --list > /dev/null

.PHONY: frontend_format_check
frontend_format_check:
	cd frontend && npx prettier --check src/

.PHONY: frontend_format_fix
frontend_format_fix:
	cd frontend && npx prettier --write src/

.PHONY: frontend_a11y
frontend_a11y: frontend_build frontend_playwright_install
	cd frontend && if [ -n "$(BROWSER)" ]; then npm run a11y -- --project "$(BROWSER)"; else npm run a11y; fi

.PHONY: frontend_playwright_install
frontend_playwright_install: frontend_install
	cd frontend && npm run playwright:install

.PHONY: frontend_playwright_install_ci
frontend_playwright_install_ci: frontend_install
	cd frontend && npx playwright install --with-deps chromium firefox webkit

.PHONY: frontend_e2e_run
frontend_e2e_run: frontend_playwright_install
	cd frontend && if [ -n "$(BROWSER)" ]; then npm run e2e -- --project "$(BROWSER)"; else npm run e2e; fi

.PHONY: frontend_a11y_chromium
frontend_a11y_chromium:
	$(MAKE) frontend_a11y BROWSER=chromium

.PHONY: frontend_a11y_firefox
frontend_a11y_firefox:
	$(MAKE) frontend_a11y BROWSER=firefox

.PHONY: frontend_a11y_webkit
frontend_a11y_webkit:
	$(MAKE) frontend_a11y BROWSER=webkit

.PHONY: frontend_a11y_all
frontend_a11y_all: frontend_a11y_chromium frontend_a11y_firefox frontend_a11y_webkit

.PHONY: frontend_e2e_chromium
frontend_e2e_chromium:
	$(MAKE) frontend_e2e BROWSER=chromium

.PHONY: frontend_e2e_firefox
frontend_e2e_firefox:
	$(MAKE) frontend_e2e BROWSER=firefox

.PHONY: frontend_e2e_webkit
frontend_e2e_webkit:
	$(MAKE) frontend_e2e BROWSER=webkit

.PHONY: frontend_e2e_all
frontend_e2e_all: frontend_e2e_chromium frontend_e2e_firefox frontend_e2e_webkit

.PHONY: frontend_playwright_chromium
frontend_playwright_chromium: frontend_a11y_chromium frontend_e2e_chromium

.PHONY: frontend_playwright_firefox
frontend_playwright_firefox: frontend_a11y_firefox frontend_e2e_firefox

.PHONY: frontend_playwright_webkit
frontend_playwright_webkit: frontend_a11y_webkit frontend_e2e_webkit

.PHONY: frontend_playwright_all
frontend_playwright_all: frontend_playwright_chromium frontend_playwright_firefox frontend_playwright_webkit

.PHONY: frontend_playwright_browser
frontend_playwright_browser:
	@if [ -z "$(BROWSER)" ]; then \
		echo "BROWSER is required (chromium|firefox|webkit)"; \
		exit 1; \
	fi
	@if [ "$(BROWSER)" != "chromium" ] && [ "$(BROWSER)" != "firefox" ] && [ "$(BROWSER)" != "webkit" ]; then \
		echo "Invalid BROWSER='$(BROWSER)'. Use chromium, firefox, or webkit."; \
		exit 1; \
	fi
	$(MAKE) frontend_a11y BROWSER=$(BROWSER)
	$(MAKE) frontend_e2e BROWSER=$(BROWSER)

.PHONY: frontend_e2e
frontend_e2e: frontend_e2e_stack

.PHONY: frontend_e2e_cleanup
frontend_e2e_cleanup:
	-@if command -v lsof >/dev/null 2>&1; then \
		PIDS_4173=$$(lsof -t -iTCP:4173 -sTCP:LISTEN); \
		if [ -n "$$PIDS_4173" ]; then \
			echo "Stopping stale process(es) on port 4173: $$PIDS_4173"; \
			kill $$PIDS_4173 2>/dev/null || true; \
		fi; \
		PIDS_8000=$$(lsof -t -iTCP:8000 -sTCP:LISTEN); \
		if [ -n "$$PIDS_8000" ]; then \
			echo "Stopping stale process(es) on port 8000: $$PIDS_8000"; \
			kill $$PIDS_8000 2>/dev/null || true; \
		fi; \
	fi
	-@docker compose down >/dev/null 2>&1 || true

.PHONY: frontend_e2e_stack
frontend_e2e_stack: frontend_playwright_install frontend_e2e_cleanup
	mkdir -p ./tmp
	docker compose up -d db redis mailhog
	rm -f ./tmp/e2e.db
	DATABASE_URL=sqlite:///./tmp/e2e.db $(UV) run alembic upgrade head
	DATABASE_URL=sqlite+aiosqlite:///./tmp/e2e.db $(UV) run uvicorn oscilla.www:app --host 127.0.0.1 --port 8000 > ./tmp/e2e-backend.log 2>&1 & \
	API_PID=$$!; \
	cd frontend && npm run build
	cd frontend && npm run preview -- --host 127.0.0.1 --port 4173 --strictPort & \
	PREVIEW_PID=$$!; \
	trap 'kill $$PREVIEW_PID $$API_PID 2>/dev/null || true; $(MAKE) frontend_e2e_cleanup' EXIT; \
	BACKEND_READY=0; \
	for i in $$(seq 1 120); do \
		if curl --silent --fail http://127.0.0.1:8000/ready >/dev/null; then \
			BACKEND_READY=1; \
			break; \
		fi; \
		sleep 1; \
	done; \
	if [ $$BACKEND_READY -ne 1 ]; then \
		echo 'Backend did not become ready at http://127.0.0.1:8000/ready within 120s'; \
		docker compose ps; \
		tail -n 200 ./tmp/e2e-backend.log; \
		exit 1; \
	fi; \
	FRONTEND_READY=0; \
	for i in $$(seq 1 120); do \
		if curl --silent --fail http://127.0.0.1:4173/app/ >/dev/null; then \
			FRONTEND_READY=1; \
			break; \
		fi; \
		sleep 1; \
	done; \
	if [ $$FRONTEND_READY -ne 1 ]; then \
		echo 'Frontend preview did not become ready at http://127.0.0.1:4173/app/ within 120s'; \
		docker compose ps; \
		tail -n 200 ./tmp/e2e-backend.log; \
		exit 1; \
	fi; \
	$(MAKE) frontend_e2e_run

.PHONY: pytest_loud
pytest_loud:
	$(UV) run pytest --log-cli-level=DEBUG -log_cli=true --cov=./${PACKAGE_SLUG} --cov-report=term-missing tests

.PHONY: ruff_check
ruff_check:
	$(UV) run ruff check

.PHONY: black_check
black_check:
	$(UV) run ruff format . --check

.PHONY: mypy_check
mypy_check:
	$(UV) run mypy ${PACKAGE_SLUG}

.PHONY: validate
validate:
	$(UV) run oscilla validate

.PHONY: prettier_check
prettier_check: frontend_install
	npx --yes prettier --check . --log-level warn
	cd frontend && npx prettier --check . --log-level warn

.PHONY: tomlsort_check
tomlsort_check:
	$(PYTHON_ENV) tombi lint $$(find . -not -path "./.venv/*" -name "*.toml")
	$(PYTHON_ENV) tombi format $$(find . -not -path "./.venv/*" -name "*.toml") --check



#
# Dependencies
#

.PHONY: lock
lock:
	$(UV) lock --upgrade

.PHONY: lock-check
lock-check:
	$(UV) lock --check


#
# Packaging
#

.PHONY: build
build: $(PACKAGE_CHECK)
	$(UV) run python -m build

#
# Database
#

.PHONY: document_schema
document_schema:
	$(UV) run python -m paracelsus.cli inject docs/dev/database.md $(PACKAGE_SLUG).models.base:Base --import-module "$(PACKAGE_SLUG).models:*"

.PHONY: paracelsus_check
paracelsus_check:
	$(UV) run python -m paracelsus.cli inject docs/dev/database.md $(PACKAGE_SLUG).models.base:Base --import-module "$(PACKAGE_SLUG).models:*" --check

.PHONY: run_migrations
run_migrations:
	$(UV) run alembic upgrade head

.PHONY: reset_db
reset_db: clear_db run_migrations

.PHONY: clear_db
clear_db:
	rm -Rf test.db*

.PHONY: create_migration
create_migration:
	@if [ -z "$(MESSAGE)" ]; then echo "Please add a message parameter for the migration (make create_migration MESSAGE=\"database migration notes\")."; exit 1; fi
	rm $(MIGRATION_DATABASE) | true
	DATABASE_URL=sqlite:///$(MIGRATION_DATABASE) $(UV) run alembic upgrade head 2>/dev/null
	DATABASE_URL=sqlite:///$(MIGRATION_DATABASE) $(UV) run alembic revision --autogenerate -m "$(MESSAGE)"
	rm $(MIGRATION_DATABASE)
	$(UV) run ruff format ./db

.PHONY: check_ungenerated_migrations
check_ungenerated_migrations:
	rm -f $(MIGRATION_DATABASE)
	DATABASE_URL=sqlite:///$(MIGRATION_DATABASE) $(UV) run alembic upgrade head 2>/dev/null | tail -5
	DATABASE_URL=sqlite:///$(MIGRATION_DATABASE) $(UV) run alembic check 2>/dev/null | tail -5
	rm -f $(MIGRATION_DATABASE)

#
# Cleanup
#

.PHONY: clean_logs
clean_logs:
	rm -f *.log

.PHONY: clean_saves
clean_saves:
	rm -f saves.db saves.db-wal saves.db-shm

.PHONY: clean_scripts
clean_scripts:
	rm -f *.py

.PHONY: clean
clean: clean_logs clean_saves clean_scripts


