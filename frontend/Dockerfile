FROM node:22-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Set VITE_PUBLIC_DEPLOYMENT=true on Railway to hide the local-only login shortcuts.
ARG VITE_PUBLIC_DEPLOYMENT=false
ENV VITE_PUBLIC_DEPLOYMENT=${VITE_PUBLIC_DEPLOYMENT}
RUN npm run build

FROM nginx:1.27-alpine
# Local Compose uses backend:8000. On Railway override API_UPSTREAM with the private backend address.
ENV API_UPSTREAM=http://backend:8000
# Only expand API_UPSTREAM: preserve Nginx runtime variables $host, $uri, etc.
ENV NGINX_ENVSUBST_FILTER=^API_UPSTREAM$
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
