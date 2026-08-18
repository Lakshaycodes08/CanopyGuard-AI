PYTHON ?= python

.PHONY: check test lint format format-check hygiene pip-check compile data features forecast risk schedule figures paper

check: lint format-check test pip-check compile

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) scripts/check_text_hygiene.py

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check . --fix

format-check:
	$(PYTHON) -m ruff format --check .

hygiene:
	$(PYTHON) scripts/check_text_hygiene.py

pip-check:
	$(PYTHON) -m pip check

compile:
	$(PYTHON) -m compileall -q src tests scripts

data:
	@echo "No data stages yet. Add DVC stages after choosing a study area."

features:
	@echo "No feature stage yet."

forecast:
	@echo "No forecast stage yet."

risk:
	@echo "No risk stage yet."

schedule:
	@echo "No scheduling stage yet."

figures:
	@echo "No figure stage yet."

paper:
	@echo "Draft manuscript at paper/main.tex."
