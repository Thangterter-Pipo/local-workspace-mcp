# Hướng dẫn thiết lập Local Workspace MCP trên Windows

> Hướng dẫn thiết lập nhanh gọn chỉ trong 3 bước trên môi trường **Windows 10 / 11**.

---

## ⚡ 3 Bước thiết lập siêu tốc

### Bước 1: Cài đặt môi trường tự động
1. Đảm bảo máy tính đã cài đặt **Python 3.10+** từ [python.org](https://www.python.org/downloads/) (lưu ý tick chọn checkbox **"Add Python to PATH"** khi cài đặt).
2. Chạy script cài đặt tự động bằng cách mở Terminal hoặc double-click vào:
   ```cmd
   scripts\install.bat
   ```
   Script sẽ tự động khởi tạo môi trường ảo `.venv`, nâng cấp `pip` và cài đặt đầy đủ các thư viện phụ thuộc (`fastmcp`, `uvicorn`, `python-dotenv`).

---

### Bước 2: Thiết lập file cấu hình `.env`
1. Sao chép file `.env.example` thành `.env`:
   ```cmd
   copy .env.example .env
   ```
2. Mở file `.env` bằng Notepad hoặc VS Code và cập nhật tối thiểu 3 thông số:
   ```ini
   # 1. Khóa API cho Claude / Cursor / CLI client
   WORKSPACE_MCP_API_KEY=tao_mot_chuoi_bi_mat_ngau_nhien_tai_day

   # 2. Mã PIN bảo mật để chủ máy duyệt cấp quyền khi ChatGPT kết nối
   WORKSPACE_MCP_CONSENT_PIN=123456

   # 3. Domain công khai sau khi mở tunnel ra Internet (xem Bước 3)
   PUBLIC_URL=https://mcp.yourdomain.com
   ```

---

### Bước 3: Khởi động Server và kết nối ChatGPT Web

#### 1. Khởi động Server
Bạn có thể chọn 1 trong 2 cách chạy:
- **Cách A (Chạy trực tiếp xem log console)**:
  ```cmd
  run.bat
  ```
- **Cách B (Chạy ngầm vĩnh viễn với Supervisor)**:
  ```cmd
  start_supervisor.bat
  ```
  *(Supervisor sẽ tự khởi động lại server nếu bị crash).*

#### 2. Đưa Server ra Internet (Tunnel)
ChatGPT Web cần một địa chỉ HTTPS công khai để kết nối đến cổng `3080` trên máy của bạn. Bạn có thể sử dụng **Cloudflare Quick Tunnel** cực kỳ tiện lợi:
```cmd
cloudflared tunnel --url http://127.0.0.1:3080
```
Lấy địa chỉ domain dạng `https://xxx.trycloudflare.com` được in ra và cập nhật vào `PUBLIC_URL` trong `.env`.

#### 3. Kết nối trên ChatGPT Web
1. Truy cập **ChatGPT** → **Settings** → **Connected apps** / **Connectors** → **Add connector (Custom MCP)**.
2. Đặt tên connector: **`Local Workspace`**.
3. Nhập URL: `https://xxx.trycloudflare.com/mcp`.
4. Chọn kiểu xác thực **OAuth**.
5. Trình duyệt tự mở trang `/consent`, bạn gõ mã `WORKSPACE_MCP_CONSENT_PIN` đã đặt ở Bước 2 rồi bấm **Cho phép (Authorize)**.
6. Tạo đoạn chat mới và bắt đầu ra lệnh cho ChatGPT!

---

## 🛠 Quản lý & Giám sát trên Windows

Khi sử dụng `start_supervisor.bat`, bạn quản lý tiến trình bằng các lệnh sau:

- **Kiểm tra trạng thái server**:
  ```cmd
  .venv\Scripts\python.exe start_mcp.py status
  ```
- **Dừng server và supervisor**:
  ```cmd
  .venv\Scripts\python.exe start_mcp.py stop
  ```
- **Vị trí file Log & Audit**:
  - Thư mục log: `%LOCALAPPDATA%\LocalWorkspaceMCP\`
  - Log server: `%LOCALAPPDATA%\LocalWorkspaceMCP\server.log`
  - Log giám sát: `%LOCALAPPDATA%\LocalWorkspaceMCP\supervisor.log`
  - Nhật ký thao tác công cụ: `%LOCALAPPDATA%\LocalWorkspaceMCP\audit.jsonl`
