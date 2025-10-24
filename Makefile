# Makefile for TeckoChecker
# Polling orchestration for async workflows

# Variables
PYTHON := python3
VENV := venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PYTEST := $(BIN)/pytest
BLACK := $(BIN)/black
RUFF := $(BIN)/ruff
UVICORN := $(BIN)/uvicorn
PYTHON_VENV := $(BIN)/python

# Project paths
APP_DIR := app
TESTS_DIR := tests
SCRIPTS_DIR := scripts

# Application settings
API_HOST := 0.0.0.0
API_PORT := 8000

# Color output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)TeckoChecker - Development Commands$(NC)"
	@echo "$(BLUE)=====================================$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Quick Start:$(NC)"
	@echo "  1. make install    - Set up development environment"
	@echo "  2. make db-init    - Initialize database"
	@echo "  3. make run-api    - Start the API server"
	@echo ""

.PHONY: install
install: ## Create virtual environment and install all dependencies
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	@$(PYTHON) -m venv $(VENV)
	@echo "$(BLUE)Upgrading pip...$(NC)"
	@$(PIP) install --upgrade pip
	@echo "$(BLUE)Installing dependencies...$(NC)"
	@$(PIP) install -r requirements.txt
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	@$(PIP) install -e ".[dev]" 2>/dev/null || $(PIP) install pytest pytest-asyncio pytest-cov black ruff mypy
	@echo "$(GREEN)Installation complete!$(NC)"
	@echo "$(YELLOW)Run 'source venv/bin/activate' to activate the virtual environment$(NC)"

.PHONY: install-dev
install-dev: install ## Install with development dependencies (same as install)
	@echo "$(GREEN)Development environment ready!$(NC)"

.PHONY: clean
clean: ## Remove virtual environment, cache files, and build artifacts
	@echo "$(BLUE)Cleaning up...$(NC)"
	@rm -rf $(VENV)
	@rm -rf .pytest_cache
	@rm -rf .ruff_cache
	@rm -rf .mypy_cache
	@rm -rf htmlcov
	@rm -rf .coverage
	@rm -rf .coverage.*
	@rm -rf coverage.json
	@rm -rf coverage.xml
	@rm -rf dist
	@rm -rf build
	@rm -rf *.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

.PHONY: run-api
run-api: ## Start the FastAPI development server (polling service starts automatically)
	@echo "$(BLUE)Starting TeckoChecker API...$(NC)"
	@echo "$(YELLOW)API will be available at:$(NC)"
	@echo "  - Main: http://localhost:$(API_PORT)"
	@echo "  - Docs: http://localhost:$(API_PORT)/docs"
	@echo "  - Health: http://localhost:$(API_PORT)/api/health"
	@echo ""
	@echo "$(YELLOW)Note: Polling service starts automatically with the API server$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop the server$(NC)"
	@echo ""
	@$(PYTHON_VENV) teckochecker.py start --reload

.PHONY: run-api-prod
run-api-prod: ## Start the FastAPI server in production mode (polling service starts automatically)
	@echo "$(BLUE)Starting TeckoChecker API (production mode)...$(NC)"
	@$(PYTHON_VENV) teckochecker.py start

.PHONY: test
test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@$(PYTEST) $(TESTS_DIR) -v

.PHONY: test-integration
test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	@$(PYTEST) $(TESTS_DIR)/integration -v

.PHONY: format
format: ## Format code with black and ruff
	@echo "$(BLUE)Formatting code with black...$(NC)"
	@$(BLACK) $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py || true
	@echo "$(BLUE)Formatting code with ruff...$(NC)"
	@$(RUFF) check --fix $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py || true
	@echo "$(GREEN)Code formatting complete!$(NC)"

.PHONY: lint
lint: ## Check code with ruff
	@echo "$(BLUE)Linting code with ruff...$(NC)"
	@$(RUFF) check $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py
	@echo "$(GREEN)Linting complete!$(NC)"

.PHONY: db-init
db-init: ## Initialize the database
	@echo "$(BLUE)Initializing database...$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/init_db.py
	@echo "$(GREEN)Database initialized!$(NC)"

.PHONY: db-show
db-show: ## Show database schema
	@echo "$(BLUE)Database schema:$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/show_schema.py

.PHONY: env
env: ## Create .env file from .env.example
	@if [ ! -f .env ]; then \
		echo "$(BLUE)Creating .env file from .env.example...$(NC)"; \
		cp .env.example .env; \
		SECRET_KEY=$$($(PYTHON) -c "import secrets; print(secrets.token_urlsafe(32))"); \
		if [ "$$(uname)" = "Darwin" ]; then \
			sed -i '' "s/SECRET_KEY=.*/SECRET_KEY=$$SECRET_KEY/" .env; \
		else \
			sed -i "s/SECRET_KEY=.*/SECRET_KEY=$$SECRET_KEY/" .env; \
		fi; \
		echo "$(GREEN).env file created with random SECRET_KEY!$(NC)"; \
		echo "$(YELLOW)Please update other settings in .env as needed$(NC)"; \
	else \
		echo "$(YELLOW).env file already exists$(NC)"; \
	fi

.PHONY: dev
dev: install env db-init ## Complete development setup (install + env + db)
	@echo "$(GREEN)Development environment is ready!$(NC)"
	@echo "$(YELLOW)Run 'make run-api' to start the server$(NC)"

# Docker commands
.PHONY: docker-build
docker-build: ## Build Docker image using distroless
	@echo "$(BLUE)Building Docker image (distroless)...$(NC)"
	@docker build -t teckochecker:latest .
	@echo "$(GREEN)Docker image built successfully!$(NC)"

.PHONY: docker-build-debug
docker-build-debug: ## Build Docker debug image with shell access
	@echo "$(BLUE)Building Docker debug image...$(NC)"
	@docker build -f Dockerfile.debug -t teckochecker:debug .
	@echo "$(GREEN)Docker debug image built successfully!$(NC)"

.PHONY: docker-run
docker-run: ## Run Docker container (requires SECRET_KEY env var)
	@echo "$(BLUE)Starting TeckoChecker Docker container...$(NC)"
	@if [ -z "$$SECRET_KEY" ]; then \
		echo "$(RED)ERROR: SECRET_KEY environment variable is required$(NC)"; \
		echo "$(YELLOW)Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"$(NC)"; \
		exit 1; \
	fi
	@docker run -d \
		--name teckochecker \
		-p 8000:8000 \
		-e SECRET_KEY=$$SECRET_KEY \
		-v teckochecker-data:/data \
		teckochecker:latest
	@echo "$(GREEN)Container started!$(NC)"
	@echo "$(YELLOW)API: http://localhost:8000$(NC)"
	@echo "$(YELLOW)Check logs: docker logs -f teckochecker$(NC)"

.PHONY: docker-compose-up
docker-compose-up: ## Start services with docker-compose (requires SECRET_KEY env var)
	@echo "$(BLUE)Starting services with docker-compose...$(NC)"
	@if [ -z "$$SECRET_KEY" ]; then \
		echo "$(RED)ERROR: SECRET_KEY environment variable is required$(NC)"; \
		echo "$(YELLOW)Generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"$(NC)"; \
		exit 1; \
	fi
	@docker-compose up -d
	@echo "$(GREEN)Services started!$(NC)"

.PHONY: docker-compose-down
docker-compose-down: ## Stop and remove docker-compose services
	@echo "$(BLUE)Stopping services...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Services stopped!$(NC)"

.PHONY: docker-compose-logs
docker-compose-logs: ## Show docker-compose logs
	@docker-compose logs -f

.PHONY: docker-stop
docker-stop: ## Stop Docker container
	@echo "$(BLUE)Stopping Docker container...$(NC)"
	@docker stop teckochecker || true
	@docker rm teckochecker || true
	@echo "$(GREEN)Container stopped!$(NC)"

.PHONY: docker-shell
docker-shell: ## Open shell in debug container (starts debug container if not running)
	@echo "$(BLUE)Opening shell in debug container...$(NC)"
	@docker run -it --rm \
		-e SECRET_KEY=$${SECRET_KEY:-dummy} \
		-v teckochecker-data:/data \
		--entrypoint /busybox/sh \
		teckochecker:debug

.PHONY: docker-clean
docker-clean: docker-stop ## Remove Docker images and volumes
	@echo "$(BLUE)Cleaning Docker resources...$(NC)"
	@docker rmi teckochecker:latest 2>/dev/null || true
	@docker rmi teckochecker:debug 2>/dev/null || true
	@docker volume rm teckochecker-data 2>/dev/null || true
	@echo "$(GREEN)Docker resources cleaned!$(NC)"

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	@docker logs -f teckochecker

.PHONY: docker-test
docker-test: docker-build ## Test Docker image (requires SECRET_KEY env var)
	@echo "$(BLUE)Testing Docker image...$(NC)"
	@if [ -z "$$SECRET_KEY" ]; then \
		SECRET_KEY=$$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"); \
	fi; \
	docker run --rm \
		-e SECRET_KEY=$$SECRET_KEY \
		-e DATABASE_URL=sqlite:////tmp/test.db \
		teckochecker:latest \
		doctor
	@echo "$(GREEN)Docker image test passed!$(NC)"

.DEFAULT_GOAL := help
