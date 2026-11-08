.PHONY: help install test coverage lint format types check clean

help:
	@echo "Objetivos disponibles:"
	@echo "  install   Instala el proyecto en modo editable con dependencias de desarrollo"
	@echo "  test      Ejecuta la suite de pruebas"
	@echo "  coverage  Ejecuta las pruebas con informe de cobertura"
	@echo "  lint      Ejecuta el linter (ruff)"
	@echo "  format    Aplica el formateador (ruff format)"
	@echo "  types     Comprueba los tipos (mypy --strict)"
	@echo "  check     Ejecuta lint, format, types y tests"
	@echo "  clean     Elimina artefactos de compilación y cachés"

install:
	.venv/bin/python -m pip install -e ".[dev]"

test:
	.venv/bin/python -m pytest

coverage:
	.venv/bin/python -m pytest --cov=cvformfiller --cov-report=term-missing

lint:
	.venv/bin/python -m ruff check .

format:
	.venv/bin/python -m ruff format .

types:
	.venv/bin/python -m mypy src

check: lint format types test
	@echo "Todas las comprobaciones han pasado."

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
