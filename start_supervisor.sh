#!/usr/bin/env bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".venv/bin/python" ]; then
    echo "[CẢNH BÁO] Chưa tìm thấy .venv! Vui lòng chạy ./scripts/install.sh trước."
    exit 1
fi

echo "Đang khởi động Local Workspace MCP Supervisor chạy ngầm..."
nohup .venv/bin/python start_mcp.py "$@" >/dev/null 2>&1 &
PID=$!
echo "Supervisor đã được khởi động ngầm (PID: $PID)."
echo "- Kiểm tra trạng thái: .venv/bin/python start_mcp.py status"
echo "- Dừng supervisor:     .venv/bin/python start_mcp.py stop"
echo "- Thư mục log tại:     ~/.local_workspace_mcp"
