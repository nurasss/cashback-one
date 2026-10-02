# Multi-stage build for POSCENTER Loyalty Admin SPA
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_BASE_URL=""
ARG VITE_ALLOW_INSECURE_HTTP="0"
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_ALLOW_INSECURE_HTTP=${VITE_ALLOW_INSECURE_HTTP}

RUN npm run build

# Production runtime image: Nginx serving static assets
FROM nginx:1.27-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
