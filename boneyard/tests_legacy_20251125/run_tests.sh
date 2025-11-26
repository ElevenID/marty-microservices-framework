#!/bin/bash

# MMF Comprehensive Test Runner
# Orchestrates all types of tests in the proper order

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test configuration
WORKSPACE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$WORKSPACE_ROOT/tests"

# Test execution flags
RUN_UNIT=true
RUN_INTEGRATION=true
RUN_CONTRACT=true
RUN_E2E=true
RUN_PERFORMANCE=false
RUN_SECURITY=false
RUN_CHAOS=false
FAIL_FAST=false
VERBOSE=false
CLEANUP=true

# Help function
show_help() {
    cat << EOF
MMF Comprehensive Test Runner

Usage: $0 [OPTIONS]

OPTIONS:
    --unit              Run unit tests only
    --integration       Run integration tests only
    --contract          Run contract tests only
    --e2e               Run e2e tests only
    --performance       Include performance tests
    --security          Include security tests
    --chaos             Include chaos engineering tests
    --all               Run all test types
    --fail-fast         Stop on first test failure
    --no-cleanup        Skip cleanup after tests
    --verbose           Verbose output
    -h, --help          Show this help message

TEST CATEGORIES:
    unit                Fast, isolated component tests
    integration         Component interaction tests
    contract            API contract and schema validation
    e2e                 End-to-end system tests
    performance         Load testing and benchmarks
    security            Security vulnerability tests
    chaos               Chaos engineering and resilience tests

EXAMPLES:
    $0                          # Run core test suite (unit + integration + contract + e2e)
    $0 --unit --integration     # Run only unit and integration tests
    $0 --all                    # Run all test categories
    $0 --e2e --verbose          # Run e2e tests with verbose output
    $0 --performance --security # Run performance and security tests

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit)
                RUN_UNIT=true
                RUN_INTEGRATION=false
                RUN_CONTRACT=false
                RUN_E2E=false
                shift
                ;;
            --integration)
                RUN_INTEGRATION=true
                RUN_UNIT=false
                RUN_CONTRACT=false
                RUN_E2E=false
                shift
                ;;
            --contract)
                RUN_CONTRACT=true
                RUN_UNIT=false
                RUN_INTEGRATION=false
                RUN_E2E=false
                shift
                ;;
            --e2e)
                RUN_E2E=true
                RUN_UNIT=false
                RUN_INTEGRATION=false
                RUN_CONTRACT=false
                shift
                ;;
            --performance)
                RUN_PERFORMANCE=true
                shift
                ;;
            --security)
                RUN_SECURITY=true
                shift
                ;;
            --chaos)
                RUN_CHAOS=true
                shift
                ;;
            --all)
                RUN_UNIT=true
                RUN_INTEGRATION=true
                RUN_CONTRACT=true
                RUN_E2E=true
                RUN_PERFORMANCE=true
                RUN_SECURITY=true
                RUN_CHAOS=true
                shift
                ;;
            --fail-fast)
                FAIL_FAST=true
                shift
                ;;
            --no-cleanup)
                CLEANUP=false
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Logging functions
log_header() {
    echo -e "\n${CYAN}===============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}===============================================${NC}"
}

log_section() {
    echo -e "\n${BLUE}🔍 $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_info() {
    echo -e "${PURPLE}ℹ️  $1${NC}"
}

# Test execution functions
run_unit_tests() {
    log_section "Running Unit Tests"

    local cmd="uv run pytest tests/unit/ -v --tb=short"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    if eval "$cmd"; then
        log_success "Unit tests passed"
        return 0
    else
        log_error "Unit tests failed"
        return 1
    fi
}

run_integration_tests() {
    log_section "Running Integration Tests"

    local cmd="uv run pytest tests/integration/ -v --tb=short"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    if eval "$cmd"; then
        log_success "Integration tests passed"
        return 0
    else
        log_error "Integration tests failed"
        return 1
    fi
}

run_contract_tests() {
    log_section "Running Contract Tests"

    local cmd="uv run pytest tests/contract/ -v --tb=short -m contract"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    if eval "$cmd"; then
        log_success "Contract tests passed"
        return 0
    else
        log_error "Contract tests failed"
        return 1
    fi
}

run_e2e_tests() {
    log_section "Running End-to-End Tests"

    log_info "Running comprehensive KIND-based e2e tests..."

    if "$TEST_DIR/e2e/kind/automated/e2e-test.sh"; then
        log_success "E2E tests passed"
        return 0
    else
        log_error "E2E tests failed"
        return 1
    fi
}

run_performance_tests() {
    log_section "Running Performance Tests"

    local cmd="uv run pytest tests/performance/ -v --tb=short -m performance"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    echo -e "${YELLOW}⚠️  Performance tests are experimental${NC}"

    if eval "$cmd"; then
        log_success "Performance tests passed"
        return 0
    else
        log_error "Performance tests failed"
        return 1
    fi
}

run_security_tests() {
    log_section "Running Security Tests"

    local cmd="uv run pytest tests/security/ -v --tb=short -m security"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    echo -e "${YELLOW}⚠️  Security tests are experimental${NC}"

    if eval "$cmd"; then
        log_success "Security tests passed"
        return 0
    else
        log_error "Security tests failed"
        return 1
    fi
}

run_chaos_tests() {
    log_section "Running Chaos Engineering Tests"

    local cmd="uv run pytest tests/chaos/ -v --tb=short -m chaos"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    echo -e "${YELLOW}⚠️  Chaos tests are experimental and may affect system stability${NC}"

    if eval "$cmd"; then
        log_success "Chaos tests passed"
        return 0
    else
        log_error "Chaos tests failed"
        return 1
    fi
}

# Cleanup function
cleanup_resources() {
    if [ "$CLEANUP" = true ]; then
        log_section "Cleaning up test resources"

        # Clean up KIND clusters
        if command -v kind >/dev/null 2>&1; then
            for cluster in $(kind get clusters 2>/dev/null | grep -E "(test|e2e)" || true); do
                echo "Cleaning up KIND cluster: $cluster"
                kind delete cluster --name "$cluster" >/dev/null 2>&1 || true
            done
        fi

        # Clean up Docker test images
        if command -v docker >/dev/null 2>&1; then
            for image in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(test|e2e)" || true); do
                echo "Cleaning up Docker image: $image"
                docker rmi "$image" >/dev/null 2>&1 || true
            done
        fi

        log_success "Cleanup completed"
    fi
}

# Generate test summary
generate_summary() {
    log_header "Test Execution Summary"

    local total_tests=0
    local passed_tests=0
    local failed_tests=0

    echo -e "\n${BLUE}Test Results:${NC}"
    echo "----------------------------------------"

    # This is a simplified summary - in a production version you'd track individual results
    echo -e "${GREEN}✅ Tests completed${NC}"
    echo "See individual test outputs above for detailed results"
    echo "----------------------------------------"
}

# Main execution function
main() {
    parse_args "$@"

    log_header "MMF Comprehensive Test Suite"
    log_info "Timestamp: $(date)"
    log_info "Workspace: $WORKSPACE_ROOT"
    log_info "Test Directory: $TEST_DIR"

    # Set up environment
    cd "$WORKSPACE_ROOT"

    local overall_success=true

    # Execute tests in order
    if [ "$RUN_UNIT" = true ]; then
        if ! run_unit_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_INTEGRATION" = true ]; then
        if ! run_integration_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_CONTRACT" = true ]; then
        if ! run_contract_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_E2E" = true ]; then
        if ! run_e2e_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_PERFORMANCE" = true ]; then
        if ! run_performance_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_SECURITY" = true ]; then
        if ! run_security_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    if [ "$RUN_CHAOS" = true ]; then
        if ! run_chaos_tests; then
            overall_success=false
            if [ "$FAIL_FAST" = true ]; then
                cleanup_resources
                exit 1
            fi
        fi
    fi

    # Cleanup
    cleanup_resources

    # Generate summary
    generate_summary

    # Exit with appropriate code
    if [ "$overall_success" = true ]; then
        echo -e "\n${GREEN}🎉 All selected tests passed!${NC}"
        exit 0
    else
        echo -e "\n${RED}💥 Some tests failed.${NC}"
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
            --integration)
                RUN_INTEGRATION=true
                RUN_UNIT=false
                RUN_CONTRACT=false
                RUN_E2E=false
                shift
                ;;
            --contract)
                RUN_CONTRACT=true
                RUN_UNIT=false
                RUN_INTEGRATION=false
                RUN_E2E=false
                shift
                ;;
            --e2e)
                RUN_E2E=true
                RUN_UNIT=false
                RUN_INTEGRATION=false
                RUN_CONTRACT=false
                shift
                ;;
            --performance)
                RUN_PERFORMANCE=true
                shift
                ;;
            --security)
                RUN_SECURITY=true
                shift
                ;;
            --chaos)
                RUN_CHAOS=true
                shift
                ;;
            --all)
                RUN_UNIT=true
                RUN_INTEGRATION=true
                RUN_CONTRACT=true
                RUN_E2E=true
                RUN_PERFORMANCE=true
                RUN_SECURITY=true
                RUN_CHAOS=true
                shift
                ;;
            --parallel)
                PARALLEL_EXECUTION=true
                shift
                ;;
            --fail-fast)
                FAIL_FAST=true
                shift
                ;;
            --no-cleanup)
                CLEANUP=false
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Logging functions
log_header() {
    echo -e "\n${CYAN}===============================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}===============================================${NC}"
}

log_section() {
    echo -e "\n${BLUE}🔍 $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_info() {
    echo -e "${PURPLE}ℹ️  $1${NC}"
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}[VERBOSE]${NC} $1"
    fi
}

# Test execution functions
run_unit_tests() {
    log_section "Running Unit Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/unit/ -v --tb=short"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"

    if eval "$cmd"; then
        unit_result="PASS"
        log_success "Unit tests passed"
    else
        unit_result="FAIL"
        log_error "Unit tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time
    end_time=$(date +%s)
    unit_duration=$((end_time - start_time))
}

run_integration_tests() {
    log_section "Running Integration Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/integration/ -v --tb=short"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"

    if eval "$cmd"; then
        test_results[integration]="PASS"
        log_success "Integration tests passed"
    else
        test_results[integration]="FAIL"
        log_error "Integration tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[integration]=$((end_time - start_time))
}

run_contract_tests() {
    log_section "Running Contract Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/contract/ -v --tb=short -m contract"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"

    if eval "$cmd"; then
        test_results[contract]="PASS"
        log_success "Contract tests passed"
    else
        test_results[contract]="FAIL"
        log_error "Contract tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[contract]=$((end_time - start_time))
}

run_e2e_tests() {
    log_section "Running End-to-End Tests"
    local start_time=$(date +%s)

    log_info "Running comprehensive KIND-based e2e tests..."

    if "$TEST_DIR/e2e/kind/automated/e2e-test.sh"; then
        test_results[e2e]="PASS"
        log_success "E2E tests passed"
    else
        test_results[e2e]="FAIL"
        log_error "E2E tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[e2e]=$((end_time - start_time))
}

run_performance_tests() {
    log_section "Running Performance Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/performance/ -v --tb=short -m performance"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"
    log_warning "Performance tests are experimental"

    if eval "$cmd"; then
        test_results[performance]="PASS"
        log_success "Performance tests passed"
    else
        test_results[performance]="FAIL"
        log_error "Performance tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[performance]=$((end_time - start_time))
}

run_security_tests() {
    log_section "Running Security Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/security/ -v --tb=short -m security"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"
    log_warning "Security tests are experimental"

    if eval "$cmd"; then
        test_results[security]="PASS"
        log_success "Security tests passed"
    else
        test_results[security]="FAIL"
        log_error "Security tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[security]=$((end_time - start_time))
}

run_chaos_tests() {
    log_section "Running Chaos Engineering Tests"
    local start_time=$(date +%s)

    local cmd="uv run pytest tests/chaos/ -v --tb=short -m chaos"
    if [ "$FAIL_FAST" = true ]; then
        cmd+=" -x"
    fi
    if [ "$VERBOSE" = true ]; then
        cmd+=" -s"
    fi

    log_verbose "Executing: $cmd"
    log_warning "Chaos tests are experimental and may affect system stability"

    if eval "$cmd"; then
        test_results[chaos]="PASS"
        log_success "Chaos tests passed"
    else
        test_results[chaos]="FAIL"
        log_error "Chaos tests failed"
        if [ "$FAIL_FAST" = true ]; then
            exit 1
        fi
    fi

    local end_time=$(date +%s)
    test_durations[chaos]=$((end_time - start_time))
}

# Cleanup function
cleanup_resources() {
    if [ "$CLEANUP" = true ]; then
        log_section "Cleaning up test resources"

        # Clean up KIND clusters
        if command -v kind >/dev/null 2>&1; then
            for cluster in $(kind get clusters 2>/dev/null | grep -E "(test|e2e)" || true); do
                log_verbose "Cleaning up KIND cluster: $cluster"
                kind delete cluster --name "$cluster" >/dev/null 2>&1 || true
            done
        fi

        # Clean up Docker test images
        if command -v docker >/dev/null 2>&1; then
            for image in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep -E "(test|e2e)" || true); do
                log_verbose "Cleaning up Docker image: $image"
                docker rmi "$image" >/dev/null 2>&1 || true
            done
        fi

        log_success "Cleanup completed"
    fi
}

# Generate test summary
generate_summary() {
    log_header "Test Execution Summary"

    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    local total_duration=0

    echo -e "\n${BLUE}Test Results:${NC}"
    echo "----------------------------------------"

    for test_type in unit integration contract e2e performance security chaos; do
        if [[ -n "${test_results[$test_type]}" ]]; then
            local status="${test_results[$test_type]}"
            local duration="${test_durations[$test_type]:-0}"
            total_duration=$((total_duration + duration))
            total_tests=$((total_tests + 1))

            if [ "$status" = "PASS" ]; then
                echo -e "${GREEN}✅ ${test_type}: PASSED${NC} (${duration}s)"
                passed_tests=$((passed_tests + 1))
            else
                echo -e "${RED}❌ ${test_type}: FAILED${NC} (${duration}s)"
                failed_tests=$((failed_tests + 1))
            fi
        fi
    done

    echo "----------------------------------------"
    echo -e "Total Tests: $total_tests"
    echo -e "${GREEN}Passed: $passed_tests${NC}"
    echo -e "${RED}Failed: $failed_tests${NC}"
    echo -e "Total Duration: ${total_duration}s"

    if [ $failed_tests -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All tests passed!${NC}"
        return 0
    else
        echo -e "\n${RED}💥 Some tests failed.${NC}"
        return 1
    fi
}

# Main execution function
main() {
    parse_args "$@"

    log_header "MMF Comprehensive Test Suite"
    log_info "Timestamp: $(date)"
    log_info "Workspace: $WORKSPACE_ROOT"
    log_info "Test Directory: $TEST_DIR"

    # Create reports directory
    mkdir -p "$REPORTS_DIR"

    # Set up environment
    cd "$WORKSPACE_ROOT"

    # Execute tests in order
    if [ "$RUN_UNIT" = true ]; then
        run_unit_tests
    fi

    if [ "$RUN_INTEGRATION" = true ]; then
        run_integration_tests
    fi

    if [ "$RUN_CONTRACT" = true ]; then
        run_contract_tests
    fi

    if [ "$RUN_E2E" = true ]; then
        run_e2e_tests
    fi

    if [ "$RUN_PERFORMANCE" = true ]; then
        run_performance_tests
    fi

    if [ "$RUN_SECURITY" = true ]; then
        run_security_tests
    fi

    if [ "$RUN_CHAOS" = true ]; then
        run_chaos_tests
    fi

    # Cleanup
    cleanup_resources

    # Generate summary and exit with appropriate code
    if generate_summary; then
        exit 0
    else
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
