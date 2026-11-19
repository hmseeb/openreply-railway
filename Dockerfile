FROM node:22-bookworm-slim AS build

ARG OPENREPLY_COMMIT=c78b2d2f68c9764ef7a7dde51dfa5bfa99304a09
LABEL org.opencontainers.image.source="https://github.com/hmseeb/openreply-railway"
LABEL org.opencontainers.image.revision="${OPENREPLY_COMMIT}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl openssl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN curl -fsSL "https://github.com/diwenne/openreply/archive/${OPENREPLY_COMMIT}.tar.gz" \
    | tar -xz --strip-components=1
RUN npm ci

ENV NEXT_TELEMETRY_DISABLED=1 \
    DATABASE_URL=postgresql://postgres:postgres@localhost:5432/openreply \
    REDIS_URL=redis://localhost:6379 \
    NEXTAUTH_URL=http://localhost:3000 \
    NEXTAUTH_SECRET=build-only-secret-replaced-at-runtime \
    CRON_SECRET=build-only-secret-replaced-at-runtime \
    ENCRYPTION_KEY=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef \
    INSTAGRAM_APP_ID=build-only \
    INSTAGRAM_APP_SECRET=build-only \
    FACEBOOK_APP_SECRET=build-only \
    WEBHOOK_VERIFY_TOKEN=build-only
RUN npm run build

FROM node:22-bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssl wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000

COPY --from=build --chown=node:node /app /app
COPY --chown=node:node boot.sh /usr/local/bin/boot.sh
RUN chmod 755 /usr/local/bin/boot.sh

USER node
EXPOSE 3000
CMD ["/usr/local/bin/boot.sh", "web"]
