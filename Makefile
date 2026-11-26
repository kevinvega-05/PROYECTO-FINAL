.PHONY: instalar demo test lint cad visor pista panel
instalar:
	pip install -r requirements-dev.txt && pip install -e .
demo:
	python -m monedas --demo
test:
	python -m pytest
lint:
	ruff check .
pista:
	python -m monedas.pista --salida docs/img
cad:
	python cad/generar_cad.py --check
visor: cad
	python visor3d/construir.py
