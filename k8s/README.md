# Signal Bot — Kubernetes & Docker Deployment Guide

## File Structure
```
signal-bot/
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── server.py, models.py, ...
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── .dockerignore
│   └── src/...
├── k8s/
│   ├── 00-namespace.yaml      ← K8s namespace
│   ├── 01-secrets.yaml        ← EDIT THIS: DB credentials
│   ├── 02-configmap.yaml      ← Non-sensitive config
│   ├── 03-mongodb.yaml        ← Local MongoDB (optional)
│   ├── 04-redis.yaml          ← Local Redis (optional)
│   ├── 05-backend.yaml        ← Backend deployment
│   ├── 06-frontend.yaml       ← Frontend deployment
│   ├── 07-services.yaml       ← K8s services
│   └── 08-ingress.yaml        ← Ingress (nginx)
├── deploy/
│   └── mongo-init.js          ← MongoDB init script
├── .env.example               ← Copy to .env and fill values
├── docker-compose.yml         ← Dev: all-in-one
├── docker-compose.prod.yml    ← Prod: external DB
└── deploy.sh                  ← Auto deploy script
```

---

## Option A: Docker Compose (Easiest)

### 1. Configure Credentials
```bash
cp .env.example .env
nano .env  # Edit all CHANGE_ME values
```

**Key values to change in `.env`:**
```
MONGO_PASSWORD=your-strong-mongo-password
REDIS_PASSWORD=your-strong-redis-password
JWT_SECRET=run: python3 -c "import secrets; print(secrets.token_hex(32))"
ADMIN_PASSWORD=your-admin-password
REACT_APP_BACKEND_URL=http://localhost:3000  # or your domain
```

### 2. Start All Services
```bash
docker-compose up -d

# Check status
docker-compose ps
docker-compose logs -f backend
```

### 3. Access
```
Dashboard: http://localhost:3000
Username:  opsculun
Password:  (your ADMIN_PASSWORD from .env)
```

---

## Option B: Docker Compose with External DB (MongoDB Atlas + Redis Cloud)

### 1. Configure
```bash
cp .env.example .env
```

Edit `.env`:
```env
# MongoDB Atlas
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/signal_bot

# Redis Cloud / Upstash
REDIS_URL=redis://:password@host.upstash.io:6379
# or with TLS:
REDIS_URL=rediss://:password@host.upstash.io:6380
```

### 2. Run
```bash
docker-compose -f docker-compose.prod.yml up -d
```

---

## Option C: Kubernetes Deploy

### Prerequisites
```bash
kubectl version        # Kubernetes cluster access
docker login           # Docker registry access
```

### 1. Edit Secrets (REQUIRED)
```bash
nano k8s/01-secrets.yaml
```

Change ALL `CHANGE_ME_*` values:
```yaml
MONGO_URL: "mongodb+srv://user:REAL_PASS@cluster.mongodb.net/signal_bot"
REDIS_URL: "redis://:REAL_REDIS_PASS@redis-host:6379"
JWT_SECRET: "your-64-char-hex-from-python"
ADMIN_PASSWORD: "your-strong-admin-password"
ENCRYPTION_KEY: "your-32-char-key-here-padding00"
CORS_ORIGINS: "https://yourdomain.com"
FRONTEND_URL: "https://yourdomain.com"
```

### 2. Build & Push Images
```bash
# Set your Docker registry
export DOCKER_REGISTRY=your-dockerhub-username
export DOMAIN=yourdomain.com

# Build backend
docker build -t $DOCKER_REGISTRY/signal-bot-backend:latest ./backend

# Build frontend (with your domain)
docker build \
  --build-arg REACT_APP_BACKEND_URL=https://$DOMAIN \
  -t $DOCKER_REGISTRY/signal-bot-frontend:latest \
  ./frontend

# Push
docker push $DOCKER_REGISTRY/signal-bot-backend:latest
docker push $DOCKER_REGISTRY/signal-bot-frontend:latest
```

### 3. Update K8s Manifests
```bash
# Update image names in deployments
sed -i "s|YOUR_REGISTRY|$DOCKER_REGISTRY|g" k8s/05-backend.yaml k8s/06-frontend.yaml
sed -i "s|yourdomain.com|$DOMAIN|g" k8s/08-ingress.yaml
```

### 4. Deploy
```bash
# Create namespace
kubectl apply -f k8s/00-namespace.yaml

# Create secrets (with your credentials)
kubectl apply -f k8s/01-secrets.yaml
kubectl apply -f k8s/02-configmap.yaml

# OPTION 1: Deploy with local MongoDB + Redis
kubectl apply -f k8s/03-mongodb.yaml
kubectl apply -f k8s/04-redis.yaml

# OPTION 2: Skip 03 and 04 if using Atlas + Redis Cloud
# (Already configured in 01-secrets.yaml MONGO_URL and REDIS_URL)

# Deploy app
kubectl apply -f k8s/05-backend.yaml
kubectl apply -f k8s/06-frontend.yaml
kubectl apply -f k8s/07-services.yaml
kubectl apply -f k8s/08-ingress.yaml
```

### 5. Verify
```bash
kubectl get pods -n signal-bot
kubectl get svc -n signal-bot
kubectl get ingress -n signal-bot

# Logs
kubectl logs -f deployment/backend -n signal-bot
kubectl logs -f deployment/frontend -n signal-bot
```

---

## MongoDB Connection String Formats

| Setup | Connection String |
|-------|------------------|
| Local Docker | `mongodb://admin:pass@mongodb-service:27017/signal_bot?authSource=admin` |
| MongoDB Atlas | `mongodb+srv://user:pass@cluster.mongodb.net/signal_bot` |
| Self-managed + Auth | `mongodb://user:pass@host:27017/signal_bot?authSource=admin` |
| Replica Set | `mongodb://user:pass@h1:27017,h2:27017/signal_bot?replicaSet=rs0` |

## Redis Connection String Formats

| Setup | Connection String |
|-------|------------------|
| Local no auth | `redis://localhost:6379` |
| Local with auth | `redis://:password@localhost:6379` |
| Redis Cloud | `redis://:password@host.redis.io:6379` |
| Upstash with TLS | `rediss://:password@host.upstash.io:6380` |
| Redis 6+ (user+pass) | `redis://username:password@host:6379` |

---

## Generate Secure Secrets

```bash
# JWT Secret (64-char hex)
python3 -c "import secrets; print(secrets.token_hex(32))"

# Encryption Key (32 chars)
python3 -c "import secrets; print(secrets.token_hex(16))"

# Strong Password
python3 -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%'; print(''.join(secrets.choice(chars) for _ in range(24)))"
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pyOpenSSL` error | `pip install --upgrade pyOpenSSL cryptography` |
| MongoDB auth failed | Check MONGO_URL includes `?authSource=admin` |
| Redis connection refused | Verify REDIS_PASSWORD matches `requirepass` in redis config |
| Frontend blank page | Check nginx logs: `kubectl logs deployment/frontend -n signal-bot` |
| No signals generated | Check backend logs for API errors |
| WebSocket not connecting | Verify Ingress has WebSocket annotations (`upgrade` headers) |
