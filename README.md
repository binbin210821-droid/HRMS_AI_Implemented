# WorkMind

Hệ thống quản lý hiệu suất nhân viên và cảnh báo quá tải, gồm FastAPI + MongoDB Replica Set ở backend và React/Vite ở frontend.

## 1. Yêu cầu môi trường

- Windows 10/11.
- Docker Desktop đang chạy và lệnh `docker compose` có trong PATH.
- Python 3.13 trở lên.
- Node.js và npm.
- Git (khuyến nghị).

## 2. Cấu hình biến môi trường

Mở PowerShell tại thư mục dự án:

```powershell
Copy-Item .env.example .env
```

Các biến chính:

- `MONGO_URI`: mặc định kết nối MongoDB Replica Set `rs0` ở cổng 27017.
- `DATABASE_NAME`: tên database, mặc định `hrms`.
- `JWT_SECRET`: thay bằng chuỗi bí mật riêng khi chạy ngoài máy cá nhân.
- `AI_API_KEY`: để trống thì Trợ lý AI trả thông báo an toàn bằng tiếng Việt; không làm ảnh hưởng các module khác.
- `AI_PROVIDER`, `AI_FALLBACK_PROVIDER`, `AI_MODEL`: provider chính, provider dự phòng và model tương ứng.
- `CORS_ORIGINS`: địa chỉ frontend, mặc định `http://localhost:5173`.
- `STORAGE_INTERNAL_ENDPOINT_URL`: endpoint MinIO/S3 mà backend dùng để upload/xóa.
- `STORAGE_PUBLIC_ENDPOINT_URL`: endpoint HTTPS mà trình duyệt dùng trong signed URL; local dùng `http://localhost:9000`.
- `STORAGE_DIRECT_UPLOAD_ENABLED`: bật presigned upload trực tiếp; mặc định tắt để fallback multipart an toàn.
- `STORAGE_UPLOAD_URL_TTL`, `STORAGE_UPLOAD_SESSION_TTL`: thời hạn URL upload và phiên upload.
- `STORAGE_PUBLIC_CORS_ORIGINS`: các origin frontend được phép PUT/HEAD lên bucket.
- `STORAGE_BUCKET`: bucket private lưu tài liệu, mặc định `hrms-evidence`.
- `MALWARE_SCANNER_ENABLED`: bật kiểm tra ClamAV; production từ chối upload nếu scanner chưa được bật.

File đính kèm không lưu trong MongoDB hoặc bundle frontend. MongoDB chỉ lưu metadata và `storage_key`; file local nằm trong bucket MinIO `hrms-evidence`, được duy trì bởi volume Docker `hrms_minio_data`.

Danh sách đánh giá chỉ trả metadata phân trang. Signed URL được tạo theo yêu cầu khi người dùng bấm tên file và có thời hạn ngắn.

Khi bật upload trực tiếp, đồng thời đặt `VITE_DIRECT_UPLOAD_ENABLED=true` trong `frontend/.env`. Frontend sẽ tính SHA-256, tải thẳng lên MinIO/S3, gọi API xác minh rồi mới lưu metadata đánh giá. Nếu storage chưa sẵn sàng hoặc trả lỗi máy chủ, frontend tự dùng lại upload multipart; lỗi kiểm tra tệp 4xx không bị bỏ qua.

Để dọn object không còn được MongoDB tham chiếu sau thời gian an toàn:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\reconcile_evidence_storage.py
```

## 3. Khởi động MongoDB bằng Docker

```powershell
docker compose up -d
docker compose ps
```

Chờ hai service `mongodb` và `mongodb-init` hoàn tất. MongoDB được chạy với Replica Set `rs0`, cần thiết cho Change Streams và WebSocket realtime.

Kiểm tra trạng thái:

```powershell
docker compose logs mongodb-init
```

Khi phát triển xong, dừng container bằng:

```powershell
docker compose down
```

Lệnh trên giữ volume dữ liệu. Muốn xóa dữ liệu local và seed lại từ đầu, dùng `docker compose down -v`.

## 4. Cài đặt và chạy backend

Tạo môi trường ảo và cài dependencies:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
```

Chạy API:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Backend cung cấp Swagger tại `http://127.0.0.1:8000/docs` và health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

## 5. Seed dữ liệu mẫu

Mở terminal PowerShell thứ hai tại thư mục gốc dự án. Chạy seed nền trước:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\seed_base_data.py --password DemoPassword123! --employees-per-department 5
backend\.venv\Scripts\python.exe backend\scripts\seed_performance_data.py --days 60
backend\.venv\Scripts\python.exe backend\scripts\seed_tasks_data.py
backend\.venv\Scripts\python.exe backend\scripts\seed_task_execution_reports.py
backend\.venv\Scripts\python.exe backend\scripts\check_data_integrity.py
```

Seed tạo 3 phòng ban, 1 tài khoản Leadership, 3 tài khoản Manager và 5 nhân viên mỗi phòng cùng 60 ngày dữ liệu hiệu suất, task mẫu và báo cáo thực thi để Manager thử nghiệm nghiệm thu bằng chứng. Script báo cáo có thể chạy lặp lại theo task/ngày.

`seed_tasks_data.py` lấy `created_by` từ Manager thật của từng phòng ban; nếu phòng chưa có Manager, script dùng tài khoản Leadership thật. `check_data_integrity.py` chỉ đọc `tasks`/`users`, báo số task có `created_by` mồ côi và trả mã lỗi khác 0 nếu phát hiện. Script seed không tự sửa task cũ.

### Checklist M1 — `created_by` của task seed

- [x] Task seed mới tham chiếu `_id` thật của Manager phòng ban hoặc Leadership fallback.
- [x] Task đã tồn tại không bị migrate khi chạy lại seed.
- [x] Có kiểm tra read-only orphan giữa `tasks.created_by` và `users._id`.

Xác minh M1:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe scripts\seed_tasks_data.py --tasks-per-employee 1
.\.venv\Scripts\python.exe scripts\check_data_integrity.py
```

Database thử nghiệm M1 trả `0 orphan`; database mặc định được kiểm tra read-only và ghi nhận `48 orphan` hiện hữu, chưa được sửa.

### Checklist M2 — index cho `threshold_configs`

- [x] Có index compound cho `department_id`, `status`, `updated_at`.
- [x] Có index `created_at` cho danh sách cấu hình theo thời gian tạo.
- [x] Service tự đảm bảo index trước `list`, `propose` và `approve`.
- [x] Threshold Configs tiếp tục là API-only theo quyết định sản phẩm, không xây UI trong lô này.

MinIO được bật cùng Docker Compose tại `http://localhost:9000` (giao diện quản trị `http://localhost:9001`). Nếu dùng `.env` mẫu, báo cáo có tệp sẽ được seed vào bucket `hrms-evidence`; khi chưa bật storage, seed vẫn tạo báo cáo không có tệp để Manager nhập lý do thiếu minh chứng.

Tài khoản demo:

| Vai trò | Tên đăng nhập | Mật khẩu |
| --- | --- | --- |
| Leadership | `demo.leadership` | `DemoPassword123!` |
| Manager Kinh doanh | `demo.manager` | `DemoPassword123!` |
| Manager Kỹ thuật | `demo.manager.tech` | `DemoPassword123!` |
| Manager CSKH | `demo.manager.cskh` | `DemoPassword123!` |

## 6. Cài đặt và chạy frontend

```powershell
Set-Location frontend
npm install
npm run dev -- --host 127.0.0.1
```

Mở `http://127.0.0.1:5173/login`. Vite proxy chuyển `/api` và `/ws` tới backend `127.0.0.1:8000` để tránh lỗi phân giải `localhost` sang IPv6 trên Windows.

## 7. Luồng chức năng chính

1. Đăng nhập bằng tài khoản demo.
2. Manager chỉ thấy nhân viên và cảnh báo thuộc phòng ban của mình; Leadership thấy dữ liệu toàn công ty.
3. Nhập điểm hàng ngày tại màn hình hiệu suất.
4. Dashboard cập nhật đồ thị khi có metric mới.
5. Hệ thống phát hiện cảnh báo sớm/quá tải qua EventBus và MongoDB Change Stream.
6. Chuông Header nhận cảnh báo realtime và hiển thị số cảnh báo chưa xử lý.
7. Mở Trợ lý AI ở góc phải, đặt câu hỏi bằng tiếng Việt. Khi chưa có API key, hệ thống hiển thị thông báo lịch sự thay vì lỗi kỹ thuật.

Luồng `Nghiệm thu và lưu điểm ngày` dùng upsert theo từng công việc/ngày. Khi tạo report
mới, `updated_at` được cập nhật duy nhất trong `$set`; dữ liệu khởi tạo trong
`$setOnInsert` không lặp trường này để tránh lỗi xung đột cập nhật MongoDB.
Index `seed_key` của `task_execution_reports` là partial theo kiểu chuỗi; vì vậy report
nghiệp vụ không có khóa seed không bị MongoDB gom chung thành `null`. Repository tự sửa
index legacy không partial ở lần gọi `ensure_indexes` đầu tiên.

Khi thay đổi điểm nghiệm thu, Manager chỉnh từng công việc trong modal. Nếu điểm mới
khác điểm đã lưu, trường `Lý do thay đổi điểm` là bắt buộc; backend lưu lý do trong
`manager_review.change_reason` và ghi audit với hành động `task_score_changed`. Các bản
ghi hiệu suất cũ chỉ có điểm tổng hợp, không có danh sách task, được hiển thị là dữ liệu
cũ và không mở chỉnh sửa theo từng công việc để tránh suy diễn dữ liệu.

Trong trang `Công việc & deadline` của Leadership, modal `Xem chi tiết` có thể lọc
`Tất cả công việc`, `Chưa ra chỉ thị` hoặc `Đã ra chỉ thị`. Các công việc quá hạn chưa
ra chỉ thị có nút `Thêm vào chỉ thị`/`Bỏ chọn`; chỉ thị chỉ được gửi cho tập công việc
đã chọn. Backend vẫn kiểm tra lại phòng ban, trạng thái quá hạn và việc đã thuộc chỉ thị
để không gửi trùng.

## 8. Kiểm thử và quality gates

Backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\isort.exe --profile black --check-only .
.\.venv\Scripts\mypy.exe app
.\.venv\Scripts\python.exe -m compileall -q app scripts tests
```

Frontend:

```powershell
Set-Location frontend
npm run lint
npm run format:check
npm test -- --run
npm run build
```

Quality gate cho bộ lọc và chọn công việc trong modal:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q tests/test_task_service.py tests/test_task_api.py
Set-Location ..\frontend
npx vitest run --config=vitest.config.js src/features/tasks/LeadershipTasksOverview.test.jsx
```

Kết quả xác nhận gần nhất: backend `11 passed`, test giao diện `3 passed`, ESLint và
Vite build thành công.

### Checklist C1 — BusinessClock

- [x] Các service nghiệp vụ nhận `BusinessClock` qua constructor; router/factory và event handler truyền clock mặc định.
- [x] Timestamp nghiệp vụ dùng `self._clock.now()`; helper ngày nghiệp vụ dùng clock được inject.
- [x] Giữ clock hệ thống tại `security.py` (JWT) và `health_service.py` (timestamp kỹ thuật).
- [x] Test thời gian của task quá hạn, cảnh báo sớm/quá tải và upload/đánh giá dùng clock cố định.

Logic: `BusinessClock` là nguồn duy nhất cho thời gian nghiệp vụ theo múi giờ cấu hình; không thay đổi API contract hoặc dữ liệu MongoDB.

Xác minh C1 từ thư mục `backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Kết quả C1: `88 passed`, Ruff đạt, compileall đạt; grep chỉ còn clock hệ thống ở `security.py` và `health_service.py`.

Khi backend và frontend đang chạy, chạy E2E:

```powershell
npm run test:e2e
```

Route contract có thể kiểm tra bằng:

```powershell
Set-Location ..\backend
.\.venv\Scripts\python.exe scripts\check_app.py
```

## 9. Dừng và xử lý sự cố

- Nếu API không kết nối MongoDB: kiểm tra Docker Desktop, `docker compose ps` và `MONGO_URI`.
- Nếu WebSocket lỗi trên Windows: bảo đảm backend bind `127.0.0.1:8000` và frontend chạy `127.0.0.1:5173`; không dùng lẫn `localhost` với `127.0.0.1`.
- Nếu port 8000 hoặc 5173 đang bận: dừng tiến trình cũ hoặc đổi port đồng thời cập nhật Vite proxy.
- Nếu Black treo khi repo nằm trong OneDrive: tạm dừng đồng bộ hoặc chuyển repo ra thư mục local không đồng bộ, rồi chạy lại `black --diff .` trước khi format.

## 10. Kiến trúc thư mục rút gọn

```text
backend/app/
  api/            # Router FastAPI
  core/           # Config, security, database, nhãn tiếng Việt
  models/         # Schema Pydantic
  repositories/   # Truy vấn Motor MongoDB
  services/       # Logic nghiệp vụ
  events/         # EventBus nội bộ
  ai/             # Interface, adapters, factory và circuit breaker
  realtime/       # Change Streams và WebSocket
frontend/src/
  components/     # Component dùng chung
  features/       # Module theo tính năng
  hooks/          # Hook dùng chung
  services/       # HTTP client
  stores/         # Zustand state
```

Phân quyền luôn được kiểm tra ở backend. Frontend chỉ điều chỉnh trải nghiệm hiển thị, không thay thế kiểm tra scope MongoDB.
