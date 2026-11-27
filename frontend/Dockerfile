# ==========================================
# Stage 1: Build (Node)
# ==========================================
FROM node:22-alpine AS build-stage
WORKDIR /app
COPY package*.json ./
RUN npm install
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY . .
RUN npm run build

# ==========================================
# Stage 2: Serve (Nginx)
# ==========================================
FROM nginx:alpine AS production-stage
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build-stage /app/dist /usr/share/nginx/html

# ⚠️ PWA: sw.js + manifest.json ต้องไม่ถูก cache (ไม่งั้น SW อัปเดตไม่ถึงเครื่องที่ติดตั้งแล้ว)
# ⚠️ SPA fallback ใช้ `try_files $uri /index.html` — ไม่ใช้ `$uri/` (กัน directory 403)
RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location = /sw.js { \
        add_header Cache-Control "no-cache, must-revalidate"; \
        try_files $uri =404; \
    } \
    location = /manifest.json { \
        add_header Cache-Control "no-cache"; \
        try_files $uri =404; \
    } \
    location / { \
        try_files $uri /index.html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
