# API inventory WorkMind

## Phạm vi và quy ước

Inventory này được lập từ `backend/app/api/*.py`, router WebSocket được đăng ký trong `backend/app/main.py`, và grep toàn bộ `frontend/src`. “Đang dùng” chỉ tính caller runtime trong component/page/hook đang được import vào ứng dụng; test hoặc page không được mount không được tính là caller thật. Quyền ghi trong bảng là quyền backend, không phải chỉ quyền ẩn/hiện menu.

Không tìm thấy frontend gọi URL không có route backend tương ứng. Các endpoint có trạng thái “Không dùng” vẫn có thể được test hoặc có API wrapper, nhưng không có caller runtime đang hoạt động.

## Auth và Health

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/auth/login` | POST | `frontend/src/pages/LoginPage.jsx`, `frontend/src/stores/authStore.js` | Đang dùng | Công khai; service kiểm tra tài khoản | `AuthenticationService.login` đọc `UserRepository`, phát JWT; không cần scope. |
| `/api/auth/me` | GET | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Bearer hợp lệ | Route tồn tại và được route check xác nhận; frontend hiện dùng claims trong token/Zustand thay vì gọi lại `/me`. |
| `/api/health` | GET | `frontend/src/components/HealthStatus.jsx` qua `useHealth.js` | Đang dùng | Công khai | `HealthService` kiểm tra Mongo và trả trạng thái/thời điểm; không phải nghiệp vụ Manager/Leadership. |

## Alerts

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/alerts` | GET | `frontend/src/pages/AlertsPage.jsx`, `frontend/src/features/notifications/NotificationBell.jsx`, `frontend/src/features/performance/PerformanceDashboard.jsx` | Đang dùng | Manager theo phòng; Leadership toàn công ty | `EarlyWarningService.list_alerts` → `AlertRepository.find_many`; lọc `status`/`alert_type`; scope từ `get_department_scope`. |
| `/api/alerts/department-summary` | GET | `frontend/src/pages/AlertsPage.jsx` | Đang dùng | Leadership | `EarlyWarningService.list_department_summaries` dùng aggregation của `AlertRepository`; không có event khi đọc. |
| `/api/alerts/scan` | POST | `frontend/src/pages/AlertsPage.jsx` | Đang dùng | Manager theo phòng; Leadership toàn công ty | Quét từng employee → threshold đã duyệt → `EarlyWarningDetector`; alert mới phát `ALERT_CREATED`, Mongo Change Stream broadcast topic `alerts`. |
| `/api/alerts/{alert_id}/resolve` | PATCH | `frontend/src/pages/AlertsPage.jsx` | Đang dùng | Manager chỉ alert phòng mình; Leadership alert toàn công ty | `EarlyWarningService.resolve` kiểm tra lại `department_id`, cập nhật alert và ghi chú; Change Stream `alerts` phát realtime. |

## Evidence/Storage

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/attachments/upload-sessions` | POST | `frontend/src/components/attachments/UploadManager.js`, được dùng bởi `DepartmentEvaluationsPage.jsx` | Đang dùng | User đăng nhập; `get_department_scope` và service kiểm tra context | Tạo presigned URL, sinh `storage_key` backend, ghi `attachment_upload_sessions`; không phát event riêng cho session. |
| `/api/attachments/upload-sessions/{session_id}/complete` | POST | `UploadManager.js` | Đang dùng | User đăng nhập, chỉ owner của session | Service đọc object, đối chiếu size/MIME/checksum, scan malware rồi chuyển `pending` → `uploaded`; owner check nằm trong `_owned_session`. |
| `/api/attachments/upload-sessions/{session_id}` | DELETE | `UploadManager.js` | Đang dùng | User đăng nhập, chỉ owner của session | Xóa object và chuyển session sang `cancelled`; không có Change Stream/topic cho collection upload session. |
| `/api/department-evaluations/{evaluation_id}/attachments/{attachment_id}/download-url` | GET | `DepartmentEvaluationsPage.jsx`, `DirectivesPage.jsx` | Đang dùng | Manager trong scope; Leadership toàn công ty | Service lấy evaluation, kiểm scope rồi mới tạo signed URL; chỉ metadata được trả ở list/detail. |
| `/api/performance/daily-review/{employee_id}/{review_date}/attachments/{attachment_id}/download-url` | GET | `frontend/src/pages/PerformanceEntryPage.jsx` | Đang dùng | Manager trong scope | `PerformanceReviewService` kiểm employee thuộc phòng, tìm attachment trong `task_execution_reports`, rồi tạo signed URL. |

## Department Evaluations

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/department-evaluations/weekly-review` | GET | `DepartmentEvaluationsPage.jsx` | Đang dùng | Leadership | Đọc context phòng ban, kỳ tuần, snapshot evidence hiện có hoặc dựng từ metrics/tasks/alerts/directives; không ghi DB. |
| `/api/department-evaluations` | GET | `DepartmentEvaluationsPage.jsx`, `DirectivesPage.jsx` | Đang dùng | Manager scope phòng mình; Leadership chọn toàn công ty/phòng | `DepartmentEvaluationService.list` → repository count + page query; Manager không thể đổi `department_id` ra ngoài scope. |
| `/api/department-evaluations/{evaluation_id}` | GET | `DepartmentEvaluationsPage.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | Đọc evaluation rồi `_ensure_scope`; response chỉ metadata attachment, không tạo signed URL hàng loạt. |
| `/api/department-evaluations/weekly-review` | POST | `DepartmentEvaluationsPage.jsx` | Đang dùng | Leadership | Form multipart hoặc direct-upload session → dựng evidence snapshot → lưu `department_weekly_evaluations`, audit, commit session; Change Stream topic `department_evaluations`. |
| `/api/department-evaluations/{evaluation_id}` | PATCH | `DepartmentEvaluationsPage.jsx` | Đang dùng | Leadership | Cập nhật điểm/ghi chú/attachment, xóa attachment cũ khi thay thế, audit; Change Stream topic `department_evaluations`. |

## Departments

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/departments` | GET | `DepartmentsPage.jsx`, `EmployeesPage.jsx`, `DepartmentEvaluationsPage.jsx`, `TasksPage.jsx`, `ManagerEvaluationsPage.jsx`, `NotificationBell.jsx`, `PerformanceDashboard.jsx` | Đang dùng | Manager scope phòng mình; Leadership toàn công ty | `get_department_scope` tự kích hoạt xác thực và lọc repository. |
| `/api/departments/{department_id}` | GET | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager chỉ phòng mình; Leadership toàn công ty | Backend route có scope; chưa có màn hình detail riêng. |
| `/api/departments` | POST | `DepartmentsPage.jsx` | Đang dùng | Leadership | `DepartmentService.create` ghi repository; Manager bị `require_role` chặn. |
| `/api/departments/{department_id}` | PATCH | `DepartmentsPage.jsx` | Đang dùng | Leadership | `DepartmentService.update` không nhận scope vì Leadership là toàn công ty. |
| `/api/departments/{department_id}` | DELETE | `DepartmentsPage.jsx` | Đang dùng | Leadership | Service kiểm tra employee count trước khi xóa; response 204. |

## Employees

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/employees` | GET | `EmployeesPage.jsx`, `DepartmentsPage.jsx`, `PerformanceEntryPage.jsx`, `TasksPage.jsx`, `DashboardPage.jsx`, `PerformanceDashboard.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | `EmployeeService.list` lọc `department_id` theo scope và xác thực lại query. |
| `/api/employees/{employee_id}` | GET | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager scope; Leadership toàn công ty | Có route detail nhưng UI hiện lấy dữ liệu từ list. |
| `/api/employees` | POST | `DepartmentsPage.jsx`, `EmployeesPage.jsx` | Đang dùng | User authenticated có scope hợp lệ; thực tế Manager/Leadership | `EmployeeService.create` tự gắn/kiểm tra phòng theo scope; không có `require_role` riêng. |
| `/api/employees/{employee_id}` | PATCH | `DepartmentsPage.jsx`, `EmployeesPage.jsx` | Đang dùng | Manager trong phòng; Leadership toàn công ty | Repository update có điều kiện scope. |
| `/api/employees/{employee_id}` | DELETE | `DepartmentsPage.jsx`, `EmployeesPage.jsx` | Đang dùng | Manager trong phòng; Leadership toàn công ty | Repository delete có điều kiện scope; response 204. |

## Performance

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/performance/daily-review` | GET | `PerformanceEntryPage.jsx` | Đang dùng | Manager; chỉ employee trong phòng | `PerformanceReviewService.get_review` đọc tasks + execution reports, dựng summary/evidence; không ghi. |
| `/api/performance/daily-review` | POST | `PerformanceEntryPage.jsx` | Đang dùng | Manager; Leadership bị chặn trong service | Validate đủ task và evidence/missing reason → update từng execution report + audit → upsert metric → publish `PERFORMANCE_METRIC_CREATED`. |
| `/api/performance/daily-review` | PATCH | `PerformanceEntryPage.jsx` | Đang dùng | Manager; Leadership bị chặn trong service | Cùng workflow POST nhưng `allow_update=True`, cho sửa lần nghiệm thu đã có. |
| `/api/performance/daily-review/{employee_id}/{review_date}/attachments/{attachment_id}/download-url` | GET | `PerformanceEntryPage.jsx` | Đang dùng | Manager scope | Signed URL cho attachment trong execution report. |
| `/api/performance/daily` | POST | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager theo phòng | `PerformanceService.create_daily` tính điểm, insert metric, publish event; đang là đường nhập điểm cũ bên cạnh daily-review. |
| `/api/performance` | GET | `PerformanceEntryPage.jsx`, `PerformanceDashboard.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | `PerformanceRepository.find_many` lấy employee IDs theo scope rồi đọc metrics. |
| `/api/performance/analytics/employee/{employee_id}` | GET | `PerformanceDashboard.jsx` | Đang dùng | Manager cùng phòng; Leadership | Aggregate trend theo employee sau kiểm tra employee/scope. |
| `/api/performance/analytics/department/{department_id}` | GET | `PerformanceDashboard.jsx` | Đang dùng | Manager chỉ phòng mình; Leadership | Aggregate so sánh employee trong phòng. |
| `/api/performance/analytics/company` | GET | `PerformanceDashboard.jsx` | Đang dùng | Leadership | `require_role(LEADERSHIP)`, aggregate có `$lookup` employees và group theo department. |

## Overload

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/overload` | GET | `PerformanceDashboard.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | `OverloadService.list_logs` đọc logs rồi với từng log đọc employee và aggregate candidate điều phối. |
| `/api/overload/scan` | POST | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager scope; Leadership toàn công ty | Detector tạo log mới và trả response; đường tự động chính vẫn là event từ metric mới. |

## Coordination

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/coordination/suggestions` | GET | `CoordinationSuggestionsCard.jsx`, `AlertsPage.jsx` | Đang dùng | Manager scope; Leadership đọc được nhưng UI card chỉ Manager | Với mỗi alert đọc plan và candidate từ Mongo; trả gợi ý. |
| `/api/coordination/alerts/{alert_id}/apply` | POST | `AlertsPage.jsx` | Đang dùng | Manager cùng phòng; Leadership bị service chặn | Ghi `coordination_plans` + audit, resolve alert, publish `COORDINATION_APPLIED`; alert Change Stream làm UI refresh. |
| `/api/coordination/department-directives/{department_id}` | POST | `AlertsPage.jsx` | Đang dùng | Leadership | Tạo chỉ thị cảnh báo cấp phòng, kiểm alert type/severity và chống overlap; collection có Change Stream. |
| `/api/coordination/department-directives` | GET | `DirectivesPage.jsx`, `AlertsPage.jsx`, `NotificationBell.jsx`, `DirectiveSummaryCard.jsx`, `ManagerAlertDirectiveAction.jsx` | Đang dùng | Manager target department; Leadership toàn công ty | Trả chỉ thị cảnh báo và tiến độ; scope truyền vào service. |
| `/api/coordination/department-directives/{directive_id}/acknowledge` | POST | `ManagerAlertDirectiveAction.jsx` | Đang dùng | Manager đúng target department | Kiểm target/status rồi chuyển pending → acknowledged, Change Stream topic `department_directives`. |
| `/api/coordination/department-directives/{directive_id}/submit` | POST | `ManagerAlertDirectiveAction.jsx` | Đang dùng | Manager đúng target department | Tính progress từ alert, chuyển sang submitted; Change Stream. |
| `/api/coordination/department-directives/{directive_id}/accept` | POST | `DirectivesPage.jsx` | Đang dùng | Leadership | Chỉ accept khi submitted và progress đủ; Change Stream. |
| `/api/coordination/department-directives/{directive_id}/request-revision` | POST | `DirectivesPage.jsx` | Đang dùng | Leadership | Chuyển submitted → needs_revision; Change Stream. |
| `/api/coordination/alerts/{alert_id}/directive-targets` | GET | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Leadership | Service tìm phòng cùng specialty; wrapper tồn tại nhưng flow cũ không còn dùng. |
| `/api/coordination/alerts/{alert_id}/direct` | POST | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Leadership; deprecated | Service luôn trả 409, thông báo flow cá nhân đã được thay bằng chỉ thị cấp phòng ban. |
| `/api/coordination/directives` | GET | `DirectivesPage.jsx`, `ManagerAlertDirectiveAction.jsx`, `DirectiveSummaryCard.jsx` | Đang dùng | Manager target department; Leadership toàn công ty | Danh sách chỉ thị điều phối chéo phòng ban. |
| `/api/coordination/directives/{directive_id}/candidates` | GET | `ManagerAlertDirectiveAction.jsx` | Đang dùng | Manager target department; Leadership bị service chặn | Lấy alert liên quan rồi aggregate candidate trong phòng đích. |
| `/api/coordination/directives/{directive_id}/fulfill` | POST | `ManagerAlertDirectiveAction.jsx` | Đang dùng | Manager target department | Ghi plan/audit, resolve alert, đánh dấu directive fulfilled, publish `COORDINATION_APPLIED`. |

## Tasks

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/tasks` | GET | `TasksPage.jsx`, `NotificationBell.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | `TaskService.list` repository lọc department/employee/status/overdue. |
| `/api/tasks/{task_id}` | GET | Không thấy caller runtime trực tiếp; deep-link dùng list/route UI | Không dùng | Manager scope; Leadership toàn công ty | Detail backend tồn tại nhưng UI mở form từ danh sách. |
| `/api/tasks` | POST | `TasksPage.jsx` | Đang dùng | Manager | Tạo task với `created_by` lấy từ JWT, employee phải thuộc scope. |
| `/api/tasks/{task_id}` | PATCH | `TasksPage.jsx` | Đang dùng | Manager | Update có scope, status/due date được chuẩn hóa; Mongo Change Stream topic `tasks`. |
| `/api/tasks/{task_id}` | DELETE | `TasksPage.jsx` | Đang dùng | Manager | Delete có scope; pre-image Change Stream giữ scope cho sự kiện xóa. |
| `/api/tasks/leadership-overview` | GET | `LeadershipTasksOverview.jsx` | Đang dùng | Leadership | Tổng hợp department/task theo range, dùng `BusinessClock.today()` cho kỳ nghiệp vụ. |
| `/api/tasks/departments/{department_id}/portfolio` | GET | `LeadershipTasksOverview.jsx` | Đang dùng | Leadership | Portfolio một phòng ban, filter focus; service kiểm department. |
| `/api/tasks/department-directives` | GET | `DirectivesPage.jsx`, `DirectiveSummaryCard.jsx`, `NotificationBell.jsx`, `LeadershipTasksOverview.jsx`, `ManagerTaskDirectives.jsx` | Đang dùng | Manager target department; Leadership toàn công ty | Danh sách chỉ thị công việc quá hạn/cần chú ý. |
| `/api/tasks/department-directives/{department_id}` | POST | `LeadershipTasksOverview.jsx` | Đang dùng | Leadership | Chỉ phát hành cho task quá hạn đang mở; lưu `department_task_directives`; Change Stream topic `task_directives`. |
| `/api/tasks/department-directives/{directive_id}/acknowledge` | POST | `ManagerTaskDirectives.jsx` | Đang dùng | Manager target department | pending → acknowledged với action note/commitment date. |
| `/api/tasks/department-directives/{directive_id}/submit` | POST | `ManagerTaskDirectives.jsx` | Đang dùng | Manager target department | Manager gửi nghiệm thu; Change Stream. |
| `/api/tasks/department-directives/{directive_id}/accept` | POST | `DirectivesPage.jsx` | Đang dùng | Leadership | Nghiệm thu khi submitted/progress đủ. |
| `/api/tasks/department-directives/{directive_id}/request-revision` | POST | `DirectivesPage.jsx` | Đang dùng | Leadership | Yêu cầu xử lý lại, Change Stream. |

## Dashboard

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/dashboard/attention-summary` | GET | `DashboardPage.jsx` | Đang dùng | Manager scope; Leadership toàn công ty | `DashboardAttentionService` đọc alerts/tasks/employees/departments/directives, dựng projection; refresh qua topic `alerts`, `tasks`, directives. |

## Manager Evaluations (legacy path)

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/manager-evaluations` | GET | Chỉ được import trong `ManagerEvaluationsPage.jsx`; page không được mount trong `App.jsx` | Không dùng | Leadership | Đọc collection `manager_evaluations`, khác với `department_weekly_evaluations` của flow hiện hành. |
| `/api/manager-evaluations` | POST | Chỉ được import trong `ManagerEvaluationsPage.jsx`; page không được mount trong `App.jsx` | Không dùng | Leadership | `ManagerEvaluationService` tính trung bình metrics rồi upsert `manager_evaluations`; không publish event. |

## Thresholds

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/threshold-configs` | GET | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager scope; Leadership toàn công ty | API đọc proposal/approved config nhưng chưa có feature/API wrapper frontend. |
| `/api/threshold-configs` | POST | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Manager | Manager đề xuất; service từ chối `scope is None`. |
| `/api/threshold-configs/{config_id}/approve` | POST | Không tìm thấy caller runtime; không tìm thấy caller nào khác trong frontend. | Không dùng | Leadership | Approve theo ID; repository hiện không có `ensure_indexes`. |

## AI

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/api/ai/chat/stream` | POST | `AiAssistantWidget.jsx`, `AiSummaryCard.jsx` qua `aiApi.js` | Đang dùng | User đăng nhập; scope do `get_department_scope` | `AiService` kiểm scope server-side, dịch field label rồi stream SSE; lỗi provider trả fallback, không làm hỏng repository nghiệp vụ. |

## Realtime

| Endpoint | Method | Gọi từ (file) | Trạng thái | Quyền truy cập | Ghi chú |
|---|---|---|---|---|---|
| `/ws/realtime?token=...` | WebSocket | `frontend/src/hooks/useRealtimeUpdates.js` và các consumer Dashboard/Alerts/Tasks/Performance/Directives/Evaluations | Đang dùng | JWT hợp lệ; Manager chỉ nhận event cùng department, Leadership nhận toàn công ty | Token được resolve lại từ Mongo; Change Stream workers phát event qua EventBus rồi `ConnectionManager` lọc scope trước khi gửi. Có topic `alerts`, `performance_metrics`, `tasks`, `department_directives`, `task_directives`, `task_execution_reports`, `department_evaluations`. |

## Mapping API function → component/page

Các wrapper runtime được grep theo tên export và đối chiếu import/call trong `frontend/src` như sau:

| API module | Function trong `*Api.js` | Component/page gọi |
|---|---|---|
| `aiApi.js` | `streamAiChat` | `AiAssistantWidget.jsx`, `AiSummaryCard.jsx` |
| `alertsApi.js` | `listAlerts` | `AlertsPage.jsx`, `NotificationBell.jsx`, `PerformanceDashboard.jsx` |
|  | `scanAlerts`, `listDepartmentAlertSummaries`, `resolveAlert` | `AlertsPage.jsx` |
| `attachmentsApi.js` | `createUploadSession`, `completeUploadSession`, `cancelUploadSession` | `UploadManager.js` → `DepartmentEvaluationsPage.jsx` |
| `authApi.js` | `login` | `LoginPage.jsx`, `authStore.js` |
| `coordinationApi.js` | `listCoordinationSuggestions`, `applyCoordination`, `issueDepartmentDirective` | `AlertsPage.jsx`, `CoordinationSuggestionsCard.jsx` |
|  | `listDirectives`, `getDirectiveCandidates`, `fulfillDirective` | `DirectivesPage.jsx`, `ManagerAlertDirectiveAction.jsx`, `DirectiveSummaryCard.jsx` |
|  | `listDepartmentDirectives`, `acknowledgeDepartmentDirective`, `submitDepartmentDirective` | `AlertsPage.jsx`, `DirectivesPage.jsx`, `ManagerAlertDirectiveAction.jsx`, `DirectiveSummaryCard.jsx`, `NotificationBell.jsx` |
|  | `acceptDepartmentDirective`, `requestDepartmentDirectiveRevision` | `DirectivesPage.jsx` |
| `dashboardApi.js` | `getAttentionSummary` | `DashboardPage.jsx` |
| `departmentEvaluationsApi.js` | `getWeeklyDepartmentReview`, `getDepartmentEvaluation`, `createDepartmentEvaluation`, `updateDepartmentEvaluation` | `DepartmentEvaluationsPage.jsx` |
|  | `listDepartmentEvaluations`, `getDepartmentEvaluationAttachmentUrl` | `DepartmentEvaluationsPage.jsx`, `DirectivesPage.jsx` |
| `departmentsApi.js` | `listDepartments` | `DepartmentEvaluationsPage.jsx`, `DepartmentsPage.jsx`, `EmployeesPage.jsx`, `ManagerEvaluationsPage.jsx`, `TasksPage.jsx`, `NotificationBell.jsx`, `PerformanceDashboard.jsx` |
|  | `createDepartment`, `updateDepartment`, `deleteDepartment` | `DepartmentsPage.jsx` |
| `employeesApi.js` | `listEmployees` | `DashboardPage.jsx`, `DepartmentsPage.jsx`, `EmployeesPage.jsx`, `PerformanceEntryPage.jsx`, `TasksPage.jsx`, `PerformanceDashboard.jsx` |
|  | `createEmployee`, `updateEmployee`, `deleteEmployee` | `DepartmentsPage.jsx`, `EmployeesPage.jsx` |
| `healthApi.js` | `getHealth` | `useHealth.js` → `HealthStatus.jsx` → `DashboardPage.jsx` |
| `managerEvaluationsApi.js` | `listManagerEvaluations`, `createManagerEvaluation` | `ManagerEvaluationsPage.jsx` only; page không được mount |
| `overloadApi.js` | `listOverloadLogs` | `PerformanceDashboard.jsx` |
| `performanceApi.js` | `listPerformance` | `PerformanceEntryPage.jsx`, `PerformanceDashboard.jsx` |
|  | `getDailyPerformanceReview`, `getDailyReviewAttachmentUrl`, `saveDailyPerformanceReview`, `updateDailyPerformanceReview` | `PerformanceEntryPage.jsx` |
|  | `getEmployeePerformanceAnalytics`, `getDepartmentPerformanceAnalytics`, `getCompanyPerformanceAnalytics` | `PerformanceDashboard.jsx` |
| `tasksApi.js` | `listTasks`, `createTask`, `updateTask`, `deleteTask` | `TasksPage.jsx`; `listTasks` còn ở `NotificationBell.jsx` |
|  | `getLeadershipTaskOverview`, `getDepartmentTaskPortfolio`, `issueDepartmentTaskDirective` | `LeadershipTasksOverview.jsx` |
|  | `listDepartmentTaskDirectives` | `DirectivesPage.jsx`, `DirectiveSummaryCard.jsx`, `NotificationBell.jsx`, `LeadershipTasksOverview.jsx`, `ManagerTaskDirectives.jsx` |
|  | `acknowledgeDepartmentTaskDirective`, `submitDepartmentTaskDirective` | `ManagerTaskDirectives.jsx` |
|  | `acceptDepartmentTaskDirective`, `requestTaskDirectiveRevision` | `DirectivesPage.jsx` |

## Caller/export audit frontend

Các API wrapper có export nhưng không có external caller nào trong `frontend/src`:

- `features/coordination/coordinationApi.js`: `listDirectiveTargets`, `issueDirective`.
- `features/overload/overloadApi.js`: `scanOverloadLogs`.
- `features/performance/performanceApi.js`: `createDailyPerformance`.

Các wrapper `managerEvaluationsApi.js` có import trong `ManagerEvaluationsPage.jsx`, nhưng trang này không được import/mount trong `App.jsx`; vì vậy cả hai endpoint legacy tương ứng vẫn được phân loại “Không dùng” ở runtime.
