# ── Stage 1: Build React app ──────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --silent --ignore-engines

# Copy source
COPY . .

# Build args (set at build time via docker-compose or kubectl)
# Default empty → frontend will use RELATIVE URLs (/api) so Nginx in this container
# proxies to backend. Image becomes domain-agnostic — deploy anywhere, no CORS issues.
ARG REACT_APP_BACKEND_URL=
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

RUN yarn build

# ── Stage 2: Serve with Nginx ─────────────────────────────────────────────────
FROM nginx:1.25-alpine

# Copy build
COPY --from=builder /app/build /usr/share/nginx/html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/index.html || exit 1

CMD ["nginx", "-g", "daemon off;"]
