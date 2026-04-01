#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
RELOAD=""
for arg in "$@"; do
  case $arg in
    --reload) RELOAD="--reload" ;;
    --port=*) PORT="${arg#*=}" ;;
    --host=*) HOST="${arg#*=}" ;;
  esac
done

# ── Dependencies ──────────────────────────────────────────────────────────────
if ! python3 -c "import fastapi, uvicorn, jinja2, apscheduler" 2>/dev/null; then
  echo "Installing Python dependencies..."
  if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
  .venv/bin/pip install -r requirements.txt -q
  echo "Dependencies installed."
  exec .venv/bin/uvicorn app:app --host "$HOST" --port "$PORT" $RELOAD
fi

# ── htmx ──────────────────────────────────────────────────────────────────────
HTMX="static/js/htmx.min.js"
if [ ! -s "$HTMX" ]; then
  echo "Downloading htmx..."
  curl -sL https://unpkg.com/htmx.org@1.9.12/dist/htmx.min.js -o "$HTMX" \
    && echo "htmx downloaded." \
    || echo "⚠️  htmx download failed — live updates disabled."
fi

# ── Launch ────────────────────────────────────────────────────────────────────
echo ""
echo "  ⚔️  Family Quest"
echo "  ─────────────────────────────"
echo "  Dashboard : http://$HOST:$PORT/"
echo "  Admin     : http://$HOST:$PORT/admin"
echo "  Log       : http://$HOST:$PORT/log"
echo "  ─────────────────────────────"
echo ""

UVICORN="uvicorn"
[ -f ".venv/bin/uvicorn" ] && UVICORN=".venv/bin/uvicorn"
exec $UVICORN app:app --host "$HOST" --port "$PORT" $RELOAD
