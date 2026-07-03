# ProCharacters 2.0 - practical make targets for verification

.PHONY: help install run test demo verify-all clean

help:
	@echo "ProCharacters 2.0 make targets:"
	@echo "  make install     Install deps (into .venv if present)"
	@echo "  make run         Start dev server (via scripts/run.sh)"
	@echo "  make test        Run pytest (python -m pytest)"
	@echo "  make demo        Run full terminal mock demo (starts server if needed)"
	@echo "  make demo-fast   Demo without aiortc signaling"
	@echo "  make verify-all  Run pytest + demo smoke (PHASE 5 VERIFY OK)"
	@echo "  make clean       Remove __pycache__ and .pytest_cache"

install:
	python -m venv .venv 2>/dev/null || true
	. .venv/bin/activate && pip install -r requirements.txt

run:
	./scripts/run.sh

test:
	python -m pytest -q --tb=line tests/ || echo "If 'pytest: No module' appears, run: pip install -r requirements.txt then retry make test"

demo:
	python scripts/demo.py --start-server

demo-fast:
	python scripts/demo.py --start-server --no-signaling

verify-all:
	python scripts/verify_all.py --start-server

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov 2>/dev/null || true
