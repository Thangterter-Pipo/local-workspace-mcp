# Hướng dẫn thiết lập Local Workspace MCP trên macOS

> Hướng dẫn thiết lập chuẩn hóa chỉ trong 3 bước trên môi trường **macOS (Apple Silicon M1/M2/M3/M4 & Intel)**.

---

## ⚡ 3 Bước thiết lập siêu tốc

### Bước 1: Chuẩn bị môi trường Terminal & Cài đặt tự động
1. Mở ứng dụng **Terminal** trên máy Mac.
2. Nếu máy chưa có Python 3 hoặc Homebrew, cài đặt nhanh qua lệnh:
   ```bash
   # Cài đặt Homebrew (nếu chưa có)
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

   # Cài đặt Python 3 và cloudflared
   brew install python cloudflared
   ```
3. Di chuyển vào thư mục dự án, cấp quyền thực thi và chạy script cài đặt tự động:
   ```bash
   cd /path/to/local-workspace-mcp
   chmod +x scripts/*.sh *.sh
   ./scripts/install.sh
   ```
   Script sẽ tự động khởi tạo môi trường ảo `.venv`, nâng cấp `pip` và cài đặt đầy đủ các thư viện phụ thuộc (`fastmcp`, `uvicorn`, `python-dotenv`).

---

### Bước 2: Cấu hình file `.env` & Cấp quyền macOS
1. Sao chép file `.env.example` thành `.env`:
   ```bash
   cp .env.example .env
   ```
2. Mở file `.env` và chỉnh sửa các thông số:
   ```ini
   # 1. Khóa API cho Claude / Cursor / CLI client
   WORKSPACE_MCP_API_KEY=tao_mot_chuoi_bi_mat_ngau_nhien_tai_day

   # 2. Mã PIN xác thực khi liên kết ChatGPT qua OAuth (/consent)
   WORKSPACE_MCP_CONSENT_PIN=123456

   # 3. Domain công khai sau khi mở tunnel ra Internet (xem Bước 3)
   PUBLIC_URL=https://mcp.yourdomain.com
   ```

3. **Cấp quyền truy cập tệp trên macOS (Tùy chọn nhưng khuyến nghị)**:
   Để server có thể đọc và ghi tệp tin khắp hệ thống (ngoài thư mục Downloads/Documents mặc định):
   - Mở **System Settings** (Cài đặt hệ thống) → **Privacy & Security** (Quyền riêng tư & Bảo mật).
   - Chọn mục **Full Disk Access** (Truy cập toàn phần vào đĩa).
   - Bật cấp quyền cho ứng dụng **Terminal** (hoặc iTerm2).

---

### Bước 3: Khởi động Server & Kết nối ChatGPT Web

#### 1. Khởi động Server
Bạn có thể chọn 1 trong 2 cách chạy:
- **Cách A (Chạy trực tiếp xem log console)**:
  ```bash
  ./run.sh
  ```
- **Cách B (Chạy ngầm vĩnh viễn với Supervisor qua nohup)**:
  ```bash
  ./start_supervisor.sh
  ```

#### 2. Mở Public Tunnel ra Internet
Mở một tab Terminal mới để tạo đường truyền bảo mật công khai cho ChatGPT truy cập cổng `3080`:

- **Sử dụng Cloudflare Quick Tunnel (Miễn phí, không cần tài khoản)**:
  ```bash
  cloudflared tunnel --url http://127.0.0.1:3080
  ```
  Terminal sẽ in ra đường link dạng: `https://xxxx.trycloudflare.com`.
  *Lưu ý:* Cập nhật link này vào `PUBLIC_URL` trong file `.env`.

- **Hoặc sử dụng ngrok**:
  ```bash
  ngrok http 3080
  ```

#### 3. Kết nối trên ChatGPT Web
1. Truy cập **ChatGPT Web** → vào **Settings** → **Connected apps** / **Connectors** → **Add connector (Custom MCP)**.
2. Đặt tên connector: **`Local Workspace`**.
3. Nhập URL: `https://xxxx.trycloudflare.com/mcp` (hoặc domain riêng của bạn).
4. Chọn kiểu xác thực **OAuth**.
5. Trình duyệt tự mở trang xác thực `/consent`, bạn nhập mã `WORKSPACE_MCP_CONSENT_PIN` đã đặt ở Bước 2 rồi bấm **Cho phép (Authorize)**.
6. Tạo một phiên chat mới và bắt đầu trải nghiệm!

---

## 🛠 Quản lý & Giám sát trên macOS

Khi chạy ngầm bằng `./start_supervisor.sh`, bạn có thể điều khiển supervisor bằng các lệnh:

- **Kiểm tra trạng thái server**:
  ```bash
  .venv/bin/python start_mcp.py status
  ```
- **Dừng server và supervisor**:
  ```bash
  .venv/bin/python start_mcp.py stop
  ```
- **Xem nhật ký hoạt động (Logs)**:
  - Thư mục log: `~/.local_workspace_mcp/`
  - Xem log server trực tiếp: `tail -f ~/.local_workspace_mcp/server.log`
  - Xem log supervisor: `tail -f ~/.local_workspace_mcp/supervisor.log`
  - Nhật ký gọi công cụ: `cat ~/.local_workspace_mcp/audit.jsonl`
