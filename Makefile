# Pick the right Python: prefer ./venv if it exists, else system "python".
PYTHON ?= $(shell test -x venv/Scripts/python.exe && echo venv/Scripts/python.exe || echo python)
PORT   ?= 8000

.PHONY: help install seed run test lint docker-build docker-run clean

help:                  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:               ## Create venv (if missing) and install dependencies
	test -d venv || python -m venv venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

seed:                  ## Load seed data into places.db
	$(PYTHON) -m src.seed

run:                   ## Start the dev server with reload on http://localhost:$(PORT)
	$(PYTHON) -m uvicorn src.main:app --reload --port $(PORT)

test:                  ## Run the full test suite
	$(PYTHON) -m pytest -v

smoke:                 ## Run the scripted endpoint walk-through (requires server running)
	$(PYTHON) scripts/try_api.py

lock:                  ## Refresh requirements.lock.txt from the current venv
	$(PYTHON) -m pip freeze > requirements.lock.txt

docker-build:          ## Build the Docker image
	docker build -t place-data-service .

docker-run:            ## Run the Docker image on http://localhost:$(PORT)
	docker run --rm -p $(PORT):8000 --name place-data-service place-data-service

clean:                 ## Remove caches and the local database
	rm -rf .pytest_cache __pycache__ src/__pycache__ tests/__pycache__ places.db
