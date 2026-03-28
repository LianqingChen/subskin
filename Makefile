# Makefile for SubSkin Project

.PHONY: help setup install dev-install test lint format type-check clean

# Default target
help:
	@echo "SubSkin Project Commands:"
	@echo ""
	@echo "  make setup          Create virtual environment and install base dependencies"
	@echo "  make install        Install all dependencies (base + web + AI)"
	@echo "  make dev-install    Install development dependencies"
	@echo "  make test           Run tests"
	@echo "  make lint           Run linting (ruff)"
	@echo "  make format         Format code (black)"
	@echo "  make type-check     Run type checking (mypy)"
	@echo "  make clean          Clean up temporary files"
	@echo "  make help           Show this help message"
	@echo ""
	@echo "Environment setup:"
	@echo "  1. make setup       # Create virtual environment"
	@echo "  2. source .venv/bin/activate  # Activate virtual environment"
	@echo "  3. make install     # Install all dependencies"
	@echo ""

# Create virtual environment and install base dependencies
setup:
	@echo "Setting up Python virtual environment..."
	python -m venv .venv
	@echo "Virtual environment created at .venv/"
	@echo ""
	@echo "To activate the virtual environment:"
	@echo "  source .venv/bin/activate   # Linux/macOS"
	@echo "  .venv\\Scripts\\activate     # Windows"
	@echo ""
	@echo "Then run: make install"

# Install all dependencies
install: setup
	@echo "Installing dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev,web,ai]"
	@echo "Dependencies installed successfully!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy configs/.env.example to .env"
	@echo "  2. Edit .env with your API keys"
	@echo "  3. Run tests: make test"

# Install development dependencies
dev-install:
	@echo "Installing development dependencies..."
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	@echo "Development dependencies installed!"

# Run tests
test:
	@echo "Running tests..."
	.venv/bin/pytest -v --cov=src --cov-report=term-missing

# Run linting
lint:
	@echo "Running linting..."
	.venv/bin/ruff check src/ tests/
	@echo "Checking formatting..."
	.venv/bin/ruff format --check src/ tests/

# Format code
format:
	@echo "Formatting code..."
	.venv/bin/ruff format src/ tests/
	@echo "Code formatted!"

# Run type checking
type-check:
	@echo "Running type checking..."
	.venv/bin/mypy src/

# Clean up temporary files
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleanup complete!"

# Database operations
db-init:
	@echo "Initializing database..."
	.venv/bin/python scripts/init_db.py

db-migrate:
	@echo "Running database migrations..."
	.venv/bin/alembic upgrade head

# Development server
run-dev:
	@echo "Starting development server..."
	.venv/bin/uvicorn src.web.api.main:app --reload --host 0.0.0.0 --port 8000

# Crawler commands
crawl-pubmed:
	@echo "Running PubMed crawler..."
	.venv/bin/python -m src.crawlers.pubmed_crawler

crawl-scholar:
	@echo "Running Semantic Scholar crawler..."
	.venv/bin/python -m src.crawlers.semantic_scholar_crawler

crawl-trials:
	@echo "Running ClinicalTrials.gov crawler..."
	.venv/bin/python -m src.crawlers.clinical_trials_crawler

crawl-all: crawl-pubmed crawl-scholar crawl-trials

# Content generation
generate-weekly:
	@echo "Generating weekly content..."
	.venv/bin/python scripts/generate_weekly.py

# Documentation
docs-serve:
	@echo "Starting documentation server..."
	.venv/bin/mkdocs serve

docs-build:
	@echo "Building documentation..."
	.venv/bin/mkdocs build