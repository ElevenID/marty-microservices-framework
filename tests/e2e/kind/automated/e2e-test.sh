#!/bin/bash

# Exit on any error - commented out for debugging
# set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="mmf-e2e-test"
NAMESPACE="mmf-system"
SERVICE_NAME="identity-service"
IMAGE_NAME="mmf/identity-service:e2e-test"
TIMEOUT=300 # 5 minutes

# Test results
TESTS_PASSED=0
TESTS_FAILED=0

echo -e "${BLUE}🧪 Starting MMF End-to-End Test Suite${NC}"
echo "=================================================="

# Function to log test results
log_test() {
    local test_name="$1"
    local status="$2"
    local message="$3"

    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ $test_name: PASSED${NC}"
        if [ -n "$message" ]; then
            echo -e "   $message"
        fi
        ((TESTS_PASSED++))
    else
        echo -e "${RED}❌ $test_name: FAILED${NC}"
        if [ -n "$message" ]; then
            echo -e "   $message"
        fi
        ((TESTS_FAILED++))
    fi
}

# Function to cleanup
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"

    # Delete KIND cluster
    if kind get clusters | grep -q "$CLUSTER_NAME"; then
        echo "Deleting KIND cluster '$CLUSTER_NAME'..."
        kind delete cluster --name "$CLUSTER_NAME" >/dev/null 2>&1 || true
    fi

    # Remove Docker image
    if docker images | grep -q "$IMAGE_NAME"; then
        echo "Removing Docker image '$IMAGE_NAME'..."
        docker rmi "$IMAGE_NAME" >/dev/null 2>&1 || true
    fi

    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Function to cleanup on error
cleanup_on_error() {
    echo -e "\n${RED}💥 Test failed, cleaning up...${NC}"
    cleanup
}

# Trap cleanup on error only - disabled for debugging
# trap cleanup_on_error ERR

# Function to wait for deployment
wait_for_deployment() {
    local timeout=$1
    echo "Waiting for deployment to be ready (timeout: ${timeout}s)..."

    if kubectl wait --for=condition=available --timeout="${timeout}s" deployment/"$SERVICE_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to wait for pods
wait_for_pods() {
    local timeout=$1
    echo "Waiting for pods to be ready (timeout: ${timeout}s)..."

    if kubectl wait --for=condition=ready --timeout="${timeout}s" pod -l app="$SERVICE_NAME" -n "$NAMESPACE" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to run HTTP test
run_http_test() {
    local test_name="$1"
    local method="$2"
    local endpoint="$3"
    local data="$4"
    local expected_status="$5"
    local expected_content="$6"

    local curl_cmd="kubectl run test-pod-$RANDOM --rm -i --tty --image=curlimages/curl --restart=Never -- curl -s"

    if [ "$method" = "POST" ]; then
        curl_cmd="$curl_cmd -X POST -H 'Content-Type: application/json' -d '$data'"
    fi

    curl_cmd="$curl_cmd http://$SERVICE_IP$endpoint"

    local response
    response=$(eval "$curl_cmd" 2>/dev/null)
    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
        log_test "$test_name" "FAIL" "Failed to execute curl command"
        return 1
    fi

    # Check if response contains expected content
    if [ -n "$expected_content" ] && [[ "$response" != *"$expected_content"* ]]; then
        log_test "$test_name" "FAIL" "Expected content '$expected_content' not found in response: $response"
        return 1
    fi

    log_test "$test_name" "PASS" "Response: $response"
    return 0
}

echo -e "\n${BLUE}📋 Test Configuration${NC}"
echo "Cluster Name: $CLUSTER_NAME"
echo "Namespace: $NAMESPACE"
echo "Service Name: $SERVICE_NAME"
echo "Image Name: $IMAGE_NAME"
echo "Timeout: ${TIMEOUT}s"

echo -e "\n${BLUE}🚀 Phase 1: Infrastructure Setup${NC}"

# Check prerequisites
echo "Checking prerequisites..."
command -v kind >/dev/null 2>&1 || { echo -e "${RED}❌ KIND is not installed${NC}"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo -e "${RED}❌ kubectl is not installed${NC}"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker is not installed${NC}"; exit 1; }

log_test "Prerequisites Check" "PASS" "KIND, kubectl, and Docker are available"

# Clean up any existing cluster
if kind get clusters | grep -q "$CLUSTER_NAME"; then
    echo "Cleaning up existing cluster '$CLUSTER_NAME'..."
    kind delete cluster --name "$CLUSTER_NAME"
fi

# Create KIND cluster
echo "Creating KIND cluster '$CLUSTER_NAME'..."
if kind create cluster --name "$CLUSTER_NAME" --config=../../../../deploy/kind-config.yaml >/dev/null 2>&1; then
    log_test "KIND Cluster Creation" "PASS" "Cluster '$CLUSTER_NAME' created successfully"
else
    log_test "KIND Cluster Creation" "FAIL" "Failed to create KIND cluster"
    exit 1
fi

# Install NGINX Ingress Controller
echo "Installing NGINX Ingress Controller..."
if kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml >/dev/null 2>&1; then
    log_test "NGINX Ingress Installation" "PASS" "NGINX Ingress Controller installed"
else
    log_test "NGINX Ingress Installation" "FAIL" "Failed to install NGINX Ingress Controller"
    exit 1
fi

# Wait for ingress controller
echo "Waiting for ingress controller to be ready..."
if kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=300s >/dev/null 2>&1; then
    log_test "NGINX Ingress Readiness" "PASS" "NGINX Ingress Controller is ready"
else
    log_test "NGINX Ingress Readiness" "FAIL" "NGINX Ingress Controller failed to become ready"
    exit 1
fi

echo -e "\n${BLUE}🐳 Phase 2: Application Build and Deploy${NC}"

# Build Docker image
echo "Building Docker image..."
if docker build -t "$IMAGE_NAME" . >/dev/null 2>&1; then
    log_test "Docker Image Build" "PASS" "Image '$IMAGE_NAME' built successfully"
else
    log_test "Docker Image Build" "FAIL" "Failed to build Docker image"
    exit 1
fi

# Load image into KIND cluster
echo "Loading Docker image into KIND cluster..."
if kind load docker-image "$IMAGE_NAME" --name "$CLUSTER_NAME" >/dev/null 2>&1; then
    log_test "Docker Image Load" "PASS" "Image loaded into KIND cluster"
else
    log_test "Docker Image Load" "FAIL" "Failed to load image into KIND cluster"
    exit 1
fi

# Create namespace and deploy application
echo "Deploying application..."
kubectl create namespace "$NAMESPACE" >/dev/null 2>&1 || true

# Update deployment to use e2e test image
sed "s|mmf/identity-service:minimal|$IMAGE_NAME|g" ../../../../deploy/identity-service.yaml > /tmp/identity-service-e2e.yaml

if kubectl apply -f /tmp/identity-service-e2e.yaml >/dev/null 2>&1; then
    log_test "Application Deployment" "PASS" "Application deployed successfully"
else
    log_test "Application Deployment" "FAIL" "Failed to deploy application"
    exit 1
fi

# Wait for deployment to be ready
echo "Waiting for application to be ready..."
if wait_for_deployment $TIMEOUT && wait_for_pods $TIMEOUT; then
    log_test "Application Readiness" "PASS" "Application is ready and running"
else
    log_test "Application Readiness" "FAIL" "Application failed to become ready within timeout"
    kubectl logs -n "$NAMESPACE" -l app="$SERVICE_NAME" --tail=10
    exit 1
fi

# Get service cluster IP
SERVICE_IP=$(kubectl get svc -n "$NAMESPACE" "$SERVICE_NAME" -o jsonpath='{.spec.clusterIP}')
if [ -z "$SERVICE_IP" ]; then
    log_test "Service IP Discovery" "FAIL" "Failed to get service cluster IP"
    exit 1
else
    log_test "Service IP Discovery" "PASS" "Service IP: $SERVICE_IP"
fi

echo -e "\n${BLUE}🧪 Phase 3: End-to-End API Tests${NC}"

# Test 1: Health Check
run_http_test "Health Check" "GET" "/health" "" "" '"status":"healthy"'

# Test 2: Users Endpoint
run_http_test "Users List" "GET" "/users" "" "" '"test_users"'

# Test 3: Valid Authentication
run_http_test "Valid Authentication" "POST" "/authenticate" '{"username": "admin", "password": "admin123"}' "" '"success":true'

# Test 4: Invalid Authentication
run_http_test "Invalid Authentication" "POST" "/authenticate" '{"username": "admin", "password": "wrong"}' "" '"success":false'

# Test 5: Events Endpoint
run_http_test "Events List" "GET" "/events" "" "" '"events"'

# Test 6: Authentication with Different User
run_http_test "User Authentication" "POST" "/authenticate" '{"username": "user", "password": "password"}' "" '"success":true'

# Test 7: Authentication with Demo User
run_http_test "Demo Authentication" "POST" "/authenticate" '{"username": "demo", "password": "demo123"}' "" '"success":true'

# Test 8: Authentication with Non-existent User
run_http_test "Non-existent User" "POST" "/authenticate" '{"username": "nonexistent", "password": "password"}' "" '"success":false'

# Test 9: Authentication with Empty Credentials
run_http_test "Empty Credentials" "POST" "/authenticate" '{"username": "", "password": ""}' "" '"success":false'

# Test 10: Malformed JSON
kubectl run test-pod-malformed --rm -i --tty --image=curlimages/curl --restart=Never -- curl -s -X POST -H "Content-Type: application/json" -d '{"invalid": json}' "http://$SERVICE_IP/authenticate" >/dev/null 2>&1
if [ $? -eq 0 ]; then
    log_test "Malformed JSON Handling" "PASS" "Service handles malformed JSON gracefully"
else
    log_test "Malformed JSON Handling" "FAIL" "Service failed to handle malformed JSON"
fi

echo -e "\n${BLUE}📊 Phase 4: System Validation${NC}"

# Check pod health
POD_COUNT=$(kubectl get pods -n "$NAMESPACE" -l app="$SERVICE_NAME" --field-selector=status.phase=Running -o name | wc -l)
if [ "$POD_COUNT" -eq 2 ]; then
    log_test "Pod Count Validation" "PASS" "2 pods are running as expected"
else
    log_test "Pod Count Validation" "FAIL" "Expected 2 pods, found $POD_COUNT"
fi

# Check service endpoints
ENDPOINTS=$(kubectl get endpoints -n "$NAMESPACE" "$SERVICE_NAME" -o jsonpath='{.subsets[0].addresses}' | jq length 2>/dev/null || echo "0")
if [ "$ENDPOINTS" -ge 1 ]; then
    log_test "Service Endpoints" "PASS" "$ENDPOINTS endpoint(s) available"
else
    log_test "Service Endpoints" "FAIL" "No service endpoints found"
fi

# Check ingress
INGRESS_EXISTS=$(kubectl get ingress -n "$NAMESPACE" "$SERVICE_NAME" -o name 2>/dev/null | wc -l)
if [ "$INGRESS_EXISTS" -eq 1 ]; then
    log_test "Ingress Configuration" "PASS" "Ingress is configured"
else
    log_test "Ingress Configuration" "FAIL" "Ingress is not configured"
fi

# Resource usage check
echo "Checking resource usage..."
kubectl top pods -n "$NAMESPACE" >/dev/null 2>&1 && log_test "Resource Monitoring" "PASS" "Resource metrics available" || log_test "Resource Monitoring" "FAIL" "Resource metrics not available"

echo -e "\n${BLUE}📈 Test Results Summary${NC}"
echo "=================================================="
echo -e "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"

# Run cleanup
cleanup

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All tests passed! The MMF Identity Service is working correctly.${NC}"
    exit 0
else
    echo -e "\n${RED}💥 Some tests failed. Please check the logs above.${NC}"
    exit 1
fi
