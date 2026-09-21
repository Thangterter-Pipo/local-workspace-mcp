#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/python" ]; then
    echo "[CẢNH BÁO] Chưa tìm thấy môi trường .venv!"
    echo "Đang tự động chạy scripts/install.sh để thiết lập..."
    bash scripts/install.sh
fi

echo "Khởi động Local Workspace MCP (local)..."
exec .venv/bin/python run.py "$@"
