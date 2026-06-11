# ── build ────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# ── development target ───────────────────────────────────────────────────
# node:20-alpine ships with a built-in `node` user (UID 1000); drop privileges.
FROM node:20-alpine AS development
WORKDIR /app
COPY --chown=node:node package.json .
RUN npm install && chown -R node:node /app
USER node
EXPOSE 5173

# ── production ───────────────────────────────────────────────────────────
# bitnami/nginx runs as UID 1001 and listens on 8080 (non-privileged port).
# Static SPA assets are served out of /app — bitnami's default document root.
FROM bitnami/nginx:1.27 AS production
COPY --from=build /app/dist /app
EXPOSE 8080
