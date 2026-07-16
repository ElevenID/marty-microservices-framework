#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Video Streaming Domain Deployment with KIND${NC}"

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
echo -e "${YELLOW}📦 Creating KIND cluster 'mmf-video-streaming'...${NC}"
if kind get clusters | grep -q mmf-video-streaming; then
    echo -e "${YELLOW}⚠️  Cluster 'mmf-video-streaming' already exists. Using it.${NC}"
else
    kind create cluster --name mmf-video-streaming --config deploy/kind-config.yaml --wait 300s
fi

# Install Metrics Server (Required for HPA)
echo -e "${YELLOW}📊 Installing Metrics Server...${NC}"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
# Patch metrics server to work insecurely in Kind
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Build Docker images
echo -e "${YELLOW}🐳 Building Catalog Service image...${NC}"
docker build -t mmf/catalog-service:latest -f examples/video_streaming_domain/services/catalog_service/Dockerfile .

echo -e "${YELLOW}🐳 Building Stream Service image...${NC}"
docker build -t mmf/stream-service:latest -f examples/video_streaming_domain/services/stream_service/Dockerfile .

echo -e "${YELLOW}🐳 Building Recommendation Service image...${NC}"
docker build -t mmf/recommendation-service:latest -f examples/video_streaming_domain/services/recommendation_service/Dockerfile .

echo -e "${YELLOW}🐳 Building UI image...${NC}"
docker build -t mmf/video-ui:latest -f examples/video_streaming_domain/ui/Dockerfile examples/video_streaming_domain/ui

# Load images into KIND cluster
echo -e "${YELLOW}📥 Loading Docker images into KIND cluster...${NC}"
kind load docker-image mmf/catalog-service:latest --name mmf-video-streaming
kind load docker-image mmf/stream-service:latest --name mmf-video-streaming
kind load docker-image mmf/recommendation-service:latest --name mmf-video-streaming
kind load docker-image mmf/video-ui:latest --name mmf-video-streaming

# Deploy application
echo -e "${YELLOW}🚀 Deploying application to Kubernetes...${NC}"
kubectl apply -f examples/video_streaming_domain/k8s/namespace.yaml
kubectl apply -f examples/video_streaming_domain/k8s/catalog-service.yaml
kubectl apply -f examples/video_streaming_domain/k8s/stream-service.yaml
kubectl apply -f examples/video_streaming_domain/k8s/recommendation-service.yaml
kubectl apply -f examples/video_streaming_domain/k8s/ui.yaml
kubectl apply -f examples/video_streaming_domain/k8s/hpa.yaml

# Wait for deployment to be ready
echo -e "${YELLOW}⏳ Waiting for deployment to be ready...${NC}"
kubectl wait --namespace video-streaming \
  --for=condition=available deployment/catalog-service \
  --timeout=300s

kubectl wait --namespace video-streaming \
  --for=condition=available deployment/stream-service \
  --timeout=300s

kubectl wait --namespace video-streaming \
  --for=condition=available deployment/recommendation-service \
  --timeout=300s

kubectl wait --namespace video-streaming \
  --for=condition=available deployment/video-ui \
  --timeout=300s

# Show status
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Cluster Status:${NC}"
kubectl get pods -n video-streaming
echo ""
kubectl get services -n video-streaming
echo ""
kubectl get hpa -n video-streaming

echo ""
echo -e "${BLUE}🌐 Access Instructions:${NC}"
echo -e "Run the following command to access the UI:"
echo -e "${YELLOW}kubectl port-forward -n video-streaming svc/video-ui 8080:80${NC}"
echo -e "Then open http://localhost:8080 in your browser."
