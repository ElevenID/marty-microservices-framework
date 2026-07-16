#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting MMF Demo with Production Features${NC}"

# 1. Setup Cluster (using existing script)
echo -e "${YELLOW}📦 Setting up Kind cluster with Istio and Observability...${NC}"
# We use the setup-cluster.sh script but we need to make sure it's executable
chmod +x scripts/dev/setup-cluster.sh
./scripts/dev/setup-cluster.sh

# 2. Build Images
echo -e "${YELLOW}🐳 Building Payment Service image...${NC}"
docker build -t mmf/payment-service:latest -f examples/production-payment-service/Dockerfile .

echo -e "${YELLOW}🐳 Building Pet Service image...${NC}"
docker build -t mmf/pet-service:latest -f examples/petstore_domain/services/pet_service/Dockerfile .

# 3. Load Images into Kind
echo -e "${YELLOW}🚚 Loading images into Kind cluster...${NC}"
kind load docker-image mmf/payment-service:latest --name microservices-framework
kind load docker-image mmf/pet-service:latest --name microservices-framework

# 4. Deploy Services
echo -e "${YELLOW}🚀 Deploying services...${NC}"
# Enable sidecar injection for default namespace
kubectl label namespace default istio-injection=enabled --overwrite

kubectl apply -f examples/k8s/payment-service.yaml
kubectl apply -f examples/k8s/pet-service.yaml

# 5. Configure Istio Gateway
echo -e "${YELLOW}🌐 Configuring Istio Gateway...${NC}"
kubectl apply -f examples/k8s/istio-gateway.yaml

# 6. Wait for rollout
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
kubectl rollout status deployment/payment-service
kubectl rollout status deployment/pet-service

echo -e "${GREEN}✅ Demo deployed successfully!${NC}"
echo -e "You can access the services via localhost (if port forwarding is set up) or via the ingress gateway IP."
echo -e "Try: curl http://localhost:8080/payments/health (mapped to port 8080)"
