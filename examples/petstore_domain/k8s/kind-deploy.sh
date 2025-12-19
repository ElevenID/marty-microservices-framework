#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-petstore}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

echo ">>> Building local images"
docker build -f "$ROOT_DIR/examples/petstore_domain/services/delivery_board_service/Dockerfile" -t petstore/delivery-board-service:dev "$ROOT_DIR"
docker build -f "$ROOT_DIR/examples/petstore_domain/services/store_service/Dockerfile" -t petstore/store-service:dev "$ROOT_DIR"
docker build -f "$ROOT_DIR/examples/petstore_domain/services/pet_service/Dockerfile" -t petstore/pet-service:dev "$ROOT_DIR"

echo ">>> Ensuring kind cluster '$CLUSTER_NAME' exists"
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}\$"; then
  kind create cluster --name "$CLUSTER_NAME"
fi

echo ">>> Loading images into kind"
kind load docker-image petstore/delivery-board-service:dev --name "$CLUSTER_NAME"
kind load docker-image petstore/store-service:dev --name "$CLUSTER_NAME"
kind load docker-image petstore/pet-service:dev --name "$CLUSTER_NAME"

echo ">>> Deploying to kind"
kubectl apply -f "$ROOT_DIR/examples/petstore_domain/k8s/petstore-kind.yaml"

echo ">>> Done. Try:"
echo "kubectl -n petstore get pods"
echo "kubectl -n petstore port-forward svc/store-service 8001:8001"
