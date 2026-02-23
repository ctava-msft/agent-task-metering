.PHONY: install lint test build clean

PYTHON ?= python3
IMAGE_NAME ?= agent-task-metering

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check src/ tests/

format:
	$(PYTHON) -m ruff format src/ tests/

test:
	$(PYTHON) -m pytest tests/ --cov=agent_task_metering --cov-report=term-missing

build:
	docker build -f src/Dockerfile -t $(IMAGE_NAME):latest .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
