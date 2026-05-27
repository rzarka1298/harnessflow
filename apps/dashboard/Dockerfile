# syntax=docker/dockerfile:1
# Multi-stage build for the HarnessFlow Next.js dashboard.
#
# Relies on `output: 'standalone'` in next.config.ts (see that file for
# why) so the runtime stage only carries the minimal server bundle, not
# the monorepo node_modules tree.

# ---- deps ------------------------------------------------------------
# Install production deps once; cached unless package.json/pnpm-lock change.
FROM node:22-alpine AS deps
RUN apk add --no-cache libc6-compat
RUN corepack enable pnpm
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# ---- build -----------------------------------------------------------
FROM node:22-alpine AS build
RUN corepack enable pnpm
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# next.config.ts sets output: 'standalone'; build emits .next/standalone
# + .next/static which the runtime stage consumes.
RUN pnpm build

# ---- runtime ---------------------------------------------------------
FROM node:22-alpine AS runtime
WORKDIR /app

# Run as a non-root user. Next's standalone server reads from the cwd, so
# we just chown everything we copy in.
RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 --ingroup nodejs nextjs

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

# The standalone bundle places `server.js` at the project root.
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=build --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
