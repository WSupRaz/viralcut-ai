FROM node:20-bookworm-slim AS base

# Remotion's headless Chromium render needs these system libs (ADR-0003)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# @viralcut/edit-plan-schema is a local `file:../../packages/edit-plan-schema/node`
# dependency -- must exist at that relative path before `npm install` can resolve it.
COPY packages/edit-plan-schema/node ./packages/edit-plan-schema/node
COPY apps/render-worker ./apps/render-worker

WORKDIR /app/apps/render-worker
RUN npm install

# Bake the headless Chromium download into the image layer (cached) instead
# of downloading it on the first production render.
RUN npx tsx scripts/ensure-browser.mjs

EXPOSE 3001

# Runs via tsx (a runtime dependency here, not just a dev tool) rather than a
# separate tsc-compile step -- this is the exact path verified locally, and
# avoids a second, untested code path where compiled dist/server.js would
# need to resolve its Remotion entry point by a different file extension
# than the source does.
#
# Persistent HTTP service (POST /render), invoked by the Python render
# orchestration task -- not a CLI tool anymore now that there's a real
# cross-service caller (task 13). `render.ts` still exists as a standalone
# CLI entrypoint for local debugging (`npm run render -- --input=... ...`).
CMD ["npx", "tsx", "src/server.ts"]
