# Báo cáo rà soát codebase WorkMind

Ngày rà soát: 2026-09-06

## Phạm vi và phương pháp

Rà soát FastAPI/MongoDB backend, React/Vite frontend, router composition, service/repository, EventBus/Change Stream, các caller trong toàn bộ `frontend/src`, `CHANGELOG.md` và `README.md`. Không sửa code nghiệp vụ, không commit, không chạy seed/migration/reconcile và không thao tác dữ liệu MongoDB thật.

Đã kiểm tra tĩnh toàn bộ endpoint HTTP trong `backend/app/api/*.py`, WebSocket `/ws/realtime`, dependency RBAC, caller/export frontend, BusinessClock, index/repository và script storage. Đã chạy các quality gate read-only: backend pytest `88 passed` với 1 warning deprecation, Ruff đạt, compileall đạt, route/OpenAPI check đạt; frontend ESLint đạt. Mypy thất bại với 41 lỗi ở 7 file. Frontend Vitest và Vite build không khởi động được do esbuild bị `Access is denied` khi resolve `frontend/vitest.config.js`/`vite.config.js`; Prettier còn 7 file chưa đúng format. Docker không có trong PATH và không có listener TCP 27017 quan sát được, vì vậy không có xác minh MongoDB live trong lần rà soát này.

## Tóm tắt điều hành

1. Luồng API hiện được đăng ký đầy đủ và caller frontend nhìn chung khớp route; không tìm thấy frontend gọi URL không tồn tại.
2. RBAC backend có cấu trúc nhất quán qua `get_current_user`, `get_department_scope` và `require_role`; chưa thấy business endpoint hoàn toàn bỏ xác thực. Các route chỉ dùng `get_department_scope` vẫn được xác thực gián tiếp.
3. Có một khoảng cách rõ giữa CHANGELOG và code hiện tại: nhiều module nghiệp vụ vẫn gọi trực tiếp `datetime.now(timezone.utc)` thay vì `BusinessClock`.
4. Hai phát hiện dữ liệu cũ chưa được giải quyết đầy đủ: script seed task vẫn ghi `created_by` bằng `ObjectId()` không tham chiếu user; repository `threshold_configs` chưa tạo index.
5. Các workflow mới về evidence/task execution đã có Change Stream cho evaluation và execution report, nhưng bản thân upload session không có topic realtime và phần review task chưa có test service riêng.
6. Một số read path có N+1: coordination suggestions, danh sách overload và lưu review nhiều task; rủi ro tăng theo số alert/task.
7. “Chỉ thị” đang là nhãn chung cho ít nhất ba khái niệm: chỉ thị cảnh báo, chỉ thị công việc và chỉ thị điều phối chéo phòng ban; backend tách collection nhưng UI gom vào một Trung tâm chỉ thị.
8. Có một nhóm endpoint/wrapper legacy chưa có caller runtime: manager-evaluations, nhập performance cũ, overload scan thủ công và flow chỉ thị cá nhân deprecated.

## Phát hiện mức Cao

### C1 — Chuẩn hóa BusinessClock chưa hoàn tất

**Mô tả.** `BusinessClock` đã tồn tại và được dùng cho một số ranh giới ngày, nhưng timestamp nghiệp vụ vẫn lấy trực tiếp từ hệ thống. Điều này làm cho claim trong CHANGELOG về chuẩn hóa task, dashboard, điều phối và review chưa đúng với code hiện tại; các test/mock clock cũng khó kiểm soát thống nhất.

**Bằng chứng.** `backend/app/core/time.py:9-29` định nghĩa clock. Các điểm còn gọi trực tiếp gồm `backend/app/services/task_service.py:84,141-143,421,434,540,599,653,705`, `coordination_service.py:132,349,484,557,624,678,730`, `performance_review_service.py:98,141`, `performance_service.py:209`, `dashboard_attention_service.py:97`, `alert_service.py:99,183`, `department_evaluation_service.py:101`, `attachment_upload_service.py:69`, `attachment_reconciliation_service.py:19`, `threshold_service.py:46,73`, cùng department/employee/manager/health/security/overload services. Không tìm thấy `datetime.utcnow()` trong `backend/app`.

**Tác động.** Ngày nghiệp vụ đang được tính qua múi giờ Việt Nam ở một số nơi nhưng thời điểm ghi/audit/URL expiry có nhiều nguồn khác nhau. Sai lệch thường chỉ lộ quanh mốc ngày, cutoff hoặc khi test dùng clock giả.

**Đề xuất hướng xử lý.** Chọn một policy rõ ràng: `business_clock.now()` cho mọi timestamp nghiệp vụ, clock hệ thống riêng cho JWT/health nếu cần; truyền clock vào service để test. Sau đó cập nhật lại bằng chứng CHANGELOG và chạy regression cho task, dashboard, điều phối, review, attachment.

### C2 — N+1 và nhiều round-trip DB trong các read/write path chính

**Mô tả.** Một số endpoint đọc danh sách rồi thực hiện thêm truy vấn/aggregation cho từng phần tử; workflow review lại ghi nhiều lần cho từng task. Đây là rủi ro hiệu năng thực tế khi dữ liệu tăng, không phải lỗi đã được chứng minh ở dataset live.

**Bằng chứng.**

- `backend/app/services/coordination_service.py:62-70`: `list_suggestions` lặp từng alert, gọi `find_plan` và có thể gọi `find_rebalance_candidates` cho từng alert. `coordination_repository.py:113-158` chạy aggregate candidate riêng theo alert.
- `backend/app/services/overload_service.py:62-64` lặp từng overload log; `_response_with_employee` tại `:50-60` gọi employee lookup và rebalancer, còn `workload_rebalancer.py:11-16` gọi aggregate candidate thêm lần nữa.
- `backend/app/services/performance_review_service.py:145-191`: mỗi item có thể `upsert_report`, `update_manager_review` và `insert_audit_log`; đây là O(số task) round-trip khi Manager chốt một ngày.
- Một số pipeline đã làm đúng hướng, ví dụ `performance_repository.py:129-172` dùng `$lookup/$group` cho company comparison và `overload_repository.py:62-107` dùng một aggregate candidate.

**Tác động.** Latency và tải Mongo tăng theo số cảnh báo/task; response list suggestions/overload có thể chậm dù mỗi query riêng lẻ vẫn đúng.

**Đề xuất hướng xử lý.** Batch lookup theo `$in`, aggregate một lần theo employee/date, hoặc thêm projection/repository method trả đủ map; review task nên có bulk update/transaction boundary phù hợp và audit batch. Đo query count/latency trước-sau bằng fixture lớn.

## Phát hiện mức Trung bình

### M1 — `tasks.created_by` vẫn có dữ liệu mồ côi từ seed

**Mô tả.** Đường API hiện đã truyền `current_user.user_id` và parse thành ObjectId khi tạo task, nhưng script seed mẫu không lấy user hợp lệ.

**Bằng chứng.** `backend/app/services/task_service.py:73-99` tạo `created_by` từ tham số caller; `backend/scripts/seed_tasks_data.py:34-60`, cụ thể dòng `57`, ghi `"created_by": ObjectId()` ngẫu nhiên. `TaskDocument` yêu cầu trường này ở `backend/app/models/task.py:37-52`.

**Tác động.** Task seed trả về `created_by` không thể resolve về user thật, làm audit/detail thiếu ý nghĩa và không chứng minh được dữ liệu demo phản ánh workflow production. Không thể kết luận số bản ghi mồ côi hiện có vì không có MongoDB live trong lần này.

**Đề xuất hướng xử lý.** Seed manager đang hoạt động theo department, hoặc cho phép `created_by` là user seed cố định đã được upsert; thêm kiểm tra orphan read-only vào smoke/health data check.

### M2 — `threshold_configs` thiếu index và chưa có UI caller

**Mô tả.** `ThresholdConfigRepository` không có `ensure_indexes`, trong khi `find_many` sort `created_at` và `find_approved` lọc status/department rồi sort `updated_at`. Đồng thời không có API wrapper/frontend page gọi ba endpoint threshold.

**Bằng chứng.** `backend/app/repositories/threshold_repository.py:8-45` không định nghĩa index; `backend/app/services/threshold_service.py:34-79` cũng không gọi ensure index. Các route là `backend/app/api/thresholds.py:20-53`; grep frontend không tìm thấy `/api/threshold-configs`.

**Tác động.** Query cấu hình có thể collection scan khi số proposal tăng; tính năng cấu hình ngưỡng tồn tại ở backend nhưng người dùng không có luồng UI hiện hành để đề xuất/duyệt. Đây là phát hiện cũ về thiếu index chưa được khắc phục theo code hiện tại.

**Đề xuất hướng xử lý.** Bổ sung index phù hợp với query và gọi ensure ở lifecycle/service; quyết định rõ đưa threshold UI vào scope hay ghi nhận API-only. Nếu giữ API-only, cần tài liệu vận hành và test contract.

### M3 — Mypy hiện không đạt sau phần evidence/task evaluation

**Mô tả.** Quality gate runtime unit vẫn đạt, nhưng static type gate không sạch: lần chạy hiện tại báo 41 lỗi ở 7 file.

**Bằng chứng.** Mypy báo lỗi tại `models/department_evaluation.py`, `infrastructure/evidence_storage.py`, `services/attachment_reconciliation_service.py`, `dashboard_attention_service.py`, `task_service.py`, `attachment_upload_service.py`, `department_evaluation_service.py`. Các nhóm lỗi gồm override type attachment, boto3 thiếu stub, `object` truyền vào `int`, biến set thiếu annotation, Literal range và các annotation bị hiểu nhầm là method `list`.

**Tác động.** Không thể coi mypy là bằng chứng bảo vệ contract cho module mới; một số lỗi có thể che khuất mismatch khi xử lý evidence/task report.

**Đề xuất hướng xử lý.** Sửa type contract theo module, thêm stub/ignore có lý do cho boto3, tránh dùng tên annotation gây shadow method, rồi chạy lại mypy trước khi cập nhật acceptance record.

### M4 — Realtime có coverage cho report/evaluation nhưng không cho upload session và event coordination không có subscriber

**Mô tả.** `task_execution_reports` và `department_weekly_evaluations` có Change Stream worker, topic và frontend consumer. Ngược lại, `attachment_upload_sessions` không có worker/topic; `COORDINATION_APPLIED` được publish nhưng không thấy subscriber.

**Bằng chứng.** Worker report ở `backend/app/realtime/change_stream_worker.py:246-264`, wiring ở `main.py:87`, broadcast ở `connection_manager.py:68-76,138-143`. Upload session chỉ cập nhật qua `attachment_upload_service.py:145-214`; không có worker cho collection này. `coordination_service.py:193,410` publish `COORDINATION_APPLIED`, còn `rg event_bus.subscribe` chỉ thấy subscriptions cho Change Stream topics và metric/overload trong `main.py`.

**Tác động.** Trạng thái upload chỉ được UI biết qua response hiện tại; client khác không có tín hiệu session lifecycle. Event coordination hiện là audit/internal signal hơn là contract có consumer, nên dễ tạo kỳ vọng sai về realtime của plan.

**Đề xuất hướng xử lý.** Xác định upload session có cần realtime hay không; nếu không, ghi rõ contract. Với coordination, hoặc thêm consumer/topic cho `coordination_plans`, hoặc bỏ event không dùng và dựa rõ vào alert/directive Change Stream.

### M5 — Evidence/task execution mới có ít test hơn phần còn lại

**Mô tả.** Tổng suite hiện có 88 test, nhưng coverage theo module không đồng đều. `test_attachment_upload_service.py` chỉ có 2 test; không có file test riêng cho `PerformanceReviewService`/`TaskExecutionRepository`, dù đây là luồng tạo và review report quan trọng. Realtime test hiện có kiểm tra alert/task/directive/metric, chưa kiểm tra report worker/evaluation worker.

**Bằng chứng.** Test hiện diện: `backend/tests/test_attachment_upload_service.py` có 2 test; `test_department_evaluation_service.py` có 6 test; `test_performance_service.py` có 7 test; `test_task_service.py` có 11 test; `test_realtime.py` có 7 test nhưng không có test task execution report. CHANGELOG mốc mới ghi backend 84 passed/frontend 42 passed; lần chạy hiện tại backend đạt 88 passed nhưng không làm thay đổi khoảng trống test theo module.

**Tác động.** Các nhánh verify checksum/scan có kiểm tra tối thiểu, nhưng thiếu contract test cho owner/scope/context, commit/discard, report upsert/update, event payload và failure rollback trong review nhiều task.

**Đề xuất hướng xử lý.** Tạo test service riêng cho daily review và repository report; thêm worker tests cho `task_execution_reports`/`department_evaluations`, upload-session context/scope và failure cleanup. Không suy ra coverage phần trăm từ số test này vì chưa chạy coverage report.

### M6 — Script reconcile storage chưa được lên lịch

**Mô tả.** Có service và script dọn session/object mồ côi, nhưng không thấy cron, scheduler, CI workflow hay lifecycle task nào gọi nó.

**Bằng chứng.** `backend/scripts/reconcile_evidence_storage.py:1-29` chỉ có entrypoint CLI; `backend/app/services/attachment_reconciliation_service.py:8-74` chỉ được import bởi script; grep toàn repo chỉ thấy README hướng dẫn chạy thủ công ở `README.md:46` và CHANGELOG.

**Tác động.** Cleanup phụ thuộc vận hành thủ công; object hết hạn hoặc mồ côi có thể tích lũy trong MinIO/S3. Báo cáo này không chạy script vì script có thể xóa object thật.

**Đề xuất hướng xử lý.** Gắn script vào scheduler/cron/CI vận hành với dry-run, grace period, log/metric và approval; bổ sung runbook xác định môi trường/bucket đích.

## Phát hiện mức Thấp / vệ sinh contract

### L1 — Ba nhóm “chỉ thị” dùng chung một nhãn trong UI

**Mô tả.** Đây không phải một collection duy nhất. Code đang có ít nhất ba khái niệm:

- `department_alert_directives`: “Chỉ thị cảnh báo”, Leadership phát hành từ alert; Manager acknowledge/submit; Leadership accept/revision.
- `department_task_directives`: “Chỉ thị công việc”, Leadership chọn task quá hạn; Manager acknowledge/submit; Leadership accept/revision.
- `coordination_directives`: “Chỉ thị điều phối chéo phòng ban”, Manager phòng đích fulfill và tạo coordination plan.

**Bằng chứng.** `frontend/src/pages/DirectivesPage.jsx:25-29,123-153,264-268` gom ba nguồn thành “Trung tâm chỉ thị” nhưng chỉ phân nhóm bằng filter/source; backend tách route/collection trong `backend/app/api/coordination.py`, `backend/app/api/tasks.py` và `backend/app/repositories/coordination_repository.py`.

**Đánh giá.** Đây đúng là các khái niệm nghiệp vụ khác nhau nhưng dùng chung từ “chỉ thị”. UI đã có nhãn phụ, song trạng thái `pending/accepted` và action điều hướng gần giống nhau; người dùng có thể nhầm “chỉ thị cảnh báo” với “chỉ thị công việc”, hoặc nhầm điều phối chéo với yêu cầu xử lý nội bộ. Mức rủi ro UX thấp đến trung bình, không phải lỗi cô lập dữ liệu vì backend vẫn tách collection.

**Đề xuất hướng xử lý.** Giữ source label luôn hiện ở card/title, dùng tên nhất quán như “Yêu cầu xử lý cảnh báo”, “Giao việc quá hạn”, “Điều phối liên phòng ban”; tách status/action copy thay vì chỉ dùng status chung.

### L2 — Endpoint/wrapper legacy còn tồn tại nhưng không có caller runtime

**Mô tả.** Inventory xác định các path không được gọi từ frontend runtime: `/api/auth/me`, `/api/coordination/alerts/{alert_id}/directive-targets`, deprecated `/direct`, `/api/performance/daily`, `/api/overload/scan`, `/api/manager-evaluations`, toàn bộ threshold endpoints, cùng một số detail endpoint chưa có caller trực tiếp. Frontend wrapper không có external caller gồm `listDirectiveTargets`, `issueDirective`, `scanOverloadLogs`, `createDailyPerformance`.

**Đánh giá.** Đây là code tồn đọng/compatibility surface, chưa phải lỗi route mismatch. Riêng `/api/coordination/alerts/{alert_id}/direct` đã được đánh dấu deprecated và service trả 409, nên nên được coi là migration surface chứ không phải chức năng hoạt động.

**Đề xuất hướng xử lý.** Lập danh sách legacy contract, quyết định deprecate/remove có versioning; không xóa chỉ dựa trên grep vì có thể có client ngoài frontend. Nếu giữ, bổ sung tài liệu caller/owner và test deprecated response.

## Nhất quán RBAC và tương tác hai vai trò

### Kết quả RBAC

Không thấy endpoint nghiệp vụ nào hoàn toàn thiếu xác thực. `get_department_scope` tại `backend/app/api/dependencies.py:72-89` gọi `get_current_user` gián tiếp, trả `None` cho Leadership và ObjectId phòng ban cho Manager. Vì vậy các route departments/employees/alerts/performance/overload/tasks dùng dependency scope mà không lặp `get_current_user` vẫn được xác thực.

Các route nhạy cảm có role guard rõ ràng: department CRUD, company analytics, Leadership overview/portfolio, manager-evaluation, threshold approve/propose, directive accept/revision/issue. Attachment complete/cancel chỉ khai báo current user ở router nhưng service kiểm owner tại `attachment_upload_service.py:267-271`; đây là kiểm soát ownership bổ sung, không phải thiếu scope. Health/login là công khai có chủ đích.

### Phân loại màn hình/module

| Module/trang | Manager | Leadership | Tương tác thực tế |
|---|---|---|---|
| Dashboard/Alerts/AI | Scope phòng ban | Toàn công ty, có department summary | Cùng component nhưng Leadership group theo phòng; Manager thao tác resolve/apply trong phòng. |
| Employees/Departments | Xem/sửa employee trong phòng | CRUD department và employee toàn công ty | Cùng API scope; tạo/sửa/xóa department chỉ Leadership. |
| Performance entry | Manager nghiệm thu daily review | Không nghiệm thu trực tiếp | Manager tạo execution review/metric; Leadership chỉ đọc analytics. |
| Performance dashboard/Overload | Dữ liệu phòng mình | So sánh phòng/toàn công ty | Cùng màn hình dashboard với nhánh chart/grouping khác; overload scan backend chưa có caller UI. |
| Tasks | CRUD task phòng mình; nhận/chốt directive | Overview/portfolio toàn công ty; phát hành và nghiệm thu directive | Đây là luồng tương tác rõ nhất giữa hai vai trò. |
| Directives | Tiếp nhận, acknowledge, submit | Phát hành, accept, request revision | `DirectivesPage` gom alert/task/cross-department directive trong một module. |
| Department evaluations | Đọc list/detail trong scope | Xem weekly review, tạo/sửa đánh giá | Leadership tạo evidence snapshot/đánh giá; Manager là manager được đánh giá và là nguồn dữ liệu task/report. |
| Manager evaluations legacy | Không thấy | Endpoint backend-only | Không có caller runtime; khác persistence với weekly department evaluation. |
| Thresholds | Đề xuất | Duyệt | Backend có workflow nhưng frontend chưa nối. |

### Các workflow liên vai trò

**Cảnh báo hiệu suất/quá tải**

`POST /api/performance/daily-review` hoặc metric insert
→ `PerformanceReviewService`/`PerformanceService` publish `PERFORMANCE_METRIC_CREATED`
→ `EarlyWarningService` và `OverloadService` detector
→ `alerts` insert + `ALERT_CREATED`
→ Mongo Change Stream
→ WebSocket `alerts`
→ Manager xử lý/điều phối hoặc Leadership theo dõi/tạo chỉ thị.

**Điều phối trong phòng**

`AlertsPage` chọn alert
→ `POST /api/coordination/alerts/{alert_id}/apply`
→ `CoordinationService.apply`
→ `coordination_plans` + `audit_logs`
→ resolve `alerts`
→ `COORDINATION_APPLIED` và Change Stream alert
→ UI chuyển alert sang đã xử lý.

**Chỉ thị cảnh báo cấp phòng**

Leadership `POST /api/coordination/department-directives/{department_id}`
→ `department_alert_directives` pending
→ Manager `acknowledge`
→ Manager `submit`
→ Leadership `accept` hoặc `request-revision`
→ Change Stream `department_directives`
→ `DirectivesPage`/`ManagerAlertDirectiveAction` refresh.

**Chỉ thị công việc quá hạn**

Leadership `POST /api/tasks/department-directives/{department_id}`
→ `TaskService.issue_department_directive` chỉ chọn task overdue đang mở
→ Manager `acknowledge`
→ Manager `submit`
→ Leadership `accept` hoặc `request-revision`
→ Change Stream `task_directives`
→ Dashboard/Tasks/Directives refresh.

**Điều phối chéo phòng ban**

Leadership phát `department coordination directive`
→ Manager phòng đích đọc `/directives/{id}/candidates`
→ Manager `fulfill`
→ `coordination_plans` + audit + resolve alert + mark directive fulfilled
→ `COORDINATION_APPLIED` và alert/directive Change Stream
→ Directives/Alerts UI cập nhật.

**Evidence và nghiệm thu task**

`UploadManager` tạo session
→ presigned PUT tới MinIO/S3
→ `complete` đọc object + checksum + malware scan
→ session `uploaded`
→ Department evaluation hoặc daily review resolve session/ghi attachment metadata
→ `department_weekly_evaluations` hoặc `task_execution_reports`
→ Change Stream topic tương ứng
→ Manager/Leadership nhận lại evidence/report theo scope.

## Đối chiếu realtime, DB và storage

- `tasks`, `alerts`, `performance_metrics`, `department_directives`, `task_directives`, `task_execution_reports`, `department_weekly_evaluations` đều có Change Stream worker/wiring trong `backend/app/main.py` và topic broadcast tương ứng.
- Coordination plan/audit không có Change Stream riêng; UI dựa vào alert/directive thay đổi. `COORDINATION_APPLIED` hiện không có subscriber được tìm thấy.
- Upload session không có Change Stream; client gọi complete/cancel trực tiếp nên UI hiện hành vẫn nhận response, nhưng client khác không có lifecycle event.
- `reconcile_evidence_storage.py` chỉ được gọi qua entrypoint thủ công trong README, không có lịch chạy trong repo.
- Không chạy Mongo aggregation/index inspection live vì Docker không có trong PATH và không quan sát được listener 27017; các kết luận về orphan/index là từ code/script, không phải snapshot dữ liệu thật.

## Kết luận

Codebase có kiến trúc phân lớp và scope RBAC khá rõ; các luồng chính Performance → Alert/Overload → Realtime và Leadership → Manager directives đã nối được từ API tới UI. Tuy nhiên, cần ưu tiên hoàn thiện policy thời gian, xử lý N+1, index threshold, sửa seed `created_by` và bổ sung test cho daily review/task execution/evidence lifecycle. Các endpoint legacy và ba loại “chỉ thị” nên được quản trị như contract riêng để tránh tiếp tục mở rộng nhầm luồng. Không có phát hiện frontend gọi route không tồn tại; các hạn chế runtime trong báo cáo chủ yếu do chưa có Mongo/Docker live và sandbox không cho esbuild resolve cấu hình Vite.

## Phân biệt xác minh tĩnh và chạy thật

**Đã chạy thật trong môi trường hiện tại:**

- Backend `pytest -q`: `88 passed`, 1 warning deprecation từ Starlette/httpx.
- Backend Ruff: đạt.
- Backend `compileall`: đạt.
- `backend/scripts/check_app.py`: đạt, OpenAPI có HTTP routes và `/ws/realtime`.
- Frontend `npm run lint`: đạt.
- Frontend `npm run format:check`: thất bại, 7 file chưa format.
- Frontend Vitest và `npm run build`: không chạy tới test/build do esbuild báo `Access is denied` khi resolve config.
- Mypy: thất bại với 41 lỗi ở 7 file.

**Chỉ xác minh tĩnh:**

- Bản đồ endpoint/caller và export API.
- RBAC dependency/call chain, workflow service/repository/event.
- Orphan `created_by` trong seed và thiếu `threshold_configs` index.
- N+1, subscriber/event gap, lịch reconcile storage và thuật ngữ “chỉ thị”.
- Không kết luận số lượng dữ liệu mồ côi, index thực tế trong Mongo, Change Stream live, signed URL/MinIO hoặc phân quyền runtime ngoài các unit/API tests đã chạy.

