#!/usr/bin/env bash
# Generates the test videos used by the E2E suites. Runs ffmpeg inside the
# worker container (the only place guaranteed to have it) and copies the
# results to tests/e2e/artifacts/.
#
# Produces:
#   ci-real.mp4           small real clip whose proxy transcode succeeds
#   ci-upload-100mb.mp4   ~100 MB file (real header + padding) for the
#                         browser resume test, which only exercises upload
#                         mechanics, not processing
set -euo pipefail
# this file lives at tests/e2e/scripts/ -> repo root is three levels up
cd "$(dirname "$0")/../../.."

mkdir -p tests/e2e/artifacts
COMPOSE=(docker compose -f infra/docker-compose.dev.yml)

echo "> generating real clip..."
"${COMPOSE[@]}" exec -T worker sh -c 'ffmpeg -y -loglevel error -f lavfi -i testsrc=duration=20:size=640x360:rate=30 -f lavfi -i sine=frequency=440:duration=20 -c:v libx264 -preset ultrafast -pix_fmt yuv420p -c:a aac -shortest /tmp/ci-real.mp4'
"${COMPOSE[@]}" cp worker:/tmp/ci-real.mp4 tests/e2e/artifacts/ci-real.mp4

echo "> generating 100 MB padded file..."
"${COMPOSE[@]}" exec -T worker sh -c 'ffmpeg -y -loglevel error -f lavfi -i testsrc=duration=10:size=640x360:rate=30 -c:v libx264 -preset ultrafast -pix_fmt yuv420p /tmp/ci-base.mp4 && dd if=/dev/zero bs=1M count=100 >> /tmp/ci-base.mp4'
"${COMPOSE[@]}" cp worker:/tmp/ci-base.mp4 tests/e2e/artifacts/ci-upload-100mb.mp4

echo "> artifacts:"
ls -la tests/e2e/artifacts/
