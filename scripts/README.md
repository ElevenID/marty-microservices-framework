# Scripts Directory

This directory contains utility scripts for development, testing, and maintenance of the Marty Microservices Framework.

## Development Scripts

- **setup_dev.py** - Development environment setup script
- **setup_framework.sh** - Framework initialization and setup
- **show_script_commands.sh** - Lists all available script commands

## Testing Scripts

- **test_runner.py** - Main test runner with validation reports
- **real_e2e_test_runner.py** - End-to-end test runner for comprehensive testing
- **test_framework.py** - Framework component testing
- **run_kind_playwright_e2e.sh** - Kind + Playwright E2E testing setup

## Validation Scripts

- **validate.sh** - General validation checks
- **validate_observability.py** - Observability system validation
- **validate_templates.py** - Template validation
- **verify_security_framework.py** - Security framework verification
- **check_dependencies.py** - Dependency checking and validation
- **check_import_order.py** - Import placement validation (pre-commit hook)

## Generation Scripts

- **helm_to_kustomize_converter.py** - Migration tool for Helm to Kustomize

## Infrastructure Scripts

- **setup-cluster.sh** - Kubernetes cluster setup
- **cleanup.sh** - Clean up development artifacts

## Usage

Most scripts can be run directly from the project root:

```bash
# Run tests
python scripts/test_runner.py

# Setup development environment
python scripts/setup_dev.py

# Validate framework
./scripts/validate.sh
```

For scripts that require specific environments or dependencies, refer to the script's documentation header for requirements and usage instructions.
