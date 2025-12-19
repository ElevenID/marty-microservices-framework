#!/bin/bash

# Marty Microservices Framework Setup Script
# This script sets up a complete development environment for the framework

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up Marty Microservices Framework${NC}"
echo "================================================================="

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed. Please install it first:"
    echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

print_status "uv is available"

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_version="3.10"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
    print_error "Python 3.10+ is required. Found: $python_version"
    exit 1
fi

print_status "Python $python_version is compatible"

# Install framework dependencies for template processing and type checking
echo "📦 Installing framework dependencies..."
cd "$FRAMEWORK_ROOT"

# Use UV to install the framework in development mode
uv sync --group dev

print_status "Framework dependencies installed"

# Create virtual environment if in project template
if [ -f "$FRAMEWORK_ROOT/microservice_project_template/pyproject.toml" ]; then
    echo "🏗️ Setting up project template environment..."
    cd "$FRAMEWORK_ROOT/microservice_project_template"

    if [ ! -d ".venv" ]; then
        uv venv
    fi

    # Install dependencies
    uv sync --group dev

    print_status "Project template environment ready"
fi

# Make scripts executable
chmod +x "$SCRIPT_DIR"/*.py
chmod +x "$SCRIPT_DIR"/*.sh

print_status "Scripts are executable"

# Validate templates
echo "🔍 Validating templates..."
cd "$FRAMEWORK_ROOT"
python3 scripts/validate_templates.py

if [ $? -eq 0 ]; then
    print_status "Template validation passed"
else
    print_error "Template validation failed"
    exit 1
fi

# Run framework tests
echo "🧪 Testing framework functionality..."
python3 scripts/test_framework.py

if [ $? -eq 0 ]; then
    print_status "Framework tests passed"
else
    print_error "Framework tests failed"
    exit 1
fi

# Run type checking
echo "🔍 Running type checking..."
python3 -m mypy scripts/ --config-file mypy.ini

if [ $? -eq 0 ]; then
    print_status "Type checking passed"
else
    print_warning "Type checking found issues (see output above)"
fi

echo ""
echo -e "${GREEN}🎉 Framework setup complete!${NC}"
echo ""
echo "📖 Quick Start:"
echo "  1. Use the project template:"
echo "     cp -r microservice_project_template my-new-project"
echo "     cd my-new-project"
echo "     uv sync --group dev"
echo ""
echo "  2. Validate templates:"
echo "     python3 scripts/validate_templates.py"
echo ""
echo "  4. Run framework tests:"
echo "     python3 scripts/test_framework.py"
echo ""
echo "  5. Run type checking:"
echo "     python3 -m mypy scripts/ --config-file mypy.ini"
echo ""
echo "📚 Documentation: See README.md for detailed usage"
