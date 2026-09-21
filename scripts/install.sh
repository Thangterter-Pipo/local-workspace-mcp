#!/usr/bin/env bash
set -e

# Chuyển về thư mục gốc của project
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "======================================================="
echo " Local Workspace MCP - Installation Script (macOS/Linux)"
echo "======================================================="

# Tìm Python 3
PY_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PY_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PY_CMD="python"
else
    echo "[ERROR] Không tìm thấy Python 3 trên hệ thống!"
    echo "Trên macOS: cài đặt qua Homebrew: 'brew install python'"
    exit 1
fi

echo "[1/4] Sử dụng Python hệ thống: $($PY_CMD --version)"

# Tạo venv
if [ ! -d ".venv" ]; then
    echo "[2/4] Đang khởi tạo virtual environment (.venv)..."
    "$PY_CMD" -m venv .venv
else
    echo "[2/4] Đã tìm thấy thư mục .venv sẵn có."
fi

# Activate venv & cài đặt
echo "[3/4] Đang kích hoạt .venv và nâng cấp pip..."
source .venv/bin/activate
pip install --upgrade pip

echo "[4/4] Đang cài đặt thư viện từ requirements.txt..."
pip install -r requirements.txt

echo ""
echo "======================================================="
echo " CÀI ĐẶT HOÀN TẤT THÀNH CÔNG!"
echo " - Chạy server trực tiếp: ./run.sh"
echo " - Chạy ngầm supervisor:  ./start_supervisor.sh"
echo "======================================================="
