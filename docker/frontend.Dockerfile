# =========================================================================
# Frontend image — Next.js standalone
# =========================================================================
FROM node:20-alpine AS deps
WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000

# Run as non-root
RUN addgroup -S app && adduser -S app -G app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
USER app

EXPOSE 3000
CMD ["npm", "run", "start"]
