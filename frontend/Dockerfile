# Recovery Orchestrator -- Frontend Dockerfile
#
# NOT BUILT OR RUN in the sandbox that authored this repository (no
# Docker daemon was available there). The Vite build itself WAS run
# and verified in-sandbox (npx vite build succeeded cleanly), but the
# containerized build/serve has not been executed end to end -- run
# `docker compose up` yourself to confirm.

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

# VITE_API_KEY is baked into the static bundle at build time (see
# src/services/api.ts's security tradeoff note -- this is a known,
# documented limitation for this MVP, not appropriate for a public
# production deployment).
ARG VITE_API_KEY=""
ENV VITE_API_KEY=${VITE_API_KEY}

RUN npm run build

FROM nginx:1.27-alpine AS serve

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://localhost:80/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
