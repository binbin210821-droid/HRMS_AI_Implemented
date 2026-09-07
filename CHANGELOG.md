# Lịch sử thay đổi

## [Fix] - Chỉnh điểm nghiệm thu theo từng công việc

### Files created/modified

- `backend/app/models/task_execution.py`
- `backend/app/services/performance_review_service.py`
- `backend/tests/test_performance_review_service.py`
- `frontend/src/pages/PerformanceEntryPage.jsx`
- `README.md`

### Logic & Luồng

- Modal chỉnh điểm hiển thị điểm hiện tại và ô nhập lý do cho từng công việc.
- Chỉ bắt buộc lý do khi điểm mới khác điểm đã lưu; quy tắc được kiểm tra lại ở backend.
- Lưu `change_reason` trong `manager_review`, đồng thời ghi audit `task_score_changed`.
- Bản ghi hiệu suất cũ không có dữ liệu task không được chỉnh sửa theo từng công việc.

### Verification

- Backend review/repository tests: `10 passed`.
- Frontend lint: đạt.
- Frontend tests: `14 test files, 47 passed`.
- Frontend build: thành công.

## [Hotfix] - Chuẩn hóa partial unique index `tasks.seed_key`

### Files created/modified

- `backend/app/repositories/task_repository.py`
- `backend/scripts/seed_tasks_data.py`
- `backend/scripts/seed_task_directive_scenario.py`
- `backend/scripts/check_task_seed_index.py` — chẩn đoán read-only số liệu task và index.
- `backend/tests/test_task_repository.py`
- `CHANGELOG.md`

### Logic & Luồng

- Nguyên nhân gốc: hai script seed đang gọi `create_index("seed_key", unique=True)` trực tiếp; index `seed_key_1` vì vậy áp dụng unique cho cả document thiếu `seed_key`, làm task tạo qua API thứ hai trở đi có thể nhận `409`.
- Đã chuyển quản lý index task về `TaskRepository.ensure_indexes()` và đổi thành partial unique index chỉ áp dụng cho document có `seed_key`:
  `partialFilterExpression={"seed_key": {"$exists": True}}`.
- Hai script seed vẫn giữ cơ chế chống trùng theo `seed_key`, nhưng không còn tự định nghĩa index rải rác.
- Read-only MongoDB trước migration: `49` task có `seed_key`, `1` task thiếu `seed_key`; index thực tế lúc kiểm tra vẫn là `seed_key_1`, `unique: true`, chưa có partial filter.
- Đã drop/recreate index trên MongoDB thật sau khi có xác nhận; không migrate hoặc cập nhật document task cũ.

### Verification

- `backend/.venv/Scripts/python.exe -m pytest -q tests/test_task_service.py tests/test_task_repository.py tests/test_seed_tasks_data.py`: `12 passed`.
- Ruff trên các file thay đổi: đạt.
- `compileall`: đạt.
- API smoke: `POST /api/tasks` hai lần liên tiếp không có `seed_key`, cả hai trả `201`; không còn `409`.
- Chạy lại `seed_tasks_data.py`: đồng bộ `48` task mẫu; số task có `seed_key` vẫn là `49`, chứng minh không tạo thêm bản ghi seed trùng.
- `check_task_seed_index.py`: sau migration xác nhận `seed_key_1` là unique partial index; `seed_key` phân biệt bằng số task có seed key.

### Phạm vi tác động

- Sửa code tạo/quản lý index, cập nhật index MongoDB thật theo xác nhận và bổ sung kiểm thử; không sửa document task hiện có.

## [Fix Lô 11] - Thống nhất nhãn yêu cầu và điều phối trên UI

### Files created/modified

- `frontend/src/features/coordination/directiveLabels.js` — mapping nhãn nguồn, trạng thái và hành động theo loại dữ liệu.
- `frontend/src/pages/DirectivesPage.jsx`
- `frontend/src/features/dashboard/DirectiveSummaryCard.jsx`
- `frontend/src/features/coordination/ManagerAlertDirectiveAction.jsx`
- `frontend/src/features/tasks/ManagerTaskDirectives.jsx`
- `frontend/src/features/notifications/NotificationBell.jsx`
- `frontend/src/features/dashboard/CoordinationSuggestionsCard.jsx`
- `frontend/src/components/layout/navigation.js`
- Các test text assertion tương ứng trong `frontend/src`.
- `CHANGELOG.md`

### Logic & Luồng

- Hiển thị nhất quán ba nhãn theo nguồn:
  - `department_alert_directives` — **Yêu cầu xử lý cảnh báo**.
  - `department_task_directives` — **Giao việc quá hạn**.
  - `coordination_directives` — **Điều phối liên phòng ban**.
- Mỗi thẻ/dòng liên quan hiển thị nhãn loại dữ liệu; trạng thái và hành động cũng được diễn đạt theo đúng ngữ cảnh thay vì chỉ hiển thị `pending`/`accepted` hoặc “chỉ thị”.
- Không đổi tên biến, API, collection hay logic xử lý backend.
- Đây là bộ nhãn bản nháp đã được xác nhận để áp dụng trong lô này; cần xác nhận lại lần cuối trước khi coi là tên chính thức trong sản phẩm.

### Verification

- `npm run lint`: đạt, không có warning.
- `npm test -- --run`: `14` test files, `43 passed`.

### Phạm vi tác động

- Chỉ thay đổi copy/UI frontend và assertion test liên quan; không thay đổi contract hoặc hành vi runtime backend.

## [Fix Lô 10] - Đánh dấu deprecated 4 endpoint legacy

### Files created/modified

- `backend/app/api/coordination.py`
- `backend/app/api/performance.py`
- `backend/app/api/overload.py`
- `backend/scripts/check_app.py`
- `CHANGELOG.md`

### Logic & Luồng

- Đánh dấu deprecated nhưng giữ nguyên hành vi cho:
  - `POST /api/coordination/alerts/{alert_id}/direct` — flow cá nhân cũ, thay bằng chỉ thị cấp phòng ban qua `/api/coordination/department-directives`.
  - `GET /api/coordination/alerts/{alert_id}/directive-targets` — flow đích điều phối cũ, thay bằng chỉ thị cấp phòng ban qua `/api/coordination/department-directives`.
  - `POST /api/performance/daily` — đã thay bằng `/api/performance/daily-review`.
  - `POST /api/overload/scan` — đường tự động chính dùng event từ metric mới; endpoint chỉ giữ tương thích ngược thủ công.
- Chỉ thay đổi FastAPI metadata `deprecated` và summary OpenAPI; không đổi logic xử lý, response hoặc mã trạng thái.

### Verification

- `check_app.py` xác nhận đủ route và kiểm tra `deprecated: true` cho đúng 4 method.
- OpenAPI inspection: cả 4 endpoint đều trả `True` ở field `deprecated`.
- `pytest -q`: `104 passed, 2 warnings`.
- Ruff đạt.

### Phạm vi tác động

- Chỉ tài liệu hóa trạng thái tương thích ngược trong OpenAPI/Swagger; không thay đổi runtime behavior.

## [Fix Lô 9] - Gỡ bỏ Manager Evaluations legacy

### Files created/modified

- Đã xóa `backend/app/services/manager_evaluation_service.py`.
- Đã xóa `backend/app/repositories/manager_evaluation_repository.py`.
- Đã xóa `backend/app/models/manager_evaluation.py`.
- Đã xóa `backend/app/api/manager_evaluations.py`.
- Đã xóa `frontend/src/pages/ManagerEvaluationsPage.jsx`.
- Đã xóa `frontend/src/features/managerEvaluations/managerEvaluationsApi.js`.
- Đã xóa `backend/tests/test_manager_evaluation_service.py`.
- Sửa `backend/app/main.py` để bỏ router legacy.
- Sửa `backend/scripts/check_app.py` để xác nhận `/api/manager-evaluations` không còn trong OpenAPI.
- Sửa `backend/scripts/smoke_overload.py` để bỏ smoke call tới endpoint legacy.
- `CHANGELOG.md`

### Logic & Luồng

- Grep trước khi xóa xác nhận không có runtime import/caller ngoài chính các module legacy, page/API wrapper của chúng và test legacy; page cũng không được mount trong `App.jsx`.
- Menu `frontend/src/components/layout/navigation.js` không có menu Manager Evaluations; mục `managers` đang trỏ tới flow hiện hành `department-evaluations` nên được giữ nguyên.
- Gỡ hoàn toàn code truy cập Manager Evaluations khỏi backend/frontend. Đây là tính năng chưa từng có caller runtime, không phải regression.
- Không xóa, migrate hoặc update collection MongoDB `manager_evaluations`; dữ liệu cũ được giữ nguyên.

### Verification

- `backend/scripts/check_app.py`: đạt; OpenAPI không còn `/api/manager-evaluations`.
- Backend `pytest -q`: `104 passed, 2 warnings`.
- `mypy app`: `0 lỗi`, `90 source files`.
- Frontend `npm run build`: đạt, Vite build `1090 modules`; chỉ còn cảnh báo chunk lớn.
- Grep sau xóa: không còn import/caller legacy trong `backend`/`frontend`; chỉ còn assertion phủ định trong `check_app.py`.

### Phạm vi tác động

- Chỉ gỡ code/test/wiring của tính năng legacy và cập nhật kiểm tra smoke/OpenAPI; không tác động dữ liệu MongoDB hoặc flow `department-evaluations` hiện hành.

## [Fix M5] - Bổ sung test cho review, task execution, upload và realtime

### Files created/modified

- `backend/tests/test_performance_review_service.py` — review thiếu minh chứng, review report có sẵn, audit batch và abort khi batch report thất bại.
- `backend/tests/test_task_execution_repository.py` — ensure index, upsert, đọc theo task/date, update review và đọc theo employee/date.
- `backend/tests/test_attachment_upload_service.py` — owner/scope, commit, cancel/discard và malware scan failure; checksum failure đã có từ trước.
- `backend/tests/test_realtime.py` — Change Stream worker cho `task_execution_reports` và `department_weekly_evaluations`.
- `CHANGELOG.md`

### Logic & Luồng

- Bổ sung kiểm thử cho đường tạo report/review sau tối ưu batch; khi batch report thất bại, service dừng trước metric và audit tiếp theo, không tạo side effect downstream.
- Bổ sung kiểm thử CRUD/query repository và các trạng thái upload trực tiếp quan trọng.
- Bổ sung kiểm thử publish event của hai Change Stream worker còn thiếu; không thay đổi worker hoặc realtime behavior.
- Không suy ra phần trăm coverage vì không chạy coverage report.

### Verification

- Baseline lịch sử theo yêu cầu: `88 passed`; baseline thực tế ngay trước M5: `94 passed`.
- Test mới: `11` test; tổng sau M5: `105 passed, 2 warnings` (`+17` so với mốc lịch sử 88, `+11` so với baseline thực tế 94).
- `ruff check .` đạt.
- `mypy app` vẫn đạt `0 lỗi` trên `94 source files`.

### Phạm vi tác động

- Chỉ bổ sung và mở rộng test cùng CHANGELOG; không thay đổi API, schema, dữ liệu MongoDB hoặc logic production.

## [Fix M3] - Sửa 41 lỗi mypy trên 7 file

### Files created/modified

- `backend/requirements-dev.txt` — thêm `boto3-stubs[s3]` cho boto3/S3.
- `backend/app/models/department_evaluation.py` — tách response attachment khỏi model lưu trữ để không override `storage_key: str` thành kiểu nullable.
- `backend/app/infrastructure/evidence_storage.py` — kiểm tra kiểu dữ liệu trước khi chuyển `file_size` sang `int`; xử lý thiếu stub boto3 bằng dependency chính thức.
- `backend/app/services/attachment_reconciliation_service.py` — annotation tường minh `set[str]` cho tập storage key được tham chiếu.
- `backend/app/services/dashboard_attention_service.py` — đổi tên biến cục bộ để không gán `dict | None` vào biến đã suy luận là `dict`.
- `backend/app/services/task_service.py` — dùng `List[...]` ở các annotation bị method `list` che khuất và cast range sau validation về `Literal["7d", "30d", "90d"]`.
- `backend/app/services/attachment_upload_service.py` — kiểm tra kiểu metadata size trước khi chuyển sang `int`.
- `backend/app/services/department_evaluation_service.py` — dùng `List[...]`/`dict[str, Any]` để tránh annotation bị hiểu là method `list`.
- `CHANGELOG.md`

### Logic & Luồng

- Không dùng `# type: ignore`; các giá trị `object` được kiểm tra kiểu tường minh trước khi chuyển đổi.
- Giữ nguyên contract runtime của attachment response: `storage_key` vẫn có thể không xuất hiện ở response metadata, còn model lưu trữ tiếp tục yêu cầu storage key.
- Không thay đổi logic nghiệp vụ, API shape hoặc cách tính dữ liệu; các thay đổi chỉ làm rõ type và giữ nguyên giá trị hợp lệ đã được hỗ trợ.

### Verification

- Baseline trước M3: `mypy app` báo `41 errors in 7 files` trên `94 source files`.
- Sau M3: `mypy app` → `Success: no issues found in 94 source files`.
- `pytest -q` → `94 passed, 1 warning`.
- `ruff check .` đạt.
- `compileall -q app tests scripts` đạt.

### Phạm vi tác động

- Chỉ sửa annotation, kiểm tra kiểu, model response attachment và dev dependency; không chạy migration, không thay đổi dữ liệu MongoDB.

## [Fix M4] - Tài liệu hóa chủ đích realtime cho upload session và coordination

### Files created/modified

- `backend/app/services/attachment_upload_service.py`
- `backend/app/services/coordination_service.py`
- `CHANGELOG.md`

### Logic & Luồng

- Upload session không phát Change Stream; owner nhận trạng thái create/complete/cancel qua response trực tiếp, nên không cần lifecycle event cho client khác.
- `COORDINATION_APPLIED` được giữ nguyên như tín hiệu nội bộ cho audit/quan sát; không có và không cần subscriber runtime mới. Client nhận cập nhật qua Change Stream của `alerts`, `department_directives` và `coordination_directives` trong cùng request.
- Đây là quyết định thiết kế có chủ đích, không phải khoảng trống để dành sửa sau; không thay đổi hành vi runtime.

### Verification

- Baseline trước M4: backend `94 passed, 1 warning`.
- Sau M4: backend `94 passed, 1 warning`.
- Chỉ thay đổi docstring/comment và CHANGELOG; không thêm topic, Change Stream hoặc subscriber.

### Phạm vi tác động

- Chỉ tài liệu hóa contract realtime; không thay đổi API, event flow, response shape hoặc dữ liệu MongoDB.

## [Fix C2] - Giảm N+1 và round-trip DB ở coordination, overload, performance review

### Files created/modified

- `backend/app/repositories/coordination_repository.py`
- `backend/app/services/coordination_service.py`
- `backend/app/repositories/overload_repository.py`
- `backend/app/services/overload_service.py`
- `backend/app/services/workload_rebalancer.py`
- `backend/app/repositories/task_execution_repository.py`
- `backend/app/repositories/task_repository.py`
- `backend/app/services/performance_review_service.py`
- `backend/tests/test_coordination_batching.py`
- `backend/tests/test_overload_batching.py`
- `backend/tests/test_performance_review_batching.py`
- `CHANGELOG.md`

### Logic & Luồng

- Coordination batch toàn bộ `find_plan` bằng một truy vấn `$in`; candidate được tải một lần cho mỗi nhóm duy nhất `(department_id, alert_date)` rồi lọc nhân viên nguồn ở tầng service cho từng alert.
- Overload batch employee bằng `$in`; candidate được tải một lần cho mỗi nhóm duy nhất `(department_id, date)` và lọc nhân viên đang quá tải theo từng log.
- Performance review dựng các `UpdateOne` cho toàn bộ execution report và ghi toàn bộ audit bằng `InsertOne` trong các `bulk_write`; công thức điểm, thứ tự dữ liệu response và API contract không đổi.

### Verification

| Luồng | Trước | Sau |
| --- | ---: | ---: |
| Coordination, 40 alert | 40 `find_plan` + tối đa 40 aggregate candidate | 1 batch plan + 4 aggregate theo nhóm |
| Overload, 40 log | 40 employee lookup + 40 aggregate candidate | 1 batch employee + 4 aggregate theo nhóm |
| Performance review, 30 task mới | 30 upsert report + 30 update review + 31 audit insert | 1 bulk execution report + 1 bulk audit write |

- Baseline trước C2: backend `91 passed, 1 warning`.
- Test batching C2: fixture `40 alert`, `40 overload log`, `30 task`; xác nhận số lần gọi repository giảm theo công thức trên và giữ response/giá trị nghiệp vụ.
- Full backend sau C2: `94 passed, 1 warning`.
- `backend/.venv\Scripts\python.exe -m ruff check .` đạt.
- `backend/.venv\Scripts\python.exe -m compileall -q app tests scripts` đạt.

### Phạm vi tác động

- Chỉ tối ưu số round-trip đọc/ghi trong ba luồng đã nêu; không đổi schema, endpoint, response shape, công thức tính điểm hoặc dữ liệu MongoDB hiện có.

## [Fix C1] - Chuẩn hóa BusinessClock cho thời gian nghiệp vụ

### Files created/modified

- `backend/app/core/time.py` (sử dụng `BusinessClock.now()` làm abstraction hiện có)
- `backend/app/main.py`
- `backend/app/api/alerts.py`
- `backend/app/api/attachments.py`
- `backend/app/api/coordination.py`
- `backend/app/api/dashboard.py`
- `backend/app/api/department_evaluations.py`
- `backend/app/api/departments.py`
- `backend/app/api/employees.py`
- `backend/app/api/manager_evaluations.py` (legacy, chỉ chuẩn hóa clock)
- `backend/app/api/overload.py`
- `backend/app/api/performance.py`
- `backend/app/api/tasks.py`
- `backend/app/api/thresholds.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/attachment_reconciliation_service.py`
- `backend/app/services/attachment_upload_service.py`
- `backend/app/services/coordination_service.py`
- `backend/app/services/dashboard_attention_service.py`
- `backend/app/services/department_evaluation_service.py`
- `backend/app/services/department_service.py`
- `backend/app/services/early_warning_detector.py`
- `backend/app/services/employee_service.py`
- `backend/app/services/manager_evaluation_service.py` (legacy, chỉ chuẩn hóa clock)
- `backend/app/services/overload_detector.py`
- `backend/app/services/overload_service.py`
- `backend/app/services/performance_review_service.py`
- `backend/app/services/performance_service.py`
- `backend/app/services/task_service.py`
- `backend/app/services/threshold_service.py`
- `backend/tests/time_fixtures.py`
- `backend/tests/test_attachment_upload_service.py`
- `backend/tests/test_department_evaluation_service.py`
- `backend/tests/test_early_warning_detector.py`
- `backend/tests/test_overload_detector.py`
- `backend/tests/test_task_service.py`

### Logic & Luồng

- Inject `BusinessClock` vào các service nghiệp vụ và truyền `BusinessClock()` từ dependency/factory/router; các event handler trong `main.py` dùng chung một clock cho vòng đời ứng dụng.
- Thay toàn bộ timestamp nghiệp vụ trực tiếp bằng `self._clock.now()`, đồng thời chuyển các helper tính ngày nghiệp vụ (`today()` và timezone) sang clock được inject.
- Giữ nguyên `datetime.now(timezone.utc)` ở `security.py` cho JWT và `health_service.py` cho timestamp kỹ thuật của health check.
- Giữ nguyên request/response contract và hành vi API; chỉ bổ sung khả năng thay clock trong test. Các test upload, đánh giá tuần, cảnh báo sớm 3 ngày, quá tải và task quá hạn dùng `FixedBusinessClock` để xác định.
- Cập nhật claim thời gian của các Phase cũ: BusinessClock hiện bao phủ toàn bộ service nghiệp vụ liên quan đến task, dashboard, điều phối, review, performance, alert, overload, threshold, department/employee và attachment.

### Verification

- Baseline trước sửa: backend `88 passed` bằng `backend/.venv`; Python hệ thống không dùng được do import nhầm gói `jose` Python 2 và thiếu plugin asyncio.
- Sau sửa: `backend/.venv\Scripts\python.exe -m pytest -q` → `88 passed, 1 warning`.
- `backend/.venv\Scripts\python.exe -m ruff check .` đạt.
- `backend/.venv\Scripts\python.exe -m compileall -q app tests` đạt.
- Grep `backend/app`: `datetime.now(timezone.utc)` chỉ còn ở `app/core/security.py` và `app/services/health_service.py`; không thao tác MongoDB/Docker/seed/reconcile.

### Phạm vi tác động

- Chỉ thay đổi nguồn clock của thời gian nghiệp vụ, wiring dependency và test deterministic; không đổi schema, API contract, dữ liệu MongoDB hay logic JWT/health.

## [Fix M1] - Sửa `created_by` mồ côi trong seed task

### Files created/modified

- `backend/scripts/seed_tasks_data.py`
- `backend/scripts/check_data_integrity.py`
- `backend/tests/test_seed_tasks_data.py`
- `README.md`
- `CHANGELOG.md`

### Logic & Luồng

- `seed_tasks_data.py` truy vấn Manager đang hoạt động của đúng phòng ban và dùng `_id` thật làm `created_by`; nếu phòng ban không có Manager, script truy vấn tài khoản Leadership đang hoạt động để fallback.
- `created_by` được đặt trong `$setOnInsert`, nên seed mới có liên kết thật nhưng rerun không tự cập nhật task cũ. Không có migration hoặc update dữ liệu MongoDB cũ.
- Thêm `check_data_integrity.py` chỉ đọc `tasks` và `users`, đếm task có `created_by` không tồn tại trong `users`, in kết quả và trả mã lỗi khác 0 khi phát hiện orphan.

### Verification

- Baseline task tests: `11 passed, 1 warning`; sau sửa: `11 passed, 1 warning`.
- Unit test creator resolution: xác nhận ưu tiên Manager phòng ban và fallback Leadership.
- Local database thử nghiệm `hrms_m1_test_20260906`: seed `3 phòng ban + 3 Manager + 1 Leadership + 15 nhân viên`, đồng bộ 15 task, integrity check `0 orphan created_by`.
- Database mặc định hiện có: integrity check read-only ghi nhận `50 task`, `48 orphan created_by`; không chạy update để sửa các bản ghi này.
- Không chạy migration, không xóa dữ liệu, không seed lại database mặc định.

### Phạm vi tác động

- Chỉ sửa hướng đi tới của script seed, thêm chẩn đoán integrity read-only và test; không thay đổi API task hoặc dữ liệu MongoDB hiện có.
- Nếu muốn dọn 48 orphan hiện có, đó là quyết định riêng và cần xác nhận trước khi chạy bất kỳ lệnh update nào trên MongoDB thật.

## [Fix M2] - Bổ sung index cho `threshold_configs`

### Files created/modified

- `backend/app/repositories/threshold_repository.py`
- `backend/app/services/threshold_service.py`
- `backend/tests/test_threshold_config.py`
- `README.md`
- `CHANGELOG.md`

### Logic & Luồng

- Thêm index compound `department_id → status → updated_at` phục vụ truy vấn cấu hình đã duyệt và index `created_at` phục vụ danh sách cấu hình theo thời gian tạo.
- `ThresholdConfigService.list`, `propose` và `approve` đều gọi `repository.ensure_indexes()` ở đầu method theo lazy-ensure pattern hiện có.
- Threshold Configs tiếp tục là API-only theo quyết định sản phẩm, không bổ sung UI trong lô này.

### Verification

- Baseline trước sửa: backend `89 passed, 1 warning`.
- Test M2: `2 passed`, gồm kiểm tra hai index và kiểm tra service gọi ensure trước cả ba method.
- Full backend pytest sau sửa: `91 passed, 1 warning`; Ruff và compileall đạt.
- Không tìm thấy UI/caller Threshold Configs trong `frontend/src` hoặc `frontend/e2e`.

### Phạm vi tác động

- Chỉ thay đổi index/wiring lazy-ensure ở backend, test và tài liệu; không thay đổi API contract, schema response hoặc frontend.

## [Phase 2] - Upload trực tiếp bằng Presigned URL

- Thêm upload session có thời hạn cho MinIO/S3, kiểm tra phạm vi, MIME, kích thước và SHA-256.
- Bổ sung API tạo, hoàn tất và hủy session; storage key luôn do backend sinh.
- Đánh giá tuần nhận `attachment_session_ids`; multipart cũ vẫn là fallback.
- Frontend có `UploadManager`, trạng thái chuẩn bị/tải/xác minh và fallback có kiểm soát.
- Direct upload mặc định tắt; bật đồng thời `STORAGE_DIRECT_UPLOAD_ENABLED` và `VITE_DIRECT_UPLOAD_ENABLED` sau khi cấu hình CORS bucket.
- Complete đọc lại object để xác minh checksum và chạy scanner trước khi session được commit.

## [Attachment performance] - 2026-09-06

- API danh sách đánh giá tuần hỗ trợ phân trang chuẩn, mặc định 12 bản ghi gần nhất.
- Danh sách/chi tiết không còn tạo signed URL hàng loạt; URL chỉ được cấp khi người dùng mở file.
- Bổ sung endpoint chi tiết và download URL có kiểm tra phạm vi phòng ban.
- Tách endpoint storage nội bộ/public; production bắt buộc public endpoint HTTPS.
- Chuẩn hóa ngày nghiệp vụ qua `BusinessClock` theo `Asia/Ho_Chi_Minh` cho toàn bộ service nghiệp vụ; task, dashboard, điều phối và review là các luồng đã được ghi nhận trước đó.
- Thêm scanner abstraction, dọn object mồ côi và lệnh `backend/scripts/reconcile_evidence_storage.py`.
- Kiểm tra: backend `84 passed`, Ruff và compileall đạt; frontend lint, test `42 passed`, build đạt.

## [Phase 0] - Hạ tầng & Khung dự án

### Files created/modified

- `.env.example`
- `.gitignore`
- `docker-compose.yml`
- `CHANGELOG.md`
- `backend/app/main.py`
- `backend/__init__.py`
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/api/health.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `backend/app/core/security.py`
- `backend/app/events/__init__.py`
- `backend/app/models/health.py`
- `backend/app/models/__init__.py`
- `backend/app/repositories/base.py`
- `backend/app/repositories/health_repository.py`
- `backend/app/repositories/__init__.py`
- `backend/app/services/health_service.py`
- `backend/app/services/__init__.py`
- `backend/app/events/event_bus.py`
- `backend/requirements.txt`
- `backend/pyproject.toml`
- `backend/scripts/check_app.py`
- `backend/scripts/check_compose.py`
- `backend/scripts/initialize_local_replica_set.py`
- `backend/tests/test_health_service.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/.eslintrc.cjs`
- `frontend/.prettierrc`
- `frontend/.prettierignore`
- `frontend/vite.config.js`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`
- `frontend/index.html`
- `frontend/src/main.jsx`
- `frontend/src/App.jsx`
- `frontend/src/index.css`
- `frontend/src/components/HealthStatus.jsx`
- `frontend/src/features/health/healthApi.js`
- `frontend/src/hooks/useHealth.js`
- `frontend/src/services/httpClient.js`
- `frontend/src/stores/appStore.js`

### Logic & Luồng

- Khung backend theo layered architecture: Router → Service → Repository → Database.
- Kết nối MongoDB bất đồng bộ bằng Motor, chạy trên MongoDB Replica Set để sẵn sàng cho Change Streams.
- Replica Set quảng bá `localhost:27017` để backend chạy trên máy host có thể hoàn tất kết nối sau handshake.
- Health check `GET /api/health` trả về trạng thái ứng dụng và thời điểm kiểm tra theo ISO 8601.
- Frontend React/Vite gọi `/api/health` qua Vite proxy và hiển thị trạng thái bằng tiếng Việt.
- Event bus nội bộ được tách riêng để các module sau giao tiếp qua sự kiện, không phụ thuộc trực tiếp vào nhau.
- Cấu hình Black/isort cho Python và ESLint/Prettier cho JavaScript/React.

### Verification

- Backend tests: `2 passed`; Python `compileall`, route check và cấu hình Compose tĩnh đều đạt.
- ESLint, Prettier và Vite production build đều đạt.
- Đã khởi động MongoDB Replica Set `rs0` cục bộ, xác nhận backend startup và gọi thật `GET http://127.0.0.1:8000/api/health` thành công.
- Đã khởi động Vite dev server và gọi `GET http://127.0.0.1:5173/api/health` qua proxy thành công.
- Đã xác minh thực tế bằng Docker Desktop 29.7.2/context `desktop-linux`: `docker compose up -d` thành công, MongoDB healthy, init container thoát mã 0 và Replica Set ở trạng thái `PRIMARY`.
- Đã xác minh backend kết nối MongoDB qua Motor bằng `GET http://127.0.0.1:8000/api/health` và frontend gọi qua Vite proxy bằng `GET http://127.0.0.1:5173/api/health`; cả hai đều trả `status: healthy`.

## [Phase 1] - Auth & Phân quyền RBAC

### Files created/modified

- `.env.example`
- `backend/requirements.txt`
- `backend/app/core/config.py`
- `backend/app/core/security.py`
- `backend/app/models/user.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/services/auth_service.py`
- `backend/app/api/auth.py`
- `backend/app/api/dependencies.py`
- `backend/app/main.py`
- `backend/scripts/check_app.py`
- `backend/scripts/seed_demo_user.py`
- `backend/scripts/smoke_auth.py`
- `backend/tests/test_auth.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/features/auth/authApi.js`
- `frontend/src/stores/authStore.js`
- `frontend/src/components/ProtectedRoute.jsx`
- `frontend/src/pages/LoginPage.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/UnauthorizedPage.jsx`
- `frontend/src/services/httpClient.js`
- `frontend/src/App.jsx`

### Logic & Luồng

- Backend xác thực bcrypt, chỉ cấp token cho tài khoản tồn tại và đang hoạt động.
- JWT chứa `sub`, `role`, `department_id`, thời hạn và được kiểm tra chữ ký, thời hạn, trạng thái tài khoản và sự khớp scope.
- `get_current_user` xác thực token rồi đọc lại user chuẩn từ MongoDB; token sai chữ ký/hết hạn hoặc token không còn khớp tài khoản trả 401.
- `require_role` trả 403 khi sai vai trò; `get_department_scope` trả phòng ban của Manager và `None` cho Leadership để biểu thị toàn công ty.
- Frontend lưu token trong Zustand + `localStorage`, tự gửi Bearer token, cung cấp `/login` và `ProtectedRoute` cho route Manager/Leadership.

### Verification

- Backend route check, compileall và tests Auth/RBAC: đạt.
- Frontend ESLint, Prettier và Vite build: đạt.
- Smoke test live qua MongoDB Replica Set: đăng nhập, JWT claims, `/api/auth/me`, token hết hạn và token sai chữ ký đều được kiểm tra; frontend Vite proxy cũng chuyển tiếp thành công.
- Không sửa chéo sang các module nghiệp vụ hiệu suất, cảnh báo, quá tải hoặc AI.

## [Phase 2] - Design System & Shared Layout

### Files created/modified

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tailwind.config.js`
- `frontend/src/index.css`
- `frontend/src/App.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/pages/WorkspaceSectionPage.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/components/layout/Header.jsx`
- `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/components/layout/MainLayout.jsx`
- `frontend/src/components/animations/FadeIn.jsx`
- `frontend/src/components/animations/SlideIn.jsx`
- `frontend/src/components/animations/CounterNumber.jsx`
- `frontend/src/components/animations/index.js`
- `frontend/scripts/check-navigation.mjs`
- `CHANGELOG.md`

### Logic & Luồng

- Chuẩn hóa theme Tailwind với bảng màu `brand`, `surface`, `ink`, trạng thái và typography `h1`, `h2`, `h3`, `body`, `caption`.
- `MainLayout` dùng Header cố định, Sidebar cố định và vùng nội dung chung; Header hiển thị logo, hồ sơ hiện tại và đăng xuất.
- Sidebar đọc role từ Zustand: Manager chỉ nhận nhóm menu phòng ban; Leadership nhận đầy đủ nhóm menu toàn công ty.
- Bổ sung thư viện Framer Motion với các wrapper `FadeIn`, `SlideIn` và `CounterNumber`; Dashboard đã tích hợp để làm mẫu sử dụng.
- Các mục menu đã được nối vào các route khung theo đúng vai trò để không tạo đường dẫn rỗng.

### Verification

- `npm run check:navigation`: đạt, xác nhận Manager có 4 mục và Leadership có 7 mục theo ma trận quyền.
- `npm run lint`: đạt.
- `npm run format:check`: đạt.
- `npm run build`: đạt với dependency Framer Motion.
- Phase 2 chỉ tác động đến lớp giao diện dùng chung, không sửa chéo các module nghiệp vụ Backend.

## [Phase 3] - Dữ liệu nền & Script Seed

### Files created/modified

- `backend/app/main.py`
- `backend/app/models/department.py`
- `backend/app/models/employee.py`
- `backend/app/repositories/department_repository.py`
- `backend/app/repositories/employee_repository.py`
- `backend/app/services/department_service.py`
- `backend/app/services/employee_service.py`
- `backend/app/api/departments.py`
- `backend/app/api/employees.py`
- `backend/scripts/check_app.py`
- `backend/scripts/seed_base_data.py`
- `backend/scripts/smoke_phase3.py`
- `frontend/src/App.jsx`
- `frontend/src/index.css`
- `frontend/src/services/httpClient.js`
- `frontend/src/features/departments/departmentsApi.js`
- `frontend/src/features/employees/employeesApi.js`
- `frontend/src/components/Modal.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/pages/DepartmentsPage.jsx`
- `frontend/src/pages/EmployeesPage.jsx`
- `frontend/scripts/check-navigation.mjs`
- `CHANGELOG.md`

### Logic & Luồng

- Bổ sung schema Pydantic và document MongoDB cho `departments` và `employees`, dùng ObjectId ở tầng dữ liệu và mã chuỗi an toàn ở API response.
- API `/api/departments`: mọi tài khoản đã xác thực được đọc theo scope; chỉ Leadership được tạo, sửa và xóa. Không cho xóa phòng ban đang có nhân viên.
- API `/api/employees`: Leadership xem toàn công ty; Manager luôn bị giới hạn bởi `department_id` trong token ở list/detail/create/update/delete, kể cả khi truyền query phòng ban khác.
- Repository dùng Motor bất đồng bộ; service chuẩn hóa dữ liệu, kiểm tra ObjectId, phòng ban tồn tại và mã trùng.
- `seed_base_data.py` tạo dữ liệu idempotent gồm 3 phòng ban (Kinh doanh, Kỹ thuật, Chăm sóc khách hàng), 1 Leadership, 3 Manager và 5 nhân viên mỗi phòng.
- Frontend bổ sung bảng dữ liệu, modal thêm/sửa/xóa phòng ban và nhân viên; màn hình nhân viên dùng đúng API scope, Leadership có lựa chọn phòng ban còn Manager không thể đổi scope trên giao diện.

### Verification

- `seed_base_data.py`: đạt, tạo 3 phòng ban, 1 Leadership, 3 Manager và 15 nhân viên.
- `smoke_phase3.py` trực tiếp qua backend `8001`: đạt CRUD phòng ban/nhân viên, Leadership RBAC và cách ly Manager giữa phòng KD/KT.
- `smoke_phase3.py` qua Vite proxy `5173` → backend `8000`: đạt cùng contract.
- Backend route check, compileall và `pytest`: đạt (`6 passed`).
- Frontend navigation role check, ESLint, Prettier và Vite production build: đạt.

## [Phase 3.5] — Stabilization

### Files created/modified

- `.gitignore`
- `backend/pyproject.toml`
- `backend/requirements-dev.txt`
- `backend/app/api/dependencies.py`
- `backend/app/api/auth.py`
- `backend/app/api/departments.py`
- `backend/app/api/health.py`
- `backend/app/core/database.py`
- `backend/app/core/security.py`
- `backend/app/events/event_bus.py`
- `backend/app/models/health.py`
- `backend/app/repositories/base.py`
- `backend/app/repositories/health_repository.py`
- `backend/app/repositories/user_repository.py`
- `backend/app/services/auth_service.py`
- `backend/app/services/department_service.py`
- `backend/app/services/employee_service.py`
- `backend/app/services/health_service.py`
- `backend/scripts/check_app.py`
- `backend/scripts/check_compose.py`
- `backend/scripts/initialize_local_replica_set.py`
- `backend/scripts/seed_base_data.py`
- `backend/scripts/seed_demo_user.py`
- `backend/scripts/smoke_phase3.py`
- `backend/tests/test_auth.py`
- `backend/tests/test_health_service.py`
- `backend/tests/test_department_service.py`
- `backend/tests/test_employee_service.py`
- `frontend/.prettierignore`
- `frontend/package.json`
- `frontend/src/services/httpClient.js`
- `frontend/src/stores/authStore.test.js`
- `frontend/src/components/ProtectedRoute.test.jsx`
- `frontend/src/components/layout/Sidebar.test.jsx`
- `frontend/src/test/setup.js`
- `frontend/vitest.config.js`
- `frontend/playwright.config.js`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Chốt formatter/import/lint/type gate: Black dùng cache tạm `BLACK_CACHE_DIR` để chạy ổn định trên thư mục OneDrive; isort dùng profile Black; Ruff bỏ `B008` có chủ đích cho router FastAPI, tự sửa import và giữ `except Exception` ngoài cùng ở mức tối thiểu với lỗi cụ thể `PyMongoError`.
- Mypy dùng `explicit_package_bases`, `mypy_path = "."` và `types-python-jose`; bổ sung kiểm tra `None` sau update ở DepartmentService/EmployeeService.
- Bổ sung unit test service cho CRUD và luật cách ly scope Manager/Leadership; coverage riêng hai service đạt 98%.
- Bổ sung Vitest/Testing Library cho authStore, ProtectedRoute và Sidebar theo role.
- Bổ sung Playwright E2E cho login thất bại, Manager chỉ thấy dữ liệu/menu phòng mình và Leadership CRUD phòng ban.
- Trong E2E đã phát hiện và sửa lỗi hạ tầng HTTP: các request POST có `Content-Type` từng làm mất `Authorization` do spread options ghi đè headers; `httpClient` nay merge headers đúng thứ tự.

### Definition of Done — Phase 0–3

- [x] `black --check .`: đạt, 43 file không cần định dạng thêm.
- [x] `isort --profile black --check-only .`: đạt; đã tự sửa 5 file import trước khi kiểm tra.
- [x] `ruff check .`: đạt hoàn toàn.
- [x] `mypy app`: đạt, 30 source files.
- [x] Backend unit tests: 17 passed; coverage tầng `department_service` + `employee_service`: 98%.
- [x] Vitest: 3 test files, 8 tests passed.
- [x] Playwright E2E: 3 tests passed.
- [x] Docker MongoDB: container healthy, Replica Set `PRIMARY`; seed idempotent thành công.
- [x] Backend `/api/health` và frontend Vite proxy `/api/health`: đều trả `status: healthy`.
- [x] Regression: auth smoke (login, claims, token hết hạn/sai chữ ký), Phase 3 scope smoke, route check, compileall, frontend navigation check, ESLint, Prettier và Vite build đều đạt.

### Phạm vi tác động

- Chỉ tác động vào quality tooling, test/config, các file backend đã được formatter/lint/type-check và lớp HTTP frontend cần sửa để E2E CRUD hoạt động đúng.
- Không thêm module nghiệp vụ mới, không sửa chéo sang Performance, Alert, Overload, AI hoặc Streaming.
- Artifact `frontend/test-results/` chỉ do Playwright sinh ra đã được loại khỏi source tree và thêm vào ignore; không có file ngoài phạm vi dự án bị tác động.

## [Phase 4] - Realtime & Streaming Engine

### Files created/modified

- `backend/app/api/dependencies.py`
- `backend/app/main.py`
- `backend/app/realtime/__init__.py`
- `backend/app/realtime/connection_manager.py`
- `backend/app/realtime/change_stream_worker.py`
- `backend/app/realtime/websocket.py`
- `backend/scripts/check_app.py`
- `backend/scripts/smoke_realtime.py`
- `backend/requirements-dev.txt`
- `backend/tests/test_realtime.py`
- `frontend/vite.config.js`
- `frontend/src/hooks/useRealtimeUpdates.js`
- `frontend/src/hooks/useRealtimeUpdates.test.js`
- `frontend/src/components/RealtimeAlertNotice.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `CHANGELOG.md`

### Logic & Luồng

- `ConnectionManager` lưu socket cùng `user_id`, `role`, `department_id`; trước mỗi lần gửi alert, manager áp dụng scope: Leadership nhận toàn công ty, Manager chỉ nhận alert đúng phòng ban của mình.
- WebSocket `/ws/realtime?token=...` dùng chung logic giải mã JWT và đọc lại user từ MongoDB; token thiếu/sai/hết hạn bị từ chối ở handshake bằng 403. Socket được loại khi client disconnect hoặc gửi thất bại.
- `AlertsChangeStreamWorker` chạy trong FastAPI lifespan, lắng nghe MongoDB Change Stream collection `alerts`, phát event qua `EventBus` rồi mới đến `ConnectionManager`; worker tự retry khi MongoDB tạm thời lỗi và được cancel khi ứng dụng shutdown.
- Hook `useRealtimeUpdates(topic, callback)` kết nối qua Vite `/ws` proxy, lọc topic, tự reconnect theo backoff và đóng socket khi logout, unmount hoặc rời trang. `RealtimeAlertNotice` là consumer mẫu trên Dashboard.
- `smoke_realtime.py` chèn một alert trực tiếp vào MongoDB để xác minh đường đi MongoDB Change Stream → EventBus → WebSocket proxy → client realtime và cách ly scope.

### Verification

- `check_app.py`: đạt, xác nhận `/ws/realtime` cùng các HTTP route Phase 0–3.
- `backend/tests/test_realtime.py`: 3 passed; kiểm tra broadcast Manager/Leadership, disconnect/failure cleanup và worker publish event.
- Backend regression: 20 passed; Black, isort, Ruff và mypy đều đạt.
- `frontend/src/hooks/useRealtimeUpdates.test.js`: kiểm tra topic filtering, reconnect và đóng socket khi logout/unmount.
- Vitest: 4 test files, 11 tests passed; ESLint, Prettier và Vite build đạt.
- Playwright Phase 3.5 regression: 3 tests passed.
- Live realtime smoke qua `ws://127.0.0.1:5173/ws/realtime`: đạt; alert phòng KD tới Manager KD và Leadership, không tới Manager KT; token không hợp lệ bị HTTP 403.
- Docker MongoDB healthy, Replica Set `PRIMARY`; backend `/api/health` healthy.

### Phạm vi tác động

- Realtime được cô lập trong `backend/app/realtime/` và hook frontend dùng chung; không import service nghiệp vụ Performance, Alert, Overload hoặc AI vào worker/manager.
- Chỉ cập nhật lifespan, dependency dùng chung, Vite WebSocket proxy và Dashboard consumer mẫu để kiểm chứng hạ tầng; chưa triển khai nghiệp vụ cảnh báo mới.

## [Phase 5] - Chỉ số hiệu suất & Bộ tính điểm

### Files created/modified

- `backend/app/models/performance.py`
- `backend/app/repositories/performance_repository.py`
- `backend/app/services/performance_score_calculator.py`
- `backend/app/services/performance_service.py`
- `backend/app/api/performance.py`
- `backend/app/main.py`
- `backend/scripts/seed_performance_data.py`
- `backend/scripts/smoke_performance.py`
- `backend/tests/test_performance_score_calculator.py`
- `backend/tests/test_performance_service.py`
- `frontend/src/features/performance/performanceApi.js`
- `frontend/src/features/performance/performanceScore.js`
- `frontend/src/pages/PerformanceEntryPage.jsx`
- `frontend/src/App.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Tách `PerformanceScoreCalculator` độc lập với công thức điểm khối lượng công việc theo chuẩn 4 task/ngày, giới hạn multiplier 1.5 và cap 100; điểm cuối dùng trọng số chất lượng/khối lượng 70/30.
- Bổ sung schema và repository async Motor cho `performance_metrics`, liên kết nhân viên qua `department_id`, lọc theo nhân viên/phòng ban/khoảng ngày và chặn trùng điểm cùng nhân viên trong cùng ngày.
- `POST /api/performance/daily` lấy người chấm từ JWT hiện tại, chỉ cho Manager ghi điểm nhân viên cùng phòng; Leadership không được dùng API nhập điểm Manager. `GET /api/performance` cho phép Leadership xem toàn công ty, còn Manager luôn bị giới hạn phòng mình.
- Script `seed_performance_data.py` tạo idempotent 60 ngày dữ liệu cho 15 nhân viên, tổng 900 bản ghi, kèm các chuỗi task volume cao/chất lượng thấp để phục vụ kiểm thử quá tải ở giai đoạn sau.
- Frontend bổ sung màn hình Manager nhập điểm với slider `quality_score`, nhập số task, chọn nhân viên/ngày, preview điểm tức thời và bảng lịch sử gần đây.

### Verification

- Backend pytest: 29 passed; test calculator xác nhận `tasks_completed=4`, `quality_score=80` cho kết quả `86.0`; test service xác nhận Manager khác phòng bị từ chối.
- Seed smoke: `Đã seed 900 bản ghi hiệu suất cho 60 ngày.`
- API smoke: `Performance smoke test passed: 60 ngày, công thức 86.0 và RBAC scope.`
- Route check: xác nhận `/api/performance/daily`, `/api/performance` và các route Phase 0–4; compileall đạt.
- Backend quality gates: Black 58 file không đổi, isort đạt, Ruff đạt, mypy đạt với 39 source files.
- Frontend Vitest: 4 files, 11 tests passed; ESLint và Prettier đạt; Vite production build đạt với 474 modules.
- Playwright E2E: 4 tests passed, gồm luồng đăng nhập, RBAC dữ liệu/menu, CRUD phòng ban và màn hình nhập điểm có slider/preview.
- Runtime: Docker MongoDB healthy, Replica Set `PRIMARY`; backend và Vite proxy `/api/health` đều trả `status: healthy`.

### Phạm vi tác động

- Chỉ bổ sung module Performance, màn hình nhập điểm, test/smoke/seed liên quan và đăng ký route cần thiết trong `main.py`/`App.jsx`.
- Không sửa chéo logic Realtime, Alert, Overload, AI hoặc các module nghiệp vụ khác.

## [Phase 6] - Dashboard Đồ thị Hiệu suất

### Files created/modified

- `backend/app/models/performance.py`
- `backend/app/repositories/performance_repository.py`
- `backend/app/services/performance_service.py`
- `backend/app/api/performance.py`
- `backend/app/realtime/change_stream_worker.py`
- `backend/app/realtime/connection_manager.py`
- `backend/app/main.py`
- `backend/scripts/check_app.py`
- `backend/scripts/smoke_performance_analytics.py`
- `backend/scripts/smoke_realtime.py`
- `backend/tests/test_performance_service.py`
- `backend/tests/test_realtime.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/features/performance/performanceApi.js`
- `frontend/src/features/performance/PerformanceDashboard.jsx`
- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/App.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Bổ sung ba API analytics dùng MongoDB aggregation: chuỗi thời gian một nhân viên, so sánh nhân viên trong phòng ban và tổng hợp so sánh phòng ban toàn công ty.
- Backend kiểm tra scope trước khi aggregation: Manager chỉ xem nhân viên/phòng ban của mình; endpoint company chỉ Leadership được gọi. Nhân viên không có điểm vẫn trả về metadata hợp lệ với `metrics: []` hoặc các giá trị tổng hợp rỗng.
- Dashboard Recharts hiển thị Line Chart xu hướng nhân viên, Bar Chart so sánh nhân viên và Bar Chart so sánh phòng ban cho Leadership. Mỗi biểu đồ có câu chú thích tiếng Việt ngay dưới tiêu đề; dữ liệu thiếu hiển thị trạng thái dễ hiểu thay vì lỗi `null/undefined`.
- Mở rộng hạ tầng realtime để lắng nghe `performance_metrics`, bổ sung `department_id` từ nhân viên trong worker và phát topic `performance_metrics`; `useRealtimeUpdates` tự refresh dữ liệu dashboard khi có điểm mới mà không tải lại toàn trang.

### Verification

- Backend pytest: 33 passed; bao gồm test scope analytics, dữ liệu nhân viên chưa có điểm và enrichment event realtime.
- Analytics smoke: `Performance analytics smoke test passed: Mongo aggregation, 60-day trend and RBAC.`
- Realtime smoke: chèn metric trực tiếp vào MongoDB; Manager đúng phòng và Leadership nhận event, Manager phòng khác không nhận.
- Route check: xác nhận `/api/performance/analytics/employee/{employee_id}`, `/api/performance/analytics/department/{department_id}`, `/api/performance/analytics/company` và WebSocket `/ws/realtime`.
- Backend quality gates: Black 59 file không đổi, isort đạt, Ruff đạt, mypy đạt với 39 source files, compileall đạt.
- Frontend Vitest: 4 files, 11 tests passed; ESLint và Prettier đạt; Vite production build đạt với 1.061 modules. Vite có cảnh báo bundle lớn do Recharts nhưng build thành công.
- Playwright E2E: 6 tests passed, gồm line chart Manager, bar chart Leadership, chú thích UX và các regression Phase 3.5.
- Runtime: Docker MongoDB healthy, Replica Set `PRIMARY`; backend `/api/health` trả HTTP 200 và trạng thái `healthy`.

### Phạm vi tác động

- Chỉ mở rộng module Performance, dashboard frontend, dependency Recharts, test/smoke và realtime infrastructure dùng chung cho topic điểm hiệu suất.
- Không sửa logic nghiệp vụ Alert, Overload hoặc AI; không thay đổi contract Auth/RBAC hiện có ngoài việc tái sử dụng dependency scope.

## [Phase 7] - Cảnh báo Ngưỡng bất lợi

### Files created/modified

- `backend/app/events/event_bus.py`
- `backend/app/models/threshold.py`
- `backend/app/models/alert.py`
- `backend/app/models/performance.py`
- `backend/app/repositories/threshold_repository.py`
- `backend/app/repositories/alert_repository.py`
- `backend/app/repositories/performance_repository.py`
- `backend/app/services/threshold_service.py`
- `backend/app/services/early_warning_detector.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/performance_service.py`
- `backend/app/api/thresholds.py`
- `backend/app/api/alerts.py`
- `backend/app/main.py`
- `backend/scripts/seed_performance_data.py`
- `backend/scripts/smoke_early_warning.py`
- `backend/scripts/check_app.py`
- `backend/tests/test_early_warning_detector.py`
- `backend/tests/test_alert_service.py`
- `backend/tests/test_performance_service.py`
- `backend/tests/test_realtime.py`
- `frontend/src/features/alerts/alertsApi.js`
- `frontend/src/pages/AlertsPage.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/App.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Thêm schema `threshold_configs` với trạng thái `proposed/approved`; Manager có thể đề xuất cấu hình theo phòng ban, Leadership có thể duyệt. Detector mặc định dùng chuỗi 3 ngày và ngưỡng giảm chất lượng 20% nếu chưa có cấu hình đã duyệt.
- `EarlyWarningDetector` quét các cửa sổ ngày liên tiếp. Cảnh báo chỉ sinh khi `T1 < T2 < T3`, `Q1 > Q2 > Q3` và mức giảm từ ngày đầu đến ngày cuối vẫn nhỏ hơn 20%; fingerprint giúp không tạo cảnh báo trùng.
- Thêm schema/repository/service cho `alerts`, API `GET /api/alerts`, `POST /api/alerts/scan` và `PATCH /api/alerts/{alert_id}/resolve`. Manager bị giới hạn theo `department_id`; Leadership xem toàn công ty.
- Khi metric mới được ghi, Performance Service chỉ phát event `PERFORMANCE_METRIC_CREATED` qua EventBus. Early Warning Service xử lý event và phát `ALERT_CREATED`; detector không gọi trực tiếp WebSocket. Alert được lưu MongoDB để Change Stream của Streaming Engine broadcast tới client đúng scope.
- Seed hiệu suất bổ sung chuỗi mẫu cho nhân viên mã `-003`: task `2 → 3 → 4`, chất lượng `88 → 82 → 78`, giảm dưới 20%, dùng để kiểm thử cảnh báo sớm.
- Frontend thêm màn hình cảnh báo Amber, nút quét lại, modal ghi chú xử lý và cập nhật trạng thái ngay sau khi API thành công; realtime topic `alerts` tự tải lại danh sách.

### Verification

- Backend pytest: 37 passed; detector xác nhận chuỗi 3 ngày, điều kiện giảm đúng dưới 20%, chống trùng và phát `ALERT_CREATED`.
- Seed: 900 bản ghi hiệu suất cho 60 ngày.
- Early-warning smoke: cảnh báo `medium` cho `KD-NV-003`, đúng suggested action và Manager chỉ nhận cảnh báo phòng KD.
- UI E2E: 7 passed; kiểm tra hiển thị cảnh báo Amber, mở modal, bấm `Đã xử lý` và lưu ghi chú. MongoDB xác nhận trạng thái `resolved` cùng ghi chú thật.
- Realtime smoke: Change Stream `alerts` và `performance_metrics` broadcast đúng Manager/Leadership scope.
- Route check: xác nhận Alerts, Threshold Config, Performance Analytics và WebSocket routes; compileall đạt.
- Backend quality gates: Black 70 file không đổi, isort đạt, Ruff đạt, mypy đạt với 48 source files.
- Frontend Vitest: 4 files, 11 tests passed; ESLint, Prettier và Vite build đạt. Vite có cảnh báo bundle lớn do Recharts nhưng build thành công.
- Runtime: backend `/api/health` HTTP 200 `healthy`; MongoDB Replica Set và Change Stream smoke hoạt động.

### Phạm vi tác động

- Chỉ bổ sung Early Warning, threshold config, alert UI/API, seed/test smoke và wiring EventBus cần thiết.
- Không sửa chéo logic Overload hoặc AI; Streaming Engine chỉ nhận event/dữ liệu Change Stream và vẫn độc lập với detector.

## [Phase 8] - Phân tích Quá tải & Đánh giá Quản lý

### Files created/modified

- `backend/app/events/event_bus.py`
- `backend/app/models/alert.py`
- `backend/app/models/overload.py`
- `backend/app/models/manager_evaluation.py`
- `backend/app/repositories/alert_repository.py`
- `backend/app/repositories/overload_repository.py`
- `backend/app/repositories/manager_evaluation_repository.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/overload_detector.py`
- `backend/app/services/workload_rebalancer.py`
- `backend/app/services/overload_service.py`
- `backend/app/services/manager_evaluation_service.py`
- `backend/app/api/overload.py`
- `backend/app/api/manager_evaluations.py`
- `backend/app/main.py`
- `backend/scripts/seed_performance_data.py`
- `backend/scripts/smoke_overload.py`
- `backend/scripts/check_app.py`
- `backend/tests/test_overload_detector.py`
- `backend/tests/test_workload_rebalancer.py`
- `backend/tests/test_manager_evaluation_service.py`
- `frontend/src/features/overload/overloadApi.js`
- `frontend/src/features/managerEvaluations/managerEvaluationsApi.js`
- `frontend/src/pages/OverloadPage.jsx`
- `frontend/src/pages/ManagerEvaluationsPage.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/App.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- `OverloadDetector` kiểm tra hai điều kiện cứng: khối lượng trong ngày lớn hơn 4 công việc; hoặc chất lượng giảm ít nhất 20% trong 3 ngày liên tiếp so với trung bình 7 ngày liền trước. Mỗi log có lý do, giá trị tại ngày vi phạm và baseline để giải thích được trên giao diện.
- `WorkloadRebalancer` chỉ đề xuất nhân viên đang hoạt động trong cùng phòng ban, có tối đa 2 công việc và chất lượng từ 80 điểm trở lên.
- Detector chỉ phát `OVERLOAD_DETECTED`; `AlertService` lắng nghe event và tạo cảnh báo mức `high`. Việc broadcast vẫn đi qua MongoDB Change Stream/Streaming Engine, không gọi trực tiếp WebSocket từ logic nghiệp vụ.
- `ManagerEvaluationService` và `ManagerEvaluationRepository` là module riêng: tính trung bình `performance_score` theo phòng ban/tháng, lưu điểm và ghi chú của Leadership; không import hoặc gọi Overload service.
- Backend áp dụng `get_department_scope`: Manager chỉ xem log quá tải phòng mình, Leadership xem toàn công ty. API đánh giá quản lý chỉ cho vai trò Leadership.
- Frontend bổ sung màn hình quá tải với badge đỏ, lý do tiếng Việt và đề xuất san sẻ; màn hình đánh giá quản lý theo tháng chỉ xuất hiện trong navigation Leadership.

### Verification

- Seed lại thành công 900 bản ghi hiệu suất/60 ngày; dữ liệu `KD-NV-001` kích hoạt điều kiện A và `KD-NV-002` kích hoạt điều kiện B với baseline 7 ngày.
- `smoke_overload.py`: đạt điều kiện A/B, tạo Alert `high` qua EventBus, đề xuất đúng nhân viên cùng phòng và Manager không đọc được dữ liệu ngoài scope.
- Backend: `pytest` 42 passed; Ruff, isort, mypy (58 source files), Black và compileall đạt.
- Frontend: Vitest 11 passed, ESLint và Prettier đạt, Vite production build đạt; build còn cảnh báo bundle Recharts lớn hơn 500 kB.
- Playwright E2E: 9 passed, gồm UI quá tải theo role/scope và Leadership lưu đánh giá quản lý theo tháng.
- Runtime: `GET /api/health` backend và Vite proxy đều trả `status: healthy`. Shell xác minh Phase 8 hiện không nhận lệnh `docker`/không tìm thấy Docker CLI trên PATH, nên trạng thái Docker không được tái xác minh trong lượt này; không có thay đổi nào vào cấu hình Docker.

### Phạm vi tác động

- Chỉ bổ sung module Overload, module Manager Evaluation, event wiring cần thiết, seed/test/smoke và route/UI tương ứng.
- Alert repository/service được mở rộng tối thiểu để phân biệt cảnh báo sớm với cảnh báo quá tải; Streaming, Performance, Auth/RBAC và AI không bị thay đổi logic nghiệp vụ.
- Đã rà soát cách ly: Overload giao tiếp với Alert/Streaming qua EventBus; Manager Evaluation không phụ thuộc Overload. Không có file ngoài phạm vi dự án bị tác động.

## [UX] - Gộp Tổng quan và Phân tích hiệu suất

### Files created/modified

- `frontend/src/App.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/features/performance/PerformanceDashboard.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Dashboard `/manager` và `/leadership` là trang duy nhất cho cả tổng quan lẫn biểu đồ phân tích hiệu suất.
- Xóa mục điều hướng phân tích riêng để tránh trùng chức năng. Các URL cũ `/manager/analytics` và `/leadership/performance` vẫn được giữ tương thích nhưng tự động redirect về Dashboard tương ứng.
- Không thay đổi API, dữ liệu MongoDB hoặc logic phân quyền.
- Khi mở Dashboard, hệ thống ưu tiên chọn nhân viên đầu tiên có dữ liệu hiệu suất; người dùng vẫn có thể chọn nhân viên chưa có điểm và nhận thông báo phù hợp.

### Verification

- Manager không còn thấy menu “Phân tích hiệu suất”.
- Route `/leadership/performance` redirect về `/leadership` thành công.
- Playwright E2E: 9 passed; Vitest: 11 passed; ESLint và Prettier đạt.

## [Fix] - WebSocket trang Tổng quan

### Files created/modified

- `frontend/vite.config.js`
- `CHANGELOG.md`

### Logic & Luồng

- Đồng nhất Vite proxy `/api` và `/ws` về backend IPv4 `127.0.0.1:8000`. Cấu hình cũ dùng `localhost`, có thể bị Windows phân giải sang `::1` trong khi Uvicorn chỉ bind `127.0.0.1`, khiến WebSocket realtime bị `failed`.

### Verification

- Realtime smoke qua `ws://127.0.0.1:5173/ws/realtime`: đạt Change Stream, WebSocket và RBAC scope.
- Vitest: 11 passed; Playwright E2E: 9 passed; ESLint và Prettier đạt.

## [Fix] - Kết nối số liệu trang Tổng quan

### Files created/modified

- `frontend/src/pages/DashboardPage.jsx`
- `frontend/src/features/alerts/alertsApi.js`
- `backend/app/api/alerts.py`
- `backend/app/services/alert_service.py`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Dashboard gọi `/api/employees` theo scope hiện tại để tính tổng nhân sự và số đang hoạt động.
- Dashboard gọi `/api/alerts?status=open&alert_type=all` để tính số cảnh báo cần theo dõi, sau đó tự tải lại khi nhận event realtime topic `alerts`.
- API cảnh báo giữ mặc định màn hình cảnh báo sớm, đồng thời cho phép Dashboard yêu cầu tổng hợp cả cảnh báo sớm và quá tải bằng `alert_type=all`.

### Verification

- Manager demo hiển thị số nhân sự và số đang hoạt động lấy từ MongoDB thay cho số 0 tĩnh.
- Playwright E2E: 9 passed; Vitest: 11 passed; ESLint và Prettier đạt.

## [Phase 9] - Trợ lý AI Tiếng Việt

### Files created/modified

- `.env.example`
- `backend/requirements.txt`
- `backend/app/core/config.py`
- `backend/app/core/field_labels_vi.py`
- `backend/app/ai/__init__.py`
- `backend/app/ai/base.py`
- `backend/app/ai/factory.py`
- `backend/app/ai/providers.py`
- `backend/app/models/ai.py`
- `backend/app/services/ai_service.py`
- `backend/app/api/ai.py`
- `backend/app/main.py`
- `backend/scripts/check_app.py`
- `backend/tests/test_field_labels_vi.py`
- `backend/tests/test_ai_factory.py`
- `backend/tests/test_ai_service.py`
- `backend/tests/test_ai_api.py`
- `frontend/src/features/ai/aiApi.js`
- `frontend/src/features/ai/AiAssistantWidget.jsx`
- `frontend/src/features/ai/AiAssistantWidget.test.jsx`
- `frontend/src/components/layout/MainLayout.jsx`
- `backend/app/services/alert_service.py` (chỉ bị Black format khi thử quality gate)
- `backend/scripts/smoke_overload.py` (chỉ bị Black format khi thử quality gate)
- `CHANGELOG.md`

### Logic & Luồng

- Tạo `FIELD_LABELS_VI` và `translate_metrics_to_vietnamese` để chuyển dữ liệu JSON hiệu suất, cảnh báo và quá tải thành văn bản tiếng Việt trước khi tạo prompt. `sanitize_ai_text` tiếp tục là lớp bảo vệ cuối cho câu hỏi và phản hồi, không để lộ tên field kỹ thuật.
- Áp dụng Strategy Pattern với interface `IAiProvider` và ba adapter `GeminiProvider`, `GroqProvider`, `OpenRouterProvider`. `AiProviderFactory` thử provider chính rồi fallback provider; circuit breaker tạm ngắt provider lỗi và trả thông báo lịch sự tiếng Việt khi chưa cấu hình/hết khả dụng.
- Thêm `POST /api/ai/chat/stream` trả Server-Sent Events. Service chỉ đọc dữ liệu qua repository với `get_department_scope`: Manager nhận ngữ cảnh phòng ban mình, Leadership nhận ngữ cảnh toàn công ty. Lỗi MongoDB/provider được cô lập ở biên AI, không làm sập API.
- Bổ sung widget `Trợ lý AI` dùng chung trong `MainLayout`; frontend đọc SSE, cập nhật hiệu ứng gõ chữ và huỷ `AbortController` khi đóng widget hoặc rời trang.

### Verification

- Backend pytest: `48 passed`; gồm kiểm tra dịch nhãn, fallback khi provider lỗi, circuit-safe response, scope Manager và SSE response an toàn.
- Route check: `backend/scripts/check_app.py` đạt, xác nhận `/api/ai/chat/stream` cùng các route Phase 0–8.
- Backend Ruff, isort, mypy và compileall đạt; mypy kiểm tra 66 source files.
- Frontend Vitest: `5 test files, 12 tests passed`; ESLint, Prettier và Vite production build đạt. Build vẫn có cảnh báo bundle lớn do Recharts.
- Khi `AI_API_KEY` rỗng, factory không gọi provider và trả thông báo tiếng Việt; test xác nhận phản hồi không chứa `tasks_completed`, `quality_score` hoặc tên field kỹ thuật khác.
- Black không thể hoàn tất trên checkout OneDrive: tiến trình bị treo quá 30 giây ngay cả khi giới hạn vào các file Phase 9 và đã được dừng. Đây là giới hạn môi trường đồng bộ, không phải lỗi format đã được báo từ Black; nên chạy lại sau khi chuyển repo khỏi OneDrive.

### Phạm vi tác động

- Chỉ thêm module AI, lớp dịch nhãn dùng cho AI, route/wiring cần thiết, widget dùng chung, test và cấu hình provider.
- Không thay đổi logic nghiệp vụ Performance, Alert, Overload, Manager Evaluation, Realtime hoặc Auth/RBAC; scope AI chỉ tái sử dụng dependency xác thực hiện có.
- Hai file ngoài phạm vi nêu trên chỉ bị công cụ Black chạm định dạng trong lần thử gate; không có thay đổi logic nghiệp vụ. Do checkout chưa có file được Git theo dõi để khôi phục chính xác, trạng thái này được ghi nhận minh bạch để review trước commit.

## [Phase 10] - Hoàn thiện Hệ thống & Thông báo

### Files created/modified

- `frontend/src/features/notifications/NotificationBell.jsx`
- `frontend/src/features/notifications/NotificationBell.test.jsx`
- `frontend/src/components/layout/Header.jsx`
- `backend/tests/test_phase10_hardening.py`
- `frontend/e2e/phase3-5.spec.js`
- `README.md`
- `CHANGELOG.md`

### Logic & Luồng

- Thêm chuông thông báo vào Header: lấy các cảnh báo đang mở, hiển thị badge số lượng chưa xử lý, dropdown 5 cảnh báo gần nhất và tự tải lại khi nhận topic `alerts` từ WebSocket. Dropdown tự đóng khi bấm ra ngoài.
- Giữ nguyên phạm vi bảo mật: backend `get_department_scope` và `ConnectionManager` quyết định dữ liệu Manager/Leadership; frontend không được dùng để thay thế RBAC.
- Bổ sung hardening test chứng minh lỗi provider AI trả fallback tiếng Việt và không chặn repository cảnh báo; test scope xác nhận yêu cầu phòng ban từ client không thể mở rộng scope Manager. Các test realtime hiện có tiếp tục xác nhận broadcast đúng phòng và loại kết nối lỗi.
- Rà soát UI mới theo Design System hiện có: dùng Tailwind tokens, animation `FadeIn`, câu chữ tiếng Việt thân thiện và icon SVG có nhãn trợ năng.
- Viết `README.md` hướng dẫn A–Z: Docker MongoDB Replica Set, môi trường backend, frontend, seed dữ liệu, tài khoản demo, luồng realtime/AI, test và xử lý sự cố OneDrive.

### Verification

- Backend pytest: `50 passed` (bao gồm hardening AI/RBAC), Ruff, isort, mypy và compileall đạt.
- Frontend Vitest: `6 test files, 13 tests passed`; ESLint, Prettier và Vite build đạt. Build còn cảnh báo bundle lớn do Recharts.
- Route/realtime contract giữ nguyên: `/api/ai/chat/stream`, `/ws/realtime` và các API Phase 0–9 đều không bị thay đổi contract.
- Playwright E2E: `10 passed`, gồm đăng nhập, nhập điểm, đồ thị, cảnh báo, RBAC, CRUD phòng ban và luồng liên thông đến chat AI fallback khi không có API key.
- Black vẫn cần chạy ngoài OneDrive do tiến trình formatter bị treo trong môi trường đồng bộ; README đã ghi cách xử lý.

### Phạm vi tác động

- Thay đổi chủ đích chỉ nằm ở Header/notification UI, hardening tests, README và CHANGELOG. Không thay đổi logic Performance, Alert, Overload, Manager Evaluation, AI provider, EventBus, Change Stream hoặc Auth/RBAC.

## [Fix] - Đồng bộ trang cảnh báo và bộ lọc đa mức

### Files created/modified

- `frontend/src/pages/AlertsPage.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `CHANGELOG.md`

### Logic & Luồng

- Trang cảnh báo gọi API với `alert_type=all`, hiển thị đồng thời cảnh báo sớm mức trung bình và cảnh báo quá tải mức cao.
- Bổ sung lọc tức thời theo tên/mã nhân viên, loại cảnh báo, mức độ và trạng thái; có tổng số đang hiển thị, số chưa xử lý và số mức cao.
- Thẻ cảnh báo dùng màu Amber cho mức trung bình, màu Đỏ cho mức cao và hiển thị nhãn loại cảnh báo tương ứng.

### Verification

- MongoDB đã đối chiếu: không có fingerprint cảnh báo mở bị trùng; các cảnh báo quá tải nhiều ngày được giữ thành các bản ghi riêng.
- ESLint và Prettier đạt; Playwright E2E: `10 passed`, gồm kiểm tra trang cảnh báo sau khi hiển thị đa mức và áp dụng bộ lọc loại cảnh báo.

## [Fix] - Hợp nhất màn hình Cảnh báo quá tải

### Files created/modified

- `frontend/src/App.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/components/layout/Sidebar.test.jsx`
- `frontend/src/pages/WorkspaceSectionPage.jsx`
- `frontend/src/pages/OverloadPage.jsx` (đã xóa)
- `frontend/src/pages/AlertsPage.jsx`
- `frontend/e2e/phase3-5.spec.js`
- `frontend/scripts/check-navigation.mjs`
- `CHANGELOG.md`

### Logic & Luồng

- Gỡ mục menu và màn hình riêng `/manager/overload`, `/leadership/overload`; toàn bộ cảnh báo quá tải mức cao được xem trong trang cảnh báo hợp nhất với bộ lọc `Quá tải`.
- Giữ redirect tương thích từ URL cũ về `/manager/alerts` hoặc `/leadership/alerts`, tránh liên kết cũ dẫn tới trang lỗi.
- Giữ nguyên backend Overload Detector, overload logs, EventBus và cảnh báo mức cao; chỉ loại bỏ UI trùng lặp.

### Verification

- Sidebar test xác nhận Manager/Leadership không còn mục menu Cảnh báo quá tải riêng.
- Playwright E2E tập trung xác nhận Manager lọc được cảnh báo quá tải trên trang hợp nhất: đạt 1/1 test. Bộ đầy đủ đã chạy được 6/10 test; 3 test sau đó gặp `ERR_CONNECTION_REFUSED` khi Vite dev server dừng, 1 test cảnh báo không nhận được dữ liệu từ backend đang chạy.
- Không xóa API hoặc schema backend; không thay đổi dữ liệu MongoDB.

## [Enhancement] - Áp dụng gợi ý điều phối từ cảnh báo

### Files created/modified

- `backend/app/models/coordination.py`
- `backend/app/repositories/coordination_repository.py`
- `backend/app/services/coordination_service.py`
- `backend/app/api/coordination.py`
- `backend/app/events/event_bus.py`
- `backend/app/main.py`
- `backend/tests/test_coordination_service.py`
- `frontend/src/features/coordination/coordinationApi.js`
- `frontend/src/pages/AlertsPage.jsx`
- `CHANGELOG.md`

### Logic & Luồng

- Mỗi cảnh báo đang mở được lấy gợi ý nhân viên cùng phòng, đang có tối đa 2 công việc và điểm chất lượng từ dữ liệu MongoDB hiện tại.
- Người dùng có thể áp dụng gợi ý mặc định hoặc mở modal để chọn nhân viên/số công việc và ghi chú trước khi áp dụng.
- Backend kiểm tra lại phạm vi phòng ban, tài khoản nhân viên đang hoạt động, sức chứa an toàn và chống áp dụng trùng trên cùng một cảnh báo.
- Phương án được lưu vào collection `coordination_plans`; hành động được ghi vào `audit_logs` và phát event nội bộ `COORDINATION_APPLIED`.
- Không thay đổi trực tiếp điểm hiệu suất hoặc nhân viên; do hệ thống hiện chưa có collection công việc, điều phối được ghi nhận dưới dạng phương án có thể truy vết.

### Verification

- Test backend điều phối: áp dụng gợi ý ghi plan/audit/event và Manager bị chặn khi truy cập khác phòng ban.
- Các route CRUD cảnh báo hiện tại vẫn giữ nguyên; lỗi gợi ý điều phối không làm ẩn danh sách cảnh báo.

## [Fix] - Chuẩn hóa kiểu ngày trước khi ghi MongoDB

### Files created/modified

- `backend/app/core/mongo_types.py`
- `backend/app/repositories/coordination_repository.py`
- `backend/app/repositories/department_repository.py`
- `backend/app/repositories/employee_repository.py`
- `backend/app/repositories/threshold_repository.py`
- `backend/app/repositories/performance_repository.py`
- `backend/app/repositories/manager_evaluation_repository.py`
- `backend/app/repositories/alert_repository.py`
- `backend/app/repositories/overload_repository.py`
- `backend/tests/test_mongo_types.py`
- `CHANGELOG.md`

### Logic & Luồng

- Nguyên nhân lỗi 500 là `datetime.date` được truyền trực tiếp vào BSON trong `coordination_plans.alert_date`; PyMongo chỉ encode `datetime.datetime`.
- Thêm `normalize_mongo_value()` chuẩn hóa đệ quy `date`, `datetime`, list và dict thành datetime UTC trước mọi thao tác insert/update của repository.
- Giữ nguyên kiểu `date` ở tầng API/model để frontend nhận dữ liệu ngày dễ dùng; chỉ chuyển kiểu tại ranh giới persistence MongoDB.

### Verification

- Regression test encode BSON cho ngày đơn, payload update lồng nhau và datetime không timezone.
- Backend full test: 55 passed; Ruff, Black và mypy đều đạt.

## [Fix] - Hoàn tất điều phối và truy vết thời gian xử lý cảnh báo

### Files created/modified

- `backend/app/repositories/coordination_repository.py`
- `backend/app/services/coordination_service.py`
- `backend/tests/test_coordination_service.py`
- `frontend/src/pages/AlertsPage.jsx`
- `CHANGELOG.md`

### Logic & Luồng

- Khi áp dụng điều phối thành công, backend cập nhật cảnh báo sang trạng thái `resolved`, lưu người xử lý, ghi chú và `resolved_at` vào MongoDB.
- Frontend chuyển thẻ ngay xuống nhóm “Cảnh báo đã xử lý”, hiển thị thời gian xử lý theo múi giờ giao diện và làm nổi bật nền xanh trong 2,5 giây trước khi trở về màu bình thường.
- Phương án điều phối vẫn được lưu trong `coordination_plans`; audit vẫn được ghi trong `audit_logs`, bảo đảm truy vết độc lập với trạng thái cảnh báo.

### Verification

- Test backend xác nhận áp dụng gợi ý đồng thời ghi plan/audit, phát event và cập nhật cảnh báo đã xử lý.
- Backend regression: 55 test đạt; Ruff, Black và mypy đạt.

## [Fix] - Điều hướng trực tiếp từ chuông tới cảnh báo

### Files created/modified

- `frontend/src/features/notifications/NotificationBell.jsx`
- `frontend/src/features/notifications/NotificationBell.test.jsx`
- `frontend/src/pages/AlertsPage.jsx`
- `CHANGELOG.md`

### Logic & Luồng

- Mỗi thông báo trong chuông là một nút có `alert_id` riêng; khi bấm, hệ thống đóng dropdown và chuyển tới `/manager/alerts?alert=<id>` hoặc `/leadership/alerts?alert=<id>` theo vai trò.
- Trang cảnh báo đọc `alert_id`, tìm đúng thẻ bằng ID DOM, tự cuộn tới vị trí cảnh báo và tô sáng tạm thời để người dùng nhận biết chính xác mục vừa chọn.
- Phạm vi dữ liệu vẫn do API backend quyết định; frontend không thể dùng query ID để vượt RBAC.

### Verification

- Unit test chuông xác nhận chọn cảnh báo `alert-1` điều hướng đúng `/manager/alerts?alert=alert-1`.
- Frontend unit: 14 test đạt; lint và Prettier đạt; production build đạt.
## [Feature] - Quản lý công việc & deadline

### Files created/modified

- `backend/app/models/task.py`
- `backend/app/repositories/task_repository.py`
- `backend/app/services/task_service.py`
- `backend/app/api/tasks.py`
- `backend/app/main.py`
- `backend/app/realtime/change_stream_worker.py`
- `backend/app/realtime/connection_manager.py`
- `backend/scripts/seed_tasks_data.py`
- `backend/scripts/smoke_tasks.py`
- `backend/scripts/smoke_realtime.py`
- `frontend/src/features/tasks/tasksApi.js`
- `frontend/src/pages/TasksPage.jsx`
- `frontend/src/features/tasks/components/CalendarView.jsx`
- `frontend/src/features/tasks/components/CalendarViews.jsx`
- `frontend/src/features/tasks/components/TaskEventChip.jsx`
- `frontend/src/features/tasks/components/calendarUtils.js`
- `frontend/src/features/tasks/components/calendarUtils.test.js`
- `frontend/src/features/tasks/components/CalendarViews.test.jsx`
- `frontend/src/index.css`
- `frontend/src/App.jsx`
- `frontend/src/components/layout/navigation.js`
- `frontend/src/components/layout/Sidebar.test.jsx`
- `frontend/scripts/check-navigation.mjs`

### Logic & Luồng

- Tạo collection `tasks` độc lập để lưu công việc, người phụ trách, việc con, ưu tiên, trạng thái và hạn hoàn thành.
- Backend tự kiểm tra phạm vi phòng ban: Manager chỉ thao tác với nhân viên trong phòng mình; Leadership được thao tác toàn công ty.
- Hạn quá hạn được tính từ ngày hiện tại và trạng thái hoàn thành ở tầng service, tránh cờ dữ liệu bị lệch.
- Frontend có bảng theo dõi, bộ lọc tìm kiếm/nhân viên/trạng thái/hạn, thẻ tổng hợp và modal thêm/sửa công việc bằng tiếng Việt.
- Bổ sung `backend/scripts/seed_tasks_data.py`: đọc nhân viên đang hoạt động từ MongoDB, tạo dữ liệu mẫu idempotent theo `seed_key` và không phụ thuộc ID cố định.
- Bổ sung Change Stream cho `tasks`, phát topic `tasks` qua Event Bus/WebSocket để trang Công việc tự tải dữ liệu mới ngay khi MongoDB insert/update/delete.
- Bổ sung `backend/scripts/smoke_tasks.py` để kiểm tra API trả đúng công việc seed, tên nhân viên, deadline và scope Manager/Leadership.
- Bật pre-image cho `tasks` để cả insert/update/delete trực tiếp trong MongoDB đều giữ được scope realtime, không phát tán sự kiện xóa sang phòng ban khác.
- `TasksPage` cập nhật state ngay khi nhận WebSocket rồi đồng bộ nền qua API, giúp thao tác insert/update/delete phản ánh tức thời mà không dùng polling.
- `+N khác` trong lịch mở popup chi tiết bằng Modal dùng chung; người dùng có thể xem đầy đủ thông tin và mở đúng form chỉnh sửa task.
- Khắc phục lỗi màn hình trắng khi mở popup do thiếu bảng nhãn ưu tiên/trạng thái trong `CalendarViews.jsx`.
- Khi mở chỉnh sửa từ popup chi tiết, popup ngày được giữ lại phía dưới; bấm `Hủy` sẽ quay lại đúng popup thay vì đóng toàn bộ ngữ cảnh.
- Tinh chỉnh khung nhìn Ngày: số ngày và tổng số công việc căn giữa, chữ lớn hơn, danh sách task có vùng đọc rộng và khoảng cách trực quan hơn.
- Khung nhìn Ngày hiển thị danh sách công việc dạng bảng căn giữa với các cột: Công việc, Nhân viên đảm nhận, Thời hạn còn lại, Ngày tạo và Ngày hết hạn.
- Popup xem thêm cũng dùng cùng bảng 5 cột và được mở rộng chiều rộng để theo dõi nhiều công việc rõ ràng hơn.
- Toàn bộ dòng trong bảng popup có thể bấm để mở hộp thoại sửa công việc, kèm hiệu ứng hover nhận biết thao tác.
- Phân biệt màu trạng thái công việc: đã hoàn thành xanh lá đậm, quá hạn đỏ và đang thực hiện xanh nhạt ở bảng, lịch và popup.
- Bảo đảm công việc đã hoàn thành luôn hiển thị nền xanh lá đậm trên lịch, kể cả khi thiếu dữ liệu mức ưu tiên hoặc đang chọn tô màu theo ưu tiên.
- Chuông thông báo được tách thành hai nhóm độc lập: Cảnh báo ngưỡng và Công việc quá hạn; cả hai nhóm đều cập nhật realtime theo phạm vi người dùng.
- Thêm hiệu ứng chuông lặp khi có mục cần xử lý và nhắc việc tự động mỗi 15 giây, hiển thị 10 giây với hiệu ứng mờ dần vào/ra.
- Bổ sung API `GET /api/dashboard/attention-summary` tổng hợp cảnh báo dấu hiệu sớm, cảnh báo quá tải và công việc quá hạn theo đúng scope Manager/Leadership.
- Nâng cấp Dashboard với tổng số việc cần xử lý, ba chỉ số phân loại và danh sách ưu tiên có điều hướng tới đúng cảnh báo/công việc.
- Thêm deep link `?task={id}` để trang Công việc tự mở đúng hộp thoại chỉnh sửa khi người dùng chọn công việc quá hạn từ Dashboard.
- Ẩn danh sách chi tiết khỏi nội dung chính Dashboard; danh sách chỉ mở khi hover/focus/chạm vào thẻ Tổng việc cần xử lý, có hỗ trợ Escape và responsive.
