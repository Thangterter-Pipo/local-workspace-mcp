# Local Workspace MCP 🖥️⚡

<p align="center">
  <b>Give ChatGPT Web full control over your local computer (Windows & macOS).</b><br>
  <i>Secure cross-platform Model Context Protocol (MCP) server empowering ChatGPT Web to inspect drives, read & edit files, execute terminal commands, and manage background processes directly from <a href="https://chatgpt.com">chatgpt.com</a>.</i>
</p>

<p align="center">
  <a href="#english-documentation">English</a> •
  <a href="#tiếng-việt">Tiếng Việt</a> •
  <a href="SETUP_WINDOWS.md">Setup Windows</a> •
  <a href="SETUP_MAC.md">Setup macOS</a> •
  <a href="docs/CHATGPT_SETUP.md">ChatGPT Setup Guide</a>
</p>

---

## English Documentation

### 1. Overview & The Problem Solved
By default, **ChatGPT Web** runs isolated in OpenAI's cloud environment. It has no access to your local machine, cannot see your drives, cannot edit project files in place, and cannot run terminal commands. Developers are forced to constantly copy and paste code back and forth.

**Local Workspace MCP** eliminates this friction. It implements the OpenAI Custom MCP Connector standard (OAuth 2.1 + PKCE + Dynamic Client Registration) to establish a secure, bidirectional bridge between **`chatgpt.com`** and your local operating system.

#### Key Features:
- **Full-Machine & Multi-Drive Access**:
  - **Windows**: Automatically detects and browses all drives (`C:\`, `D:\`, `E:\`...), verifies free space, and resolves Windows paths.
  - **macOS / Linux**: Full support for POSIX paths (`/Users/...`, `~/...`, `/Volumes/...` for external drives), and resolves relative paths against the current working directory.
- **Intelligent File & Code Editing**:
  - Read large files with offsets, search codebases with regex/ripgrep, patch lines, replace text blocks, and create directories.
  - Zip-slip protection ensures archives cannot extract files outside destination folders.
- **Terminal & Process Execution**:
  - Execute commands (`exec_command`) with timeout limits and output buffer caps.
  - Spawn long-running background processes (`process_manager`) with ring buffers for real-time monitoring and graceful termination.
- **Security & Privacy by Design**:
  - **OAuth 2.1 + PKCE with Owner Consent PIN**: When ChatGPT connects, you must enter your private `WORKSPACE_MCP_CONSENT_PIN` on the local `/consent` web page to authorize access.
  - **OS-Level Permissions (Current User ACLs)**: Runs under your user account with zero privilege escalation.
  - **Secret Redaction**: Environment variable inspection automatically masks tokens, keys, and passwords with `<redacted>`.
  - **Audit Logging**: All tool actions are recorded locally in `audit.jsonl` without logging sensitive file contents or secrets.

---

### 2. Architecture

```text
┌──────────────────────────────────────────────────────────┐
│                       chatgpt.com                        │
│             (ChatGPT Web Custom Connector)               │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTPS (OAuth 2.1 + PKCE)
                             ▼
┌──────────────────────────────────────────────────────────┐
│ Public HTTPS Tunnel (Cloudflare Quick Tunnel / ngrok /   │
│ SSH Reverse Tunnel)  e.g. https://mcp.yourdomain.com     │
└────────────────────────────┬─────────────────────────────┘
                             │ HTTP (Port 3080)
                             ▼
┌──────────────────────────────────────────────────────────┐
│                 Local Workspace MCP                      │
│  - FastMCP Streamable HTTP Engine (/mcp)                 │
│  - OAuth 2.1 & Web Consent Screen (/consent)             │
│  - Cross-Platform Path Normalizer (security/paths.py)    │
│  - Process Lifecycle Manager (services/process_manager)  │
│  - Local Audit Logger (security/audit.py)                │
└────────────────────────────┬─────────────────────────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
       Windows Desktop                  macOS Desktop
  - Drives: C:\, D:\, E:\...        - Mounts: /, /Users, /Volumes
  - Shell: PowerShell / cmd.exe     - Shell: /bin/zsh, /bin/bash
  - Processes: Win32 process group  - Processes: POSIX process group
```

---

### 3. Environment Variables (`.env`)

Copy `.env.example` to `.env` in the root folder:

| Variable | Required | Default | Description |
|---|:---:|:---:|---|
| `WORKSPACE_MCP_API_KEY` | **Yes** | - | Secret Bearer token for HTTP authentication. |
| `WORKSPACE_MCP_CONSENT_PIN` | **Yes** | - | Private PIN entered on `/consent` during ChatGPT Web pairing. |
| `PUBLIC_URL` | **Yes** (OAuth) | - | Public HTTPS URL (e.g. Cloudflare tunnel) required for ChatGPT OAuth discovery and callbacks. |
| `WORKSPACE_MCP_HOST` | No | `127.0.0.1` | Local bind address. |
| `WORKSPACE_MCP_PORT` | No | `3080` | Local port. |
| `WORKSPACE_MCP_ROOT` | No | Current dir | Default root workspace directory. |
| `COMMAND_TIMEOUT_SECONDS` | No | `120` | Max execution time per command. |
| `MAX_COMMAND_OUTPUT_MB` | No | `50` | Output buffer cap for commands. |
| `MAX_FILE_READ_MB` | No | `100` | Max size when reading single files. |

*(Legacy `FLOW_VEO_MCP_*` variable names remain supported as backward-compatible fallbacks).*

---

### 4. 3-Step Quick Start

#### On Windows
See detailed guide: [SETUP_WINDOWS.md](SETUP_WINDOWS.md).
```cmd
:: 1. Automated installation
scripts\install.bat

:: 2. Configure environment
copy .env.example .env

:: 3. Run server
run.bat
:: Or start as a persistent background supervisor:
start_supervisor.bat
```

#### On macOS
See detailed guide: [SETUP_MAC.md](SETUP_MAC.md).
```bash
# 1. Grant permissions and install
chmod +x scripts/*.sh *.sh
./scripts/install.sh

# 2. Configure environment
cp .env.example .env

# 3. Run server
./run.sh
# Or start as a persistent background supervisor:
./start_supervisor.sh
```

---

### 5. Connecting with ChatGPT Web

1. Open **[ChatGPT](https://chatgpt.com)** → Click your Profile (bottom left) → **Settings** → **Connected apps** / **Connectors**.
2. Click **Add connector (Custom MCP)**.
3. Fill in the connector details:
   - **Name**: `Local Workspace`
   - **Server URL**: `https://<your-public-url>/mcp`
   - **Authentication**: Select **OAuth** (Advanced options will automatically discover endpoints via `/.well-known/oauth-authorization-server`).
4. Click **Connect**. Your browser will open the `/consent` authorization page.
5. Enter your `WORKSPACE_MCP_CONSENT_PIN` (set in `.env`) and click **Authorize**.
6. ChatGPT will verify credentials and register all 65+ tools.
7. Open a new chat in ChatGPT, enable the **Local Workspace** connector, and prompt:
   > *"Check all available disk drives and list my current project folder."*

---

## Tiếng Việt

### 1. Giới thiệu & Vấn đề giải quyết
Mặc định, **ChatGPT Web** chạy hoàn toàn trên đám mây của OpenAI (`chatgpt.com`). Nó bị cô lập khỏi máy tính cá nhân của bạn: không thể đọc ổ đĩa, không thể mở file code trong máy, không thể chạy thử lệnh terminal và bạn phải liên tục copy/paste qua lại rất mất thời gian.

**Local Workspace MCP** ra đời để giải quyết triệt để vấn đề này. Dự án tuân thủ chuẩn Custom MCP Connector của OpenAI (OAuth 2.1 + PKCE + Dynamic Client Registration), đóng vai trò là cây cầu nối bảo mật 2 chiều biến ChatGPT Web thành một trợ lý kỹ thuật có thể trực tiếp thao tác trên máy tính của bạn.

#### Ưu điểm nổi bật:
- **Truy cập toàn diện hệ thống (Full-Machine)**:
  - **Windows**: Tự động nhận diện mọi ổ đĩa (`C:\`, `D:\`, `E:\`...), kiểm tra dung lượng trống, hỗ trợ đường dẫn Windows.
  - **macOS / Linux**: Nhận diện cây thư mục POSIX (`/Users/...`, `~/...`, `/Volumes/...` cho các ổ cứng gắn ngoài), tự động resolve đường dẫn tương đối (`.` hay thư mục con) theo thư mục làm việc hiện tại.
- **Thao tác đọc, sửa mã nguồn thông minh**:
  - Đọc file lớn theo phân trang, tìm kiếm mã nguồn bằng regex, vá từng dòng code (`patch_file`), thay thế khối văn bản (`replace_text`).
  - Kiểm tra chống Zip-Slip nghiêm ngặt khi giải nén tệp.
- **Thực thi dòng lệnh & Quản lý tiến trình ngầm**:
  - Chạy lệnh (`exec_command`) với cơ chế kiểm soát timeout và giới hạn bộ đệm output.
  - Quản lý các tác vụ dài hạn (`process_manager`) có bộ đệm vòng chống tràn RAM, tự động dọn dẹp sạch sẽ khi tắt server (không để lại tiến trình rác).
- **Bảo mật đa tầng**:
  - **Xác thực OAuth 2.1 + Consent PIN**: Khi ChatGPT kết nối, bạn phải nhập mã PIN riêng (`WORKSPACE_MCP_CONSENT_PIN`) trên trang xác thực `/consent` mới cấp quyền.
  - **Giữ nguyên quyền người dùng (User ACLs)**: Không nâng quyền, không bypass quyền hạn bảo mật của hệ điều hành.
  - **Ẩn thông tin nhạy cảm**: Công cụ đọc biến môi trường tự động ẩn các key, token, password nhạy cảm thành `<redacted>`.
  - **Nhật ký kiểm toán an toàn (`audit.jsonl`)**: Ghi lại mọi lệnh AI thực hiện trên máy mà không làm rò rỉ nội dung file hay secret.

---

### 2. Hướng dẫn thiết lập nhanh 3 bước

#### Dành cho Windows
Xem chi tiết tại [SETUP_WINDOWS.md](SETUP_WINDOWS.md).
1. Nhấp đúp hoặc chạy lệnh: `scripts\install.bat` (tự động tạo `.venv` và cài thư viện).
2. Sao chép `.env.example` thành `.env` và đặt `WORKSPACE_MCP_CONSENT_PIN` cùng `WORKSPACE_MCP_API_KEY`.
3. Mở public URL bằng Cloudflare Tunnel:
   ```cmd
   cloudflared tunnel --url http://127.0.0.1:3080
   ```
   Điền link tunnel vào `PUBLIC_URL` trong `.env`.
4. Chạy server: `run.bat` (hoặc chạy nền với `start_supervisor.bat`).

#### Dành cho macOS
Xem chi tiết tại [SETUP_MAC.md](SETUP_MAC.md).
1. Mở Terminal và chạy:
   ```bash
   chmod +x scripts/*.sh *.sh
   ./scripts/install.sh
   ```
2. Sao chép `.env.example` thành `.env` và cấu hình PIN/Key.
3. Mở tunnel và cập nhật `PUBLIC_URL` trong `.env`.
4. Chạy server: `./run.sh` (hoặc chạy nền với `./start_supervisor.sh`).

---

### 3. Kết nối với ChatGPT Web

1. Truy cập **[ChatGPT](https://chatgpt.com)** → Bấm vào Avatar tài khoản (góc dưới bên trái) → **Settings** → **Connected apps** (hoặc **Connectors**).
2. Bấm **Add connector (Custom MCP)**.
3. Điền thông số kết nối:
   - **Name**: `Local Workspace`
   - **Server URL**: `https://<link-cloudflare-tunnel-cua-ban>/mcp`
   - **Authentication**: Chọn **OAuth**.
4. Bấm **Connect**. Trình duyệt sẽ tự động mở trang web xác thực `/consent`.
5. Nhập mã PIN bạn đã đặt trong `WORKSPACE_MCP_CONSENT_PIN` và bấm **Authorize (Cho phép)**.
6. ChatGPT sẽ kết nối thành công và nạp hơn 65 công cụ. Mở một phiên chat mới, bật connector **Local Workspace** và bắt đầu trải nghiệm!

---

### 4. Kiểm thử tự động (Automated Testing)

Chạy bộ kiểm thử đa nền tảng để kiểm tra toàn vẹn mã nguồn:
```bash
python test/test_crossplatform.py
```
Bộ test tự động xác thực:
1. Cú pháp AST của toàn bộ mã nguồn Python.
2. Logic chuẩn hóa đường dẫn trên cả Windows và POSIX (macOS).
3. Nhận diện danh sách ổ đĩa và tính toán dung lượng (`get_roots`).
4. Tìm kiếm ứng dụng hệ thống (`which_command`).
5. Che giấu an toàn các biến môi trường nhạy cảm (`get_environment`).

---

## Giấy phép / License
Phát hành theo giấy phép mã nguồn mở MIT License. Tự do sử dụng, chỉnh sửa và đóng góp cho cộng đồng.
