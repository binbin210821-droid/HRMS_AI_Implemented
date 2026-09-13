# Lịch sử thay đổi

## [UI-only frontend standardization] - Chuẩn hóa bộ giao diện dùng chung

- Bổ sung và chuẩn hóa các primitive `Input`, `Select`, `Textarea`, `Table`,
  `Skeleton`, `Toast`, `Dialog`, `Tooltip` và trạng thái loading/empty/error.
- Áp dụng giao diện dùng chung cho Login, Nhân viên, Phòng ban, Công việc,
  Cảnh báo, Header, Sidebar và thẻ Tổng quan; giữ nguyên handler, API call,
  payload, route và dữ liệu hiển thị.
- Bổ sung nút ẩn/hiện cho các gợi ý AI trên Tổng quan, Công việc và Cảnh báo;
  lưu đề xuất trong `sessionStorage` theo vai trò/phạm vi để không gọi lại khi
  chuyển trang trong cùng phiên, đồng thời xoá cache sau khi áp dụng thành công.
- Đưa `AiAssistantWidget` lên cấp `App` để không bị khởi tạo lại khi đổi Page;
  Đóng chat chỉ ẩn cửa sổ và giữ nguyên phiên hội thoại.
- Không thay đổi `backend/**`, API contract, RBAC, store/hook dữ liệu hoặc luồng
  nghiệp vụ. Playwright UI-only không phát sinh request ghi dữ liệu.
- Verification: frontend `42 file / 141 test`, ESLint đạt, Vite build đạt,
  Playwright UI-only `11/11` đạt cho desktop/mobile, hai role, route dữ liệu nền,
  redirect, fallback và keyboard; SSE AI chỉ được mock tại local.
- Bổ sung inventory route và Network boundary để phân biệt rõ kiểm thử mock UI
  với nghiệm thu live workflow.

## [Weekly department evaluation date normalization] - Khắc phục lỗi 422 khi chọn ngày trong tuần

- Chuyển frontend sang route v1 chuẩn `weekly-reviews/{department_id}/{week_start}`;
  không còn gọi route cũ số ít khiến router hiểu nhầm thành `evaluation_id`.
- Service chuẩn hóa mọi ngày được gửi vào thành thứ Hai của tuần trước khi đọc evidence,
  kiểm tra trùng, lưu đánh giá hoặc xử lý tệp; các request chọn thứ Bảy như `2026-09-12`
  được xử lý cùng tuần `2026-09-07`.
- Regression test bao phủ route frontend và chuẩn hóa ngày ở service.

## [Performance history response compatibility] - Khôi phục lịch sử hiệu suất của Quản lý

- `listPerformance()` nhận cả phản hồi v1 dạng mảng `[...]` và dạng phân trang
  `{ items: [...] }`, không thay đổi contract backend hiện tại.
- Bổ sung regression test cho phản hồi mảng; kiểm chứng live trang Hiệu suất của Quản lý
  đã hiển thị lại các bản ghi lịch sử thật.
- Verification: frontend `40 file / 126 test` passed, ESLint passed, Vite build passed.

## [Notification Belt visual distinction] - Phân biệt nền từng nhóm thông báo

- Notification Belt sử dụng nền riêng cho từng nhóm: hổ phách cho cảnh báo, xanh dương
  cho chỉ thị và đỏ hồng cho công việc quá hạn.
- Giữ nguyên dữ liệu, điều hướng, trạng thái hover và độ tương phản chữ; chỉ bổ sung lớp
  nhận diện trực quan để người dùng phân biệt nhanh các nhóm cần theo dõi.

## [Notification Belt directives] - Bổ sung số lượng chỉ thị đang theo dõi

- Notification Belt hiện hiển thị riêng mục “Chỉ thị đang theo dõi” cho cả Manager và
  Leadership, lấy từ ba nguồn chỉ thị hiện có: yêu cầu xử lý cảnh báo, giao việc quá hạn
  và điều phối liên phòng ban.
- Badge tổng và nội dung nhắc được cộng thêm số chỉ thị đang hoạt động; chỉ thị đã
  `accepted` hoặc `fulfilled` không bị tính lại.
- Phạm vi dữ liệu vẫn do API/RBAC backend quyết định; bấm vào mục chỉ thị sẽ mở đúng
  Trung tâm chỉ thị theo role.
- Bổ sung cập nhật theo realtime cho `department_directives` và `task_directives` cùng
  regression test cho Manager.

## [Manager directive progress] - Đồng bộ tiến độ nghiệm thu với task mới nhất

- Card giao việc quá hạn của Quản lý tự tính lại tiến độ từ danh sách task hiện tại khi
  đã tải đủ toàn bộ task, không tiếp tục dùng snapshot `0%` cũ từ lúc chỉ thị vừa được
  tiếp nhận.
- Card lắng nghe thay đổi ở resource `tasks` để tải lại tiến độ chỉ thị; backend vẫn
  kiểm tra lại trạng thái task khi nhận request gửi nghiệm thu.
- Regression test bao phủ trường hợp 4/4 task đã `done` nhưng response chỉ thị cũ còn
  `completed_item_count=0`; UI hiện 100% và bật nút “Gửi nghiệm thu”.

## [Task directive reissue] - Cho phép phát hành lại sau nghiệm thu

- Gỡ việc tạo unique index `directed_task_once_unique` trên `task_ids`, vì index này
  khiến MongoDB từ chối chỉ thị mới cho task đã thuộc chỉ thị `accepted` trước đó.
- Service chỉ trả lại chỉ thị hiện hữu khi lỗi trùng khớp với chỉ thị đang hoạt động;
  chỉ thị lịch sử không còn làm thao tác phát hành mới hiển thị thành công giả.
- Thêm migration an toàn
  [migrate_drop_directed_task_once_index.py](backend/scripts/migrate_drop_directed_task_once_index.py)
  để drop index cũ mà không thay đổi document.

## [Leadership task portfolio] - Sửa bộ lọc việc chưa ra chỉ thị

- Bổ sung `has_active_directive` trong dữ liệu danh mục công việc để phân biệt chỉ thị
  đang xử lý với lịch sử chỉ thị đã nghiệm thu.
- Việc đã thuộc chỉ thị `accepted` nhưng được mở lại sẽ xuất hiện đúng trong bộ lọc
  “Chưa ra chỉ thị” và có thể được chọn để phát hành chỉ thị mới; các trạng thái active
  (`pending`, `acknowledged`, `submitted`, `needs_revision`) vẫn bị loại đúng.
- Giữ lại thông tin chỉ thị cũ để tra cứu, đồng thời hiển thị rõ “Đã nghiệm thu trước đó ·
  Có thể ra chỉ thị mới” trên giao diện Lãnh đạo.
- Verification: backend `test_task_service.py` 19 passed; frontend
  `LeadershipTasksOverview.test.jsx` 4 passed.

## [Active task directive status filtering] - Sửa việc quá hạn bị chặn vĩnh viễn

- Thêm `ACTIVE_DIRECTIVE_STATUSES` dùng chung cho `pending`, `acknowledged`,
  `submitted` và `needs_revision`; `accepted` được coi là trạng thái đã kết thúc.
- `TaskRepository.list_directed_task_ids()` lọc MongoDB theo tập trạng thái active.
  Leadership overview, phát hành chỉ thị, portfolio `not_directed` và cả bốn công cụ AI
  về việc quá hạn dùng cùng một quy tắc.
- Portfolio vẫn hiển thị thông tin lịch sử của chỉ thị `accepted`, nhưng không dùng nó để
  chặn task mở lại khỏi nhóm chưa gửi chỉ thị.
- Regression test bao phủ task quá hạn trở lại `todo` sau `accepted` và cả bốn trạng thái
  active; focused suite đạt `46 passed`.

## [Legacy personal coordination flow removed] - Xóa flow điều phối cá nhân cũ

- Gỡ `issue_directive()` và `list_directive_targets()` cùng các endpoint
  `/api/coordination/alerts/{alert_id}/direct` và
  `/api/coordination/alerts/{alert_id}/directive-targets`, bao gồm alias `/api/v1`.
- Gỡ `IssueDirectiveRequest`, `DirectiveTargetResponse`, repository method tạo
  `coordination_directives` và cấu hình tạo unique index `coordination_directives.alert_id`
  vốn chỉ phục vụ phát hành cá nhân. Collection/model đọc và `fulfill` chỉ thị điều phối hiện
  hữu vẫn được giữ để bảo toàn dữ liệu lịch sử.
- Chạy migration [migrate_drop_legacy_coordination_index.py](backend/scripts/migrate_drop_legacy_coordination_index.py)
  trên MongoDB Replica Set `rs0`: đã drop `alert_id_1`; số document trước/sau migration đều là
  `0`, không có document nào bị thay đổi. Migration có kiểm tra đúng key/unique trước khi drop
  và có thể chạy lại an toàn.
- Luồng chính thức còn lại: chỉ thị cấp phòng ban cho alert/task và `coordination_directives`
  hiện hữu với vòng đời `pending → fulfilled`.
- Verification: `test_legacy_personal_coordination_flow_is_removed` và full backend suite pass.

## [Directive flow hardening] - Đồng bộ route, transaction và trạng thái xử lý lại

- Frontend Manager dùng đúng các route v1 `POST` số nhiều cho cả giao việc quá hạn
  (`/api/v1/tasks/.../acknowledgements|submissions|acceptances|revision-requests`) và
  yêu cầu xử lý cảnh báo (`/api/v1/alerts/...`), giữ nguyên `Idempotency-Key`.
- `CoordinationService.apply()` và `fulfill_directive()` ghi plan, audit, trạng thái
  cảnh báo và trạng thái chỉ thị trong MongoDB transaction; MongoDB runtime đã xác nhận
  Replica Set `rs0` và session transaction hoạt động. Lỗi giữa bước được rollback để
  lần gửi lại cùng nghiệp vụ không bị kẹt 409.
- Bắt lỗi `DuplicateKeyError`/`PyMongoError` khi bổ sung công việc vào chỉ thị đang chờ,
  trả HTTP 409 bằng tiếng Việt thay vì 500.
- `needs_revision` có màu cảnh báo và nhãn hành động riêng, không hiển thị như đã nghiệm thu.
- Verification: backend `test_api_v1_phase8.py` 6 passed, `test_coordination_service.py`
  12 passed, `test_task_service.py` 14 passed; frontend focused Vitest 4 files / 14 passed.
- Flow `issue_directive` cá nhân cũ đã được dọn sau khi xác nhận không có caller runtime; việc
  chống đếm kép giữa flow cũ và chỉ thị cấp phòng ban không còn áp dụng.

## [Leadership directive visibility] - Không ẩn chỉ thị đang chờ tiếp nhận

- Sửa bộ lọc mặc định của Trung tâm chỉ thị Leadership từ `submitted` sang `all`.
- Chỉ thị công việc hoặc cảnh báo đang `pending` của các phòng ban, gồm Chăm sóc khách hàng,
  nay hiển thị ngay sau khi tải trang; Leadership vẫn có thể chọn riêng bộ lọc “chờ nghiệm thu”.
- API và MongoDB không thay đổi; kiểm tra live cho Manager Chăm sóc khách hàng vẫn trả `200`
  và đúng 1 chỉ thị `pending` gồm 10 công việc.

## [Leadership directive status] - Phân biệt đã phát hành và đã thực hiện chỉ thị

- Danh sách công việc của Leadership vẫn xác định “đã ra chỉ thị” bằng liên kết thật
  `directive_id`/`task_ids` từ backend, không dựa vào tên hoặc trạng thái công việc.
- Bổ sung nhãn theo vòng đời chỉ thị: chờ tiếp nhận, đang thực hiện, chờ nghiệm thu,
  đã nghiệm thu hoặc cần xử lý lại; công việc không có liên kết chỉ thị vẫn hiển thị
  “Chưa ra chỉ thị”.
- Read-only MongoDB verification: 54 công việc, 34 công việc có liên kết vào 5 chỉ thị
  thật và 20 công việc chưa có chỉ thị; không thay đổi dữ liệu live.
- Verification: focused frontend suite `3 passed`.

## [Cross-role directive matching] - Đồng bộ chỉ thị Leadership và Manager

- Hai role dùng chung bản ghi chỉ thị theo `target_department_id`; Manager chỉ nhận
  các bản ghi thuộc phòng mình, còn Leadership xem toàn bộ bản ghi đó.
- Tiến độ ở các màn hình nghiệp vụ lấy từ các khóa con thật của chỉ thị và tiến độ
  backend, tránh ghép nhầm task/cảnh báo ngoài chỉ thị.
- Read-only MongoDB verification trên database `hrms`: 5 task directives và 6 alert
  directives; không có liên kết con bị thiếu, lệch phòng ban, lệch Manager hoặc task
  bị gắn trùng nhiều chỉ thị.
- Ghi chú dữ liệu hiện tại: 3 task directives đã `accepted` nhưng task hiện tại lần
  lượt là `5/11`, `0/1`, `1/1` hoàn thành; đây là thay đổi sau nghiệm thu cần snapshot
  lịch sử riêng nếu muốn giữ “tiến độ tại thời điểm nghiệm thu”. Không tự sửa dữ liệu live.

## [Manager directive workflow] - Hiển thị lại sau tiếp nhận và đồng bộ tiến độ

- Trung tâm chỉ thị của Manager mặc định hiển thị toàn bộ trạng thái; bổ sung bộ lọc
  `đang thực hiện` để chỉ thị không biến mất sau khi được tiếp nhận.
- Trang Công việc và Cảnh báo ưu tiên tiến độ do backend tính theo đúng `task_ids`/
  `alert_ids` của chỉ thị, thay vì phụ thuộc hoàn toàn vào danh sách dữ liệu frontend
  đang có tại thời điểm render.
- Trang Công việc chỉ hiển thị các task thuộc chỉ thị tương ứng, tránh trộn task khác
  vào tiến độ hoặc danh sách chi tiết.
- Verification: focused frontend suite `13 passed`; toàn bộ frontend `35 test files,
  100 passed`; ESLint đạt.

## [Leadership overdue count] - Đồng bộ số việc quá hạn giữa các màn hình

- Sửa `TaskService`, `DashboardAttentionService` và `NotificationBell` để Lãnh đạo
  luôn thấy và đếm toàn bộ công việc đang quá hạn trong phạm vi toàn công ty, kể cả
  công việc đã được đưa vào chỉ thị.
- Giữ bộ lọc `focus=not_directed` riêng cho nhu cầu tìm các việc quá hạn chưa gửi
  chỉ thị; bộ lọc này không còn được dùng để làm sai số liệu giám sát tổng quát.
- `listTasks()` tải tiếp các trang v1 khi còn `has_next`, tránh đếm thiếu khi có hơn
  100 công việc quá hạn. Dashboard Leadership hiển thị thêm tổng số công việc quá hạn
  bên cạnh số phòng ban bị ảnh hưởng.
- Verification: backend `331 passed, 2 deselected`; frontend `35 test files, 98
  passed`; Ruff, Mypy, ESLint và Vite build đạt.

## [Leadership overdue workload] - Hiển thị đủ số việc quá hạn toàn công ty

- `get_overdue_work_summary` của Leadership nay tính toàn bộ công việc đang quá hạn theo
  từng phòng ban, không loại bỏ các việc đã nằm trong chỉ thị.
- Kết quả bổ sung cả tổng số việc quá hạn toàn công ty và số việc quá hạn chưa gửi chỉ thị,
  giúp Lãnh đạo phân biệt số liệu giám sát với số liệu cần phát hành chỉ thị.
- Sửa bộ lọc `focus=not_directed` của danh mục công việc Leadership để khớp với frontend.
- Verification: AI/task focused suite `40 passed`, Ruff đạt và OpenAPI xác nhận enum lọc mới.

## [Leadership AI chat] - Fallback có dữ liệu khi Cloudflare không diễn giải được

- Bổ sung fallback cục bộ cho các Data Tool của Lãnh đạo: so sánh hiệu suất phòng ban,
  đánh giá Quản lý, rủi ro vận hành, công việc quá hạn và phương án hỗ trợ liên phòng ban.
- Khi backend đã đọc được dữ liệu thật nhưng provider trả rỗng/lỗi, chatbot vẫn hiển thị
  Kết luận, Bằng chứng, Kỳ dữ liệu và Gợi ý bằng tiếng Việt; không trả lại thông báo chung
  “chưa thể diễn giải” và không gọi thêm dữ liệu ngoài phạm vi.
- Fallback không hiển thị mã phòng ban nội bộ; các điểm số và số lượng đều lấy trực tiếp từ
  kết quả Data Tool đã được backend kiểm tra quyền.
- Verification: nhóm test AI Leadership `54 passed`, Mypy không lỗi, Ruff không lỗi.

## [Leadership overdue tasks v1] - Khôi phục luồng danh sách việc quá hạn

- Bổ sung `GET /api/v1/tasks/departments/{department_id}/portfolio` để màn hình Lãnh đạo
  tải đúng danh mục theo phòng ban, bao gồm nhóm `overdue`, `due_soon`, ưu tiên cao và đang
  đúng tiến độ; route dùng lại `TaskService.department_portfolio` và kiểm tra RBAC Leadership.
- Bổ sung `POST /api/v1/tasks/department-directives/{department_id}` để thao tác phát hành
  chỉ thị từ danh sách quá hạn dùng đúng API v1, rate limit và Idempotency-Key hiện có.
- Nguyên nhân chính là frontend đã gọi các path v1 nhưng router v1 chỉ có một phần route;
  các endpoint tương ứng trước đó chỉ tồn tại ở router legacy `/api/tasks`.
- OpenAPI route audit và focused backend suite đạt: `27 passed`; Ruff và `git diff --check`
  đạt.

## [Leadership tasks v1] - Khắc phục 422 ở tổng quan công việc 90 ngày

- Bổ sung route tĩnh `GET /api/v1/tasks/leadership-overview` với các khoảng `7d`, `30d`,
  `90d`, tái sử dụng `TaskService.leadership_overview`, RBAC Leadership và rate limit
  `read_heavy` hiện có.
- Nguyên nhân là router v1 chưa đăng ký route này nên request bị bắt nhầm vào `/{task_id}`;
  chuỗi `leadership-overview` bị xử lý như mã công việc và trả `422`.
- Regression test xác nhận `range=90d` trả `200`; focused suite đạt `5 passed`, Ruff và
  `git diff --check` đạt.

## [Leadership AI proposal] - Bản nháp chỉ thị cấp phòng ban có human-in-the-loop

- Bổ sung `AiLeadershipContextService` ghép hiệu suất phòng ban, rủi ro, công việc quá hạn
  và `department_weekly_evaluations` thành context cấp công ty; không đưa dữ liệu cá nhân
  hoặc mã kỹ thuật vào phần diễn giải mặc định.
- Bổ sung `POST /api/v1/ai/leadership-proposal`, dùng cùng nhóm rate limit `ai_chat`; chỉ
  Leadership được gọi, Manager bị `403`. JSON được validate bằng Pydantic rồi lọc lần hai
  theo phòng ban thật trong context; output lỗi hoặc không có action trả fallback an toàn.
- Dashboard Leadership cho phép chỉnh sửa loại/mức cảnh báo và ghi chú trước khi áp dụng;
  nút phát hành gọi thẳng `issueDepartmentDirective` hiện có, qua popup xác nhận và
  `Idempotency-Key`. AI không có endpoint thực thi riêng, không tự ghi MongoDB.
- Bổ sung Data Tool điều phối liên phòng ban ở cấp tổng hợp: backend tính khả năng nhận thêm
  việc, mức khớp kỹ năng, khả năng đúng hạn, chất lượng gần đây và mức độ phù hợp từ dữ liệu
  thật; AI chỉ được tham chiếu đúng cặp phòng ban có trong context.
- Bổ sung schema proposal cho điều phối liên phòng ban và đề xuất ngưỡng; Pydantic validation
  kết hợp lọc theo phòng ban/cặp ứng viên thật. UI hiển thị các bản nháp này nhưng không tạo
  nút áp dụng cho luồng điều phối chưa có API nghiệp vụ được duy trì.
- Bổ sung tổng quan Leadership, so sánh phòng ban và chính sách từ chối chi tiết nhân viên;
  các thao tác phát hành chỉ thị vẫn qua popup, API nghiệp vụ, RBAC và Idempotency-Key.
- Sửa lỗi định tuyến kỳ dữ liệu Leadership: các tool tổng hợp hiện giữ đúng khoảng ngày rõ ràng
  do người dùng nêu, tránh bỏ qua kỳ lịch sử rồi gọi Cloudflare không cần thiết khi kỳ đó không có dữ liệu.
- Verification bổ sung: backend Leadership context/routing/proposal `30 passed` trong focused suite,
  full backend `325 passed, 2 deselected`, `mypy app`
  và `ruff check app` đạt; frontend Leadership/dashboard `5 passed`, lint và production build
  đạt (Vite chỉ còn cảnh báo kích thước bundle).
- Sau khi bổ sung kiểm thử khoảng ngày, full backend đạt `326 passed, 2 deselected`; live boundary
  smoke đạt `no_data_status=200` và `policy_status=200`. Full frontend đạt `35 test files / 98 tests`.

## [Leadership AI roadmap] - Khảo sát và khóa phạm vi dữ liệu Leadership

- Ghi nhận kế hoạch 6 giai đoạn để mở rộng AI cho Lãnh đạo theo nghiệp vụ toàn công ty:
  context tổng hợp phòng ban, phân tích rủi ro, đánh giá Quản lý, dự thảo chỉ thị và
  đề xuất điều phối liên phòng ban.
- Xác nhận dùng lại `AiProviderFactory`/Cloudflare Workers AI, Data Tool registry,
  RBAC, audit, idempotency và cơ chế popup xác nhận hiện có; AI chỉ đề xuất, không tự
  phát hành hoặc ghi dữ liệu.
- Rà soát cho thấy các tool hiện tại đã hỗ trợ Leadership ở scope toàn công ty và có
  `department_weekly_evaluations`, nhưng chưa đủ an toàn để gọi là Leadership AI hoàn chỉnh:
  cần tách contract tổng hợp, lọc dữ liệu chi tiết nhân viên và bổ sung tool đánh giá Quản lý,
  rủi ro phòng ban, quá hạn theo phòng ban và điều phối liên phòng ban.
- Giai đoạn tiếp theo phải kiểm thử riêng Leadership thành công, Manager gọi nhầm tool bị
  `403`, dữ liệu phòng ban không tồn tại không gây `500`, JSON AI lỗi fallback an toàn và
  đề xuất chỉ thị không tự áp dụng.

## [Leadership AI context contract] - Hợp đồng dữ liệu tổng hợp cấp công ty

- Thêm `backend/app/models/ai_leadership.py` với các model strict cho tổng hợp phòng ban,
  rủi ro, công việc quá hạn, đánh giá Quản lý và `LeadershipAiContext`.
- `LeadershipAiContextBuilder` kiểm tra role ở backend, cố định phạm vi `company` và từ chối
  field ngoài contract; payload đưa vào prompt dùng nhãn tiếng Việt, không chứa email,
  số điện thoại hoặc dữ liệu cá nhân.
- Contract mới chưa thay đổi registry/tool cũ để giữ tương thích; bước tiếp theo là nối
  từng Leadership Data Tool vào contract và bổ sung kiểm thử Manager nhận `403`.
- Verification: `backend/tests/test_ai_leadership_context.py` đạt `3 passed`; Ruff và
  `git diff --check` đạt.

## [Leadership AI read tools] - Data Tools tổng hợp chỉ dành cho Lãnh đạo

- Bổ sung 4 tool chỉ-đọc với `allowed_roles={leadership}`: tổng hợp hiệu suất toàn công ty,
  rủi ro theo phòng ban, đánh giá Quản lý từ `department_weekly_evaluations` và công việc
  quá hạn theo phòng ban.
- Tuyến deterministic nhận diện các câu hỏi Leadership về hiệu suất, cảnh báo/quá tải,
  quá hạn và đánh giá để ưu tiên tool tổng hợp; Manager không được thấy hoặc gọi 4 tool này.
- Các bản tổng hợp không trả tên người phụ trách, không đưa email/số điện thoại và loại bỏ
  công việc đã nằm trong chỉ thị hiện hành; scope phòng ban cụ thể vẫn được kiểm tra ở backend.
- Các tool có thể trả dữ liệu cá nhân/chi tiết đã được giới hạn cho Manager ở registry;
  Leadership không thể gọi chúng chỉ bằng cách gửi tên tool từ planner.
- Các tool Manager và các route thay đổi dữ liệu chưa bị thay thế; mọi hành động phát hành
  chỉ thị/điều phối vẫn chờ human-in-the-loop ở giai đoạn tiếp theo.

## [Action confirmation feedback] - Xác nhận và phản hồi kết quả thao tác

- Bổ sung `ActionFeedbackProvider` dùng chung: popup xác nhận có animation trước mọi thao tác
  thêm, sửa, xóa, nghiệm thu, xử lý cảnh báo, điều phối và phát hành chỉ thị quan trọng.
- Popup hiển thị đúng đối tượng, người phụ trách/phòng ban, thời hạn, số lượng và ghi chú liên
  quan; người dùng có thể hủy trước khi request được gửi.
- Sau request, hiển thị toast thành công hoặc thất bại với thông tin cụ thể từ thao tác/API;
  lỗi vẫn được giữ ở vùng thông báo nghiệp vụ tại trang để không mất ngữ cảnh.
- Các test component xác nhận đường thành công, hủy thao tác và lỗi; không thay đổi API nghiệp vụ
  hay RBAC hiện có.

## [AI loading animations] - Hiệu ứng trạng thái xử lý của Trợ lý AI

- Thêm `AiLoadingIndicator` dùng chung với biểu tượng nhịp nhẹ, ba chấm chuyển động và
  thông báo trạng thái cho chatbot, tóm tắt AI và các thẻ đề xuất.
- Tôn trọng `prefers-reduced-motion` để giảm chuyển động khi người dùng bật tùy chọn trợ năng.

## [UI animation audit] - Chuyển cảnh xuất hiện và đóng đồng bộ

- Bổ sung animation vào/ra cho chuyển trang, modal, menu mobile, bảng thông báo, chatbot,
  tin nhắn, card tóm tắt và các nhóm nội dung xuất hiện động.
- Chuẩn hóa `FadeIn`, `SlideIn`, `PageTransition` với trạng thái `exit`, dùng
  `AnimatePresence` ở các vùng có mount/unmount và giữ hỗ trợ `prefers-reduced-motion`.
- Tăng nhẹ thời lượng fade/slide, chuyển trang, modal và loading AI để chuyển cảnh mềm hơn;
  vẫn giữ thời lượng bằng 0 khi người dùng bật `prefers-reduced-motion`.
- Tập trung các mốc thời gian vào motion tokens, chuẩn hóa utility Tailwind cho control và
  bổ sung `ANIMATION_GUIDELINES.md` để các tính năng mới dùng cùng quy ước.
- Thêm `StaggerList` cho danh sách động, áp dụng stagger cho KPI/gợi ý/việc cần ưu tiên và
  chuẩn hóa transition của các control trên Tasks, Calendar, Alerts, AI và Notifications.
- Chuông thông báo chỉ rung một lần khi có nhóm thông báo mới; nhắc việc chỉ xuất hiện một lần
  theo phiên tải để tránh chuyển động lặp gây phân tâm.
- Bổ sung `AnimatedTableRows` cho danh sách nhân viên, phòng ban, công việc, lịch công việc,
  hiệu suất và đánh giá; hàng mới/hàng bị xoá được fade/slide theo motion token, đồng thời
  hỗ trợ `prefers-reduced-motion` và giữ nguyên cấu trúc bảng hợp lệ.
- Các card đề xuất xử lý quá hạn/cảnh báo của AI chuyển trạng thái nút → loading → kết quả
  bằng `AnimatePresence`, đồng thời stagger các phương án để người dùng dễ theo dõi.
- Lỗi validation của trường nhập liệu có rung nhẹ một lần để dễ nhận biết, nhưng vẫn giữ nguyên
  thông báo tiếng Việt và tự giảm về không chuyển động theo tùy chọn trợ năng.
- Biểu đồ xu hướng cảnh báo trên AlertsPage có hiệu ứng các cột dựng lên tuần tự, dùng token
  motion và không lặp vô hạn.
- Event chip trong lịch tháng/tuần/ngày có enter/exit và stagger khi dữ liệu công việc thay đổi.
- Nút “+N khác” trong ô lịch có chuyển cảnh vào/ra khi danh sách công việc thay đổi.

## [Manager task-action planning] - Xếp hạng nhiều phương án xử lý việc quá hạn

- Thêm `TaskActionPlanningService`: backend lọc ứng viên theo phòng ban, trạng thái hoạt
  động, số việc đang mở/quá hạn, lịch sử hiệu suất 14 ngày, chất lượng và kỹ năng tùy chọn.
- Sinh các phương án giữ người và gia hạn 1/3/5 ngày, đổi người, đổi người kèm gia hạn;
  khi thiếu dữ liệu thì chỉ trả phương án xử lý thủ công. Mỗi phương án có `fit_score`
  0–100, `confidence`, bằng chứng và `plan_version`.
- Điểm được tính deterministic ở backend theo trọng số sức chứa 30%, chất lượng 20%,
  khôi phục deadline 20%, kỹ năng 10%, độ tin cậy deadline 10% và hiệu suất 10%;
  model AI chỉ diễn giải rationale, không được thêm/bớt hoặc đổi điểm/phương án.
- Bổ sung trường tùy chọn `estimated_effort_hours`, `required_skills` cho task và `skills`
  cho employee, giữ tương thích với dữ liệu cũ nhờ giá trị mặc định rỗng.
- Nút áp dụng gửi `expected_updated_at` và `planning_version`; backend từ chối `409` nếu
  task đã thay đổi, đồng thời ghi audit khi áp dụng kế hoạch có đổi người/deadline.
- Không còn sinh nhánh đổi người với deadline quá hạn cũ; nhánh đổi người đặt lại hạn tối
  thiểu ngày mai hoặc gia hạn 3 ngày. Backend từ chối proposal thiếu deadline mới/quá khứ
  và kiểm tra `updated_at` ngay trong câu lệnh cập nhật để tránh race condition.

## [Manager AI overdue-task proposal] - Đề xuất xử lý công việc quá hạn có human approval

- Bổ sung `POST /api/v1/tasks/{task_id}/ai-proposal`, chỉ cho Manager trong đúng phạm vi
  phòng ban và dùng chung rate limit `ai_chat`. Endpoint chỉ nhận công việc còn quá hạn;
  công việc ngoài scope hoặc không còn quá hạn không được đưa vào prompt.
- Thêm schema Pydantic cho đề xuất `update_overdue_task`, giới hạn thay đổi ở `status`
  và/hoặc `due_date`, đồng thời loại action không khớp `task_id` hoặc không có trường
  thay đổi. JSON lỗi, sai schema hoặc action rỗng đều fallback an toàn.
- Giao diện công việc hiển thị nút hỏi AI cho Manager, cho phép sửa trạng thái và deadline
  trước khi áp dụng. Nút xác nhận gọi trực tiếp `updateTask`/`PATCH /api/v1/tasks/{task_id}`;
  không có endpoint thực thi kế hoạch AI, không cho AI tự ghi dữ liệu.
- Bổ sung test provider mock cho proposal hợp lệ và mã công việc giả, test UI sửa proposal
  rồi gọi đúng API nghiệp vụ. Các thao tác cập nhật tiếp tục đi qua RBAC, audit và rate limit
  của API công việc hiện có.

## [AI Data Tools reliability] - Ngăn model bịa thời gian và chọn sai tool

- Với các câu hỏi Manager tiếng Việt có ý định rõ, backend định tuyến Data Tool bảo thủ
  trước khi gọi Cloudflare planner; provider không còn là nguồn quyết định duy nhất cho
  các truy vấn đã nhận diện được.
- Chuẩn hóa lại `date_from`/`date_to`: không chấp nhận ngày do model tự bịa khi người dùng
  không nêu kỳ, tự tính khoảng 7 ngày gần nhất cho các truy vấn xu hướng và giới hạn mọi
  khoảng đọc tối đa 90 ngày. Tên phòng ban do model tự điền cho “phòng tôi/phòng mình”
  cũng bị loại bỏ trước khi qua Pydantic và repository.
- Tách `AI_TOOL_MAX_COMPLETION_TOKENS=256` khỏi ngân sách chat/summary; system prompt của
  tool planner cấm bịa ngày, phòng ban, nhân viên và mã định danh.
- Khi planner chọn sai, không chọn được tool hoặc kết quả rỗng, orchestrator chỉ recovery
  một lần bằng tuyến xác định; audit phân biệt `deterministic_route`,
  `planner_tool_mismatch`, `deterministic_recovery` và `no_data_after_recovery`. Không có
  đường mới để AI tự ghi dữ liệu.
- Follow-up context có kỳ tương lai, kỳ đảo chiều, quá 90 ngày hoặc argument không hợp lệ
  bị từ chối với yêu cầu người dùng chọn lại kỳ; không âm thầm chuyển sang fallback kỳ khác.
- Route deterministic giữ lại tên phòng ban được người dùng nêu để lớp scope backend kiểm tra;
  Manager hỏi phòng ngoài phạm vi nhận kết quả rỗng an toàn thay vì dữ liệu phòng mình.
- Bổ sung test cho ngày cũ bị model bịa, khoảng lịch “tuần trước”, giới hạn 90 ngày,
  phòng ban giả và recovery an toàn khi không có dữ liệu.

## [Manager AI Copilot v2] - Chốt kế hoạch nâng cấp cho role Quản lý

### Đã triển khai MC0–MC5 (2026-09-10)

- Chuẩn hóa contract Data Tools tiếng Việt: `co_du_lieu`, `pham_vi`, `ky_du_lieu`,
  `tong_quan`, `du_lieu`, `nguon_du_lieu`; backend tính trend/compare và loại ID kỹ
  thuật trước khi đưa dữ liệu sang model.
- Bổ sung `get_performance_trend`, `compare_performance_periods` và `explain_alert`,
  cùng bộ 37 câu hỏi Manager để regression định tuyến; RBAC/scope vẫn được kiểm tra
  tại tool/repository, không tin phòng ban do người dùng nhập.
- Thêm `ManagerBriefingService` cho bản tin chủ động và ứng viên nhận thêm việc; AI
  chỉ diễn giải aggregate đã xếp hạng, cache summary vẫn giữ nguyên nguyên tắc không
  cache fallback.
- Thêm hội thoại nhiều lượt có context bounded theo `conversation_id`, user và scope;
  chỉ lưu tool arguments đã validate, không lưu prompt/output đầy đủ. Câu hỏi nối tiếp
  phải gọi lại tool và kiểm tra scope.
- Mở rộng proposal với `rationale`, bằng chứng, mức ưu tiên, thời điểm dữ liệu và điều
  kiện áp dụng. Human-in-the-loop vẫn bắt buộc: candidate thật được lọc lại, alert/scope
  được kiểm tra lại, và mutation chỉ đi qua `resolveAlert`/`applyCoordination` có audit/
  idempotency; không có endpoint “execute AI plan”.
- Structured audit/log có trạng thái chọn tool, thực thi, không có dữ liệu, provider
  fallback, timeout, empty output và reasoning bị cắt; raw prompt/dữ liệu nhân viên không
  được ghi. Production không bật `AI_DEBUG_STREAM`.
- Bằng chứng quality gate: backend `286 passed, 2 deselected`; frontend `85 passed`;
  `mypy app`, `ruff check`, `npm run lint` và `npm run build` đều đạt. Build chỉ còn cảnh
  báo kích thước chunk Vite, không phải lỗi triển khai.

- Chốt lộ trình `MC0 → MC1 → MC2 → MC3 → MC4 → MC5`: chuẩn hóa contract và bộ
  đánh giá; phân tích xu hướng/so sánh kỳ/giải thích cảnh báo; bản tin chủ động;
  hội thoại nhiều lượt; đề xuất hành động có human approval; cuối cùng là đo chất
  lượng, regression và hardening production.
- Chốt kiến trúc: Cloudflare Workers AI tiếp tục là provider; backend tính toán,
  kiểm tra RBAC/scope và thực thi nghiệp vụ; model chỉ chọn tool đọc hoặc diễn giải
  dữ liệu đã được kiểm tra. Chưa fine-tune và không gửi toàn bộ MongoDB cho model.
- Giữ nguyên nguyên tắc an toàn: Manager chỉ đọc phòng ban của mình, không tạo
  endpoint AI tự thực thi, mọi resolve/điều phối vẫn đi qua API nghiệp vụ hiện có,
  human approval, audit và Idempotency-Key.
- Mỗi giai đoạn có checklist, test RBAC/provider-fallback, quality gate và tiêu chí
  chuyển giai đoạn; implementation đã được ghi nhận ở checklist README.
- Ghi chú phạm vi: luồng Leadership tạo “chỉ thị cảnh báo cấp phòng ban” vẫn chờ
  xác định chính xác API nghiệp vụ trước khi đưa vào MC4.

## [AI Data Tools] - Chat grounded theo dữ liệu thật và phạm vi RBAC

- Phân biệt thông báo khi tool không truy cập được dữ liệu/quyền không phù hợp với
  trường hợp tool đã đọc thành công nhưng không có cảnh báo mở; tránh hiển thị fallback
  gây hiểu nhầm cho Manager không có cảnh báo trong phòng ban.
- Bổ sung tuyến định tuyến dự phòng bảo thủ cho các câu hỏi tiếng Việt phổ biến khi
  planner không trả `tool_calls`: chỉ ánh xạ vào tên tool allowlist và ngày được backend
  tự tính, sau đó vẫn kiểm tra schema/scope/RBAC như bình thường; không cho phép model
  tạo truy vấn MongoDB.

- Nối `POST /api/v1/ai/chat/stream` với lớp chọn công cụ đọc dữ liệu riêng; giữ nguyên
  contract `AiProviderFactory.generate_insight_stream(prompt)` và không cho model gửi
  raw Mongo query/collection/filter.
- Bổ sung bảy công cụ chỉ-đọc cho hiệu suất phòng ban/nhân viên, cảnh báo mở, nhân viên
  quá tải, ứng viên điều phối, đánh giá phòng ban theo tuần và công việc quá hạn. Mọi
  tham số đều qua Pydantic, giới hạn số lượng ở backend và kết quả được rút gọn với nhãn
  tiếng Việt, loại trường ID trước khi gửi sang model trả lời.
- Manager chỉ đọc được dữ liệu trong phòng ban của mình; Leadership có thể đọc tổng hợp
  toàn công ty. Tool mutation `apply_coordination` vẫn dừng ở human approval và không
  có endpoint AI tự áp dụng nghiệp vụ.
- Khi planner lỗi, không chọn được tool, tham số/scope không hợp lệ hoặc không có dữ liệu,
  chat trả lời an toàn: “Chưa đủ dữ liệu hoặc quyền truy cập để trả lời câu hỏi này.”
  Không gọi model tự do để bịa dữ liệu; audit chỉ lưu metadata và kết quả tổng quát.
- Bổ sung `tong_quan` cho tool hiệu suất phòng ban, tính điểm hiệu suất/chất lượng theo trọng
  số số ngày ghi nhận để câu hỏi tổng hợp không cần model tự tính từ danh sách nhân viên.
- Khi tool đã đọc được dữ liệu nhưng provider không sinh được câu trả lời, backend trả số liệu
  tổng hợp cục bộ đã được kiểm tra quyền thay vì báo nhầm lỗi truy cập; log thêm
  `ai_text_generation_failure` với loại lỗi provider/stream nhưng không ghi prompt hay dữ liệu.
- Kiểm chứng bổ sung: backend `242 passed, 2 deselected`, mypy 126 source files sạch và
  test AI tập trung `17 passed`.
- Bổ sung trạng thái UI “Đang đọc dữ liệu hệ thống…”. Kiểm chứng: backend `238 passed,
  2 deselected`, Ruff/mypy sạch; frontend `32` file/`82` test, ESLint sạch và production
  build thành công.
- Chuẩn hóa hiển thị câu trả lời có danh sách của Trợ lý AI: backend yêu cầu mỗi nhân viên
  trên một dòng, frontend tách các mục dồn dòng và hiển thị dấu đầu dòng/in đậm an toàn;
  bổ sung test cho phản hồi hiệu suất dạng compact. Kiểm chứng frontend `32` file/`83` test,
  ESLint sạch và production build thành công.

## [AI infrastructure reliability] - Chuẩn hóa runtime, parser và Dashboard summary

- Chuẩn hóa backend/frontend theo một origin backend cấu hình được; health check bổ sung
  provider/model, trạng thái cấu hình chính/dự phòng và thời điểm process khởi động mà không
  lộ credentials.
- Cloudflare stream parser nhận diện `reasoning_content`, `finish_reason`, stream rỗng,
  malformed SSE, timeout và HTTP lỗi; factory ghi structured event có request id, timing,
  số chunk/ký tự và loại lỗi nhưng không ghi prompt/token.
- Bổ sung cấu hình `AI_MAX_COMPLETION_TOKENS=4096`, feature flag
  `AI_ENABLE_THINKING` và debug flag `AI_DEBUG_STREAM`. Khi stream kết thúc bằng
  `finish_reason=length` nhưng chưa có đủ nội dung hiển thị, hệ thống ghi nhận lỗi riêng
  `reasoning_truncated` để phân biệt với network/timeout.
- Tách context Dashboard thành số liệu tổng hợp nhỏ gọn, giới hạn output summary và thêm
  timeout theo pha. Cache theo user/phạm vi/ngày kèm single-flight; fallback không được cache.
- Giữ nguyên nguyên tắc human-in-the-loop và quota `ai_chat`; fallback provider hỗ trợ
  model riêng qua `AI_FALLBACK_MODEL`.

## [AI orchestration, RAG và governance] - Giai đoạn 5–7

- Thêm lớp tool-calling riêng, không sửa contract `IAiProvider.generate_insight_stream`:
  tool được allowlist, có Pydantic input schema, kiểm tra role/scope và đi qua
  `CoordinationService` hiện có. Tool đọc candidate chỉ đọc; nhánh mutation chỉ trả
  `approval_required`, không có đường AI tự tạo plan hoặc resolve alert.
- Thêm RAG tùy chọn với chunking, Cloudflare `@cf/qwen/qwen3-embedding-0.6b`,
  indexing pipeline `document → chunk → embedding → Mongo`, MongoDB Atlas
  `$vectorSearch` và lọc theo phòng ban. Khi RAG tắt, embedding thiếu,
  hoặc local Mongo chưa có vector index, chat vẫn chạy với context hiện có và trả
  fallback rỗng an toàn. Development có local cosine fallback opt-in; production
  vẫn phải dùng Atlas `$vectorSearch`.
- Tách `ai_audit_logs`: chỉ lưu actor, provider/model, loại request, trạng thái,
  độ dài và SHA-256 của input/output cùng summary; không lưu nguyên prompt/output.
- Kiểm thử sau từng lớp: tool/RAG/governance đạt `18 passed`; live adapter Cloudflare
  trả `ToolCall` hợp lệ; live RAG indexing/retrieval với policy fixture tổng hợp
  trả về chunk và score; chat live với repository rỗng ghi governance metadata thành
  công. Không dùng context HR thật trong live acceptance.

## [AI reliability hardening] - Giới hạn timeout, output, retry và cache

- Bổ sung deadline tổng `AI_TOTAL_TIMEOUT_SECONDS=60` cho chat/proposal; timeout
  không làm request chờ vô hạn và luôn trả fallback an toàn.
- Giới hạn `AI_MAX_COMPLETION_TOKENS=768`; proposal Cloudflare dùng JSON object mode
  nội bộ và tắt thinking mode của Gemma cho proposal để token budget dành cho JSON;
  sau đó vẫn bắt buộc qua Pydantic và lọc candidate thật.
- Retry tối đa một lần cho timeout và HTTP `408/429/5xx`, có backoff cấu hình được;
  lỗi credentials hoặc JSON/schema không bị retry lặp.
- Cache proposal hợp lệ theo `alert_id`, `updated_at` và snapshot candidates trong
  Redis; fallback in-memory khi Redis không sẵn sàng. Proposal fallback rỗng không
  được cache để tránh giữ lỗi tạm thời.
- Test riêng sau từng lớp hardening đã đạt; full backend suite đạt `213 passed,
  2 deselected`, mypy sạch.

## [Cloudflare Workers AI] - Tích hợp Gemma 4 qua backend

- Bổ sung `CloudflareProvider` gọi Workers AI qua endpoint OpenAI-compatible; cấu hình
  `AI_PROVIDER=cloudflare` và `AI_MODEL=@cf/google/gemma-4-26b-a4b-it` không làm thay đổi
  API hoặc frontend hiện có.
- `CLOUDFLARE_ACCOUNT_ID` và `CLOUDFLARE_API_TOKEN` chỉ được đọc ở backend; không đưa
  credentials xuống frontend. Provider lỗi, timeout hoặc HTTP 401/403/429 đi qua circuit
  breaker/fallback hiện có và trả thông báo an toàn khi không còn provider khả dụng.
- Giữ nguyên nguyên tắc AI chỉ đề xuất, không tự thực thi nghiệp vụ; các lớp function
  calling, RAG và AI audit log riêng được bổ sung ở mục Giai đoạn 5–7 phía trên.
- Kiểm chứng: mock provider tests cho response stream, credentials thiếu, 401/403/429,
  timeout và fallback; backend `208 passed`, Ruff/mypy sạch; frontend `79 tests passed`
  và production build thành công.

## [AI alert proposal] - Manager xem và chỉnh sửa đề xuất xử lý cảnh báo

- Thêm `POST /api/v1/alerts/{alert_id}/ai-proposal`, dùng chung quota `ai_chat`
  (`RATE_LIMIT_AI_CHAT=10/phút`) và chỉ cho Manager trong đúng phòng ban với
  cảnh báo đang mở.
- AI chỉ tạo đề xuất; mọi nút áp dụng vẫn gọi trực tiếp nghiệp vụ hiện có
  (`resolveAlert` hoặc `applyCoordination`), qua nguyên RBAC, audit và
  Idempotency-Key. Không có endpoint thực thi kế hoạch AI.
- Đề xuất được kiểm tra hai lớp: Pydantic schema (bao gồm giới hạn chuyển
  chính xác 1–2 công việc) và đối chiếu `target_employee_id` với candidates thật;
  action sai bị loại, lỗi JSON/schema trả thông báo an toàn, không làm crash API.
- Đã thêm UI cho Manager để xem rationale, sửa ghi chú/ứng viên/số công việc
  trước khi áp dụng. Giai đoạn 2 cho Leadership đang chờ xác định đúng tên hàm
  API tạo “chỉ thị cảnh báo cấp phòng ban”.

## [Alert resolve fix] - Bổ sung trạng thái resolved cho PATCH v1

- Nguyên nhân: `AlertResolveV1Request` bắt buộc `status="resolved"`, nhưng
  frontend chỉ gửi `resolution_note`, khiến FastAPI trả `422` trước khi gọi
  service.
- Đã sửa `alertsApi.resolveAlert()` gửi đủ `status` và `resolution_note`.
- Test frontend: `29` file, `76` test đạt; ESLint và production build đạt.
- Live smoke: PATCH cảnh báo đang mở trả `200`, response có
  `status=resolved`, logout trả `204`.

## [Rate-limit enforcement] - Bật chặn thật read_operational

- Đã thêm `read_operational` vào `RATE_LIMIT_ENFORCED_GROUPS` trong `.env` và
  `.env.example`; `read_heavy` vẫn giữ shadow mode.
- Backend mới trên cổng kiểm thử đã xác nhận: 120 request tasks/alerts đầu trả
  `200`, request thứ 121 trả `429` với `X-RateLimit-Limit=120`,
  `X-RateLimit-Remaining=0` và `Retry-After` hợp lệ.
- Tài khoản Manager khác vẫn có quota riêng và request đầu trả `200`.
- Full backend test: `191 passed`; mypy và Ruff đạt.
- Lưu ý vận hành: service đang giữ cổng `8000` không thuộc process có thể
  restart từ môi trường hiện tại; smoke trên cổng `8000` vẫn cho request 121
  trả `200`, nên cần restart service đó để nạp `.env` mới trước khi coi rollout
  live trên cổng chính đã hoàn tất.

## [Rate-limit remediation] - Tách quota đọc vận hành và giảm refetch trùng

### Thay đổi

- Thêm group `read_operational` với quota riêng `RATE_LIMIT_OPERATIONAL=120`;
  group này dùng cho `GET /api(tasks|alerts)` và các route v1 tương ứng.
- `read_heavy=30/phút` tiếp tục dành cho performance analytics, weekly trend và
  các read-model tổng hợp nặng; không còn dùng chung quota với danh sách tasks/
  alerts vận hành.
- Tạm đưa `read_heavy` ra khỏi `RATE_LIMIT_ENFORCED_GROUPS` trong thời gian đo
  để request hợp lệ không bị 429; shadow counter vẫn tiếp tục ghi nhận.
- Thêm `requestCoordinator` phía frontend để deduplicate request đọc đồng thời,
  giữ cache rất ngắn 750ms và xóa cache theo resource sau mutation hoặc đổi
  session. Đây không phải cache nghiệp vụ dài hạn.

### Phạm vi không thay đổi

- Không dùng header frontend để tự khai báo loại request.
- Không thay đổi payload, RBAC, response API, WebSocket contract hoặc logic
  nghiệp vụ.
- WebSocket frame không bị tính vào `read_operational`; chỉ các HTTP refetch do
  callback realtime mới dùng quota đọc.

### Kiểm thử ban đầu

- Backend rate-limit focused: đạt `34 passed`.
- Frontend test chưa chạy được trong sandbox hiện tại vì esbuild/Vitest bị
  `Access is denied` khi đọc `vitest.config.js`; cần chạy lại trong môi trường
  frontend có quyền đọc đầy đủ.

### Xác minh bổ sung

- Sau khi sửa test, backend đạt `191 passed`, mypy `app` và Ruff đạt; frontend
  đạt `29 test files / 75 tests`, ESLint và Vite production build đạt (chỉ còn
  cảnh báo bundle lớn hơn 500 kB).
- Live cookie smoke với `demo.manager` gọi xen kẽ 20 request Tasks/Alerts trên
  backend đang chạy: cả 20 trả `200`, quota hiển thị `120` của
  `read_operational`, không có `429`; `Remaining` giảm từ `117` xuống `98`.
- `GET /api/v1/performance/analytics/...` vẫn trả header quota `read_heavy=30`,
  xác nhận analytics chưa bị nới theo group vận hành.
- `smoke_realtime_cookie.py` live đạt: WebSocket cookie/RBAC Manager KD,
  Manager KT và Leadership nhận đúng phạm vi; event tạm thời được dọn khỏi
  MongoDB sau kiểm thử.
- Playwright production-build live đạt: test theo dõi response `/alerts` và
  `/tasks` khi chuyển trang, sau đó phát burst 5 frame realtime `alerts` trên
  các socket của browser. Không có `429`, mỗi URL alerts chỉ phát sinh tối đa
  một request trong burst, và event alerts không kéo theo GET tasks.
- Một lần chạy trước đó bị `ERR_CONNECTION_REFUSED` vì preview tạm đã kết thúc;
  sau khi khởi động lại preview và xác nhận listener, lần chạy chính thức đạt
  `1 passed` trong `7.3s`.

Đây là bước đầu của rollout: sau khi đo production build và xác nhận không còn
refetch trùng, mới cân nhắc đưa `read_operational` vào enforcement thật.

## [Phase 14 - Frontend Idempotency-Key] - Hoàn tất chuyển đổi frontend

### Phạm vi

- Giữ nguyên endpoint, payload và hành vi nghiệp vụ; chỉ bổ sung option
  `idempotencyKey` khi gọi các request ghi.
- `httpClient` tiếp tục là nơi duy nhất chuyển option này thành header
  `Idempotency-Key`.
- Key được sinh ở component/form bằng `generateIdempotencyKey()`, giữ nguyên
  khi cùng form gửi lại sau lỗi, và tạo key mới khi mở hành động mới hoặc thay
  đổi nội dung request.
- `IDEMPOTENCY_ENABLED=true` vẫn giữ semantics opt-in hiện tại: request thiếu
  header được xử lý bình thường, không bị 400/503; request có header vẫn có
  replay, conflict và in-progress protection.

### Hàm đã gắn key

- Chỉ thị công việc: `issueDepartmentTaskDirective`,
  `acknowledgeDepartmentTaskDirective`, `submitDepartmentTaskDirective`,
  `acceptDepartmentTaskDirective`, `requestTaskDirectiveRevision`.
- Chỉ thị cảnh báo: `issueDepartmentDirective`,
  `acknowledgeDepartmentDirective`, `submitDepartmentDirective`,
  `acceptDepartmentDirective`, `requestDepartmentDirectiveRevision`.
- Điều phối: `applyCoordination`, `fulfillDirective`.
- Nghiệm thu hiệu suất ngày: `saveDailyPerformanceReview`,
  `updateDailyPerformanceReview`.
- Đánh giá phòng ban tuần: `createDepartmentEvaluation`,
  `updateDepartmentEvaluation`.
- Upload: `createUploadSession`, `completeUploadSession`.

### Vòng đời key theo giao diện

- `LeadershipTasksOverview`, `ManagerTaskDirectives`, `DirectivesPage`,
  `AlertsPage`, `ManagerAlertDirectiveAction` và `PerformanceEntryPage` giữ key
  trong `useRef`; lỗi mạng không làm mất key trước khi người dùng thử lại.
- `DepartmentEvaluationsPage` giữ key cho request đánh giá và một cặp key riêng
  cho từng upload session (`create`/`complete`); `UploadManager` chỉ nhận và
  chuyển tiếp các key này, không tự sinh key trong API wrapper.
- Khi hành động thành công hoặc form bị đóng/mở lại, key được xóa/tạo lại để
  hành động tiếp theo không dùng lại key cũ.

### Kiểm thử

- Vitest: `28 test files, 73 tests passed`.
- ESLint: đạt với `--max-warnings 0`.
- Vite production build: đạt; vẫn còn cảnh báo chunk JavaScript lớn hơn 500 kB,
  không phải lỗi của lô này.
- `git diff --check`: đạt.

Đây là bước frontend cuối để đóng Phase 14, sau các lô chuyển API v1 cho
resource, sửa crash PerformanceDashboard, read-model xu hướng tuần và tải đủ
Tasks/Alerts/Overload trong giới hạn hiện tại.

## [Phase 14.3/19] - Tải đầy đủ Tasks, Alerts và Overload trong giới hạn hiện tại

- `listTasks()`, `listAlerts()` và `listOverloadLogs()` khai báo tường minh
  `page_size=100`, đúng giới hạn tối đa hiện tại của `ListQueryParams`.
- Cả ba wrapper vẫn trả về mảng `response.items ?? []`, không thay đổi caller hay
  logic lọc/nhóm ở `TasksPage`, `AlertsPage`, `DirectivesPage`,
  `PerformanceDashboard` và `NotificationBell`.
- Khi API trả `has_next=true`, wrapper ghi cảnh báo rõ ràng để phát hiện dữ liệu
  vượt 100 bản ghi; không làm thay đổi hành vi vận hành hiện tại.
- Số liệu MongoDB live tại thời điểm triển khai: `54 tasks`, `57 alerts`,
  `42 overload_logs`. Tất cả đều nằm trong một trang 100 bản ghi, nên vận hành
  bình thường không phát sinh `console.warn`.
- Đây là giải pháp phù hợp quy mô hiện tại, không phải chiến lược dài hạn. Khi
  resource vượt 100 bản ghi, cần chuyển sang `fetchAllPages` hoặc read-model
  tổng hợp riêng, tương tự quyết định đã áp dụng cho Performance.

## [Phase 14.2/19] - Read-model xu hướng hiệu suất theo tuần

### Thay đổi

- Thêm `GET /api/v1/performance/analytics/department/{department_id}/weekly-trend`.
- `PerformanceRepository.aggregate_weekly_average()` lấy employee IDs từ
  `employees.department_id`, sau đó dùng một pipeline MongoDB `$facet` để nhóm
  theo tuần Thứ 2 bằng `$dateTrunc` và tính `overall_average` trong cùng một
  round-trip. MongoDB live hiện tại là `8.3.4`.
- Giữ nguyên semantics cũ của `PerformanceDashboard`: tuần bắt đầu Thứ 2,
  nhãn ngày/tháng tiếng Việt và điểm tuần làm tròn half-up một chữ số; thêm
  `overall_average` để % thay đổi vẫn tính trên toàn bộ metrics, không lấy trung
  bình đơn giản của các trung bình tuần.
- `PerformanceDashboard` không còn gọi `listPerformance()`. Đã xóa truy vấn
  metrics raw khi mount, `getWeekStart()`, `averageByWeek()`,
  `averagePerformance()` và state raw `previousWeeklyMetrics`; thay bằng hai
  lời gọi read-model tuần hiện tại/kỳ trước.
- Việc chọn nhân viên mặc định nay lấy từ
  `departmentAnalytics.employees[*].employee_id`, ưu tiên nhân viên có
  `metric_days > 0`, chỉ chạy một lần và không ghi đè lựa chọn thủ công.
- `PerformanceEntryPage` vẫn giữ `listPerformance()` vì đây là use-case lịch sử
  nhập điểm độc lập, đã được bảo vệ bằng unwrap `response.items ?? []` ở hotfix
  trước đó.

### Đối chiếu dữ liệu thật và rate limit

- MongoDB live có `1.127` bản ghi `performance_metrics`. Với phòng KD trong cửa
  sổ `2026-08-11` đến `2026-09-09`, có `175` metrics; kết quả service và phép
  tính thủ công khớp cả 5 tuần (`84.0`, `83.2`, `82.7`, `82.1`, `79.5`) và
  `overall_average=82.69771428571428`.
- Production build smoke trên Redis thật: baseline trước lô này là `15/30`
  request `read_heavy`; sau khi reset counter test-only và chạy một Dashboard
  Manager sạch, bucket ghi `9/30`, không có 429, xu hướng tuần và 2 line chart
  hiển thị đúng.
- Audit cho thấy `GET /api/v1/performance` cũ đang thuộc `read_light`, nên không
  tự đổi nhóm rate-limit của endpoint mới khỏi `read_heavy` theo contract đã yêu
  cầu. Việc giảm `15` xuống `9` đến từ việc loại bỏ các truy vấn raw metrics và
  không phát sinh thêm truy vấn duplicate; các request heavy còn lại thuộc các
  read-model khác của Dashboard.

### Verification

- Backend: `pytest -q` đạt `188 passed`; Ruff và mypy `app` đạt.
- Frontend: Vitest `22 test files, 66 tests passed`; ESLint và production build
  đạt. Vite chỉ còn cảnh báo chunk lớn hơn 500 kB, không phải lỗi build.
- HTTP live `GET /api/v1/.../weekly-trend` trả `200`, đúng RBAC và response
  `{department_id, department_name, weeks, overall_average}`.

## [Hotfix 2026-09-09] - Khôi phục PerformanceDashboard sau thiếu unwrap API v1

- Sửa `frontend/src/features/performance/performanceApi.js`: `listPerformance()`
  trả về `response.items ?? []` thay vì trả thẳng `PageResponse`.
- Nguyên nhân: trong lúc chuyển frontend sang `/api/v1`, hàm này thiếu một dòng
  unwrap so với các API danh sách đã chuyển trước đó (`departments`, `employees`,
  `alerts`, `overload`).
- Ảnh hưởng: `PerformanceDashboard` nhận object thay vì mảng và có thể lỗi tại
  bước `.map()`, làm hỏng toàn bộ màn hình dashboard hiệu suất; lịch sử trong
  `PerformanceEntryPage` cũng bị ảnh hưởng.
- Audit toàn bộ caller: `PerformanceDashboard` (3 lời gọi) và
  `PerformanceEntryPage` (1 lời gọi). Không có caller nào tự unwrap `.items`,
  không có unwrap hai lần và không có mock `listPerformance()` trả
  `{ items: ... }` che giấu lỗi.
- Phát hiện ngày 2026-09-09 trong đợt audit di chuyển frontend Phase 14.1.
- Verification: thêm 2 unit test khóa contract mảng của `listPerformance()`.

## [Test fix 2026-09-09] - Loại bỏ ngày cam kết hardcode trong test chỉ thị

- `ManagerTaskDirectives.test.jsx` dùng ngày cam kết được tính động là ngày mai
  theo local date, nên không còn bị thuộc tính HTML `min` làm chặn submit khi thời
  gian chạy test thay đổi.
- Không thay đổi component, API, service hoặc dữ liệu nghiệp vụ.
- Verification: Vitest `21 test files, 63 tests passed`; ESLint và production
  build đều đạt.

## [Phase 14.1/19] - Chuẩn hóa caller Departments/Employees dùng API v1

### Audit và thay đổi

- Dữ liệu MongoDB hiện tại có `3` phòng ban và `16` nhân viên; cả hai đều nằm
  trong một trang `page=1&page_size=20`.
- `departmentsApi.js` và `employeesApi.js` dùng các endpoint v1 cho list/detail/
  POST/PATCH/DELETE; lô này chuẩn hóa list về `response.items` và cảnh báo qua
  `console.warn` nếu `has_next=true` thay vì âm thầm bỏ dữ liệu trang sau.
- Thêm `unwrapPageItems()` dùng chung cho hai resource và
  `generateIdempotencyKey()` dựa trên `crypto.randomUUID()`. Helper idempotency
  chỉ chuẩn bị cho Phase 14.5, chưa gắn vào Departments/Employees.

### Caller đã rà soát

`DepartmentsPage`, `EmployeesPage`, `TasksPage`, `PerformanceDashboard`,
`PerformanceEntryPage`, `DepartmentEvaluationsPage`, `DashboardPage` và
`NotificationBell` tiếp tục nhận mảng từ `listDepartments()`/
`listEmployees()`, không cần sửa contract component. Live smoke động xác nhận
Employees, Tasks, Performance và Department Evaluations gọi `/api/v1` và không
gọi `/api/departments` hoặc `/api/employees` cũ.

### Verification

- Unit mới: `3 test files, 5 tests passed`.
- Live smoke production preview: `2 passed`.
- `npm run lint`: đạt; `npm run build`: đạt.
- Full Vitest: `62 passed, 1 failed`; lỗi duy nhất là test cũ
  `ManagerTaskDirectives.test.jsx` dùng `commitment_date` đã quá hạn, không liên
  quan lô 14.1 và không sửa trong phạm vi này.

Tasks, Alerts, Overload và Performance list chưa được di chuyển theo Phase 14.1.
Các resource này có thể phụ thuộc toàn bộ danh sách hoặc read-model tổng hợp, sẽ
được quyết định riêng ở Phase 14.2-14.4; không áp dụng cơ chế lấy một trang này
cho chúng một cách máy móc.

## [Hotfix 2026-09-09] - Sửa route ordering cho chỉ thị công việc v1

- Thêm route tĩnh `GET /api/v1/tasks/department-directives` trước route động
  `GET /api/v1/tasks/{task_id}`.
- Tái sử dụng nguyên handler legacy để giữ payload list và các header phân trang;
  chỉ loại route compatibility trùng khỏi mount v1. `/api/tasks` cũ không thay đổi.
- Regression test xác nhận endpoint trả `200`, quota `read_light=120` và không
  còn bị route detail bắt nhầm dẫn tới `422`.
- Kiểm thử liên quan: `9 passed`, Ruff và mypy `app` đạt.
- Full backend: `186 passed, 1 failed`; lỗi còn lại là
  `test_ai_sse_returns_safe_vietnamese_response` trả `503` khi Redis không chạy,
  do nhóm `ai_chat` đang fail-closed; không liên quan hotfix route này.

## [Phase 12.1/19] - Gom debounce realtime và giảm refetch trùng

### Đã triển khai

- Thêm `REALTIME_COALESCE_DELAY_MS = 800` và hook
  `useCoalescedRealtimeUpdates(topics, callback, { delay })`.
- Một kết nối WebSocket có thể theo dõi nhiều topic; các event trong cùng burst
  được gom thành một callback. Nếu callback bất đồng bộ còn đang chạy, hook xếp
  đúng một lần chạy tiếp theo và không chạy chồng lấn; timer được dọn khi unmount.
- `DashboardPage` gom các topic `alerts`, `tasks`, `department_directives` và
  `task_directives` thành một luồng refetch chung.
- `PerformanceDashboard` dùng hook coalesce cho topic `performance_metrics`.
- `AlertsPage` áp dụng delay dùng chung cho callback cảnh báo, tránh gọi
  `loadAlerts()` liên tiếp khi realtime phát nhiều event.
- WebSocket browser tiếp tục dùng cookie session, không đưa access token lên
  query string.

### Caller realtime ngoài phạm vi lô này

Đã rà soát và ghi nhận, chưa gom lại trong Phase 12.1 để giữ phạm vi thay đổi:
`DirectiveSummaryCard`, `CoordinationSuggestionsCard`, `NotificationBell`,
`ManagerAlertDirectiveAction`, `LeadershipTasksOverview`, `ManagerTaskDirectives`,
`RealtimeAlertNotice`, `DepartmentEvaluationsPage`, `DirectivesPage`,
`PerformanceEntryPage` và `TasksPage`. Các caller này vẫn dùng hook tương thích
hiện tại và sẽ được xử lý theo từng màn hình ở lô frontend riêng.

### Kiểm thử và giới hạn đã ghi nhận

- Unit test hook: burst nhiều topic chỉ gọi callback một lần; callback chậm có
  đúng một follow-up sau khi hoàn tất, không overlap.
- `npm run lint`, `npm run format:check` và build trước live smoke đạt.
- Đo dev trước khi sửa route-ordering ghi nhận hai E2E Manager chạy tuần tự với
  Redis DB 15 cô lập; cold-load chạm quota `read_heavy=30/phút` và có 429 ở
  request vượt ngưỡng. Kết quả này được giữ làm baseline lịch sử, không dùng làm
  bằng chứng production vì còn nhiễu StrictMode và route tĩnh bị bắt nhầm.
- Full Vitest trước đó còn một test date-sensitive ngoài phạm vi thay đổi:
  `ManagerTaskDirectives.test.jsx` dùng `commitment_date` đã thấp hơn ngày hiện
  tại nên native validation chặn submit. Không sửa test nghiệp vụ này trong lô
  realtime.

### Audit bổ sung nguồn gốc `read_heavy`

- Request trace trực tiếp trên luồng Dashboard Manager → Alerts ghi nhận `20`
  lượt `read_heavy`, trong đó chỉ có frame WebSocket `connected`, không có frame
  event dữ liệu. Các lượt này đến từ cold-load/effect mount, không phải callback
  `useRealtimeUpdates`.
- Hai cụm request giống nhau xuất hiện gần như đồng thời do `React.StrictMode`
  của Vite dev chạy lại effect khi mount. Đây là đặc thù môi trường phát triển,
  không nên dùng riêng nó để kết luận traffic production.
- `GET /api/v1/tasks/department-directives` từng bị route động `/tasks/{task_id}`
  bắt trước, trả `422` và vẫn bị tính vào nhóm `read_heavy`. Hotfix 2026-09-09 đã
  đưa route tĩnh lên trước, tái sử dụng handler cũ và loại route compatibility
  trùng; regression test xác nhận `200`.
- Vì vậy số `28` và `30` trước/sau không phải hai phép đo hoàn toàn đồng nhất:
  `28` là số quan sát phía browser, còn `30` là số Redis gồm cả request nền và
  các lần kiểm thử nối tiếp.

### Đo xác minh bằng production build 2026-09-09

- Chạy `npm run build` thành công; E2E chạy qua `vite preview`, không còn
  React.StrictMode double-invoke của Vite dev.
- Hai kịch bản Manager (`Dashboard Manager render` và `Manager xử lý cảnh báo
  sớm`) chạy tuần tự trên cùng user, cùng backend tạm và Redis DB 14 cô lập; cả
  hai đều `passed`.
- Redis ghi nhận đúng khóa user
  `rl:user:6a90e6e7dca6d6b592fdff53:read_heavy` với `15` request trong cùng
  bucket 60 giây, còn `15` quota so với giới hạn `30`; log backend không có 429.
- So với baseline dev `20` lượt trace và các phép đo `28/30` không đồng nhất,
  phép đo production sạch cho thấy biên độ đã cải thiện rõ. Không thay đổi hoặc
  nới `RATE_LIMIT_READ_HEAVY`.
- Kết luận: phần điều tra rate-limit của Phase 12.1 đủ bằng chứng để đề nghị
  đóng sau khi người phụ trách xác nhận; tối ưu cold-load còn có thể ghi backlog,
  nhưng không còn là blocker của phép đo này. Chưa tự động chuyển Phase 14.

## [Live validation 2026-09-08] - Khắc phục các điểm chưa đạt sau smoke

### Đã xử lý

- Sửa lỗi `daily-review` trả `500`: service tạo đúng `DailyReviewAttachmentResponse`
  thay vì truyền model metadata cha vào trường response con. Live
  `GET /api/v1/performance/daily-reviews/{employee_id}/{date}` đã trả `200` với 5 công việc.
- `seed_performance_data.py` không còn giả định employee code luôn có hậu tố số;
  mã `NGB` hiện được hỗ trợ bằng giá trị dẫn xuất ổn định.
- Smoke performance lọc đúng cửa sổ 60 ngày và tính expected theo số nhân viên thực tế.
- Smoke overload đối chiếu ứng viên theo `department_id`, không suy luận phòng ban từ tiền tố mã.
- `check_app.py` dùng mapping tường minh cho route resource-shaped
  `/api/v1/department-evaluations/weekly-evaluations`.

### Xác nhận live

- MongoDB host `127.0.0.1:27017` được giữ làm nguồn dữ liệu chính vì đang chứa dữ liệu live;
  MongoDB Docker vẫn rỗng và không được dùng lẫn trong profiler/smoke.
- Seed thành công `960` metrics cho `16` employee trong `60` ngày; mỗi employee có đúng `60` bản ghi.
- Performance smoke đạt: 60 ngày, công thức `86.0`, RBAC scope.
- Overload smoke đạt: điều kiện A/B, rebalancer, alert high và RBAC scope.
- Quality gates: `186 passed`, Ruff đạt, mypy `app` đạt.
- Frontend đã sửa wrapper biểu đồ để Recharts đo đúng chiều rộng trong grid; fixture
  E2E tái sử dụng cookie theo vai trò và chờ hoàn tất điều hướng sau login.
- Vitest đạt `56/56`, lint/format/build đạt. Full E2E đạt `8/11`; 3 test dashboard/cảnh báo
  đã đạt khi chạy focused sau reset key rate-limit. Full suite còn chạm quota thật
  `read_heavy=30/phút` do các test dùng chung user/IP, nên cần Redis namespace hoặc
  cấu hình test riêng trước khi coi full E2E là bằng chứng độc lập.

### Việc còn lại

- Không tự động chuyển dữ liệu sang MongoDB Docker; việc đó cần quy trình dump/restore và xác nhận riêng.
- Frontend E2E đã dùng session cookie state để tránh quota `login=10/phút`; vẫn cần Redis
  test namespace/cấu hình test riêng để không chia sẻ quota `read_heavy=30/phút` giữa các test.

## [Hotfix 2026-09-08] - Khôi phục traffic khi Idempotency-Key chưa được frontend gửi

### Sự cố và nguyên nhân gốc

- `IDEMPOTENCY_ENABLED=true` đã được áp dụng trong môi trường chạy backend, trong khi
  frontend hiện tại chưa truyền `Idempotency-Key` cho các mutation liên quan.
- Dependency cũ đọc header bắt buộc trước khi kiểm tra cờ. Khi cờ là `false`, nó lại
  ném `503` thay vì bypass; vì vậy đây là lỗi killswitch kết hợp với một breaking
  change không có bước đệm.
- Chưa xác định được thời gian traffic thật bị ảnh hưởng; bằng chứng hiện có chỉ đủ
  xác nhận cấu hình nguy hiểm và các caller frontend chưa truyền header.

### Khôi phục khẩn cấp

- Đã đặt `IDEMPOTENCY_ENABLED=false` trong `.env` môi trường hiện tại và khởi động
  lại backend local trên cổng `8000` để process nhận cấu hình mới.
- Đã sửa `idempotent(...)`: khi cờ tắt, dependency `yield None` và `return` ngay,
  không đọc header, không gọi Redis, không raise exception. Đây là killswitch hoạt
  động cả khi Redis chết hoặc không tồn tại.
- Đã thêm test riêng cho killswitch. HTTP smoke không header trên 4 route mục tiêu
  trả `401` do chưa xác thực, không trả `400`/`503` do idempotency.

Việc phân tích bản đồ mount `/api`/`/api/v1` và quyết định bật lại tính năng được hoãn
đến sau khi xác nhận khôi phục Ưu tiên 1. Phần audit Ưu tiên 2 bên dưới đã hoàn tất;
Giai đoạn 14 vẫn phải bổ sung việc frontend gửi `Idempotency-Key` cho 8 nhóm route
để có thể theo dõi và dùng dedup đầy đủ.

### Ưu tiên 2: bản đồ mount thật và nguyên tắc mới

- `main.py` include **14 router legacy** dưới `/api`: `health`, `auth`, `alerts`,
  `attachments`, `ai`, `departments`, `department_evaluations`, `coordination`,
  `dashboard`, `employees`, `performance`, `overload`, `thresholds`, `tasks`.
- `/api/v1` được include đúng **một lần** từ `api_v1_router`; root này chứa 11
  router v1 riêng (`departments`, `employees`, `tasks`, `alerts`, `overload`,
  `performance`, `department_evaluations`, `coordination`, `thresholds`,
  `attachments`, `scans`) và các alias tương thích legacy.
- 8 router legacy được truyền trực tiếp lần nữa vào root v1 (`health`, `auth`,
  `attachments`, `ai`, `coordination`, `dashboard`, `performance`, `thresholds`).
  6 nhóm còn lại dùng compatibility router mới nhưng tái sử dụng các `APIRoute`
  legacy (`departments`, `employees`, `tasks`, `alerts`, `overload`,
  `department_evaluations`). Vì vậy `/api/v1` không thuần implementation mới.
- Các resource path v1 riêng đã xác nhận là implementation thật, ví dụ
  `/api/v1/departments`, `/api/v1/employees`, `/api/v1/tasks`,
  `/api/v1/performance/daily-reviews`, `/api/v1/department-evaluations/weekly-evaluations`,
  `/api/v1/coordination/directives/{id}/fulfillments`, `/api/v1/upload-sessions`,
  `/api/v1/alert-scans` và `/api/v1/overload-scans`.
- Các path như `/api/v1/performance/daily-review`, `/api/v1/performance/analytics/*`,
  `/api/v1/dashboard/attention-summary`, `/api/v1/ai/chat/stream`,
  `/api/v1/auth/*`, `/api/v1/attachments/upload-sessions` và các action legacy
  của task/alert/coordination là alias tương thích, không phải resource v1 mới.
- Ứng dụng vẫn khởi động được, nhưng introspection phát hiện một operation trùng
  chính xác: `GET /api/v1/department-evaluations/{evaluation_id}/attachments/{attachment_id}/download-url`.
  Router v1 riêng được đăng ký trước nên hiện là route được match; chưa tự ý xóa
  alias, cần quyết định migration riêng.
- Từ hotfix này, `Idempotency-Key` là **tùy chọn**. Không có header thì request đi
  qua như trước; có header thì vẫn giữ claim/replay, conflict `409` và in-progress
  `409`. Bộ đếm trong `app.state.idempotency_counters` và structured log
  `idempotency_request_observed` theo dõi `with_key`/`without_key` theo scope và
  route, không ghi raw key/token.

## [Phase 13/19] - Idempotency-Key cho chỉ thị, nghiệm thu và upload session

### Kết quả audit và quyết định kiến trúc

- Audit trước khi triển khai cho thấy dự án **đã có** `backend/app/infrastructure/idempotency.py`
  với store Redis/in-memory và middleware thử nghiệm. Vì vậy không tạo thêm thư mục
  `infrastructure/idempotency/` trùng tên; phần triển khai mới được bổ sung vào module
  hiện có để tránh hai abstraction cùng trách nhiệm.
- Production app không còn gắn middleware idempotency toàn cục. Enforcement hiện nằm ở
  dependency `idempotent(scope)` trên đúng các route ghi đã đăng ký; middleware cũ vẫn
  được giữ làm adapter tương thích cho test/consumer cũ, nhưng không chạy song song.
- Store Redis được rate limit và idempotency dùng chung một async Redis client runtime
  theo `REDIS_URL`, không tạo connection thứ hai cho hai cơ chế này. Trạng thái đang xử lý có TTL 30 giây;
  kết quả hoàn tất có TTL theo `IDEMPOTENCY_TTL_SECONDS` (mặc định 24 giờ). TTL ngắn là
  đánh đổi có chủ đích để request sau có thể thử lại nếu xử lý lỗi hoặc quá lâu.

### Route đã đăng ký Idempotency-Key

| Scope | Route áp dụng |
|---|---|
| `task_directive` | `POST /api/tasks/department-directives/{department_id}` và đường tương thích `/api/v1/tasks/department-directives/{department_id}` |
| `alert_directive` | `POST /api/coordination/department-directives/{department_id}` và `/api/v1/coordination/department-directives/{department_id}` |
| `coordination_directive` | `POST /api/coordination/alerts/{alert_id}/direct` và đường tương thích `/api/v1/coordination/alerts/{alert_id}/direct` |
| `coordination_fulfillment` | `POST /api/coordination/directives/{directive_id}/fulfill`, alias `/fulfillment`, và các route v1 `/api/v1/coordination/directives/{directive_id}/fulfillments`/`fulfill`/`fulfillment` |
| `daily_review` | `POST /api/performance/daily-review` và `POST /api/v1/performance/daily-reviews` |
| `weekly_evaluation` | `POST /api/department-evaluations/weekly-review` và `POST /api/v1/department-evaluations/weekly-evaluations` |
| `upload_session` | `POST /api/attachments/upload-sessions` và `POST /api/v1/upload-sessions`/`attachments/upload-sessions` |
| `upload_completion` | Completion legacy (`POST .../complete`, `PATCH .../{id}`) và các route v1 tương ứng (`PATCH .../{id}`, `POST .../completions`) |

Các route `DELETE` hủy upload session không bắt buộc khóa trong lô này vì danh sách
nghiệm thu chỉ yêu cầu tạo/completion. Các action acknowledge/submit/accept/revision
đã tồn tại dưới v1 nhưng không được tự động mở rộng phạm vi ngoài danh sách route đã
được audit; việc mở rộng phải là một quyết định migration riêng.

### Hành vi và xác minh

- Thiếu header từng trả `400` theo contract ban đầu; contract này đã được thay thế
  bởi hotfix: thiếu header được bypass bình thường.
- Cùng scope + key + request body đã hoàn tất sẽ replay nguyên status code, body và
  `Location` header; response replay có thêm `Idempotency-Replayed: true`.
- Cùng key nhưng body khác trả `409`; key đang xử lý trả `409`. Exception giữa chừng
  giải phóng claim để lần gửi lại hợp lệ có thể chạy tiếp.
- `IDEMPOTENCY_ENABLED=true` đã được bật trong `.env`, `.env.example` và Settings;
  các route đã đăng ký cần Redis sẵn sàng, nếu không sẽ trả `503` có chủ đích.
- OpenAPI hiện hiển thị header là tùy chọn trên mọi route; đây là contract tương thích
  sau hotfix.
- Phân biệt với index nghiệp vụ `pending_task_directive_focus_unique`: index chỉ ngăn
  hai chỉ thị pending trùng focus; Idempotency-Key ngăn client thực hiện lặp cùng một
  request do timeout/mất kết nối. Hai cơ chế bổ sung, không thay thế nhau.
- Xác minh: `pytest -q` đạt **183 passed**, Redis smoke thật đạt atomic claim/replay
  qua nhiều adapter, `mypy app`, `ruff check app tests/test_rate_limit.py` và
  compileall bằng project virtualenv đều đạt. Chưa coi đây là live Mongo/API smoke;
  kiểm thử route thật cần chạy khi Redis/Mongo và backend đang hoạt động.

## [Phase 12/19] - Enforcement nhóm đọc sau khi giảm refetch storm

### Kết quả audit

- Audit ban đầu đã xác nhận refetch storm từ realtime: trước đây
  `PerformanceDashboard.jsx` gọi callback cho từng event `performance_metrics`,
  còn `DashboardPage.jsx` gọi `loadSummary` cho từng event `alerts`/`tasks`.
- Không có polling API định kỳ. `NotificationBell` dùng `setInterval` chỉ để
  hiển thị/ẩn nhắc nhở trên UI; các `setTimeout` còn lại phục vụ reconnect,
  highlight hoặc cleanup, không gọi endpoint đọc.
- Không tìm thấy runtime log `shadow_denied` thực tế để định lượng traffic
  nhiều ngày; quyết định rollout dưới đây dựa trên mô phỏng code và test tự động,
  không giả định có số liệu production chưa thu thập.

### Triển khai hướng 1

- `useRealtimeUpdates` có tuỳ chọn trailing coalesce; mặc định `0` để bảo toàn
  các handler cần xử lý payload từng event.
- Các callback chỉ dùng để refetch dữ liệu trong dashboard, đánh giá, chỉ thị,
  thông báo, quá tải và điều phối dùng chung cửa sổ coalesce `250ms`. Handler
  cập nhật trực tiếp theo payload ở `TasksPage` và `AlertsPage` không bị đổi.
- Test mô phỏng 5 event liên tiếp xác nhận còn 1 callback, nhận payload mới nhất.
  Theo dependency graph hiện tại, `PerformanceDashboard` giảm từ 30/35 GET
  xuống 6/7 GET mỗi burst (Manager/Leadership); `DashboardPage` giảm từ 10
  xuống 2 GET với 5 event cùng topic.

### Sửa phân loại

- Đồng bộ `GET /api/tasks`, `GET /api/alerts` và `GET /api/overload` legacy sang
  `read_heavy`, khớp với route v1 và bảng phân loại Phase 5. Không thay đổi
  response hoặc logic nghiệp vụ.
- `/api/health` vẫn không có dependency rate limit và `health` vẫn nằm trong
  `HEALTH_BYPASS_GROUPS`.

### Quyết định rollout

Đã thêm `read_light,read_heavy` vào `RATE_LIMIT_ENFORCED_GROUPS` trong `.env` và
`.env.example`. `RATE_LIMIT_SHADOW_MODE=true` vẫn giữ nguyên; các nhóm không
nằm trong danh sách tiếp tục shadow. Không tăng quota đọc. `/api/health` vẫn
bypass rate limit.

## [Phase 11/19] - Enforcement thật cho nhóm `mutation`

### Audit trước rollout

- Đã rà soát đầy đủ các route có `rate_limit_group("mutation")` ở cả `/api` và
  `/api/v1`. Nhóm dự kiến Departments/Employees/Tasks CRUD và Performance/
  Department Evaluations là đúng, nhưng thực tế còn có các route mutation đã
  tồn tại: resolve alert, logout, apply coordination, đề xuất threshold config,
  cùng các alias legacy tương ứng. Không có route mutation bị thiếu dependency;
  danh sách thực tế gồm 34 decorator route trong source (bao gồm các alias).
- Không tìm thấy frontend loop gọi `updateTask`, `updateEmployee`, delete hoặc
  review mutation theo từng item. `UploadManager` có loop theo file nhưng dùng
  nhóm upload riêng, không phải `mutation`; các thao tác mutation hiện tại đều
  là single-request.
- Không tìm thấy log file/runtime record `shadow_denied` thực tế để thống kê vài
  ngày. Quyết định bật là rollout có chủ đích dựa trên quota `30/phút`, test
  atomic/key partition và không có bằng chứng false-positive traffic hợp lệ;
  không tuyên bố có số liệu production chưa thu thập.
- Cơ chế `RATE_LIMIT_ENFORCED_GROUPS` đã được test với việc thêm riêng một group:
  group được thêm bị chặn thật trong khi group khác vẫn shadow; các group Phase
  10 không bị thay đổi.
- DELETE departments/employees/tasks chạy dependency trước handler. Khi bị
  chặn, service không được gọi; mỗi thao tác là một request đơn, không có
  workflow bulk/transaction nhiều bước bị dừng giữa chừng. Business rule và
  kiểm tra scope vẫn nằm trong service hiện hữu.

### Thay đổi

- Thêm `mutation` vào `RATE_LIMIT_ENFORCED_GROUPS` trong `.env` và `.env.example`;
  giữ `RATE_LIMIT_MUTATION=30` và `RATE_LIMIT_SHADOW_MODE=true`.
- Không thêm logic nghiệp vụ hoặc endpoint mới. Enforcement vẫn dùng chung
  dependency hiện tại trên cả `/api` và `/api/v1`.
- Bổ sung test: request thứ 31 trong cùng quota nhận `429`, user khác có bucket
  riêng, còn group chưa rollout tiếp tục nhận `200` với header shadow.

Danh sách đầy đủ tại thời điểm bàn giao:

- Legacy `/api`: `PATCH /alerts/{alert_id}` và `PATCH /alerts/{alert_id}/resolve`;
  `POST /auth/logout`; `POST /coordination/alerts/{alert_id}/plans` và
  `POST /coordination/alerts/{alert_id}/apply`.
- Legacy `/api`: `POST /department-evaluations/weekly-review` và `PATCH
  /department-evaluations/{evaluation_id}`; `POST /departments`, `PATCH
  /departments/{department_id}`, `DELETE /departments/{department_id}`; `POST
  /employees`, `PATCH /employees/{employee_id}`, `DELETE
  /employees/{employee_id}`; `POST /tasks`, `PATCH /tasks/{task_id}`, `DELETE
  /tasks/{task_id}`.
- Legacy `/api`: `POST /performance/daily-review`, `PATCH
  /performance/daily-review`, `POST /performance/daily`; `POST /thresholds`.
- v1: `PATCH /alerts/{alert_id}`; `POST
  /department-evaluations/weekly-evaluations`, `PATCH
  /department-evaluations/{evaluation_id}`; POST/PATCH/DELETE tương ứng trên
  `/departments`, `/employees` và `/tasks`; `POST /performance/daily-reviews`,
  `PATCH /performance/daily-reviews/{employee_id}/{date}`.

Các route dự kiến từ Phase 6-7 đều có mặt. Phần thừa so với danh sách dự kiến là
resolve alert, logout, coordination plan/apply, threshold proposal và legacy
`performance/daily`, cùng các alias legacy của chúng; không loại bỏ vì đây là
compatibility/traffic đang tồn tại.

### Verification

- Full backend: `180 passed`.
- `ruff check .`: đạt.
- `mypy app`: đạt trên 114 source files.
- Test warning enforcement xác nhận log warning chỉ phát một lần cho cùng
  group/key trong cửa sổ 60 giây.

## [Phase 10/19] - Enforcement chọn lọc cho rate limit

### Phạm vi rollout

- Đã xác nhận Phase 9 có kết luận provenance rõ ràng: các file v1 scan là
  untracked, không có lịch sử Git/blame và được giữ nguyên, không xóa/đổi tên.
- Bật enforcement thật cho 5 nhóm: `login`, `ai_chat`, `upload_session`,
  `upload_completion`, `scan`.
- `rate_limit_shadow_mode=true` vẫn được giữ toàn cục; các nhóm không nằm trong
  rollout (`read_light`, `read_heavy`, `mutation`, `directive_action`,
  `websocket_handshake`) tiếp tục shadow.
- Thêm `RATE_LIMIT_ENFORCED_GROUPS` và property parse/cache trong `Settings`,
  cho phép rollback từng nhóm qua biến môi trường.

### Căn cứ quan sát

Không tìm thấy log/counter vận hành tập trung chứa dữ liệu shadow-mode của vài
ngày trước để định lượng traffic hợp lệ. Vì vậy rollout được ghi nhận là bật
theo cấu hình ngưỡng đã chốt và kiểm thử tự động, không suy diễn rằng đã có dữ
liệu production đủ dài.

### Enforcement và logging

- `rate_limit_group()` chỉ shadow khi `RATE_LIMIT_SHADOW_MODE=true` và group
  không nằm trong `RATE_LIMIT_ENFORCED_GROUPS`.
- Request bị chặn thật trả `429`, `Retry-After` và response contract hiện hữu.
- Log `warning` event `rate_limit_enforced` chỉ phát một lần mỗi `(group,
  key-fingerprint)` trong 60 giây. Log không chứa raw IP, token hoặc username;
  key chỉ được ghi dưới dạng fingerprint.
- Login vẫn dùng hai khóa đồng thời (IP+tài khoản và IP), AI SSE bị từ chối ở
  dependency trước khi handler stream được khởi chạy.

### Verification

- Test rate-limit/config tập trung: `34 passed`.
- Toàn bộ backend sau thay đổi: `pytest -q` đạt `175 passed`.
- `ruff check .` đạt.
- `mypy app` đạt trên 114 source files.
- Frontend caller/login/AI không thay đổi logic nghiệp vụ; các test/build
  frontend trước đó vẫn đạt. Prettier toàn frontend vẫn còn 5 file tồn đọng
  ngoài phạm vi Phase 10.

## [Phase 9/19] - Upload session và scan trên `/api/v1`

### Kết quả audit và nguồn gốc route scan

- `app/api/v1/alerts.py` và `app/api/v1/overload.py` là file untracked trong
  working tree; `git log --all -- app/api/v1` không có commit và không thể dùng
  `git blame` cho file chưa được Git theo dõi. Không xóa hoặc đổi tên các alias
  scan hiện hữu.
- PATCH `/api/attachments/upload-sessions/{id}` không nhận body; thực chất gọi
  `AttachmentUploadService.complete`, nên route v1 giữ nguyên hành vi này.
- `AttachmentUploadService` hiện có vòng đời `create → complete/cancel`; cờ
  `STORAGE_DIRECT_UPLOAD_ENABLED` vẫn được service kiểm tra, không bị hard-code
  trong router. Test dùng fake repository/storage và bật cờ trong `Settings` test.
- Hai download-url hiện có dùng service riêng theo ngữ cảnh, nhưng đều gọi
  chung `EvidenceStorage.signed_url`. Không tạo method generic mới và không tạo
  route generic vì code thật không có endpoint generic tương ứng.
- Alert scan có caller thật từ `AlertsPage`; overload scan hiện chưa có caller
  khác ngoài hàm API. Cả hai scan vẫn xử lý đồng bộ `200`; với quy mô seed hiện
  tại khoảng 16 nhân viên, chưa cần `202` và polling.

### Route mới

| Method | Endpoint | Nhóm rate limit |
| --- | --- | --- |
| POST | `/api/v1/upload-sessions` | `upload_session` |
| PATCH | `/api/v1/upload-sessions/{session_id}` | `upload_completion` |
| DELETE | `/api/v1/upload-sessions/{session_id}` | `upload_completion` |
| POST | `/api/v1/upload-sessions/{session_id}/completions` | `upload_completion` |
| GET | `/api/v1/performance/daily-reviews/{employee_id}/{date}/attachments/{attachment_id}/download-url` | `read_light` |
| GET | `/api/v1/department-evaluations/{evaluation_id}/attachments/{attachment_id}/download-url` | `read_light` |
| POST | `/api/v1/alert-scans` | `scan` |
| POST | `/api/v1/overload-scans` | `scan` |

Không tạo `GET /api/v1/upload-sessions/{id}` vì bản cũ không có route tương ứng.
Download-url được giữ lồng theo daily review/department evaluation để bảo toàn
kiểm tra quyền và storage key theo đúng ngữ cảnh hiện hữu, không mở rộng thành
API generic.

### Compatibility và TODO

- Các route `/api` cũ vẫn giữ nguyên. Alias `/api/v1/alerts/scan`,
  `/api/v1/overload/scans` và các route upload cũ trong compatibility router vẫn
  được giữ để tránh breaking change ngoài phạm vi.
- Caller frontend đã chuyển sang `/api/v1/alert-scans`,
  `/api/v1/overload-scans` và resource upload session v1.
- TODO Idempotency-Key cho `POST /api/v1/upload-sessions` được ghi ngay tại
  route; triển khai thuộc Giai đoạn 13, chưa thực hiện ở giai đoạn này.
- Không sửa `attachment_upload_service.py` hoặc `infrastructure/evidence_storage.py`;
  `mypy` riêng hai file này đạt.

### Verification

- Test upload/scan/download v1 và upload service: `11 passed`.
- Toàn bộ backend: `175 passed`.
- Frontend: `55 tests passed`, `npm run lint` và `npm run build` đạt.
- Ruff và mypy cho các module v1 mới: đạt.
- OpenAPI xác nhận có 8 route mới đúng path, không có GET session hoặc generic
  download-url.

## [Phase 8/19] - Resource action cho workflow chỉ thị và duyệt ngưỡng trên `/api/v1`

### State machine thực tế đã đối chiếu

| Collection | Trạng thái hiện tại | Hành động | Trạng thái mới | Payload/audit |
| --- | --- | --- | --- | --- |
| `department_task_directives` | `pending` | acknowledge | `acknowledged` | `action_note`, `commitment_date`, audit |
| `department_task_directives` | `acknowledged`, `needs_revision` | submit | `submitted` | `completion_note`, audit |
| `department_task_directives` | `submitted` | accept | `accepted` | `note`, audit |
| `department_task_directives` | `submitted` | revision request | `needs_revision` | `note` bắt buộc, audit |
| `department_alert_directives` | `pending` | acknowledge | `acknowledged` | `note`, `commitment_date`, audit |
| `department_alert_directives` | `acknowledged`, `needs_revision` | submit | `submitted` | `completion_note`, audit |
| `department_alert_directives` | `submitted` | accept | `accepted` | `note`, audit |
| `department_alert_directives` | `submitted` | revision request | `needs_revision` | `note` bắt buộc, audit |
| `coordination_directives` | `pending` | fulfill | `fulfilled` | `target_employee_id`, tạo plan/resolve alert/fulfill directive + audit |

Không có trạng thái `completed` và không có transition status-only trong code thật. Vì
mọi transition hiện tại đều kèm kiểm tra nghiệp vụ, payload hoặc audit, không tạo PATCH
tổng quát để bypass service. Do đó task/alert directives dùng sub-resource actions; coordination
chỉ có fulfillment action.

### Route mới

| Loại | Method | Endpoint | Nhóm rate limit |
| --- | --- | --- | --- |
| Task directive | POST | `/api/v1/tasks/department-directives/{directive_id}/acknowledgements` | `directive_action` |
| Task directive | POST | `/api/v1/tasks/department-directives/{directive_id}/submissions` | `directive_action` |
| Task directive | POST | `/api/v1/tasks/department-directives/{directive_id}/acceptances` | `directive_action` |
| Task directive | POST | `/api/v1/tasks/department-directives/{directive_id}/revision-requests` | `directive_action` |
| Alert directive | POST | `/api/v1/alerts/department-directives/{directive_id}/acknowledgements` | `directive_action` |
| Alert directive | POST | `/api/v1/alerts/department-directives/{directive_id}/submissions` | `directive_action` |
| Alert directive | POST | `/api/v1/alerts/department-directives/{directive_id}/acceptances` | `directive_action` |
| Alert directive | POST | `/api/v1/alerts/department-directives/{directive_id}/revision-requests` | `directive_action` |
| Coordination directive | POST | `/api/v1/coordination/directives/{directive_id}/fulfillments` | `directive_action` |
| Alert resolve | PATCH | `/api/v1/alerts/{alert_id}` | `mutation` |
| Threshold approval | POST | `/api/v1/threshold-configs/{config_id}/approvals` | `directive_action` |

- Alert resolve v1 chỉ nhận `status: "resolved"`, sau đó chuyển sang nguyên
  `EarlyWarningService.resolve`; service cũ vẫn chỉ nhận `resolution_note`.
- Threshold approval v1 tái sử dụng `ThresholdConfigService.approve`; endpoint tồn tại
  cho contract REST đầy đủ, không bổ sung UI.
- Các action v1 tái sử dụng factory/service hiện có, nên validation state, RBAC và audit
  log của route cũ được giữ nguyên.
- Các endpoint `/api` tương ứng (`/acknowledge`, `/submit`, `/accept`, `/request-revision`,
  `/resolve`, `/approve`) không bị sửa. Alias v1 cũ chỉ được giữ khi không xung đột path/
  operation; alias resolve v1 trùng path đã được thay bằng contract body mới.

### Kiểm tra track khắc phục song song

`git log` hiện chỉ có commit nền `489ed67` cho `coordination_service.py` và
`task_service.py`, không có commit track riêng để đối chiếu. Không thực hiện reset,
cherry-pick hoặc ghi đè hai service; các route mới chỉ gọi lại method hiện hữu.

### Verification

- Test Phase 8 và service liên quan: `28 passed`.
- `mypy app`: đạt.
- OpenAPI xác nhận đủ 11 route action/resource mới và không phát sinh duplicate operation ID.
- `ruff check .` cần chạy lại ở cổng nghiệm thu toàn bộ sau khi hoàn tất các lô.

## [Phase 7/19] - Migrate daily performance và weekly department evaluations sang resource v1

### Thay đổi

- Bổ sung resource-shaped API cho nghiệm thu hiệu suất hằng ngày:

  | Method | Endpoint |
  | --- | --- |
  | GET | `/api/v1/performance/daily-reviews/{employee_id}/{date}` |
  | POST | `/api/v1/performance/daily-reviews` |
  | PATCH | `/api/v1/performance/daily-reviews/{employee_id}/{date}` |

- Bổ sung resource-shaped API cho đánh giá phòng ban hằng tuần:

  | Method | Endpoint |
  | --- | --- |
  | GET | `/api/v1/department-evaluations/weekly-reviews/{department_id}/{week_start}` |
  | POST | `/api/v1/department-evaluations/weekly-evaluations` |
  | PATCH | `/api/v1/department-evaluations/{evaluation_id}` |

- PATCH daily review v1 yêu cầu `reason` cấp cao nhất cho toàn bộ lần cập nhật. Lý do này
  được truyền vào `PerformanceReviewService`, dùng làm fallback cho các task đổi điểm
  không có `items[*].change_reason`, và được lưu trong audit log. Field per-task cũ vẫn
  được giữ và được ưu tiên khi caller gửi riêng.
- POST v1 trả `201` và header `Location` trỏ tới resource tương ứng. Các route mới dùng
  lại factory/service hiện có và gắn rate-limit `read_light` hoặc `mutation` theo loại thao tác.
- Giữ nguyên RBAC hiện tại: Manager thực hiện daily review; Leadership thực hiện weekly
  department evaluation.
- Loại các route weekly-review cũ khỏi lớp alias `/api/v1` để tránh trùng resource route;
  route `/api/department-evaluations/weekly-review` và toàn bộ API `/api` cũ không bị sửa.
- Không tạo alias v1 `/weekly-review` dạng số ít. Alias đó chỉ cần khi đổi tên tại chỗ
  trên cùng API; kiến trúc hiện tại giữ API cũ song song với resource v1.

### Sai lệch so với tài liệu kế hoạch gốc

- Tài liệu gốc dự kiến các method `upsert_report` và `update_manager_review`, nhưng code
  thật dùng `get_review`, `save_review` và `update_review`; implementation tái sử dụng đúng
  tên method đang tồn tại.
- Code thật đã có `items[*].change_reason`, không có `reason` cấp cao nhất và chỉ bắt buộc
  lý do khi điểm của task thay đổi. Theo lựa chọn hướng 2, v1 bổ sung `reason` cấp operation;
  API `/api` cũ giữ nguyên semantics và payload.
- Legacy weekly review nhận `department_id` và `week_start` qua query string; v1 chuyển
  hai giá trị này vào path theo contract resource mới.

### Verification

- Test focused Phase 7 và các service liên quan: `18 passed`.
- `mypy app`: đạt.
- `ruff check app tests/test_api_v1_phase7.py tests/test_performance_review_service.py`: đạt.
- OpenAPI xác nhận đủ 6 resource endpoints v1, giữ các endpoint `/api` cũ và không còn
  alias `/api/v1/department-evaluations/weekly-review`.

## [Phase 6/19] - Migrate CRUD chính sang `/api/v1`

### Thay đổi

- Bổ sung đủ 9 endpoint CRUD v1 cho departments, employees và tasks:

  | Resource | POST | PATCH | DELETE |
  | --- | --- | --- | --- |
  | Departments | `/api/v1/departments` | `/api/v1/departments/{department_id}` | `/api/v1/departments/{department_id}` |
  | Employees | `/api/v1/employees` | `/api/v1/employees/{employee_id}` | `/api/v1/employees/{employee_id}` |
  | Tasks | `/api/v1/tasks` | `/api/v1/tasks/{task_id}` | `/api/v1/tasks/{task_id}` |

- POST thành công trả `Location` trỏ tới resource vừa tạo; response body và status code vẫn giữ nguyên contract cũ.
- Giữ nguyên RBAC: department CRUD chỉ Leadership; employee CRUD dùng scope backend hiện có; task CRUD chỉ Manager và tiếp tục gọi nguyên `TaskService.create/update/delete`, bao gồm tính lại `completed_at` khi đổi trạng thái.
- Các route CRUD v1 dùng rate-limit group `mutation`.
- Xác nhận `seed_key_1` trên Mongo live có `partialFilterExpression: { seed_key: { $exists: true } }` trước khi migrate task POST.
- Không cần vá `DuplicateKeyError`: `department_service`, `employee_service` và `task_service` đều đã map duplicate insert/update thành HTTP 409. Vì vậy `/api` cũ và `/api/v1` mới cùng giữ schema lỗi 409, không rơi thành 500.
- Xóa phòng ban có nhân viên tiếp tục trả HTTP 409 như `/api` cũ.
- Các POST deprecated dùng cho chuyển trạng thái `department-directives` vẫn giữ nguyên như compatibility action; không thuộc CRUD chính và không được thay đổi trong giai đoạn này.
- Không thêm `Idempotency-Key`; để dành cho Giai đoạn 13.

### Verification

- CRUD route v1 được kiểm tra OpenAPI không trùng với compatibility route cũ.
- Test Location và service reuse: đạt; test theo resource departments/employees/tasks đạt.
- Backend full suite và static gates được chạy sau khi hoàn tất migrate.

## [Phase 5/19] - Migrate API đọc sang `/api/v1`

### Thay đổi

- Mở rộng pattern walking skeleton cho các resource đọc lớn: employees, tasks, alerts và overload; giữ nguyên service/repository/factory dùng chung với `/api` cũ.
- Bổ sung GET detail cho departments và các GET detail đã tồn tại của employees/tasks; không tự tạo alert/overload detail vì API cũ không có GET tương ứng.
- Bổ sung `paginate_aggregate()` dùng một pipeline MongoDB `$facet` để lấy trang dữ liệu và `total` trong một round-trip. Employees, tasks, alerts và overload không còn dùng cách lấy toàn bộ collection rồi cắt trong Python ở v1.
- Chuẩn hóa query v1: `page`, `page_size`, `sort`, `status`, `department_id`, `from`, `to`; RBAC `get_department_scope()` vẫn được áp dụng trước tầng service và scope Manager luôn ghi đè department filter do client gửi.
- Cập nhật adapter frontend và smoke script để bóc `items` từ `PageResponse`, không làm thay đổi shape nội bộ mà các màn hình hiện tại đang sử dụng.
- Không có route `manager-evaluation*` trong `/api/v1`; `department-evaluations` là module đánh giá phòng ban hàng tuần độc lập và chưa được migrate thành resource mới trong lô này.

### Bảng route GET đã migrate

| API cũ | API v1 | Nhóm rate limit | Ghi chú |
| --- | --- | --- | --- |
| `GET /api/departments` | `GET /api/v1/departments` | `read_light` | `PageResponse`, Mongo `$facet` |
| `GET /api/departments/{department_id}` | `GET /api/v1/departments/{department_id}` | `read_light` | Trả object trực tiếp |
| `GET /api/employees` | `GET /api/v1/employees` | `read_light` | Filter phòng ban/trạng thái, Mongo `$facet` |
| `GET /api/employees/{employee_id}` | `GET /api/v1/employees/{employee_id}` | `read_light` | Trả object trực tiếp |
| `GET /api/tasks` | `GET /api/v1/tasks` | `read_heavy` | Filter employee/status/phòng ban/ngày/overdue, Mongo `$facet` |
| `GET /api/tasks/{task_id}` | `GET /api/v1/tasks/{task_id}` | `read_heavy` | Trả object trực tiếp |
| `GET /api/alerts` | `GET /api/v1/alerts` | `read_heavy` | Filter status/type/phòng ban/severity/ngày, Mongo `$facet` |
| `GET /api/overload` | `GET /api/v1/overload` | `read_heavy` | Mongo `$facet` |

### Các GET cố ý chưa migrate thành router đọc mới

Các path GET thật đã được grep nhưng giữ nguyên dưới dạng compatibility alias/module riêng trong giai đoạn này:

| Nhóm | GET chưa migrate thành router đọc mới |
| --- | --- |
| Hệ thống/xác thực | `/api/health`, `/api/auth/me` |
| Read-model cảnh báo/dashboard | `/api/alerts/department-summary`, `/api/dashboard/attention-summary` |
| Coordination | `/api/coordination/suggestions`, `/api/coordination/department-directives`, `/api/coordination/alerts/{alert_id}/directive-targets`, `/api/coordination/directives`, `/api/coordination/directives/{directive_id}/candidates` |
| Đánh giá phòng ban | `/api/department-evaluations/weekly-review`, `/api/department-evaluations`, `/api/department-evaluations/{evaluation_id}`, `/api/department-evaluations/{evaluation_id}/attachments/{attachment_id}/download-url` |
| Performance | `/api/performance/daily-review`, `/api/performance/daily-review/{employee_id}/{review_date}/attachments/{attachment_id}/download-url`, `/api/performance`, `/api/performance/analytics/employee/{employee_id}`, `/api/performance/analytics/department/{department_id}`, `/api/performance/analytics/company` |
| Task read-model | `/api/tasks/leadership-overview`, `/api/tasks/departments/{department_id}/portfolio`, `/api/tasks/department-directives` |
| Threshold | `/api/threshold-configs` |

Các path trên vẫn có alias tương ứng `/api/v1` nếu đã tồn tại từ các giai đoạn trước; giai đoạn này không đổi response shape và không coi đó là một resource list/detail mới.
- Không migrate `manager-evaluations`: grep trước khi code xác nhận module/route này không còn được include.
- `/api` cũ vẫn giữ nguyên response list và logic tương thích; các method `*_page` cũ dùng cho contract cũ không bị thay đổi. Các method `*_page_v1` dùng `$facet` riêng cho contract mới.

### Verification

- `pytest -q` từ thư mục `backend`: đạt sau khi cập nhật stub walking-skeleton và thêm test pipeline `$facet`.
- `mypy app`, `ruff check app`: đạt.
- `scripts/check_app.py`: OpenAPI có đủ path v1 mới, không trùng path cũ và không có `manager-evaluation`.
- Live smoke MongoDB với tối thiểu 50 bản ghi và kiểm tra profiler/query log vẫn cần chạy trong môi trường Docker đang hoạt động; đây là bước nghiệm thu runtime, không thay thế bằng test mock.

## [Phase 4] - Rate Limit Shadow Mode

### Thay đổi

- Bổ sung state `shadow_denied` trong `rate_limit_group()` và header `X-RateLimit-Shadow: true` khi request vượt quota nhưng vẫn được cho đi qua.
- Bổ sung structured log quan sát theo nhóm với ba trạng thái `allowed`, `shadow_denied`, `backend_error`; key chỉ ghi fingerprint SHA-256 rút gọn, không ghi token, IP hoặc username thô.
- Giữ nguyên nhánh blocking khi `RATE_LIMIT_SHADOW_MODE=false`, bao gồm `429` và `Retry-After`.
- Đây là bản vá thiếu sót phát sinh từ kiến trúc Rate Limit Depends của Giai đoạn 2.1; không phải tính năng nghiệp vụ mới.
- Lần đầu đặt `RATE_LIMIT_ENABLED=true` trong `Settings`, `.env` và `.env.example`; enforcement vẫn chưa bật vì `RATE_LIMIT_SHADOW_MODE=true`. Môi trường nào override biến này thủ công cần kiểm tra lại trước khi deploy.

### Verification

- Shadow mode: request vượt quota vẫn trả thành công, có header shadow và log `shadow_denied`.
- Blocking mode tạm thời: request vượt quota trả `429` và `Retry-After`; test xong cấu hình được trả lại shadow mode.
- Áp dụng nhất quán cho route `/api` cũ và `/api/v1/departments` vì cả hai đều khai báo `rate_limit_group("read_light")`.

## [Phase 3] - API v1 walking skeleton và lớp tương thích

### Thay đổi

- Thêm `backend/app/api/v1/` với root `/api/v1` và endpoint mẫu `GET /api/v1/departments`.
- Endpoint mẫu dùng chung `get_department_service()` và `get_department_scope()` với API hiện hữu, thêm `read_light` rate-limit dependency và trả `PageResponse`.
- Cập nhật adapter `departmentsApi.js` và smoke scripts để đọc `items` từ PageResponse, giữ các màn hình hiện tại tiếp tục nhận list nội bộ.
- Mở rộng `backend/app/core/pagination.py` bằng `ListQueryParams`, `DateRangeParams` và `PageResponse[T]`, đồng thời giữ nguyên API legacy `offset/limit`.
- Giữ các route `/api/v1` đã tồn tại ngoài collection departments như compatibility aliases để không làm hỏng frontend, smoke script và client hiện hành; chỉ thay đường vào GET collection departments.
- Không sửa `backend/app/api/departments.py`, không thay đổi service/repository nghiệp vụ và không thêm wrapper response đại trà.

### Giới hạn cần ghi nhớ

`GET /api/v1/departments` đang phân trang in-memory: service lấy toàn bộ danh sách rồi mới cắt trang. Cách này chỉ chấp nhận được vì departments có ít bản ghi và chỉ là walking skeleton; không được sao chép cho employees, tasks, alerts hoặc performance_metrics. Giai đoạn 5 phải phân trang thật bằng `skip/limit` ở tầng MongoDB.

### Verification

- Kiểm tra OpenAPI: `/api/v1/departments` là path riêng, không trùng với `/api/departments`.
- Kiểm tra `page >= 1`, `page_size` trong khoảng 1–100 và lỗi validation v1 dùng `V1ApiError`.
- Kiểm tra header rate-limit trên route mẫu và giữ response legacy `/api/departments` không đổi.

## [Infrastructure] - Hoàn tất migrate rate limit sang Depends tường minh

### Thay đổi

- `RateLimitMiddleware` không còn suy luận policy theo URL hoặc tự gọi limiter; middleware chỉ đọc `request.state.rate_limit_decision` sau `call_next()` và ghi các header `X-RateLimit-*`.
- `rate_limit_group("...")` là nơi enforcement duy nhất của HTTP route, lưu decision kể cả khi request được cho qua; shadow mode vẫn ghi nhận decision nhưng không chặn.
- Xóa hoàn toàn `RateLimitPolicy.rule_for(request)`; policy chỉ nhận group tường minh qua `rule_for_group(group)`.
- Migrate toàn bộ route nghiệp vụ trong `backend/app/api/*.py` theo group đã thống nhất. `/health`, `/docs` và `/openapi.json` không gắn rate limit dependency.
- WebSocket `/ws/realtime` kiểm tra thủ công trước xác thực token bằng key IP `rl:ip:{ip}:anonymous:websocket_handshake`; lần bị giới hạn đóng code `1013`.

### Phạm vi

- Đây là bản sửa kiến trúc theo thiết kế Giai đoạn 2, không thêm nghiệp vụ hoặc thay đổi API response thành công.

### Verification

- HTTP route allow vẫn trả `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` khi bật rate limit.
- WebSocket handshake: 10 lần đầu cùng IP không bị rate limit, lần thứ 11 đóng `1013`.
- `RATE_LIMIT_ENABLED=false` được giữ trong `.env` và `.env.example`; enforcement thật chưa bật.

## [Infrastructure] - Điều chỉnh rate limit theo contract canonical

### Thay đổi

- Chuẩn hóa kết quả limiter thành `RateLimitResult` với `allowed`, `remaining` và `reset_at: datetime`; giữ `RateLimitDecision` làm alias compatibility.
- Redis limiter chuyển sang Lua atomic approximate sliding-window counter theo bucket hiện tại và bucket trước; smoke Redis bổ sung kiểm tra đồng thời bằng `asyncio.gather`.
- Bổ sung các group canonical `read_light`, `read_heavy`, `mutation`, `directive_action`, `login`, `upload_session`, `upload_completion`, `ai_chat`, `scan`, `websocket_handshake` và `health` bypass.
- Bổ sung `rate_limit_group("...")` dependency để route tự khai báo policy.
- Chuẩn hóa key builder theo ba mẫu contract, bao gồm hai key song song cho login và trusted proxy với `TRUSTED_PROXY_IPS`.
- Bổ sung quota canonical trong `Settings` và `.env.example`, vẫn giữ tên biến legacy để chuyển đổi dần.

### Phạm vi chuyển đổi

- Toàn bộ route nghiệp vụ đã chuyển sang `Depends(rate_limit_group(...))`; middleware không còn compatibility enforcement theo URL.
- `/api` và `/api/v1`, service nghiệp vụ, RBAC và schema dữ liệu không thay đổi.

### Verification

- Backend pytest: `151 passed, 3 warnings`.
- `ruff check .`: đạt.
- `mypy app`: đạt.
- Redis smoke: đạt multi-instance atomicity, idempotency replay và 20 request đồng thời với quota 5 chỉ cho phép đúng 5 request.

## [Infrastructure] - Request ID và error contract phân nhánh API

### Audit trước khi sửa

| Hạng mục | Kết quả xác nhận | Xử lý |
| --- | --- | --- |
| `raise HTTPException` trong `backend/app` | Có 205 vị trí; `detail` đều là chuỗi/chuỗi nội suy, không có payload dict/list custom. | Giữ nguyên nguồn phát sinh lỗi; handler chuẩn hóa ở tầng HTTP. |
| Shape lỗi hiện tại | `backend/app/core/http_contract.py` đã có custom handler cho `HTTPException`, `StarletteHTTPException`, validation và lỗi 500. Vì vậy `/api` hiện dùng `ApiError`, không phải mặc định FastAPI `{"detail": ...}`. | Giữ nguyên `ApiError` cho `/api` và các path cũ; không đổi ngược hành vi đang chạy. |
| `datetime` trong `*Response` | Các model response hiện dùng `datetime`/`date`; Pydantic/FastAPI tự serialize ISO-8601. | Xác nhận, không sửa schema. |
| `id: str` trong `*Response` | Các response model dùng string cho ObjectId; service đã chuyển bằng `str(document.id)`/`str(...)`. | Xác nhận, không sửa schema. |
| Middleware hiện có | `RequestIdMiddleware` đã tồn tại và được gắn trong `main.py`; CORS, CSRF, rate limit và idempotency cũng đã truy cập request ID. | Gia cố vị trí middleware và mở rộng handler theo path. |
| Route `/api/v1` | Repo đã có route `/api/v1` thật, cùng test/smoke/client đang sử dụng. | Không xóa route để tránh phá contract hiện hành; error contract mới được áp dụng cho các route v1 đang tồn tại. |

### Thay đổi

- `RequestIdMiddleware` tiếp tục đọc `X-Request-ID` hợp lệ hoặc sinh UUID, lưu vào `request.state.request_id` và trả lại header trên mọi response; được đăng ký ngoài CORS để bao phủ cả preflight.
- Bổ sung `V1ApiError` với shape `{code, message, details: dict | null, request_id}`.
- Handler rẽ nhánh chính xác cho `/api/v1`: HTTP error, validation error và lỗi 500 dùng `V1ApiError`; `/api` giữ `ApiError` hiện hành.
- Bổ sung `V1_ERROR_RESPONSES` tái sử dụng cho 400/401/403/404/409/422/429/500 và component OpenAPI `V1ApiError`; response OpenAPI của `/api` vẫn tham chiếu `ApiError`.
- Không sửa các model response `datetime`/ObjectId vì audit xác nhận chúng đã đúng.

### Verification

- `tests/test_http_contract.py`: `7 passed`.
- Full backend pytest: `148 passed, 3 warnings`.
- Ruff, mypy và compileall: đạt.
- Đã kiểm tra riêng header Request-ID trên CORS preflight, schema v1, validation details dạng object và shape `/api` không đổi.

## [Phase 2] - Hoàn thiện Design System & Shared Layout

### Files created/modified

- `frontend/tailwind.config.js`, `frontend/src/index.css`
- `frontend/src/components/ui/`
- `frontend/src/components/layout/Header.jsx`, `frontend/src/components/layout/MainLayout.jsx`, `frontend/src/components/layout/Sidebar.jsx`
- `frontend/src/components/animations/`
- `frontend/src/pages/LoginPage.jsx`, `frontend/e2e/phase3-5.spec.js`
- `README.md`

### Logic & Luồng

- Mở rộng Design Token cho màu, typography, spacing, bo góc, shadow và focus state; vẫn giữ giao diện sáng WorkMind.
- Bổ sung bộ component UI dùng chung gồm Button, FormField, Card, Badge, StatusBadge và trạng thái tải/rỗng/lỗi.
- Sidebar có bản desktop và mobile drawer; menu vẫn lấy từ `getNavigationItems(role)`, tự đóng sau khi chọn route và không thay đổi RBAC.
- Header giữ logo WorkMind, bổ sung nút menu mobile và dùng style button dùng chung cho đăng xuất.
- Thêm `PageTransition`; `FadeIn`, `SlideIn` và `CounterNumber` xử lý `prefers-reduced-motion` để không gây cản trở người dùng nhạy cảm với chuyển động.
- Login chuyển sang component UI dùng chung; không thay đổi request API, session cookie, backend hoặc dữ liệu nghiệp vụ.

### Verification

- Vitest: `18 test files, 55 tests passed`.
- ESLint, Vite production build và kiểm tra navigation role: đạt.
- Playwright E2E đã bổ sung kịch bản menu mobile; live E2E chưa hoàn tất vì backend/frontend không sẵn sàng và test đầu tiên timeout sau 30 giây.
- Prettier đã chạy trên toàn bộ file thay đổi Phase 2; một số file giao diện cũ ngoài phạm vi vẫn còn cảnh báo format.

## [Feature] - API v1, error contract, deprecation và bảo vệ request ghi

### Files created/modified

- `backend/app/main.py`, `backend/app/core/http_contract.py`, `backend/app/core/api_deprecation.py`, `backend/app/core/config.py`, `backend/app/core/database.py`, `backend/app/realtime/change_stream_worker.py`
- `backend/app/infrastructure/rate_limit/`, `backend/app/infrastructure/idempotency.py`, `docker-compose.yml`, `.env.example`, `backend/requirements.txt`
- Tất cả router backend, `frontend/src/components/layout/navigation.js`, `frontend/src/features/auth/authApi.js`, `frontend/src/stores/authStore.js` và các `frontend/src/features/*/*Api.js`, `frontend/src/services/httpClient.js`
- `backend/tests/test_http_contract.py`, `backend/tests/test_config_security.py`, `backend/tests/test_pagination.py`, `backend/tests/test_rate_limit.py`, `backend/scripts/check_app.py`, `backend/scripts/smoke_realtime_cookie.py`, `backend/scripts/smoke_redis.py`, `README.md`

### Logic & Contract

- Cùng router/service/repository được mount dưới `/api` và `/api/v1`; frontend đã chuyển sang `/api/v1`, alias `/api` giữ tương thích.
- Thêm resource-style action routes cho resolve alert, approve threshold, overload scan và upload completion; frontend dùng route v1 mới, action path cũ được đánh dấu deprecated.
- Workflow coordination và task directives đã có sub-resource/PATCH routes v1; các API wrapper frontend không còn gọi flow điều phối cá nhân legacy.
- Các danh sách v1 chính đã có contract `offset`/`limit` và quota headers; alias `/api` không bị cắt payload để giữ tương thích.
- Các Repository của departments, employees, alerts, performance, tasks, overload, thresholds và coordination đã thêm `count/skip/limit` cho v1; các luồng legacy vẫn dùng truy vấn đầy đủ.
- Alias `/api` trả `Deprecation: true`, `Sunset` và `Link` tới successor `/api/v1`.
- OpenAPI cũng đánh dấu toàn bộ operation dưới `/api` là `deprecated`, trong khi operation `/api/v1` giữ là contract hiện hành.
- HTTP error thống nhất `{code, message, details, request_id}`; `X-Request-ID` được tạo/giữ xuyên request và OpenAPI mô tả `ApiError`.
- Mongo client bật timezone-aware UTC; response tiếp tục chuẩn hóa ObjectId qua schema hiện có.
- Tasks Change Stream tạo collection với pre-image option trước khi `collMod`, bảo đảm delete event vẫn có dữ liệu phòng ban để lọc WebSocket.
- Redis-backed rate limiter có policy/key abstraction, shadow mode, header quota và fail-closed cho login/AI/upload/scan; Redis service đã thêm vào Compose.
- `Idempotency-Key` áp dụng cho request ghi khi bật cờ: replay response đã hoàn tất, `409` khi payload khác hoặc request đang chạy, fail-closed khi store unavailable; replay luôn ghi `X-Request-ID` của request hiện tại.
- Claim idempotency được release atomically khi request trả 5xx, cho phép retry cùng key mà không phải chờ TTL.
- Redis rate-limit và idempotency clients được đóng trong FastAPI lifespan khi shutdown để không giữ connection pool qua reload/worker restart.
- Auth session store không còn chứa URL HTTP trực tiếp; `/auth/me` và `/auth/logout` đi qua `features/auth/authApi.js`, còn AI streaming giữ caller riêng do cần đọc SSE.

### Verification

- Backend `.venv`: `145 passed`, Ruff/isort/mypy đạt, compileall đạt, route/OpenAPI gate đạt.
- Contract, config-security, pagination, rate/idempotency test: `31 passed`, gồm identity ổn định theo role/user qua token refresh, anonymous partition theo IP, query-aware idempotency scope, request ID replay hiện tại, release sau 5xx, production chặn memory backend, quota/TTL dương và atomic Lua scripts của Redis idempotency adapter.
- Redis client `redis 5.3.1` đã được cài trong `backend/.venv`; `smoke_redis.py` live đạt atomic rate-limit và idempotency replay qua hai adapter độc lập.
- Full Vitest frontend: `15 test files, 50 tests passed`; ESLint và Vite production build đạt. `npm run format:check` còn báo 5 file frontend cũ không thuộc thay đổi lần này.
- `npm run format:check` còn báo 5 file frontend cũ không thuộc thay đổi lần này: `DirectiveSummaryCard.jsx`, `NotificationBell.jsx`, `LeadershipTasksOverview.jsx`, `LeadershipTasksOverview.test.jsx`, `DepartmentEvaluationsPage.jsx`.
- Live local MongoDB Replica Set: health, cookie/CSRF/logout, Bearer compatibility, Phase 3 RBAC scope, v1 pagination và Change Streams/WebSocket smoke đều đạt; Redis multi-instance đã chạy live và đạt.
- Cookie WebSocket smoke mới (`smoke_realtime_cookie.py`) đã xác nhận browser-style cookie session, Manager/Leadership scope và từ chối kết nối không có cookie.
- `smoke_redis.py` đã kiểm tra thành công Redis `localhost:6379`: multi-instance rate-limit atomicity và idempotency replay đều đạt.
- Live cookie auth smoke (`smoke_cookie_auth.py`) và cookie WebSocket/RBAC smoke (`smoke_realtime_cookie.py`) đều đạt.
- Backend tạm với `IDEMPOTENCY_ENABLED=true` đã xác nhận request ghi lỗi validation được replay (`Idempotency-Replayed: true`) và cùng key khác payload trả `409`, không tạo dữ liệu nghiệp vụ.
- Performance analytics smoke đã đạt với dữ liệu hiện tại; gate dùng tối thiểu 60 ngày và tối thiểu 5 nhân viên/phòng thay vì phụ thuộc đúng số lượng seed.
- Playwright E2E hiện hành: `10 passed`; cập nhật assertion theo màn hình nghiệm thu bằng chứng, đánh giá phòng ban theo tuần, menu phòng ban và các chart/filter hiện tại.
- Live smoke bổ sung: Phase 3 RBAC `pass`, tasks `Manager=23/Leadership=54`, performance analytics `pass` với dữ liệu hiện tại.
- `check_api_callers.py` xác nhận frontend không còn caller `/api` legacy và không có URL `/api/v1` ngoài các `*Api.js`/hạ tầng được phép; chỉ còn `smoke_auth.py` và phần ghi metric cũ trong `smoke_performance.py` nằm trong compatibility allowlist.
- `check_app.py` xác nhận mọi route nghiệp vụ dưới `/api` và `/api/v1` có dependency xác thực/RBAC; health và login/logout là các ngoại lệ public có chủ đích.
- `npm run check:navigation` xác nhận menu Manager/Leadership đúng role, mỗi role có 7 mục và Leadership có mục “Đánh giá quản lý”.

### Compatibility / Rollout

- `/api`, Bearer và WebSocket query token tiếp tục là compatibility path; chưa được phép xóa cho đến khi caller/script audit không còn phụ thuộc.
- Bật `RATE_LIMIT_ENABLED=true` ở shadow mode trước, theo dõi header và log, sau đó mới tắt shadow mode.
- Chỉ bật `IDEMPOTENCY_ENABLED=true` sau khi Redis sẵn sàng và các client ghi quan trọng đã truyền key ổn định.

## [Feature] - Giai đoạn 1 Auth & RBAC dùng HttpOnly cookie

### Files created/modified

- `backend/app/core/security.py`, `backend/app/core/csrf.py`, `backend/app/api/dependencies.py`, `backend/app/api/auth.py`, `backend/app/realtime/websocket.py`
- `backend/app/core/config.py`, `backend/app/models/user.py`, `backend/scripts/seed_demo_user.py`, `backend/scripts/smoke_cookie_auth.py`
- `frontend/src/stores/authStore.js`, `frontend/src/services/httpClient.js`, `frontend/src/services/csrf.js`, `frontend/src/hooks/useRealtimeUpdates.js`, `frontend/src/features/ai/aiApi.js`
- `README.md`, `.env.example`, `CHANGELOG.md` và test liên quan

### Logic & Luồng

- Login set access JWT vào HttpOnly cookie `hrms_access_token` và CSRF token vào cookie đọc được `hrms_csrf_token`.
- `/api/auth/me` đọc session từ cookie, đối chiếu role/phòng ban với MongoDB và tự bổ sung CSRF cookie khi cần; `/api/auth/logout` xóa cả hai cookie.
- Request mutation dùng cookie phải gửi `X-CSRF-Token`; Bearer-only client cũ được miễn CSRF.
- Bearer header và query token WebSocket vẫn là compatibility path có cờ `LEGACY_*`; frontend mới không lưu token và WebSocket browser không gắn token query.
- Manager vẫn bị giới hạn theo phòng ban ở backend; Leadership vẫn có scope toàn công ty.
- Seed Manager bắt buộc `--department-id` của phòng ban đang hoạt động, không còn sinh ObjectId ngẫu nhiên.

### Verification

- Backend: `113 passed`; Ruff đạt; compileall đạt; route/OpenAPI check đạt.
- Frontend: `48 passed`; ESLint đạt; Vite production build đạt.
- Live MongoDB/E2E chưa chạy trong lượt này vì chưa khởi động backend/MongoDB runtime; smoke cookie đã được bổ sung để chạy sau khi môi trường sẵn sàng.

### Phạm vi tác động

- Chỉ tác động Auth/RBAC, session client, AI streaming, realtime WebSocket và seed/smoke auth; chưa chuyển `/api` sang `/api/v1`, chưa thêm Redis rate limiting và chưa thay đổi schema nghiệp vụ.

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
# Giai đoạn 15/19 — Kiểm thử đa worker Rate Limiting & Idempotency-Key

- Thêm bộ kiểm thử tích hợp `backend/tests/test_multi_worker_integration.py`, khởi động Uvicorn với 4 worker bằng subprocess trên cổng tạm; test mặc định bị loại khỏi `pytest -q` và chỉ chạy khi đặt `RUN_MULTI_WORKER_TESTS=1` cùng marker `integration`.
- Kiểm tra quota `read_light` dùng Redis database 15 riêng: 40 request đồng thời với quota 3/phút phải cho đúng 3 request thành công và 37 request `429`, chứng minh quota là dùng chung giữa các worker.
- Kiểm tra `Idempotency-Key` qua HTTP trên `POST /api/v1/coordination/department-directives/{department_id}`: hai request JSON đồng thời không tạo quá một chỉ thị; request lặp sau khi hoàn tất replay cùng body và status. Dữ liệu kiểm thử được xóa trong `finally`. Upload session không được chọn làm target vì MinIO local hiện trả `NotImplemented` khi service lazy-configure `PutBucketCors`; đây là giới hạn môi trường được ghi nhận, không phải lỗi Redis.
- Kiểm thử dùng MongoDB database cô lập theo PID và Redis database 15; fixture seed dữ liệu nền trước khi khởi động Uvicorn và dọn toàn bộ dữ liệu sau test.
- Không bật `--workers` cho lệnh dev/production hiện tại và không thay đổi `main.py`.

## Phát hiện: Change Stream chạy lặp khi nhiều worker

`lifespan` hiện khởi động 7 Change Stream worker trong mỗi process. Khi chạy 4 worker, mỗi process có watcher riêng trên các collection `alerts`, `performance_metrics`, `tasks`, các directive, task execution reports và department evaluations. Vì vậy một thay đổi MongoDB được quan sát bởi tối đa 4 process; mỗi process lại publish vào `EventBus`/`ConnectionManager` cục bộ của nó. Đây là bằng chứng tĩnh từ code và cấu hình; lượt integration này không gắn một client WebSocket sau mutation để đếm frame lặp, nên chưa khẳng định được số frame thực tế mà một client nhận. Các handler side-effect nếu được đăng ký trong từng process vẫn có nguy cơ chạy lặp theo số worker. Đây là rủi ro kiến trúc cần một giai đoạn riêng (ví dụ tách một worker Change Stream được chỉ định), không sửa trong Giai đoạn 15.

## Giai đoạn 16/19 — Theo dõi sử dụng API `/api` cũ

### Audit

- Rà toàn bộ `frontend/src`: không tìm thấy caller nghiệp vụ nào còn gọi `/api` không có `/v1`. Các API wrapper hiện dùng `/api/v1`; `/api/auth` và `/api/health` là phạm vi loại trừ theo contract.
- Các endpoint deprecated vẫn giữ nguyên: `/api/coordination/alerts/{id}/direct`, `/api/coordination/alerts/{id}/directive-targets`, `/api/performance/daily` và `/api/overload/scan`.
- Dự án chưa có metrics tập trung; logging chuẩn của Python là cơ chế quan sát duy nhất được tái sử dụng.

### Thay đổi

- Thêm `LegacyApiUsageMiddleware` cạnh middleware tương thích API cũ. Middleware chỉ ghi JSON log mức `INFO` với `event`, `path`, `method`, `user_id` nếu dependency xác thực đã chạy, `user_agent`, `request_id` và thời gian UTC; không query DB/Redis, không chặn và không đổi response.
- Loại trừ chính xác `/api/v1/*`, `/api/auth*` và `/api/health*` khỏi log legacy.
- Thêm `scripts/report_legacy_api_usage.py` để lọc `--since`/`--until`, tổng hợp tần suất theo path và User-Agent. Ví dụ:
  `python scripts/report_legacy_api_usage.py --log-file app.log --since 2026-09-09T00:00:00+00:00`.
- Middleware được đăng ký trong `main.py`; `get_current_user` chỉ bổ sung `request.state.authenticated_user_id` sau khi xác thực thành công, vẫn tương thích các lời gọi trực tiếp cũ.

### Verification

- Test middleware xác nhận chỉ path legacy được log; v1/auth/health không bị ghi nhận.
- Test parser/report xác nhận lọc theo thời gian và nhóm path/User-Agent.
- Backend: `193 passed, 2 deselected`; `mypy app` đạt; `ruff check .` đạt.
- Chưa đo benchmark production đầy đủ; đường log chỉ thực hiện kiểm tra path, đọc state và một lần gọi logger, không có I/O ngoài logging handler.

### Khuyến nghị rollout

Giữ giám sát tối thiểu `1–2 tuần` trên môi trường vận hành thật trước khi quyết định ngừng API cũ. Nếu báo cáo còn path deprecated, phân loại tiếp theo User-Agent để phân biệt bundle trình duyệt cũ với script/client bên ngoài; không xóa route chỉ dựa trên grep frontend.
