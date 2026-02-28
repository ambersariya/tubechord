.PHONY: install lint format format-check typecheck test build clean check upgrade lock

# Install all dependencies including dev tools
install:
	poetry install --with dev

# Run ruff linter
lint:
	poetry run ruff check .

# Auto-fix lint issues
lint-fix:
	poetry run ruff check --fix .

# Format code with ruff
format:
	poetry run ruff format .

# Check formatting without modifying files (used in CI)
format-check:
	poetry run ruff format --check .

# Run mypy type checker
typecheck:
	poetry run mypy tubechord/

# Run tests
test:
	poetry run pytest -v

# Build wheel + sdist
build:
	poetry build

# Run all checks (lint + format-check + typecheck) — used before committing
check: lint format-check typecheck

# Regenerate poetry.lock without upgrading any package (pin current resolution)
lock:
	poetry lock

# Upgrade all dependencies to their latest allowed versions, then commit the lock file
upgrade:
	poetry update
	git add poetry.lock
	git commit -m "chore: upgrade dependencies"

# Remove build artefacts and caches
clean:
	rm -rf dist/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} +
	find . -type d -name .pytest_cache -not -path './.venv/*' -exec rm -rf {} +
