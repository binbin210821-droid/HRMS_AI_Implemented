# SRS — Software Requirements Specification

## 1. Mục đích và phạm vi

WorkMind là HRMS tập trung vào hiệu suất nhân viên, cảnh báo sớm, quá tải, điều phối công việc và trợ lý AI tiếng Việt. Phạm vi hiện tại được xác nhận trong `README.md`: phòng ban/nhân viên, hiệu suất, cảnh báo, quá tải, công việc/chỉ thị/nghiệm thu, đánh giá phòng ban theo tuần, thông báo, realtime, evidence storage và AI có kiểm soát.

Chưa thuộc phiên bản hiện tại: chấm công, nghỉ phép, tuyển dụng, tiền lương và machine-learning dự đoán chuyên sâu.

## 2. Actor và hệ thống ngoài

| Actor | Trách nhiệm |
|---|---|
| Manager | Xem dữ liệu phòng mình; nhập/nghiệm thu hiệu suất; xử lý cảnh báo; quản lý công việc; xác nhận chỉ thị. |
| Leadership | Xem toàn công ty; quản lý phòng ban; duyệt ngưỡng; đánh giá tuần; phát hành/chấp nhận chỉ thị. |
| React/Vite Client | Giao diện, gọi API v1, nhận SSE/WebSocket, không phải lớp thực thi quyền. |
| MongoDB (local replica set / production Atlas) | Lưu dữ liệu nghiệp vụ, audit, context AI và Change Streams; Backend production đã được xác nhận trỏ Atlas. Network Access/RBAC, Change Streams, regular indexes, Atlas Vector Search index và Backup/PITR đã được xác nhận theo runtime evidence do chủ dự án cung cấp. Cluster/user/network values không lưu trong repo. |
| Redis | Rate limit, idempotency và cache AI; `.env.production` production đã được xác nhận dùng `RATE_LIMIT_BACKEND=redis`. Giá trị Redis URI cụ thể không lưu trong repo. |
| S3-compatible storage | Lưu evidence và cấp signed URL; local dùng MinIO, production S3 bucket AWS đã được xác nhận cấu hình với endpoint tương thích S3. Tên bucket/region/credential không lưu trong repo. |
| Cloudflare Workers AI | FastAPI gọi trực tiếp Cloudflare Workers AI qua REST API; production runtime đã xác nhận `AI_PROVIDER=cloudflare`, model `@cf/google/gemma-4-26b-a4b-it` và provider được cấu hình. Repo vẫn chưa có custom Worker riêng hoặc `workers.dev` deployment artifact. |
| GitHub Actions/GHCR/EC2 SSH deploy host | CI quality gates, build image, publish image và deploy SSH; runtime thủ công đã xác nhận SSH target là máy Ubuntu chạy trên AWS EC2 và workflow CI/CD đã chạy thành công theo xác minh production. |

## 3. Yêu cầu chức năng

| ID | Yêu cầu | Bằng chứng hiện có |
|---|---|---|
| FR-AUTH | Đăng nhập, JWT, HttpOnly cookie, CSRF middleware, logout, legacy Bearer tương thích có kiểm soát. | `backend/app/api/auth.py` (`login`, `get_me`, `logout`), `backend/app/core/security.py`, `backend/app/core/csrf.py`, `backend/app/api/dependencies.py` |
| FR-RBAC | Backend kiểm tra token/role và department scope; Manager bị giới hạn ở phòng được gán; Leadership dùng scope toàn công ty. | `backend/app/api/dependencies.py` (`resolve_current_user`, `require_role`, `get_department_scope`), `backend/app/repositories/employee_repository.py`, `backend/app/services/employee_service.py` |
| FR-MASTER | CRUD phòng ban và nhân viên; CRUD phòng ban yêu cầu Leadership, nhân viên được kiểm scope ở service/repository. | `backend/app/api/v1/departments.py`, `backend/app/api/v1/employees.py`, `backend/app/services/department_service.py`, `backend/app/services/employee_service.py`, `backend/app/repositories/department_repository.py`, `backend/app/repositories/employee_repository.py` |
| FR-PERF | Daily review kiểm task/evidence, tính quality và số task, ghi/upsert `performance_metrics`, rồi phát event hiệu suất. Leadership không trực tiếp nghiệm thu nhân viên. | `backend/app/api/v1/performance.py`, `backend/app/services/performance_review_service.py`, `backend/app/services/performance_score_calculator.py`, `backend/app/repositories/performance_repository.py`, `backend/app/events/event_bus.py` |
| FR-ALERT | Quét cảnh báo sớm; nhận cảnh báo quá tải từ event; lọc/pagination, tổng hợp theo phòng, xử lý và ghi chú. | `backend/app/api/v1/alerts.py`, `backend/app/api/v1/scans.py`, `backend/app/services/early_warning_detector.py`, `backend/app/services/alert_service.py`, `backend/app/repositories/alert_repository.py` |
| FR-OVERLOAD | Phát hiện quá tải từ khối lượng hoặc chất lượng; lưu log, phát event và trả candidate đang hoạt động cùng phòng, có tối đa 2 công việc/ngày và chất lượng tối thiểu 80, sắp theo ít việc rồi chất lượng cao. | `backend/app/services/overload_detector.py`, `backend/app/services/overload_service.py`, `backend/app/repositories/overload_repository.py`, `backend/app/api/v1/overload.py`, `backend/app/api/v1/scans.py` |
| FR-TASK | Tạo/sửa/xóa task, trạng thái, deadline, overdue, chỉ thị và nghiệm thu theo lifecycle. | `backend/app/api/v1/tasks.py`, `backend/app/services/task_service.py`, `backend/app/repositories/task_repository.py`, `backend/app/models/task.py` |
| FR-EVAL | Leadership ghi đánh giá phòng ban theo tuần, dựng evidence snapshot, lưu attachment/evidence và audit. | `backend/app/api/department_evaluations.py`, `backend/app/api/v1/department_evaluations.py`, `backend/app/services/department_evaluation_service.py`, `backend/app/repositories/department_evaluation_repository.py` |
| FR-AI | Chat SSE tiếng Việt, summary mode, proposal và tool preview; tool đọc dữ liệu được scope server-side, mutation AI không có handler tự thực thi và cần đường nghiệp vụ/người dùng xác nhận. | `backend/app/api/ai.py`, `backend/app/services/ai_chat_orchestrator.py`, `backend/app/services/ai_tool_service.py`, `backend/app/ai/tooling.py`, `backend/app/ai/governance.py` |
| FR-REALTIME | Change Streams → EventBus → WebSocket; ConnectionManager lọc Leadership toàn công ty và Manager theo department. | `backend/app/realtime/change_stream_worker.py`, `backend/app/events/event_bus.py`, `backend/app/realtime/connection_manager.py`, `backend/app/realtime/websocket.py`, `backend/app/main.py` |
| FR-AUDIT | Ghi audit cho các flow nghiệp vụ chính và AI governance; AI audit chỉ lưu summary/hash, không lưu nguyên prompt/output. | `backend/app/repositories/task_repository.py`, `backend/app/repositories/coordination_repository.py`, `backend/app/services/performance_review_service.py`, `backend/app/ai/governance.py`, `backend/app/api/ai.py` |

## 4. Yêu cầu phi chức năng

| ID | Yêu cầu/định hướng | Bằng chứng hoặc cách nghiệm thu |
|---|---|---|
| NFR-SEC-01 | Không dùng CORS wildcard khi credentials; production cookie phải Secure; JWT secret riêng ≥ 32 ký tự. | `backend/app/core/config.py` validators, `backend/app/main.py`, `backend/app/core/security.py` |
| NFR-SEC-02 | Production rate limiting phân tán dùng Redis khi được bật; CSRF áp dụng cho cookie-auth mutation; idempotency được wiring ở các mutation retry-sensitive, không phải mọi route ghi. | `backend/app/core/csrf.py`, `backend/app/infrastructure/rate_limit/`, `backend/app/infrastructure/idempotency.py`, `backend/app/api/*.py`, `backend/app/core/config.py` |
| NFR-SEC-03 | AI data/tool flow nhận scope do backend cấp; dữ liệu và output đi qua lớp dịch/sanitize nhãn tiếng Việt. | `backend/app/api/dependencies.py`, `backend/app/services/ai_data_tool_service.py`, `backend/app/core/field_labels_vi.py`, `backend/app/api/ai.py` |
| NFR-REL-01 | Lỗi AI được cô lập bằng timeout, retry/fallback, cache best-effort và circuit breaker; vẫn cần kiểm thử provider lỗi để xác nhận runtime. | `backend/app/ai/providers.py`, `backend/app/ai/factory.py`, `backend/app/ai/cache.py`, `backend/app/services/ai_service.py`, `backend/app/core/config.py` |
| NFR-REL-02 | Event handler lỗi được cô lập; Change Stream worker retry khi Mongo lỗi. | `backend/app/events/event_bus.py`, `backend/app/realtime/change_stream_worker.py`, `backend/app/main.py` |
| NFR-PERF-01 | Các endpoint list v1 hiện có hỗ trợ pagination và, tùy resource, date range; repository có các index phục vụ query chính, nhưng chưa chứng minh đầy đủ bằng explain/index audit cho mọi route. | `backend/app/core/pagination.py`, `backend/app/api/v1/alerts.py`, `backend/app/api/v1/overload.py`, `backend/app/api/v1/performance.py`, `backend/app/repositories/alert_repository.py`, `backend/app/repositories/overload_repository.py`, `backend/app/repositories/performance_repository.py`, `backend/app/repositories/task_repository.py` |
| NFR-OBS-01 | Có request ID, health check và structured AI/provider log; AI audit lưu summary/hash thay vì raw prompt/output. | `backend/app/core/http_contract.py`, `backend/app/api/health.py`, `backend/app/services/health_service.py`, `backend/app/ai/providers.py`, `backend/app/ai/governance.py` |
| NFR-DEP-01 | CI chạy lint/test/build/contract/integration/E2E/security; CD chạy khi tag `v*.*.*` hoặc `workflow_dispatch`, có Environment production và health check sau deploy. Production runtime đã được kiểm tra thủ công trên EC2 với Docker/Docker Compose; CI/CD workflow đã được xác nhận chạy thành công, nhưng nên lưu run URL/ảnh làm evidence ngoài repo. | `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `.github/workflows/security.yml`, `docker-compose.production.yml`, bằng chứng terminal EC2 và GitHub Actions do chủ dự án cung cấp |

### Bằng chứng runtime đã xác minh bổ sung

- Trên máy production, `hostname`, `uname -a`, Docker và Docker Compose xác nhận môi trường Ubuntu/AWS EC2.
- `.env.production` trên máy production đã được kiểm tra thủ công có các biến cấu hình cần thiết, gồm `MONGO_URI`, `AI_PROVIDER`, `AI_MODEL`, `CLOUDFLARE_ACCOUNT_ID` và `CLOUDFLARE_API_TOKEN`; không ghi giá trị secret vào tài liệu.
- `.env.production` đã được xác nhận có cấu hình cho MongoDB Atlas, S3 bucket AWS và Redis rate limiting. Backend production đã được xác nhận trỏ Atlas; Network Access/RBAC, Change Streams, regular indexes, Atlas Vector Search index và Backup/PITR đã được chủ dự án xác nhận theo runtime evidence. Chỉ ghi tên biến/trạng thái, không ghi URI, credential hoặc tên tài nguyên nhạy cảm.
- Sau khi truyền `BACKEND_IMAGE`/`FRONTEND_IMAGE` và recreate backend container, `GET /api/v1/health` trả `status=healthy`, `ai_provider=cloudflare`, `ai_model=@cf/google/gemma-4-26b-a4b-it` và `ai_provider_configured=true`; `/api/health` vẫn là alias compatibility.
- GitHub Actions CI/CD đã được xác nhận chạy thành công; run URL hoặc ảnh workflow là bằng chứng ngoài repo cần lưu kèm hồ sơ phát hành.
- Cloudflare Workers AI Dashboard đã hiển thị usage của model text generation `@cf/google/gemma-4-26b-a4b-it` và embedding `@cf/qwen/qwen3-embedding-0.6b`. Đây là bằng chứng dashboard ngoài repository; chưa phải load test hoặc audit định lượng.

### Mục tiêu đo lường cần phê duyệt

Các con số dưới đây là **acceptance target đề xuất**, chưa phải số đo production đã xác nhận:

| Chỉ tiêu | Target đề xuất | Cách đo |
|---|---:|---|
| Health/read API p95 | ≤ 500 ms | Load test endpoint read-only, loại trừ cold start |
| Mutation API p95 | ≤ 1.000 ms | Test với Redis/Mongo staging và payload chuẩn |
| AI first token p95 | ≤ 5.000 ms | Đo từ FastAPI nhận request tới SSE chunk đầu tiên |
| AI total timeout | 60 s hard limit | Đã có `AI_TOTAL_TIMEOUT_SECONDS=60` trong config; cần xác nhận qua test |
| Realtime propagation p95 | ≤ 2.000 ms | Mongo write có chủ đích → client nhận WebSocket event |
| Baseline tải | 50 request/s read, 10 request/s mutation | Cần chốt theo quy mô thật và chạy load test |
| Error rate | < 1% ở baseline | Theo request ID/HTTP status, không tính lỗi validation cố ý |

Không dùng các target này để tuyên bố hệ thống đã đạt cho đến khi có report load/staging tương ứng.

## 5. Quy tắc nghiệp vụ cốt lõi

```text
task_volume_score = min(tasks_completed / 4, 1.5) × 100
performance_score = quality_score × 0.7 + task_volume_score × 0.3
```

`quality_score` do Manager đánh giá. Các field kỹ thuật được chuyển sang nhãn tiếng Việt trước khi đưa vào context/output AI.

### Ngưỡng cảnh báo và quá tải đã thấy trong code

- **Quá tải theo khối lượng:** `tasks_completed > 4` trong `OverloadDetector.TASK_VOLUME_LIMIT`.
- **Quá tải theo chất lượng:** lấy đúng 7 ngày liên tiếp làm baseline, tiếp ngay sau đó là 3 ngày liên tiếp; cả 3 điểm chất lượng phải `≤ baseline_average × 0.8`. Code không dùng `threshold_configs` để thay đổi hai hằng số hard overload này.
- **Cảnh báo sớm:** mặc định 3 ngày và 20% trong `EarlyWarningDetector`; có thể lấy `consecutive_days`/`quality_drop_percent` từ cấu hình đã duyệt. Điều kiện yêu cầu số task tăng nghiêm ngặt từng ngày, chất lượng giảm nghiêm ngặt từng ngày và mức giảm tổng thể **nhỏ hơn** ngưỡng cấu hình, để cảnh báo sớm hơn hard overload.

Bằng chứng: `backend/app/services/overload_detector.py`, `backend/app/services/early_warning_detector.py`, `backend/app/services/alert_service.py`, `backend/app/services/threshold_service.py`.

## 6. Tiêu chí nghiệm thu cấp hệ thống

- OpenAPI `/api/v1` khớp implementation và contract/caller audit không phát hiện frontend business caller dùng alias `/api` khi endpoint v1 đã tồn tại.
- Manager không đọc/ghi được dữ liệu ngoài phòng; Leadership đọc được phạm vi toàn công ty.
- AI production provider đã được xác minh bằng health check là Cloudflare và đã có usage tương ứng trên Cloudflare Dashboard; timeout/HTTP error/empty stream vẫn cần kiểm thử failure-path riêng để xác nhận fallback và thông báo thân thiện. AI không ghi mutation nghiệp vụ trực tiếp.
- CI phải chạy đủ quality/security/integration/E2E gates; image backend/frontend phải build được; CD phải gọi health check sau deploy. Trạng thái xanh/đạt là bằng chứng runtime của từng workflow, không thể kết luận chỉ bằng đọc SRS/source.
- Production EC2, `.env.production`, MongoDB Atlas, S3 bucket, Redis configuration, CI/CD và Cloudflare AI đã được xác minh theo thông tin runtime do chủ dự án cung cấp. Giá trị chi tiết nhạy cảm và ảnh redacted cần được lưu ở hồ sơ evidence ngoài repo. Domain/HTTPS vẫn chưa cấu hình; HTTPS/Secure cookie, S3/Redis end-to-end và các điều kiện staging cũng vẫn cần bằng chứng runtime riêng.

## 7. Hướng dẫn bổ sung ảnh minh chứng

Các ảnh dưới đây dùng để bổ sung bằng chứng triển khai/runtime cho SRS. Ảnh chỉ nên thể hiện thông tin cần thiết để xác minh; tuyệt đối che hoặc cắt bỏ API token, secret key, mật khẩu, JWT, private key và phần credential trong `MONGO_URI`.

| Mã | Vị trí liên quan trong SRS | Ảnh minh chứng nên bổ sung | Ảnh dùng để xác nhận | Trạng thái |
|---|---|---|---|---|
| E-01 | Mục 2, Cloudflare Workers AI; Mục 6, AI production | Cloudflare Workers AI Dashboard hiển thị usage của `@cf/google/gemma-4-26b-a4b-it` và `@cf/qwen/qwen3-embedding-0.6b` | Tài khoản Cloudflare đã phát sinh text generation và embedding usage phù hợp với cấu hình dự án | Đã có ảnh dashboard; không phải load test |
| E-02 | Mục 2, EC2 deploy host; Mục 4 NFR-DEP-01 | Terminal EC2 gồm `hostname`, `uname -a`, phiên bản Docker, `docker ps`/mapping frontend và `curl http://127.0.0.1:80/api/v1/health` | SSH target là môi trường Ubuntu/AWS EC2, Nginx frontend proxy và health check chuẩn qua port 80 hoạt động | Chưa hoàn tất: cần lưu ảnh lệnh thành công; hiện đang kiểm tra lỗi health check port 80 |
| E-03 | Mục 2 MongoDB; Mục 6 database runtime | Terminal hoặc editor hiển thị **tên biến** trong `.env.production` như `MONGO_URI`, không hiển thị credential; kèm health response/runtime evidence đã che secret | Production container có connection target MongoDB và Backend production đã trỏ đúng Atlas | Đã xác minh theo evidence runtime do chủ dự án cung cấp; lưu ảnh/log redacted ngoài repo |
| E-04 | Mục 2 Cloudflare; Mục 4 NFR-REL-01 | Terminal/container health response hiển thị `ai_provider=cloudflare`, model Gemma và `ai_provider_configured=true` | Process backend production thực sự nạp cấu hình Cloudflare, không chỉ file local có biến môi trường | Đã xác minh qua health response |
| E-05 | Mục 2 GitHub Actions/GHCR/EC2; Mục 6 CI/CD | GitHub Actions workflow run hiển thị các job publish image, deploy production và health check thành công | Pipeline thực tế đã build/publish/deploy thành công; source workflow alone không đủ | Đã xác minh workflow thành công theo chủ dự án; cần lưu run URL/ảnh |
| E-06 | Mục 2 S3-compatible storage; Mục 6 storage | AWS S3 Console hiển thị bucket, region, Block Public Access và encryption; không chụp access key/secret key | Bucket production tồn tại và có cấu hình bảo mật cơ bản | Đã xác nhận bucket được cấu hình; cần ảnh console redacted và smoke test nếu muốn chứng minh end-to-end |
| E-07 | Mục 2 MongoDB; Mục 6 database | MongoDB Atlas hiển thị cluster, Network Access, Database User, index/Vector Search và Backup/PITR; che credential và thông tin nhạy cảm | Xác nhận Atlas security/network, Change Streams, regular indexes, Vector Search index và Backup/PITR theo evidence runtime | Đã xác minh theo thông tin runtime do chủ dự án cung cấp; chỉ lưu ảnh/log redacted ngoài repo |
| E-08 | Mục 4 NFR-SEC-01/02 và Mục 6 HTTPS | AWS Security Group/HTTPS reverse proxy hoặc trình duyệt hiển thị HTTPS hợp lệ, Secure cookie và CORS origin production | Các điều kiện bảo mật production đã được bật, không chỉ tồn tại trong config | Đã xác nhận domain/HTTPS chưa cấu hình; chưa phải tiêu chí đạt |

### Quy tắc đặt tên và lưu ảnh

- Đặt tên theo mã, ví dụ: `E-01-cloudflare-usage.png`, `E-02-ec2-health.png`, `E-05-github-actions-success.png`.
- Mỗi ảnh nên có ngày/giờ hoặc liên kết workflow tương ứng trong phần ghi chú nghiệm thu.
- Ảnh GitHub Actions nên hiển thị tên workflow, commit/tag, job và trạng thái; không hiển thị giá trị secret.
- Ảnh `.env.production` chỉ nên hiển thị tên biến và trạng thái đã cấu hình. Nếu cần chứng minh giá trị, chỉ hiển thị dạng `set` hoặc che toàn bộ giá trị.
- Ảnh Cloudflare chỉ cần hiển thị account/model/usage; không hiển thị API token.
- Ảnh MongoDB Atlas chỉ cần hiển thị cluster, Network Access và trạng thái kết nối; không chụp connection string đầy đủ.
- Ảnh không thay thế cho load test, failure-path test, `explain()` index audit hoặc kiểm thử end-to-end có log định lượng.
