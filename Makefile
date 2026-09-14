.PHONY: check self packs boundary

BASE ?= origin/main

check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests python3 -B -m unittest discover -s tests -t tests -v

self:
	PYTHONPATH=src python3 -m dossier check . --pack agent-control

packs:
	PYTHONPATH=src python3 -m dossier packs

boundary:
	python3 tools/check_boundary.py $(BASE)
