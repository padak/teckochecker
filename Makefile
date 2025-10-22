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
	@rm -rf dist
	@rm -rf build
	@rm -rf *.egg-info
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	@echo "$(GREEN)Cleanup complete!$(NC)"

.PHONY: clean-db
clean-db: ## Remove database file
	@echo "$(YELLOW)Removing database file...$(NC)"
	@rm -f teckochecker.db
	@echo "$(GREEN)Database file removed!$(NC)"

.PHONY: run-api
run-api: ## Start the FastAPI development server
	@echo "$(BLUE)Starting TeckoChecker API...$(NC)"
	@echo "$(YELLOW)API will be available at:$(NC)"
	@echo "  - Main: http://localhost:$(API_PORT)"
	@echo "  - Docs: http://localhost:$(API_PORT)/docs"
	@echo "  - Health: http://localhost:$(API_PORT)/api/health"
	@echo ""
	@echo "$(YELLOW)Press Ctrl+C to stop the server$(NC)"
	@echo ""
	@$(UVICORN) app.main:app --reload --host $(API_HOST) --port $(API_PORT)

.PHONY: run-api-prod
run-api-prod: ## Start the FastAPI server in production mode (no reload)
	@echo "$(BLUE)Starting TeckoChecker API (production mode)...$(NC)"
	@$(UVICORN) app.main:app --host $(API_HOST) --port $(API_PORT)

.PHONY: run-cli
run-cli: ## Show CLI help
	@echo "$(BLUE)TeckoChecker CLI$(NC)"
	@$(PYTHON_VENV) teckochecker.py --help

.PHONY: test
test: ## Run all tests with coverage
	@echo "$(BLUE)Running all tests...$(NC)"
	@$(PYTEST) $(TESTS_DIR) -v --cov=$(APP_DIR) --cov-report=html --cov-report=term-missing

.PHONY: test-unit
test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	@$(PYTEST) $(TESTS_DIR)/unit -v

.PHONY: test-integration
test-integration: ## Run integration tests
	@echo "$(BLUE)Running integration tests...$(NC)"
	@$(PYTEST) $(SCRIPTS_DIR)/test_integration.py -v

.PHONY: test-api
test-api: ## Run API test script
	@echo "$(BLUE)Running API tests...$(NC)"
	@./$(SCRIPTS_DIR)/test_api.sh

.PHONY: test-fast
test-fast: ## Run tests without coverage (faster)
	@echo "$(BLUE)Running tests (fast mode)...$(NC)"
	@$(PYTEST) $(TESTS_DIR) -v

.PHONY: test-watch
test-watch: ## Run tests in watch mode (requires pytest-watch)
	@echo "$(BLUE)Running tests in watch mode...$(NC)"
	@$(BIN)/ptw $(TESTS_DIR) -- -v

.PHONY: format
format: ## Format code with black and ruff
	@echo "$(BLUE)Formatting code with black...$(NC)"
	@$(BLACK) $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py || true
	@echo "$(BLUE)Formatting code with ruff...$(NC)"
	@$(RUFF) check --fix $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py || true
	@echo "$(GREEN)Code formatting complete!$(NC)"

.PHONY: format-check
format-check: ## Check code formatting without making changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	@$(BLACK) --check $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py
	@echo "$(GREEN)Format check complete!$(NC)"

.PHONY: lint
lint: ## Check code with ruff
	@echo "$(BLUE)Linting code with ruff...$(NC)"
	@$(RUFF) check $(APP_DIR) $(TESTS_DIR) $(SCRIPTS_DIR) *.py
	@echo "$(GREEN)Linting complete!$(NC)"

.PHONY: type-check
type-check: ## Run type checking with mypy
	@echo "$(BLUE)Running type checks...$(NC)"
	@$(BIN)/mypy $(APP_DIR) || true
	@echo "$(GREEN)Type checking complete!$(NC)"

.PHONY: check
check: format-check lint type-check ## Run all code quality checks
	@echo "$(GREEN)All checks complete!$(NC)"

.PHONY: db-init
db-init: ## Initialize the database
	@echo "$(BLUE)Initializing database...$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/init_db.py
	@echo "$(GREEN)Database initialized!$(NC)"

.PHONY: db-reset
db-reset: ## Reset the database (drop and recreate)
	@echo "$(YELLOW)Resetting database...$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/init_db.py --reset
	@echo "$(GREEN)Database reset complete!$(NC)"

.PHONY: db-show
db-show: ## Show database schema
	@echo "$(BLUE)Database schema:$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/show_schema.py

.PHONY: verify
verify: ## Verify the setup
	@echo "$(BLUE)Verifying setup...$(NC)"
	@$(PYTHON_VENV) $(SCRIPTS_DIR)/verify_setup.py

.PHONY: docker-build
docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(NC)"
	@docker build -t teckochecker:latest .
	@echo "$(GREEN)Docker image built!$(NC)"

.PHONY: docker-run
docker-run: ## Run Docker container
	@echo "$(BLUE)Running Docker container...$(NC)"
	@docker run -d -p $(API_PORT):$(API_PORT) --name teckochecker --env-file .env teckochecker:latest
	@echo "$(GREEN)Docker container started!$(NC)"
	@echo "$(YELLOW)API available at: http://localhost:$(API_PORT)$(NC)"

.PHONY: docker-stop
docker-stop: ## Stop Docker container
	@echo "$(BLUE)Stopping Docker container...$(NC)"
	@docker stop teckochecker || true
	@docker rm teckochecker || true
	@echo "$(GREEN)Docker container stopped!$(NC)"

.PHONY: docker-logs
docker-logs: ## Show Docker container logs
	@docker logs -f teckochecker

.PHONY: docker-shell
docker-shell: ## Open shell in Docker container
	@docker exec -it teckochecker /bin/bash

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

.PHONY: deps-update
deps-update: ## Update dependencies
	@echo "$(BLUE)Updating dependencies...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install --upgrade -r requirements.txt
	@echo "$(GREEN)Dependencies updated!$(NC)"

.PHONY: deps-list
deps-list: ## List installed dependencies
	@$(PIP) list

.PHONY: deps-tree
deps-tree: ## Show dependency tree (requires pipdeptree)
	@$(PIP) install pipdeptree 2>/dev/null || true
	@$(BIN)/pipdeptree

.PHONY: shell
shell: ## Open Python shell with app context
	@echo "$(BLUE)Opening Python shell...$(NC)"
	@$(PYTHON_VENV) -i -c "import sys; sys.path.insert(0, '.'); from app import *; print('TeckoChecker context loaded')"

.PHONY: requirements
requirements: ## Generate requirements.txt from current environment
	@echo "$(BLUE)Generating requirements.txt...$(NC)"
	@$(PIP) freeze > requirements.txt
	@echo "$(GREEN)requirements.txt updated!$(NC)"

.PHONY: serve
serve: run-api ## Alias for run-api

.PHONY: start
start: run-api ## Alias for run-api

.PHONY: all
all: clean install test lint ## Clean, install, test, and lint

.PHONY: ci
ci: install test lint ## Run CI pipeline (install, test, lint)
	@echo "$(GREEN)CI pipeline complete!$(NC)"

.DEFAULT_GOAL := help
