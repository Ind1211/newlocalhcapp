# Build stage — compiles the React app. Vite env vars are baked in at BUILD time,
# not read at container runtime, which is why these are ARGs (set via docker-compose
# build args) rather than plain environment variables on the final image.
FROM node:20-slim AS build
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# VITE_API_URL is deliberately empty — nginx (in the serve stage below) reverse-proxies
# /api and /health to the backend container, so the frontend just calls relative paths
# like /api/patients. That works identically whether the page is loaded from
# localhost, a LAN IP, or a shared ngrok URL — no rebuild needed per environment,
# and no CORS to configure, since it's all same-origin from the browser's perspective.
ARG VITE_API_URL=""
ARG VITE_AUTH0_DOMAIN
ARG VITE_AUTH0_CLIENT_ID
ARG VITE_AUTH0_AUDIENCE
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_AUTH0_DOMAIN=$VITE_AUTH0_DOMAIN
ENV VITE_AUTH0_CLIENT_ID=$VITE_AUTH0_CLIENT_ID
ENV VITE_AUTH0_AUDIENCE=$VITE_AUTH0_AUDIENCE

RUN npm run build

# Serve stage — just nginx + the static build output, nothing else.
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
