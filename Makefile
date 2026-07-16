# Marty Microservices Framework - Makefile
# Convenient commands for framework development and usage

.PHONY: help setup install test dev setup-dev generate new clean docs scripts

# Default target
help: ## Show this help message
	@echo "Marty Microservices Framework"
	@echo "=============================="
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ==============================================================================
# Setup & Installation
# ==============================================================================

setup: ## Complete setup: install deps, hooks, and validate
	@echo "🚀 Setting up Marty Microservices Framework..."
	@uv sync --group dev
	@uv run playwright install chromium
	@uv run pre-commit install
	@python3 scripts/validate_templates.py
	@echo "✅ Setup complete!"

install: ## Install framework dependencies
	@echo "📦 Installing framework dependencies..."
	@uv sync --group dev
	@echo "✅ Dependencies installed!"

# ==============================================================================
# Testing
# ==============================================================================

test: ## Run all tests (unit + integration + contract + e2e)
	@echo "🧪 Running comprehensive test suite..."
	@uv run pytest mmf/tests -v

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	@uv run pytest mmf/tests/unit -v

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	@uv run pytest mmf/tests/integration -v

test-contract: ## Run contract tests only
	@echo "🧪 Running contract tests..."
	@uv run pytest mmf/tests/contract -v

test-e2e: ## Run comprehensive end-to-end tests with KIND
	@echo "🧪 Running comprehensive E2E tests with KIND..."
	@./tests/e2e/kind/automated/e2e-test.sh

test-performance: ## Run performance tests
	@echo "🚀 Running performance tests..."
	@uv run pytest tests/performance/ -v -m performance

test-security: ## Run security tests
	@echo "🔒 Running security tests..."
	@uv run pytest tests/security/ -v -m security

test-chaos: ## Run chaos engineering tests
	@echo "💥 Running chaos engineering tests..."
	@uv run pytest tests/chaos/ -v -m chaos

test-all: ## Run all test categories including experimental
	@echo "🧪 Running all test categories..."
	@./tests/run_tests.sh --all

test-core: ## Run core test suite (unit + integration + contract + e2e)
	@echo "🧪 Running core test suite..."
	@./tests/run_tests.sh --unit --integration --contract --e2e

test-e2e-quick: ## Run quick E2E tests for development
	@echo "⚡ Running quick E2E tests..."
	@./tests/e2e/kind/test-e2e.sh -m quick

test-e2e-smoke: ## Run smoke tests only
	@echo "💨 Running smoke tests..."
	@./tests/e2e/kind/test-e2e.sh -m smoke

test-e2e-dev: ## Run E2E tests and keep cluster for debugging
	@echo "🔧 Running E2E tests with debug cluster..."
	@./tests/e2e/kind/test-e2e.sh -m quick -k -v

test-e2e-clean: ## Clean up all E2E test resources
	@echo "🧹 Cleaning up E2E test resources..."
	@./tests/e2e/kind/test-e2e.sh -m clean

test-kind: ## Run Kind-based E2E tests only (legacy pytest)
	@echo "🎭 Running legacy Kind + Playwright E2E tests..."
	@uv run pytest tests/e2e/test_kind_playwright_e2e.py tests/e2e/simple_kind_playwright_test.py -v

test-coverage: ## Run all tests with coverage report
	@echo "🧪 Running tests with coverage..."
	@uv run pytest --cov=src --cov-report=html --cov-report=term

test-quick: ## Run tests with fail-fast mode
	@echo "🧪 Running quick tests (fail-fast)..."
	@uv run pytest -x --tb=short

# ==============================================================================
# Automated Quality Checks (Converted from Legacy Scripts)
# ==============================================================================

test-code-quality: ## Run automated code quality tests
	@echo "🔍 Running automated code quality tests..."
	@uv run pytest tests/unit/test_code_quality.py -v

test-dependencies: ## Run automated dependency validation tests
	@echo "📦 Running automated dependency validation tests..."
	@uv run pytest tests/unit/test_dependency_checks.py -v

test-observability: ## Run automated observability validation tests
	@echo "📊 Running automated observability validation tests..."
	@uv run pytest tests/unit/test_observability_validation.py -v

test-framework: ## Run automated framework functionality tests
	@echo "🏗️ Running automated framework functionality tests..."
	@uv run pytest tests/unit/test_framework_functionality.py -v

test-security: ## Run automated security validation tests
	@echo "🔒 Running automated security validation tests..."
	@uv run pytest tests/unit/test_security_validation.py -v

test-all-quality: ## Run all automated quality tests
	@echo "✨ Running all automated quality tests..."
	@uv run pytest tests/unit/test_code_quality.py tests/unit/test_dependency_checks.py tests/unit/test_observability_validation.py tests/unit/test_framework_functionality.py tests/unit/test_security_validation.py -v

validate: ## Run all validation checks (legacy scripts + automated tests)
	@echo "🔍 Running comprehensive validation..."
	@$(MAKE) test-all-quality
	@python3 scripts/validate_templates.py
	@python3 scripts/validate_observability.py

# ==============================================================================
# Development
# ==============================================================================

dev: ## Setup complete development environment
	@echo "🔧 Setting up development environment..."
	@$(MAKE) setup
	@echo "🎉 Development environment ready!"
	@echo "💡 Try: make test, make generate, make new"

setup-dev: ## Run comprehensive development setup script
	@echo "🚀 Running comprehensive development setup..."
	@python3 scripts/setup_dev.py

check: ## Run all code quality checks
	@echo "🔍 Running code quality checks..."
	@uv run ruff check .
	@uv run ruff format --check .
	@python3 -m mypy scripts/ --config-file mypy.ini
	@python3 scripts/validate_templates.py
	@echo "✅ All checks passed!"

fix: ## Fix code formatting and linting issues
	@echo "🔧 Fixing code issues..."
	@uv run ruff check --fix .
	@uv run ruff format .
	@echo "✅ Code formatting fixed!"

security: ## Run security checks
	@echo "🔒 Running security checks..."
	@uv run bandit -r src/

# ==============================================================================
# Local Development with Kind
# ==============================================================================

kind-up: ## Start local Kubernetes cluster with observability stack
	@echo "🚀 Starting local development environment with Kind..."
	@echo "📋 This will create:"
	@echo "   • Kind Kubernetes cluster"
	@echo "   • Prometheus (metrics) - http://localhost:9090"
	@echo "   • Grafana (dashboards) - http://localhost:3000"
	@echo "   • Complete observability stack"
	@echo ""
	@if ! command -v kind >/dev/null 2>&1; then \
		echo "❌ Kind not found. Installing..."; \
		brew install kind; \
	fi
	@if ! command -v kubectl >/dev/null 2>&1; then \
		echo "❌ kubectl not found. Installing..."; \
		brew install kubectl; \
	fi
	@if ! command -v helm >/dev/null 2>&1; then \
		echo "❌ Helm not found. Installing..."; \
		brew install helm; \
	fi
	@echo "🏗️ Creating Kind cluster..."
	@kind create cluster --name microservices-framework --config ops/k8s/kind-cluster-config.yaml || true
	@echo "⏳ Waiting for cluster to be ready..."
	@kubectl wait --for=condition=Ready nodes --all --timeout=300s
	@echo "📊 Deploying observability stack..."
	@kubectl apply -f ops/k8s/observability/
	@echo "⏳ Waiting for observability pods to be ready..."
	@kubectl wait --for=condition=Ready pods -l app=prometheus -n observability --timeout=300s || true
	@kubectl wait --for=condition=Ready pods -l app=grafana -n observability --timeout=300s || true
	@echo "🌐 Setting up port forwarding..."
	@(kubectl port-forward -n observability svc/prometheus 9090:9090 > /dev/null 2>&1 &)
	@(kubectl port-forward -n observability svc/grafana 3000:3000 > /dev/null 2>&1 &)
	@sleep 3
	@echo ""
	@echo "✅ Local development environment is ready!"
	@echo ""
	@echo "🎯 Access your UIs:"
	@echo "   📊 Prometheus: http://localhost:9090"
	@echo "   📈 Grafana:    http://localhost:3000 (admin/admin)"
	@echo ""
	@echo "🛠️ Development commands:"
	@echo "   make kind-status    # Check cluster status"
	@echo "   make kind-logs      # View logs"
	@echo "   make kind-down      # Stop cluster"

kind-status: ## Check Kind cluster and services status
	@echo "📊 Kind Cluster Status"
	@echo "====================="
	@echo ""
	@if kind get clusters | grep -q microservices-framework; then \
		echo "✅ Kind cluster: microservices-framework"; \
		kubectl cluster-info --context kind-microservices-framework; \
		echo ""; \
		echo "📦 Observability Pods:"; \
		kubectl get pods -n observability; \
		echo ""; \
		echo "🌐 Services:"; \
		kubectl get svc -n observability; \
	else \
		echo "❌ Kind cluster not running"; \
		echo "💡 Run: make kind-up"; \
	fi

kind-logs: ## View logs from observability services
	@echo "📋 Observability Logs"
	@echo "===================="
	@echo ""
	@echo "🔍 Prometheus logs:"
	@kubectl logs -n observability -l app=prometheus --tail=20
	@echo ""
	@echo "🔍 Grafana logs:"
	@kubectl logs -n observability -l app=grafana --tail=20

kind-restart: ## Restart Kind cluster and observability stack
	@echo "🔄 Restarting Kind cluster..."
	@$(MAKE) kind-down
	@sleep 2
	@$(MAKE) kind-up

kind-down: ## Stop and remove Kind cluster
	@echo "🛑 Stopping Kind cluster..."
	@pkill -f "kubectl port-forward" || true
	@kind delete cluster --name microservices-framework || true
	@echo "✅ Kind cluster stopped"

# ==============================================================================
# Code Generation
# ==============================================================================

generate: ## Generate a service (make generate TYPE=fastapi NAME=my-service)
	@if [ -z "$(TYPE)" ] || [ -z "$(NAME)" ]; then \
		echo "❌ Error: TYPE and NAME parameters are required"; \
		echo "Usage: make generate TYPE=fastapi NAME=my-service"; \
		echo "Available types: fastapi, grpc, hybrid, auth"; \
		exit 1; \
	fi
	@echo "🏗️ Generating $(TYPE) service: $(NAME)"
	@uv run python3 scripts/generate_service.py $(TYPE) $(NAME) --description "$(NAME) service"

new: ## Create a new project (make new NAME=my-project)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make new NAME=my-project"; \
		exit 1; \
	fi
	@if [ -d "$(NAME)" ]; then \
		echo "❌ Error: Directory $(NAME) already exists"; \
		exit 1; \
	fi
	@echo "�️ Creating new project: $(NAME)"
	@cp -r microservice_project_template $(NAME)
	@echo "✅ Project created: ./$(NAME)"
	@echo "🚀 Next: cd $(NAME) && make dev"

# ==============================================================================
# Utilities
# ==============================================================================

clean: ## Clean build artifacts and cache files
	@echo "🧹 Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ htmlcov/ .coverage
	@rm -f test_results.json *_test_demo_results.json *_test_results.json coverage.xml
	@echo "✅ Cleanup complete!"

docs: ## Show documentation and usage examples
	@echo "📚 Marty Microservices Framework"
	@echo "================================="
	@echo ""
	@echo "📖 Quick Start:"
	@echo "   make setup                              # Complete setup"
	@echo "   make test                               # Run all tests"
	@echo "   make generate TYPE=fastapi NAME=api     # Generate service"
	@echo "   make new NAME=my-project                # Create new project"
	@echo ""
	@echo "🧪 Testing:"
	@echo "   make test-unit                          # Unit tests only"
	@echo "   make test-integration                   # Integration tests"
	@echo "   make test-e2e                          # All E2E tests"
	@echo "   make test-kind                          # Kind E2E tests only"
	@echo "   make test-coverage                      # With coverage"
	@echo ""
	@echo "🔧 Development:"
	@echo "   make dev                                # Setup dev environment"
	@echo "   make check                              # Run all quality checks"
	@echo "   make fix                                # Fix formatting/linting"
	@echo ""
	@echo "🏗️ Generation (TYPE: fastapi, grpc, hybrid, auth):"
	@echo "   make generate TYPE=fastapi NAME=user-api"
	@echo "   make generate TYPE=grpc NAME=data-processor"
	@echo "   make new NAME=my-awesome-project"
	@echo ""
	@echo "📜 Scripts:"
	@echo "   make scripts                            # Show available scripts"

scripts: ## Show available development scripts
	@echo "📜 Development Scripts"
	@echo "====================="
	@echo ""
	@echo "📖 For detailed descriptions, see: scripts/README.md"
	@echo ""
	@echo "🔧 Development:"
	@echo "   python3 scripts/setup_dev.py           # Development environment setup"
	@echo "   python3 scripts/test_framework.py      # Framework component testing"
	@echo ""
	@echo "🧪 Testing:"
	@echo "   python3 scripts/test_runner.py         # Main test runner with reports"
	@echo "   python3 scripts/real_e2e_test_runner.py # E2E test runner"
	@echo "   ./scripts/run_kind_playwright_e2e.sh   # Kind + Playwright E2E"
	@echo ""
	@echo "✅ Validation:"
	@echo "   ./scripts/validate.sh                  # General validation"
	@echo "   python3 scripts/validate_templates.py  # Template validation"
	@echo "   python3 scripts/validate_observability.py # Observability validation"
	@echo "   python3 scripts/verify_security_framework.py # Security verification"
	@echo ""
	@echo "🏗️ Generation:"
	@echo "   python3 scripts/generate_service.py    # Service generation utility"
	@echo ""
	@echo "🛠️ Utilities:"
	@echo "   python3 scripts/check_dependencies.py  # Dependency checking"
	@echo "   ./scripts/cleanup.sh                   # Clean up artifacts"
	@echo "   ./scripts/show_script_commands.sh      # Show script commands"

status: ## Show framework status
	@echo "📊 Framework Status"
	@echo "=================="
	@echo ""
	@if command -v uv >/dev/null 2>&1; then echo "✅ UV installed"; else echo "❌ UV missing"; fi
	@if [ -d ".venv" ]; then echo "✅ Virtual environment"; else echo "❌ No virtual environment"; fi
	@if [ -f "scripts/validate_templates.py" ]; then echo "✅ Scripts available"; else echo "❌ Scripts missing"; fi
	@if [ -d "microservice_project_template" ]; then echo "✅ Project template"; else echo "❌ Template missing"; fi

# ==============================================================================
# CI/CD
# ==============================================================================

ci: ## Run CI/CD pipeline (validate, test, check)
	@echo "🚀 Running CI/CD pipeline..."
	@$(MAKE) test-all-quality
	@python3 scripts/validate_templates.py
	@uv run pytest -m "unit or integration" --tb=short
	@uv run ruff check .
	@python3 -m mypy scripts/ --config-file mypy.ini
	@echo "✅ CI/CD pipeline completed!"

# ==============================================================================
# Petstore Demo
# ==============================================================================

petstore-compose-up: ## Start Petstore demo with Docker Compose
	@echo "🚀 Starting Petstore demo with Docker Compose..."
	@cd examples/petstore_domain && docker compose up --build -d
	@echo "✅ Petstore demo running!"
	@echo "  - Pet Service: http://localhost:8000"
	@echo "  - Store Service: http://localhost:8001"
	@echo "  - Delivery Board Service: http://localhost:8002"
	@echo "Observability:"
	@echo "  - Log Viewer (Dozzle): http://localhost:8888"
	@echo "  - Jaeger (Tracing):    http://localhost:16686"
	@echo "  - Prometheus (Metrics): http://localhost:9090"
	@echo "  - Grafana (Dashboards): http://localhost:3000"

petstore-compose-down: ## Stop Petstore demo
	@echo "🛑 Stopping Petstore demo..."
	@cd examples/petstore_domain && docker compose down
	@echo "✅ Petstore demo stopped!"


petstore-demo-run: ## Run the Petstore demo driver scenario
	@echo "🚗 Running Petstore demo scenario..."
	@uv run python examples/petstore_domain/demo_driver.py
