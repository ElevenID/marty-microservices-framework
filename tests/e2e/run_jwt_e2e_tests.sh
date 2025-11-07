#!/usr/bin/env bash
#
# JWT Authentication E2E Test Runner
# =================================
#
# This script runs both the full Kind-based E2E tests and the simplified
# integration E2E tests for the JWT authentication system.
#
# Usage:
#     ./run_jwt_e2e_tests.sh [--kind-only|--integration-only|--all]
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default to run all tests
RUN_KIND_TESTS=true
RUN_INTEGRATION_TESTS=true

# Parse command line arguments
case "${1:-}" in
    --kind-only)
        RUN_KIND_TESTS=true
        RUN_INTEGRATION_TESTS=false
        ;;
    --integration-only)
        RUN_KIND_TESTS=false
        RUN_INTEGRATION_TESTS=true
        ;;
    --all|"")
        RUN_KIND_TESTS=true
        RUN_INTEGRATION_TESTS=true
        ;;
    --help|-h)
        echo "Usage: $0 [--kind-only|--integration-only|--all]"
        echo ""
        echo "Options:"
        echo "  --kind-only         Run only Kind-based full E2E tests"
        echo "  --integration-only  Run only integration E2E tests"
        echo "  --all              Run all E2E tests (default)"
        echo "  --help, -h         Show this help message"
        exit 0
        ;;
    *)
        echo -e "${RED}Error: Unknown option '$1'${NC}"
        echo "Use --help for usage information"
        exit 1
        ;;
esac

echo -e "${BLUE}JWT Authentication E2E Test Runner${NC}"
echo "========================================"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check if we're in the right directory
if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
    echo -e "${RED}Error: Not in project root directory${NC}"
    exit 1
fi

# Check Python environment
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv not found. Please install uv package manager${NC}"
    exit 1
fi

# Check Kind if running Kind tests
if [[ "$RUN_KIND_TESTS" == "true" ]]; then
    if ! command -v kind &> /dev/null; then
        echo -e "${YELLOW}Warning: Kind not found. Installing Kind...${NC}"
        # Install Kind based on OS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &> /dev/null; then
                brew install kind
            else
                echo -e "${RED}Error: Homebrew not found. Please install Kind manually${NC}"
                exit 1
            fi
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
            chmod +x ./kind
            sudo mv ./kind /usr/local/bin/kind
        else
            echo -e "${RED}Error: Unsupported OS for automatic Kind installation${NC}"
            exit 1
        fi
    fi

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${YELLOW}Warning: kubectl not found. Please install kubectl${NC}"
        echo "You can install it from: https://kubernetes.io/docs/tasks/tools/"
    fi

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}Error: Docker not found. Please install Docker${NC}"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        echo -e "${RED}Error: Docker is not running. Please start Docker${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Prerequisites check completed${NC}"
echo ""

# Change to project root
cd "$PROJECT_ROOT"

# Install test dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
uv sync --group dev
echo -e "${GREEN}Dependencies installed${NC}"
echo ""

# Set Python path
export PYTHONPATH="$PROJECT_ROOT"

# Run tests
test_results=()

if [[ "$RUN_INTEGRATION_TESTS" == "true" ]]; then
    echo -e "${BLUE}Running Integration E2E Tests${NC}"
    echo "----------------------------------------"

    if uv run python tests/e2e/test_jwt_integration_e2e.py; then
        echo -e "${GREEN}✅ Integration E2E tests passed${NC}"
        test_results+=("integration:passed")
    else
        echo -e "${RED}❌ Integration E2E tests failed${NC}"
        test_results+=("integration:failed")
    fi
    echo ""
fi

if [[ "$RUN_KIND_TESTS" == "true" ]]; then
    echo -e "${BLUE}Running Kind-based E2E Tests${NC}"
    echo "----------------------------------------"
    echo -e "${YELLOW}Note: This will create a Kind cluster and may take several minutes${NC}"
    echo ""

    if timeout 1800 uv run python tests/e2e/test_jwt_auth_e2e.py; then
        echo -e "${GREEN}✅ Kind E2E tests passed${NC}"
        test_results+=("kind:passed")
    else
        echo -e "${RED}❌ Kind E2E tests failed or timed out${NC}"
        test_results+=("kind:failed")
    fi
    echo ""
fi

# Summary
echo -e "${BLUE}Test Results Summary${NC}"
echo "===================="

passed_count=0
failed_count=0

for result in "${test_results[@]}"; do
    test_name=$(echo "$result" | cut -d: -f1)
    test_status=$(echo "$result" | cut -d: -f2)

    if [[ "$test_status" == "passed" ]]; then
        echo -e "${GREEN}✅ $test_name E2E tests: PASSED${NC}"
        ((passed_count++))
    else
        echo -e "${RED}❌ $test_name E2E tests: FAILED${NC}"
        ((failed_count++))
    fi
done

total_count=$((passed_count + failed_count))
echo ""
echo "Total test suites: $total_count"
echo "Passed: $passed_count"
echo "Failed: $failed_count"

if [[ $failed_count -eq 0 ]]; then
    echo -e "${GREEN}🎉 All E2E tests passed!${NC}"
    echo "JWT authentication system is working correctly in all tested scenarios."
    exit 0
else
    echo -e "${RED}⚠️  Some E2E tests failed.${NC}"
    echo "Please review the test output above for details."
    exit 1
fi
