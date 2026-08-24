FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE=http://localhost:8010
ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
# next.config.ts uses output:"export" (needed for Tauri desktop packaging),
# so there is no Next server to run — serve the static export instead.
RUN npm i -g serve@14
COPY --from=builder /app/out ./out

EXPOSE 3000

CMD ["serve", "-s", "out", "-l", "3000"]
