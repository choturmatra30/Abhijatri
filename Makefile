# Abhijatri shortcuts for Linux, macOS and Windows. Run from this folder:  make help
# Needs: make, Node (npm), and either `uv` or a Python with the backend installed. `railway` only for PROD=1.
# Windows: install GNU make (e.g. `winget install ezwinports.make` or MinGW) and Git for Windows (its sh is used).
# Commands that touch the database use the local one by default; add PROD=1 to run them against production
# through the linked Railway project (railway run).

# --- per-OS settings ---
ifeq ($(OS),Windows_NT)
# Never WSL's bash (it cannot see Windows npm/uv/railway): use Git's sh (8.3 paths, no spaces). Falls back to sh in PATH.
SHELL := $(firstword $(wildcard C:/PROGRA~1/Git/bin/sh.exe C:/PROGRA~2/Git/bin/sh.exe) sh)
OPEN := cmd /c start ""
# Git's sh rewrites arguments such as /staff/ into Windows paths; this switch turns that off.
export MSYS_NO_PATHCONV := 1
else
UNAME := $(shell uname -s)
ifeq ($(UNAME),Darwin)
OPEN := open
else
OPEN := xdg-open
endif
endif

ifeq ($(PROD),1)
RUN := railway run
else
RUN :=
endif

# `uv` when installed, otherwise the virtualenv in backend/.venv (either layout), otherwise python on PATH.
ifneq ($(shell command -v uv 2>/dev/null),)
PY := uv run --no-sync python
UVICORN := uv run --no-sync uvicorn
else ifneq ($(wildcard backend/.venv/Scripts/python.exe),)
PY := .venv/Scripts/python.exe
UVICORN := .venv/Scripts/python.exe -m uvicorn
else ifneq ($(wildcard backend/.venv/bin/python),)
PY := .venv/bin/python
UVICORN := .venv/bin/python -m uvicorn
else
PY := python
UVICORN := python -m uvicorn
endif

EMAIL ?=
ROLE ?= moderator
LIVE_API ?= https://abhijatri-backend.up.railway.app

.PHONY: help backend frontend staff staff-open staff-live staff-bundle list-staff superadmin moderator revoke-role bootstrap reset-mfa gmail-token test-mail

help:
	@echo "make backend                         start the API on :8000 (local)"
	@echo "make frontend                        start the member app on :5173"
	@echo "make staff                           start the staff app (moderator + superadmin) on :5175"
	@echo "make staff-open                      open the LIVE staff dashboard (superadmin / moderator) in your browser"
	@echo "make staff-live                      staff app on http://localhost:5175 using the PRODUCTION API (opens the browser)"
	@echo "make staff-bundle                    build the staff app into the API (served at /staff after you commit and deploy)"
	@echo "make list-staff [PROD=1]             who holds a staff role"
	@echo "make superadmin EMAIL=a@b.c [PROD=1] give that verified account the superadmin role"
	@echo "make moderator EMAIL=a@b.c [PROD=1]  give it the moderator role (must be a Verified Member)"
	@echo "make revoke-role EMAIL=a@b.c [PROD=1] remove its staff role"
	@echo "make bootstrap EMAIL=a@b.c [PROD=1]  first superadmin only (refused if one exists)"
	@echo "make reset-mfa EMAIL=a@b.c [PROD=1]  let a staff member enrol a new authenticator"
	@echo "make gmail-token                     get a new Gmail refresh token"
	@echo "make test-mail EMAIL=a@b.c           send a test email with the provider in backend/.env"

backend:
	cd backend && $(UVICORN) app.main:app --reload

frontend:
	cd frontend && npm run dev

staff:
	cd staff && npm run dev

staff-open:
	$(OPEN) $(LIVE_API)/staff/

# Local page, production data: for signing in as the real superadmin or moderator. Change LIVE_API if the API host changes.

staff-live:
	@echo "Staff app on http://localhost:5175 using $(LIVE_API). Close the window or press Ctrl+C to stop."
	@(i=0; while [ $$i -lt 60 ]; do curl -s -o /dev/null http://localhost:5175/ && break; i=$$((i+1)); sleep 1; done; $(OPEN) http://localhost:5175 >/dev/null 2>&1) &
	cd staff && STAFF_API_PROXY=$(LIVE_API) VITE_API_BASE_URL= npm run dev

# Build the staff dashboard for the API to serve at /staff, then commit backend/app/staff_site and deploy.
staff-bundle:
	cd staff && npm run build -- --base=/staff/
	rm -rf backend/app/staff_site
	cp -r staff/dist backend/app/staff_site
	@echo "Bundled into backend/app/staff_site. Commit it and push; the API then serves /staff."

list-staff:
	cd backend && $(RUN) $(PY) -m app.jobs.list_staff

superadmin:
	@test -n "$(EMAIL)" || (echo "Usage: make superadmin EMAIL=person@example.com [PROD=1]" && exit 1)
	cd backend && $(RUN) $(PY) -m app.jobs.grant_role --email $(EMAIL) --role superadmin

moderator:
	@test -n "$(EMAIL)" || (echo "Usage: make moderator EMAIL=person@example.com [PROD=1]" && exit 1)
	cd backend && $(RUN) $(PY) -m app.jobs.grant_role --email $(EMAIL) --role moderator

revoke-role:
	@test -n "$(EMAIL)" || (echo "Usage: make revoke-role EMAIL=person@example.com [PROD=1]" && exit 1)
	cd backend && $(RUN) $(PY) -m app.jobs.grant_role --email $(EMAIL) --role none

bootstrap:
	@test -n "$(EMAIL)" || (echo "Usage: make bootstrap EMAIL=person@example.com [PROD=1]" && exit 1)
	cd backend && $(RUN) $(PY) -m app.jobs.bootstrap_admin --email $(EMAIL)

reset-mfa:
	@test -n "$(EMAIL)" || (echo "Usage: make reset-mfa EMAIL=person@example.com [PROD=1]" && exit 1)
	cd backend && $(RUN) $(PY) -m app.jobs.reset_mfa --email $(EMAIL)

gmail-token:
	cd backend && $(PY) -m app.jobs.gmail_authorize

test-mail:
	@test -n "$(EMAIL)" || (echo "Usage: make test-mail EMAIL=person@example.com" && exit 1)
	cd backend && $(PY) -m app.jobs.send_test_email --to $(EMAIL)
