#!/bin/bash

# Microservices Framework Setup Script for Kind
# This script sets up a complete Kind cluster with service mesh and observability

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
CLUSTER_NAME="microservices-framework"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
SERVICE_MESH=${SERVICE_MESH:-"istio"} # Options: istio, linkerd, none
OBSERVABILITY=${OBSERVABILITY:-"true"}

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_dependencies() {
    print_status "Checking dependencies..."

    local deps=("kind" "kubectl" "helm")
    local missing_deps=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" &> /dev/null; then
            missing_deps+=("$dep")
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing dependencies: ${missing_deps[*]}"
        print_status "Please install the missing dependencies and try again."
        exit 1
    fi

    print_success "All dependencies found"
}

create_kind_cluster() {
    print_status "Creating Kind cluster: $CLUSTER_NAME"

    if kind get clusters | grep -q "^$CLUSTER_NAME$"; then
        print_warning "Cluster $CLUSTER_NAME already exists. Deleting..."
        kind delete cluster --name "$CLUSTER_NAME"
    fi

    kind create cluster --name "$CLUSTER_NAME" --config "$PROJECT_ROOT/deploy/kind-config.yaml"

    # Wait for cluster to be ready
    kubectl cluster-info --context "kind-$CLUSTER_NAME"
    kubectl wait --for=condition=Ready nodes --all --timeout=300s

    print_success "Kind cluster created successfully"
}

setup_observability() {
    if [ "$OBSERVABILITY" != "true" ]; then
        print_status "Skipping observability setup"
        return
    fi

    print_status "Setting up observability stack..."

    # Apply observability namespace and components
    kubectl apply -f "$PROJECT_ROOT/ops/k8s/observability/prometheus.yaml"
    kubectl apply -f "$PROJECT_ROOT/ops/k8s/observability/grafana.yaml"
    kubectl apply -f "$PROJECT_ROOT/ops/k8s/observability/kafka.yaml"

    # Wait for observability components to be ready
    print_status "Waiting for observability components to be ready..."
    kubectl wait --for=condition=Available deployment/prometheus -n observability --timeout=300s
    kubectl wait --for=condition=Available deployment/grafana -n observability --timeout=300s
    kubectl wait --for=condition=Available deployment/kafka -n observability --timeout=300s

    print_success "Observability stack deployed successfully"
}

setup_istio() {
    print_status "Setting up Istio service mesh..."

    # Check if istioctl is available
    if ! command -v istioctl &> /dev/null; then
        print_status "Installing istioctl..."
        curl -L https://istio.io/downloadIstio | sh -
        export PATH="$PWD/istio-*/bin:$PATH"
    fi

    # Install Istio
    istioctl install --set values.defaultRevision=default -y

    # Apply custom configuration
    kubectl apply -f "$PROJECT_ROOT/ops/service-mesh/production/istio-production.yaml"

    # Wait for Istio to be ready
    kubectl wait --for=condition=Available deployment/istiod -n istio-system --timeout=300s

    print_success "Istio service mesh deployed successfully"
}

setup_linkerd() {
    print_status "Setting up Linkerd service mesh..."

    # Check if linkerd CLI is available
    if ! command -v linkerd &> /dev/null; then
        print_status "Installing linkerd CLI..."
        curl -sL https://run.linkerd.io/install | sh
        export PATH=$HOME/.linkerd2/bin:$PATH
    fi

    # Check pre-installation
    linkerd check --pre

    # Install Linkerd control plane
    linkerd install --crds | kubectl apply -f -
    linkerd install | kubectl apply -f -

    # Install Linkerd viz extension
    linkerd viz install | kubectl apply -f -

    # Apply custom configuration
    kubectl apply -f "$PROJECT_ROOT/ops/service-mesh/production/linkerd-production.yaml"

    # Wait for Linkerd to be ready
    kubectl wait --for=condition=Available deployment/linkerd-controller -n linkerd --timeout=300s

    print_success "Linkerd service mesh deployed successfully"
}

setup_service_mesh() {
    case "$SERVICE_MESH" in
        "istio")
            setup_istio
            ;;
        "linkerd")
            setup_linkerd
            ;;
        "none")
            print_status "Skipping service mesh setup"
            ;;
        *)
            print_error "Unknown service mesh: $SERVICE_MESH"
            print_status "Supported options: istio, linkerd, none"
            exit 1
            ;;
    esac
}

setup_ingress() {
    print_status "Setting up ingress controller..."

    # Install NGINX ingress controller for Kind
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

    # Wait for ingress controller to be ready
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s

    print_success "Ingress controller deployed successfully"
}

create_sample_services() {
    print_status "Creating sample microservices..."

    # Create sample namespace
    kubectl create namespace microservice-framework --dry-run=client -o yaml | kubectl apply -f -

    # Label namespace for service mesh injection
    if [ "$SERVICE_MESH" = "istio" ]; then
        kubectl label namespace microservice-framework istio-injection=enabled --overwrite
    elif [ "$SERVICE_MESH" = "linkerd" ]; then
        kubectl annotate namespace microservice-framework linkerd.io/inject=enabled --overwrite
    fi

    # Create sample deployment and service
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sample-api
  namespace: microservice-framework
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sample-api
  template:
    metadata:
      labels:
        app: sample-api
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
    spec:
      containers:
      - name: sample-api
        image: nginx:1.21
        ports:
        - containerPort: 80
          name: http
        resources:
          requests:
            memory: 64Mi
            cpu: 50m
          limits:
            memory: 128Mi
            cpu: 100m
---
apiVersion: v1
kind: Service
metadata:
  name: sample-api
  namespace: microservice-framework
spec:
  selector:
    app: sample-api
  ports:
    - port: 80
      targetPort: 80
  type: ClusterIP
EOF

    print_success "Sample services created successfully"
}

display_access_info() {
    print_success "Microservices Framework deployed successfully!"
    echo
    print_status "Access Information:"
    echo "==================="

    if [ "$OBSERVABILITY" = "true" ]; then
        echo "📊 Grafana Dashboard: http://localhost:3000 (admin/admin)"
        echo "📈 Prometheus: http://localhost:9090"
        echo "📬 Kafka: kafka.observability.svc.cluster.local:9092"
        echo
        print_status "Port forwarding commands:"
        echo "kubectl port-forward -n observability svc/grafana 3000:3000"
        echo "kubectl port-forward -n observability svc/prometheus 9090:9090"
    fi

    if [ "$SERVICE_MESH" = "istio" ]; then
        echo "🕸️  Istio Gateway: http://localhost:80"
        echo "📊 Kiali (if installed): http://localhost:20001"
        echo
        print_status "Istio commands:"
        echo "kubectl port-forward -n istio-system svc/istio-ingressgateway 80:80"
    elif [ "$SERVICE_MESH" = "linkerd" ]; then
        echo "🕸️  Linkerd Dashboard: http://localhost:50750"
        echo
        print_status "Linkerd commands:"
        echo "linkerd viz dashboard &"
    fi

    echo
    print_status "Cluster commands:"
    echo "kubectl get pods -n microservice-framework"
    echo "kubectl get pods -n observability"
    echo "kubectl get pods -n istio-system"
    echo "kubectl get pods -n linkerd"
    echo
    print_status "To delete the cluster:"
    echo "kind delete cluster --name $CLUSTER_NAME"
}

main() {
    print_status "Starting Microservices Framework setup..."
    print_status "Service Mesh: $SERVICE_MESH"
    print_status "Observability: $OBSERVABILITY"
    echo

    check_dependencies
    create_kind_cluster
    setup_observability
    setup_service_mesh
    setup_ingress
    create_sample_services

    # Wait a bit for everything to settle
    sleep 10

    display_access_info
}

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service-mesh)
            SERVICE_MESH="$2"
            shift 2
            ;;
        --no-observability)
            OBSERVABILITY="false"
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --service-mesh <istio|linkerd|none>  Choose service mesh (default: istio)"
            echo "  --no-observability                   Skip observability setup"
            echo "  --help                               Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main
