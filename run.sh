#!/usr/bin/env bash
set -euo pipefail

# ── Anqush — one command to start everything ────────────────────────────────
# Usage:
#   ./run.sh              — start server + dashboard
#   ./run.sh --build      — force rebuild before starting
#   ./run.sh --help       — show this help

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

help() {
  sed -n '3,6p' "$0"
  exit 0
}

# ── Parse args ──────────────────────────────────────────────────────────────
BUILD_FLAG=""
for arg in "$@"; do
  case "$arg" in
    --build) BUILD_FLAG="--build" ;;
    --help|-h) help ;;
  esac
done

# ── Check Docker ────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "❌ Docker is not installed."
  echo "   Install it: https://docs.docker.com/engine/install/"
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "❌ docker compose (v2) is required."
  echo "   Install it: https://docs.docker.com/compose/install/"
  exit 1
fi

# ── Start ────────────────────────────────────────────────────────────────────
echo "▸ Starting Anqush..."
docker compose up $BUILD_FLAG -d

# ── Wait for server health ───────────────────────────────────────────────────
echo "▸ Waiting for server to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo "  ✓ Server ready"
    break
  fi
  sleep 1
done

# ── Show URLs ────────────────────────────────────────────────────────────────
echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │  Anqush is running                           │"
echo "  │                                              │"
echo "  │  Dashboard →  http://localhost:8080           │"
echo "  │  API        →  http://localhost:8000          │"
echo "  │  Health     →  http://localhost:8000/health   │"
echo "  │                                              │"
echo "  │  Stop with:  docker compose down              │"
echo "  └──────────────────────────────────────────────┘"
echo ""

# ── Setup demo agent ────────────────────────────────────────────────────────
echo "▸ Setting up demo agent..."
curl -sf -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{"id":"demo","name":"Demo Agent","max_session_cost":5.0}' \
  >/dev/null 2>&1 && echo "  ✓ Demo agent registered (budget: \$5.00/session)" || echo "  - Agent already exists"

echo ""
echo "  Try it:  curl http://localhost:8000/api/agents"
echo ""
