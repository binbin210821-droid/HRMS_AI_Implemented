# Baseline tối ưu code — 12/09/2026

## Phạm vi

Baseline được ghi nhận trên working tree hiện tại của HRMS_v2. Working tree có 285 mục thay đổi/chưa theo dõi, gồm nhiều thay đổi từ các giai đoạn trước; không sử dụng `git reset`, `git checkout` hoặc thao tác xóa để làm sạch trạng thái.

## Kết quả kiểm tra tĩnh và test tự động

| Kiểm tra | Kết quả |
| --- | --- |
| Backend pytest | `352 passed, 3 deselected, 3 warnings` |
| Ruff | Đạt |
| Python compileall | Đạt |
| Mypy | Chưa đạt: 1 lỗi tại `backend/app/repositories/overload_repository.py:105` |
| Frontend Vitest | `42 files / 142 tests passed` khi chạy ngoài sandbox |
| ESLint | Đạt |
| Prettier | Chưa đạt: 12 file |
| Vite production build | Đạt; cảnh báo bundle JavaScript khoảng 1.14 MB |
| OpenAPI | 158 HTTP paths: 90 `/api/v1`, 68 legacy `/api` |
| API route/dependency audit | Đạt qua `backend/scripts/check_app.py` |
| Compose configuration audit | Đạt qua `backend/scripts/check_compose.py` |
| Frontend caller audit | Đạt; không còn business caller dùng `/api` legacy |

Backend warnings hiện tại gồm cảnh báo Starlette/httpx deprecation và hai vị trí dùng `HTTP_422_UNPROCESSABLE_ENTITY` trong `performance_review_service.py`.

## Live environment

Baseline live đã được dựng trên môi trường local riêng bằng Docker Compose:

- MongoDB 7 chạy healthy trên `27017`, Replica Set `rs0` ở trạng thái `PRIMARY`.
- Redis 7 chạy healthy trên `6379`, `redis-cli ping` trả `PONG`.
- MinIO chạy trên `9000/9001`.
- Backend Uvicorn chạy 2 worker trên `8000`; `/api/v1/health` trả `200`.
- Frontend Vite trả `200` tại `http://127.0.0.1:5173/` và có root React.
- Dữ liệu demo idempotent: 3 phòng ban, 4 tài khoản demo, 16 nhân viên, 960 metric/60 ngày và 48 task.

Live smoke đã đạt:

- `smoke_redis.py`: atomic rate-limit đa instance và idempotency replay.
- `smoke_cookie_auth.py`: login, `/me`, CSRF logout/session clear cho Manager và Leadership.
- `smoke_phase3.py`: seed, role scope và department RBAC.
- `smoke_performance.py`: 60 ngày, công thức điểm 86.0 và RBAC scope.
- `smoke_performance_analytics.py`: aggregation, trend 60 ngày và RBAC.
- `smoke_tasks.py`: scope Manager/Leadership, tên nhân viên và deadline.
- `smoke_early_warning.py`: chuỗi 3 ngày, cảnh báo medium, EventBus/Change Stream và scope.
- `smoke_overload.py`: điều kiện A/B, rebalancer, alert high và RBAC scope.
- `smoke_realtime_cookie.py`: cookie session và RBAC WebSocket scope.

Browser live smoke chưa thực hiện được vì in-app browser hiện không có backend khả dụng (`agent.browsers.list()` trả danh sách rỗng). HTTP preview smoke đã đạt; kiểm tra hình ảnh/interaction cần chạy bổ sung khi browser khả dụng.

## Quyết định chuyển giai đoạn

Giai đoạn 0 **đã đạt live acceptance** cho hạ tầng local, API health, MongoDB Replica Set, Redis, backend multi-worker và frontend HTTP preview. Browser visual acceptance còn mở do giới hạn môi trường.

## Tiến độ Giai đoạn 1 — cấu hình production

Đã triển khai phần fail-fast trong `backend/app/core/config.py` và test trong `backend/tests/test_config_security.py` cho JWT secret, credential storage, HTTPS storage endpoint, rate-limit shadow-only và malware scanner.

Quality gate sau thay đổi:

- Focused config test: `13 passed`.
- Full backend regression: `357 passed, 3 deselected, 3 warnings`.
- Ruff và compileall: đạt.
- Full frontend Vitest: `42 files / 142 tests passed`.
- ESLint: đạt.

Live acceptance Giai đoạn 1:

- Production settings hợp lệ được khởi tạo thành công với secret/credential an toàn.
- Cấu hình production không an toàn bị từ chối với lỗi JWT fail-fast.
- Cookie auth live cho Manager và Leadership đạt; CSRF logout/session clear đạt.

Giai đoạn 1 **đã đạt acceptance backend/live**, còn browser visual acceptance mở. Mypy vẫn còn 1 lỗi baseline tại `backend/app/repositories/overload_repository.py:105`; Prettier vẫn còn 12 file chưa đạt.

## Tiến độ Giai đoạn 2 — EventBus

Đã triển khai cô lập lỗi handler trong `backend/app/events/event_bus.py`, chống đăng ký trùng handler và hủy đăng ký các handler của `lifespan` trong `backend/app/main.py`. Đã bổ sung `backend/tests/test_event_bus.py` cho lỗi handler, chạy các handler còn lại và vòng đời subscribe/unsubscribe.

Quality gate sau thay đổi:

- Focused EventBus test: `2 passed`.
- Full backend regression: `359 passed, 3 deselected, 3 warnings`.
- Full frontend Vitest: `42 files / 142 tests passed`.
- Ruff, compileall và ESLint: đạt.

Live acceptance Giai đoạn 2:

- Backend 2 worker chạy ổn định trong live environment.
- Redis smoke đa instance đạt.
- Early-warning và realtime-cookie smoke xác nhận đường EventBus/Change Stream → WebSocket và RBAC scope.
- Fault isolation handler và duplicate subscribe/unsubscribe được kiểm chứng bằng focused EventBus tests (`2 passed`); chưa có endpoint fault-injection dành riêng cho production process.

Giai đoạn 2 **đã đạt acceptance cho phạm vi code hiện tại**, với ghi chú fault-injection process-level và browser visual acceptance còn mở.

## Tiến độ Giai đoạn 3 — transaction review hiệu suất

Đã bọc ba nhóm ghi của daily review trong một MongoDB transaction khi client hỗ trợ session: cập nhật hàng loạt báo cáo thực thi, upsert metric ngày và ghi audit log. Session được truyền xuyên suốt repository; event chỉ phát sau commit. Các fake repository không có client vẫn giữ đường chạy test tương thích.

Quality/live gate:

- Focused performance-review tests: `9 passed`.
- Full backend regression: `360 passed, 3 deselected, 3 warnings`.
- Ruff và compileall: đạt.
- Live PATCH daily review cho `KD-NV-001`: 3 task, 3 review, quality `88.0`.
- Read-only Mongo verification sau request: 3 report có review, 1 metric ngày, audit tồn tại.

Giai đoạn 3 **đã đạt acceptance cho transaction path**. Cần tiếp tục kiểm tra rollback bằng lỗi giữa transaction trên Mongo live ở gate kế tiếp; không thực hiện thao tác xóa dữ liệu demo.

## Tiến độ Giai đoạn 4–6 — race safety, upload ownership và ngày nghiệp vụ

Đã bổ sung điều kiện trạng thái nguyên tử cho resolve alert (`resolve_if_open`), truyền owner vào các thao tác commit/fail upload session và giới hạn truy vấn context AI ở tầng Mongo query. Dashboard frontend và khóa cache tóm tắt AI dùng múi giờ nghiệp vụ `Asia/Ho_Chi_Minh`; không còn suy ra ngày nghiệp vụ bằng UTC `toISOString()`.

Quality gate:

- Alert focused tests: `11 passed`.
- Attachment/evaluation focused tests: `14 passed`.
- AI focused tests: `26 passed`.
- Mypy: `Success: no issues found in 132 source files`.
- Ruff: đạt cho các module thay đổi.
- Frontend Vitest: `42 files / 142 tests passed`.
- Frontend ESLint, Prettier và navigation contract: đạt.
- Vite build: đạt; còn cảnh báo bundle JS khoảng `1.13 MB`.
- Live alert PATCH: request thứ hai không ghi đè resolution note của request đầu.
- Live Mongo rollback fault injection với session truyền vào từng write: metric và audit đều còn `0` sau rollback.
- Seed integrity live: sau khi rerun idempotent `seed_tasks_data.py`, 49 task demo có `0` orphan `created_by`.
- Threshold v1 GET đã được tách route `PageResponse` và OpenAPI xác nhận đúng contract; live gọi route hiện bị chặn ở `ensure_indexes` do Mongo `OutOfDiskSpace` (449,495,040 bytes < 524,288,000), chưa tự ý dọn dữ liệu để vượt blocker.

Các thay đổi này đã đạt focused/live gate trong phạm vi hiện tại. Browser visual acceptance vẫn mở do browser backend không khả dụng; cần bổ sung visual smoke khi môi trường cho phép.

## Quality gate hiện tại sau toàn bộ patch trong phiên

- Backend: `364 passed, 3 deselected, 1 cảnh báo thư viện Starlette/httpx`; Ruff, compileall và mypy đạt.
- Frontend: `43 files / 143 tests passed`; ESLint, Prettier và navigation check đạt.
- Vite production build đạt; sau route splitting chunk chính khoảng `380 kB`, không còn cảnh báo chunk lớn.
- `git diff --check` đạt.
- Live backend đã restart thành công 2 worker sau patch; `/api/v1/health` trả healthy.
- AI page/widget: không còn mount trong `App`; direct `/manager/assistant` và `/leadership/assistant` được redirect về tổng quan; regression test mới đạt.
