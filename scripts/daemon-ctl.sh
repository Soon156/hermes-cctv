#!/usr/bin/env bash
# Hermes CCTV — daemon control (restart / update)
# Called by the Hermes skill when user sends /cctv restart or /cctv update.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ACTION="${1:-}"

usage() {
    echo "Usage: daemon-ctl.sh [restart|update]"
    exit 1
}

case "$ACTION" in
    restart)
        bash "$PROJECT_DIR/hermes-cctv" restart
        ;;
    update)
        echo "Pulling latest changes..."
        cd "$PROJECT_DIR"
        git pull 2>&1 || { echo "git pull failed"; exit 1; }
        echo ""
        echo "Reinstalling dependencies..."
        if [ -f "$PROJECT_DIR/venv/bin/pip" ]; then
            "$PROJECT_DIR/venv/bin/pip" install -q -e "$PROJECT_DIR" 2>&1 || true
        fi
        echo ""
        bash "$PROJECT_DIR/hermes-cctv" restart
        ;;
    *)
        usage
        ;;
esac
