#!/usr/bin/env bash
set -e

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo "Starting backend on http://localhost:5000 ..."
python3 run.py &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:5173 ..."
npm run dev &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
