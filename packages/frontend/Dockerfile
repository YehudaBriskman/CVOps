# ── build ────────────────────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json .
RUN npm install
COPY . .
RUN npm run build

# ── development target ───────────────────────────────────────────────────
FROM node:20-alpine AS development
WORKDIR /app
COPY package.json .
RUN npm install
EXPOSE 5173

# ── production ───────────────────────────────────────────────────────────
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
