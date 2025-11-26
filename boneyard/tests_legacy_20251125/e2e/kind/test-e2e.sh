#!/bin/bash

# MMF Local E2E Test Runner
# This script provides different testing modes for local development

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
MODE="full"
CLUSTER_NAME="mmf-local-test"
KEEP_CLUSTER=false
VERBOSE=false

# Help function
show_help() {
    cat << EOF
MMF Local E2E Test Runner

Usage: $0 [OPTIONS]

OPTIONS:
    -m, --mode MODE         Test mode: full, quick, smoke (default: full)
    -c, --cluster NAME      KIND cluster name (default: mmf-local-test)
    -k, --keep-cluster      Keep the cluster after tests (default: false)
    -v, --verbose           Verbose output (default: false)
    -h, --help              Show this help message

MODES:
    full    - Complete E2E test suite (default)
    quick   - Rapid smoke tests for development
    smoke   - Basic health checks only
    clean   - Clean up existing clusters and images

EXAMPLES:
    $0                      # Run full test suite
    $0 -m quick -k          # Quick tests, keep cluster
    $0 -m smoke -v          # Smoke tests with verbose output
    $0 -m clean             # Clean up resources

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -c|--cluster)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        -k|--keep-cluster)
            KEEP_CLUSTER=true
            shift
            ;;
        -v|--verbose)
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

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_verbose() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}[VERBOSE]${NC} $1"
    fi
}

# Clean mode
if [ "$MODE" = "clean" ]; then
    log_info "Cleaning up MMF test resources..."

    # Clean up all MMF test clusters
    for cluster in $(kind get clusters 2>/dev/null | grep -E "(mmf-|e2e-test)" || true); do
        log_info "Deleting cluster: $cluster"
        kind delete cluster --name "$cluster"
    done

    # Clean up test images
    for image in $(docker images --format "table {{.Repository}}:{{.Tag}}" | grep -E "(mmf/.*:(test|e2e)" || true); do
        log_info "Removing image: $image"
        docker rmi "$image" || true
    done

    log_success "Cleanup completed"
    exit 0
fi

# Validate mode
case $MODE in
    full|quick|smoke)
        ;;
    *)
        log_error "Invalid mode: $MODE"
        show_help
        exit 1
        ;;
esac

log_info "Starting MMF E2E tests in '$MODE' mode"
log_info "Cluster: $CLUSTER_NAME"
log_info "Keep cluster: $KEEP_CLUSTER"

# Check prerequisites
log_info "Checking prerequisites..."
command -v kind >/dev/null 2>&1 || { log_error "KIND is not installed"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { log_error "kubectl is not installed"; exit 1; }
command -v docker >/dev/null 2>&1 || { log_error "Docker is not installed"; exit 1; }

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^$CLUSTER_NAME$"; then
    log_warning "Cluster '$CLUSTER_NAME' already exists"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deleting existing cluster..."
        kind delete cluster --name "$CLUSTER_NAME"
    else
        log_info "Using existing cluster..."
        kubectl cluster-info --context "kind-$CLUSTER_NAME" >/dev/null 2>&1 || {
            log_error "Existing cluster is not accessible"
            exit 1
        }
    fi
fi

# Start time tracking
START_TIME=$(date +%s)

# Run tests based on mode
case $MODE in
    smoke)
        log_info "Running smoke tests..."
        export CLUSTER_NAME
        ./automated/e2e-test.sh --smoke
        ;;
    quick)
        log_info "Running quick tests..."
        export CLUSTER_NAME
        ./automated/e2e-test.sh --quick
        ;;
    full)
        log_info "Running full test suite..."
        export CLUSTER_NAME
        ./automated/e2e-test.sh
        ;;
esac

# Calculate test duration
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

log_success "Tests completed in ${DURATION} seconds"

# Handle cleanup
if [ "$KEEP_CLUSTER" = false ]; then
    log_info "Cleaning up cluster..."
    kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
    log_success "Cluster cleaned up"
else
    log_info "Cluster '$CLUSTER_NAME' is kept for further testing"
    log_info "To access: kubectl cluster-info --context kind-$CLUSTER_NAME"
    log_info "To clean up later: kind delete cluster --name $CLUSTER_NAME"
fi

log_success "MMF E2E test run completed successfully!"
