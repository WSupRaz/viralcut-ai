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

COPY apps/render-worker/package.json apps/render-worker/package-lock.json ./
RUN npm ci --omit=dev

COPY apps/render-worker ./

EXPOSE 3001

CMD ["node", "dist/render.js"]
