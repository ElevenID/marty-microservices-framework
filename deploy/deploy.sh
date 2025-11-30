#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting MMF Minimal Example Deployment with KIND${NC}"

# Check if KIND is installed
if ! command -v kind &> /dev/null; then
    echo -e "${RED}❌ KIND is not installed. Please install KIND first.${NC}"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Create KIND cluster
echo -e "${YELLOW}📦 Creating KIND cluster 'mmf-example'...${NC}"
if kind get clusters | grep -q mmf-example; then
    echo -e "${YELLOW}⚠️  Cluster 'mmf-example' already exists. Deleting it first...${NC}"
    kind delete cluster --name mmf-example
fi

kind create cluster --config deploy/kind-config.yaml --wait 300s

# Install nginx ingress controller
echo -e "${YELLOW}🌐 Installing NGINX Ingress Controller...${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml

# Wait for ingress controller to be ready
echo -e "${YELLOW}⏳ Waiting for ingress controller to be ready...${NC}"
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=300s

# Build Docker image
echo -e "${YELLOW}🐳 Building Docker image...${NC}"
docker build -t mmf/identity-service:minimal .

echo -e "${YELLOW}🐳 Building UI Docker image...${NC}"
docker build -t mmf/identity-ui:latest -f mmf_new/services/identity/ui/Dockerfile mmf_new/services/identity/ui

# Load image into KIND cluster
echo -e "${YELLOW}📥 Loading Docker image into KIND cluster...${NC}"
kind load docker-image mmf/identity-service:minimal --name mmf-example
kind load docker-image mmf/identity-ui:latest --name mmf-example

# Deploy Vault
echo -e "${YELLOW}🔐 Deploying Vault...${NC}"
kubectl apply -f deploy/vault.yaml
echo -e "${YELLOW}⏳ Waiting for Vault to be ready...${NC}"
kubectl wait --namespace default \
  --for=condition=available deployment/vault \
  --timeout=300s

# Deploy application
echo -e "${YELLOW}🚀 Deploying application to Kubernetes...${NC}"
kubectl apply -f deploy/namespace.yaml
kubectl apply -f deploy/identity-service.yaml
kubectl apply -f deploy/identity-ui.yaml

# Wait for deployment to be ready
echo -e "${YELLOW}⏳ Waiting for deployment to be ready...${NC}"
kubectl wait --namespace mmf-system \
  --for=condition=available deployment/identity-service \
  --timeout=300s

kubectl wait --namespace mmf-system \
  --for=condition=available deployment/identity-ui \
  --timeout=300s

# Show status
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Cluster Status:${NC}"
kubectl get pods -n mmf-system
echo ""
kubectl get services -n mmf-system
echo ""
kubectl get ingress -n mmf-system

# Add local DNS entry instructions
echo ""
echo -e "${BLUE}🌐 Access Instructions:${NC}"
echo -e "Add this to your /etc/hosts file:"
echo -e "${YELLOW}127.0.0.1 identity.local${NC}"
echo ""
echo -e "Then access the service at:"
echo -e "${GREEN}http://identity.local:8080/health${NC}"
echo -e "${GREEN}http://identity.local:8080/users${NC}"
echo ""
echo -e "Access the UI at:"
echo -e "${GREEN}http://localhost:8080${NC}"
echo ""
echo -e "To test authentication:"
echo -e "${GREEN}curl -X POST http://identity.local:8080/authenticate \\${NC}"
echo -e "${GREEN}  -H \"Content-Type: application/json\" \\${NC}"
echo -e "${GREEN}  -d '{\"username\": \"admin\", \"password\": \"admin123\"}'${NC}"

echo ""
echo -e "${BLUE}🔧 Useful Commands:${NC}"
echo -e "View logs: ${YELLOW}kubectl logs -n mmf-system -l app=identity-service -f${NC}"
echo -e "Port forward App: ${YELLOW}kubectl port-forward -n mmf-system svc/identity-service 8000:80${NC}"
echo -e "Port forward Vault: ${YELLOW}kubectl port-forward svc/vault 8200:8200${NC}"
echo -e "Delete cluster: ${YELLOW}kind delete cluster --name mmf-example${NC}"
