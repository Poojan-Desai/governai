.PHONY: demo cloud-status test test-python test-web lint build clean

demo:
	PYTHONPATH=backend python3 -m governai.cli demo --project-root . --reset

cloud-status:
	PYTHONPATH=backend python3 -m governai.cli cloud-status --project-root .

test: test-python test-web lint build

test-python:
	PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v

test-web:
	npm run test:web

lint:
	npm run lint

build:
	npm run build

clean:
	python3 -c "from pathlib import Path; import shutil; p=Path('.local'); shutil.rmtree(p) if p.exists() else None"
