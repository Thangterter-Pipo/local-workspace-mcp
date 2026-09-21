# Local Workspace MCP (Cross-Platform)

> **Máy chủ Model Context Protocol (MCP) đa nền tảng** dành cho **ChatGPT Web**, **Claude Code**, **Cursor** và các MCP client khác, hỗ trợ đầy đủ cả **Windows** và **macOS / Linux**.

---

## 1. Giới thiệu tổng quan

Local Workspace MCP cung cấp cho AI khả năng tương tác trực tiếp với toàn bộ máy tính (filesystem, command line, process manager, git, CDP browser) một cách an toàn, minh bạch và có kiểm soát, vận hành trực tiếp dưới quyền của tài khoản người dùng hiện tại (Current User ACLs).

### Điểm nổi bật
- **Hỗ trợ đa nền tảng (Cross-Platform)**:
  - **Windows**: Tự động nhận diện tất cả các ổ đĩa (`C:\`, `D:\`, `E:\`...), hỗ trợ PowerShell/CMD, đường dẫn Windows.
  - **macOS / Linux**: Hỗ trợ đường dẫn POSIX (`/Users/...`, `~/...`, `/Volumes/...`), shell Bash/Zsh.
- **Chuẩn giao thức FastMCP 3.x**:
  - Streamable HTTP tại `/mcp` với quản lý session stateful (`Mcp-Session-Id`).
  - Tích hợp chuẩn **OAuth 2.1 Authorization Code + PKCE** và **Dynamic Client Registration (DCR)** theo khuyến nghị của OpenAI cho Custom MCP Connectors.
  - Hỗ trợ bảo mật 2 lớp qua **Consent PIN** tại giao diện `/consent`.
- **Hệ thống hơn 65+ công cụ mạnh mẽ**:
  - Quản lý tệp & thư mục: Đọc, ghi, sửa phân đoạn (`patch_file`, `replace_text`, `insert_text`), tìm kiếm nội dung (ripgrep/regex), giải nén an toàn chống zip-slip.
  - Thực thi lệnh (`exec_command`): Thực thi bất kỳ CLI nào với timeout và giới hạn dung lượng output.
  - Quản lý tiến trình ngầm (`process_manager`): Bật tác vụ dài, theo dõi stdout/stderr bounded buffer, dừng tiến trình sạch sẽ khi tắt server.
  - Git & kiểm thử tự động: `git status`, `git diff`, `git log`, `run_pytest`, `run_python_script`.
  - CDP / Browser Automation: Điều khiển trình duyệt qua Chrome DevTools Protocol.

---

## 2. Kiến trúc hệ thống (Architecture)

```text
┌──────────────────────────────────────────────────────────┐
│             ChatGPT Web / Claude / Cursor               │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTPS (OAuth 2.1 / Bearer)
                             ▼
┌──────────────────────────────────────────────────────────┐
│ Public Endpoint (Cloudflare Tunnel / SSH Reverse / ngrok)│
│ e.g. https://mcp.yourdomain.com                          │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP (Port 3080)
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 Local Workspace MCP                       │
│  - FastMCP Streamable HTTP (/mcp)                        │
│  - OAuth Provider & Consent PIN (/authorize, /token)     │
│  - Path Normalizer (security/paths.py)                   │
│  - JSONL Audit Logger (security/audit.py)                │
│  - Process Manager (services/process_manager.py)         │
└────────────────────────────┬─────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
      Hệ điều hành Windows            Hệ điều hành macOS / Linux
  - Ổ đĩa: C:\, D:\, E:\...         - Đường dẫn: /, /Users, ~/
  - Shell: PowerShell / cmd.exe     - Shell: /bin/zsh, /bin/bash
  - Tiến trình: taskkill, Win32     - Tiến trình: POSIX signals
```

---

## 3. Cấu hình biến môi trường (`.env`)

Sao chép `.env.example` thành `.env` tại thư mục gốc của server và điền các thông tin:

| Biến môi trường | Bắt buộc | Mặc định | Mô tả |
|---|:---:|:---:|---|
| `WORKSPACE_MCP_API_KEY` | **Có** | - | Khóa API bí mật dùng xác thực Bearer token trên `/mcp` cho các MCP client (Claude, Cursor, curl). |
| `WORKSPACE_MCP_CONSENT_PIN` | **Có** | - | Mã PIN xác thực khi liên kết ChatGPT Web qua OAuth. Bạn nhập mã PIN này trên trang `/consent`. |
| `PUBLIC_URL` | **Có** (cho OAuth) | - | URL công khai của server (ví dụ: `https://mcp.yourdomain.com`). Bắt buộc cho ChatGPT OAuth callback. |
| `WORKSPACE_MCP_HOST` | Không | `127.0.0.1` | Địa chỉ IP server lắng nghe tại máy local. |
| `WORKSPACE_MCP_PORT` | Không | `3080` | Cổng HTTP của server. |
| `ALLOWED_ROOTS` | Không | Cwd | Giới hạn thư mục được phép thao tác. Để trống để nhận diện theo thư mục làm việc hiện tại. |
| `COMMAND_TIMEOUT_SECONDS` | Không | `120` | Giới hạn thời gian tối đa cho mỗi lệnh `exec_command` (giây). |
| `MAX_COMMAND_OUTPUT_MB` | Không | `50` | Giới hạn dung lượng output tối đa cho mỗi lệnh (MB). |
| `MAX_FILE_READ_MB` | Không | `100` | Giới hạn dung lượng tối đa khi đọc tệp (MB). |
| `WORKSPACE_MCP_SSH_HOST` | Không | - | Tùy chọn SSH host nếu dùng tính năng tự động mở SSH reverse tunnel trong supervisor. |

---

## 4. An toàn & Bảo mật (Security Model)

1. **Phân quyền cấp hệ điều hành (No Privilege Escalation)**:
   - Server chạy dưới quyền của tài khoản người dùng hiện tại; OS sẽ từ chối nếu thao tác vượt quá quyền hạn (ACLs).
2. **Chuẩn hóa đường dẫn & chống Zip-Slip**:
   - Mọi đường dẫn đều được chuẩn hóa qua `security/paths.py`, triệt tiêu `..`, NUL bytes và các tên thiết bị cấm trên Windows (`CON`, `PRN`, `AUX`, `NUL`...).
   - Giải nén file nén kiểm tra nghiêm ngặt đích đến, ngăn chặn ghi đè ra ngoài thư mục cho phép.
3. **Nhật ký kiểm toán an toàn (JSONL Audit Log)**:
   - Mọi thao tác công cụ đều được ghi nhận vào `audit.jsonl` (Windows: `%LOCALAPPDATA%\LocalWorkspaceMCP\audit.jsonl`, macOS: `~/.local_workspace_mcp/audit.jsonl`).
   - Tự động lọc bỏ bí mật, token, mật khẩu; không ghi nội dung file hay thông tin nhạy cảm vào log.
4. **Dọn dẹp tiến trình (Clean Shutdown)**:
   - Khi server hoặc supervisor dừng, toàn bộ tiến trình con đang chạy ngầm sẽ được dọn dẹp để tránh tiến trình mồ côi (zombies).

---

## 5. Khởi động nhanh (Quick Start)

### Trên Windows
Xem chi tiết tại [SETUP_WINDOWS.md](SETUP_WINDOWS.md).
```cmd
:: 1. Chạy script cài đặt tự động
scripts\install.bat

:: 2. Tạo cấu hình .env
copy .env.example .env

:: 3. Khởi động server
run.bat
:: Hoặc chạy ngầm vĩnh viễn với supervisor:
start_supervisor.bat
```

### Trên macOS
Xem chi tiết tại [SETUP_MAC.md](SETUP_MAC.md).
```bash
# 1. Cấp quyền và chạy cài đặt
chmod +x scripts/*.sh *.sh
./scripts/install.sh

# 2. Tạo cấu hình .env
cp .env.example .env

# 3. Khởi động server
./run.sh
# Hoặc chạy ngầm vĩnh viễn với supervisor:
./start_supervisor.sh
```

---

## 6. Hướng dẫn kết nối Client

### A. Kết nối với ChatGPT Web (Custom MCP Connector)

1. Mở **ChatGPT Web** → vào **Settings** → **Connected apps** / **Connectors** → Chọn **Add connector (Custom MCP)**.
2. Nhập thông tin:
   - **Name**: `Local Workspace`
   - **Server URL**: `https://<ten-mien-cua-ban>/mcp`
   - **Authentication**: Chọn **OAuth** → chọn Advanced nếu cần xem endpoint. Server tự quảng bá metadata tại `/.well-known/oauth-authorization-server`.
3. Nhấn **Connect**. Trình duyệt sẽ mở trang `/consent`. Nhập mã `WORKSPACE_MCP_CONSENT_PIN` đã thiết lập trong `.env` và bấm **Authorize**.
4. ChatGPT hoàn tất xác thực và quét được toàn bộ hơn 65 công cụ. Mở đoạn chat mới và yêu cầu:
   > *"Kiểm tra danh sách ổ đĩa và thư mục trên máy tính của tôi."*

### B. Kết nối với Claude Code

```bash
claude mcp add --transport http local-workspace https://<ten-mien-cua-ban>/mcp \
  --header "Authorization: Bearer <WORKSPACE_MCP_API_KEY>"
```

### C. Kết nối với Cursor

Thêm vào cấu hình MCP trong settings của Cursor (`cursor-settings`):
```json
{
  "mcpServers": {
    "local-workspace": {
      "url": "https://<ten-mien-cua-ban>/mcp",
      "headers": {
        "Authorization": "Bearer <WORKSPACE_MCP_API_KEY>"
      }
    }
  }
}
```

---

## 7. Kiểm thử tự động (Testing)

Chạy bộ test đa nền tảng để kiểm tra toàn vẹn mã nguồn:
```bash
# Chạy bộ test cross-platform
python test/test_crossplatform.py
```
Bộ test tự động kiểm tra cú pháp AST toàn bộ codebase, logic chuẩn hóa đường dẫn Windows/POSIX, danh sách ổ đĩa `get_roots()` và định vị lệnh `which_command()`.
