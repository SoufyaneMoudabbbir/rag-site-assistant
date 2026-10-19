#!/usr/bin/env bash
# Deploy the latest code from GitHub: run on the server from the repository folder.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up -d --build
docker image prune -f
docker compose ps
