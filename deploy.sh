#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
#  Signal Bot — Kubernetes Deployment Script
#  Usage: chmod +x deploy.sh && ./deploy.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

REGISTRY="${DOCKER_REGISTRY:-your-registry}"
TAG="${IMAGE_TAG:-latest}"
DOMAIN="${DOMAIN:-yourdomain.com}"
NAMESPACE="signal-bot"

echo "================================================"
echo " Signal Bot — Kubernetes Deploy"
echo " Registry : $REGISTRY"
echo " Tag      : $TAG"
echo " Domain   : $DOMAIN"
echo "================================================"

# ── Step 1: Build Docker images ───────────────────────────────────────────────
echo ""
echo "[1/5] Building Docker images..."

docker build -t $REGISTRY/signal-bot-backend:$TAG ./backend
docker build \
  --build-arg REACT_APP_BACKEND_URL=https://$DOMAIN \
  -t $REGISTRY/signal-bot-frontend:$TAG \
  ./frontend

# ── Step 2: Push images ───────────────────────────────────────────────────────
echo ""
echo "[2/5] Pushing images to registry..."

docker push $REGISTRY/signal-bot-backend:$TAG
docker push $REGISTRY/signal-bot-frontend:$TAG

# ── Step 3: Update image references in K8s manifests ─────────────────────────
echo ""
echo "[3/5] Updating Kubernetes manifests..."

sed -i "s|YOUR_REGISTRY/signal-bot-backend:latest|$REGISTRY/signal-bot-backend:$TAG|g" k8s/05-backend.yaml
sed -i "s|YOUR_REGISTRY/signal-bot-frontend:latest|$REGISTRY/signal-bot-frontend:$TAG|g" k8s/06-frontend.yaml
sed -i "s|yourdomain.com|$DOMAIN|g" k8s/08-ingress.yaml

# ── Step 4: Apply secrets (only if not already set) ───────────────────────────
echo ""
echo "[4/5] Applying Kubernetes manifests..."
echo "⚠️  IMPORTANT: Edit k8s/01-secrets.yaml with your actual credentials first!"
echo ""

kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmap.yaml

# Choose: deploy local DB or skip if using external
read -p "Deploy local MongoDB? [y/N] (N = using external/Atlas): " deploy_mongo
if [[ $deploy_mongo == "y" || $deploy_mongo == "Y" ]]; then
    kubectl apply -f k8s/03-mongodb.yaml
fi

read -p "Deploy local Redis? [y/N] (N = using external/Upstash): " deploy_redis
if [[ $deploy_redis == "y" || $deploy_redis == "Y" ]]; then
    kubectl apply -f k8s/04-redis.yaml
fi

kubectl apply -f k8s/05-backend.yaml
kubectl apply -f k8s/06-frontend.yaml
kubectl apply -f k8s/07-services.yaml
kubectl apply -f k8s/08-ingress.yaml

# ── Step 5: Wait and verify ────────────────────────────────────────────────────
echo ""
echo "[5/5] Waiting for deployments..."

kubectl rollout status deployment/backend -n $NAMESPACE --timeout=120s
kubectl rollout status deployment/frontend -n $NAMESPACE --timeout=120s

echo ""
echo "================================================"
echo " Deployment complete!"
echo " Access: https://$DOMAIN"
echo " Login: opsculun / (your ADMIN_PASSWORD)"
echo "================================================"

kubectl get pods -n $NAMESPACE
