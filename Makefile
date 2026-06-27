.PHONY: up up-logs down build logs shell db-shell redis-cli clean dev

# ── Docker Compose (production) ───────────────────────────────────────────────

up:          ## Start all services in background
	docker compose up -d

up-logs:     ## Start all services with live logs
	docker compose up

down:        ## Stop all services
	docker compose down

build:       ## Rebuild image after code changes
	docker compose up -d --build

logs:        ## Follow web container logs
	docker compose logs -f web

shell:       ## Open bash inside web container
	docker compose exec web bash

db-shell:    ## Open psql inside postgres container
	docker compose exec postgres psql -U skillswap -d skillswap

redis-cli:   ## Open redis-cli inside redis container
	docker compose exec redis redis-cli

clean:       ## Stop + delete all volumes (DESTRUCTIVE — wipes DB + Redis)
	docker compose down -v

# ── Dev mode (live reload) ────────────────────────────────────────────────────

dev:         ## Start with dev overrides (Flask dev server, exposed DB/Redis ports)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

dev-down:    ## Stop dev services
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

# ── Local (no Docker) ─────────────────────────────────────────────────────────

local:       ## Run locally without Docker
	python app.py

install:     ## Install Python deps locally
	pip install -r requirements.txt

# ── Helpers ───────────────────────────────────────────────────────────────────

ps:          ## Show running containers
	docker compose ps

help:        ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'
