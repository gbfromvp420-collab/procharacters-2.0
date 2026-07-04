# ProCharacters 2.0 - practical make targets for verification

.PHONY: help install run test demo verify-all verify-empire verify-forge verify-theater verify-orchestration verify-lounge verify-revenue verify-character verify-live verify-scale verify-empire-complete verify-innovation docker-build docker-up docker-down clean

help:
	@echo "ProCharacters 2.0 make targets:"
	@echo "  make install        Install deps (into .venv if present)"
	@echo "  make run            Start dev server (via scripts/run.sh)"
	@echo "  make test           Run pytest (python -m pytest)"
	@echo "  make demo           Run full terminal mock demo (starts server if needed)"
	@echo "  make demo-fast      Demo without aiortc signaling"
	@echo "  make verify-all     Run pytest + demo smoke (PHASE 5 VERIFY OK)"
	@echo "  make verify-empire  Phase 11: pytest + live/ready probes"
	@echo "  make verify-forge  Phase 12: pytest + provider forge smoke"
	@echo "  make verify-theater Phase 13: pytest + agent theater dispatch"
	@echo "  make verify-orchestration Phase 14: pytest + orchestration chain smoke"
	@echo "  make verify-lounge       Phase 15: pytest + agent lounge API"
	@echo "  make verify-revenue      Phase 16: pytest + revenue forge API"
	@echo "  make verify-character    Phase 17: pytest + character forge API"
	@echo "  make verify-live         Phase 18: pytest + live stage API"
	@echo "  make verify-scale        Phase 19: pytest + sovereign scale API"
	@echo "  make verify-empire-complete Phase 20: pytest + crown completion v1.0"
	@echo "  make verify-innovation     Lane 1: pytest + real provider innovation API"
	@echo "  make docker-build   Build production image"
	@echo "  make docker-up      Start docker compose stack"
	@echo "  make docker-down    Stop docker compose stack"
	@echo "  make clean          Remove __pycache__ and .pytest_cache"

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

verify-empire:
	python scripts/verify_empire.py --start-server --skip-demo

verify-forge:
	python scripts/verify_forge.py --start-server

verify-theater:
	python scripts/verify_theater.py --start-server

verify-orchestration:
	python scripts/verify_orchestration.py --start-server

verify-lounge:
	python scripts/verify_lounge.py --start-server

verify-revenue:
	python scripts/verify_revenue.py --start-server

verify-character:
	python scripts/verify_character.py --start-server

verify-live:
	python scripts/verify_live.py --start-server

verify-scale:
	python scripts/verify_scale.py --start-server

verify-empire-complete:
	python scripts/verify_empire_complete.py --start-server

verify-innovation:
	python scripts/verify_innovation.py --start-server

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov 2>/dev/null || true