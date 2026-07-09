#!/bin/zsh
# Start backend + web for E2E testing.
# Usage:  ./scripts/dev-up.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env from apps/backend
if [[ -f "$ROOT/apps/backend/.env" ]]; then
  set -a
  source "$ROOT/apps/backend/.env"
  set +a
fi

export API_TOKEN="${API_TOKEN:-changeme}"
export NEXT_PUBLIC_API_TOKEN="$API_TOKEN"

echo "Starting backend on :8800…"
(cd "$ROOT/apps/backend" && ./.venv/bin/uvicorn ragcore.api.app:app --host 127.0.0.1 --port 8800) &
BACKEND_PID=$!

sleep 2

echo "Starting web on :3000…"
(cd "$ROOT/apps/web" && pnpm dev) &
WEB_PID=$!

trap "echo 'Stopping…'; kill $BACKEND_PID $WEB_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "Backend: http://127.0.0.1:8800"
echo "Web:     http://127.0.0.1:3000"
echo "Token:   $API_TOKEN"
echo ""
echo "Press Ctrl-C to stop."
wait
