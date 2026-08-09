#!/usr/bin/env bash
# One command to run both backend and frontend locally.
# First run sets up the venv / npm install automatically; later runs skip that.
# Ctrl+C stops both.
set -e -m  # job control (-m) so each service gets its own process group;
           # needed so Ctrl+C can kill "npm run dev" AND the "next dev" child it spawns.
cd "$(dirname "$0")"

# If a previous run wasn't stopped cleanly (closed terminal instead of Ctrl+C,
# crashed, etc.) its server keeps serving stale code on these ports while a
# new run silently falls back to 3001/8001 — so localhost:3000 looks "stuck"
# on old code with no indication why. Free the expected ports first so every
# run is self-healing.
free_port() {
  local port="$1"
  local pids
  pids=$(lsof -ti "tcp:${port}" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Port ${port} was still in use (leftover from a previous run) — stopping it..."
    kill -9 $pids 2>/dev/null || true
    sleep 1
  fi
}
free_port 8000
free_port 3000

echo "==> Backend"
(
  cd backend
  if [ ! -d ".venv" ]; then
    echo "First run: creating venv + installing backend deps..."
    python3 -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install -q -e ".[dev]"
  else
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
  [ -f .env ] || cp .env.example .env
  exec uvicorn app.main:app --reload
) &
BACKEND_PID=$!

echo "==> Frontend"
(
  cd frontend
  if [ ! -d "node_modules" ]; then
    echo "First run: npm install..."
    npm install
  fi
  [ -f .env.local ] || cp .env.local.example .env.local
  exec npm run dev
) &
FRONTEND_PID=$!

trap 'echo; echo "Stopping..."; kill -TERM -$BACKEND_PID -$FRONTEND_PID 2>/dev/null; wait' INT TERM

echo
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop both."
echo

wait
