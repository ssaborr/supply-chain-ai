# Multi-Stage Dockerfile for Angular Frontend

# ---------- Stage 1: Build Environment ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Optimize build caching: copy package manifests first
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit

# Copy application code and compile
COPY . .
RUN npm run build

# ---------- Stage 2: Hardened Runtime ----------
FROM nginx:alpine-slim AS runtime

# Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy compiled Angular production bundle from builder stage
COPY --from=builder /app/dist/FrontEnd/browser /usr/share/nginx/html

# Copy hardened Nginx security configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# DevSecOps Healthcheck probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
