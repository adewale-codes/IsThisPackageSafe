# Build context is ./web (see docker-compose.yml)

# ---- builder ----
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# NEXT_PUBLIC_* vars are inlined into the JS bundle at build time, so this
# has to be a build ARG rather than a runtime env var. It's the app's only
# NEXT_PUBLIC_* var (see web/app/layout.tsx) - used for absolute OG image
# URLs, so it should be the URL a browser (or Slack/X unfurling a link) can
# actually reach, not the in-network service name.
ARG NEXT_PUBLIC_SITE_URL=http://localhost:3000
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL

RUN npm run build

# ---- runner ----
FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

EXPOSE 3000

CMD ["npm", "start"]
