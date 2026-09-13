# WorkMind

Hệ thống quản lý hiệu suất nhân viên và cảnh báo quá tải, gồm FastAPI + MongoDB Replica Set ở backend và React/Vite ở frontend.

## Chuẩn hóa frontend UI-only

Đợt chuẩn hóa giao diện hiện tại chỉ thay đổi JSX/class UI, component dùng chung,
test frontend và tài liệu. Không thay đổi backend, API contract, route, payload,
store/hook dữ liệu, RBAC hoặc luồng nghiệp vụ. Bộ UI dùng chung gồm Button,
Input, Select, Textarea, FormField, Badge, Card, Table, Dialog, Tooltip,
Skeleton, LoadingState, EmptyState, ErrorState và Toast.

Kiểm chứng gần nhất: Vitest `42 file / 141 test`, ESLint và production build
đạt; Playwright UI-only đạt `11/11` cho desktop/mobile, hai role, route dữ liệu
nền, redirect, fallback và keyboard. Smoke UI chặn request ghi dữ liệu, chỉ
mô phỏng response đọc và SSE AI, không gửi dữ liệu ra cloud.

Các thẻ gợi ý AI trên Tổng quan, Công việc và Cảnh báo có nút ẩn/hiện. Nội dung
đã nhận được lưu trong `sessionStorage` theo vai trò và phạm vi thẻ, nên chuyển
trang rồi quay lại không gửi lại request; thao tác Làm mới vẫn cho phép lấy dữ
liệu mới và cache được xoá sau khi áp dụng thành công.

Trợ lý AI được mount ở cấp ứng dụng nên giữ nguyên phiên, nội dung hội thoại và
conversation khi chuyển Page. Nút Đóng chỉ ẩn cửa sổ; mở lại vẫn giữ nguyên cuộc
trò chuyện hiện tại.
Danh sách route và Network boundary được ghi tại
`docs/review/ui-route-inventory.md`.

## Kiểm chứng luồng chỉ thị hiện tại

- Luồng đánh giá phòng ban theo tuần dùng đúng route v1 `GET
  /api/v1/department-evaluations/weekly-reviews/{department_id}/{week_start}`;
  mọi ngày được chọn trong tuần được chuẩn hóa về thứ Hai trước khi đọc hoặc lưu,
  nên ngày cuối tuần không còn gây lỗi 422 do không phải ngày bắt đầu kỳ.
- Lịch sử gần đây trên trang Hiệu suất của Quản lý tương thích với cả response hiệu suất v1
  dạng mảng và dạng phân trang; dữ liệu thật không còn bị bỏ qua khi API trả về `[...]`.
  Regression test và kiểm thử live UI đã xác nhận các bản ghi được hiển thị.
- Notification Belt có mục “Chỉ thị đang theo dõi” dùng chung cho Manager và Leadership;
  mục này tổng hợp chỉ thị cảnh báo, giao việc quá hạn và điều phối còn hoạt động, không
  đếm lại trạng thái `accepted`/`fulfilled`, đồng thời điều hướng về đúng Trung tâm chỉ thị.
- Các nhóm trên Notification Belt có nền riêng để dễ phân biệt: hổ phách cho cảnh báo,
  xanh dương cho chỉ thị và đỏ hồng cho công việc quá hạn.
- Tiến độ trên card giao việc của Quản lý được đồng bộ theo task mới nhất: khi đã tải đủ
  các task trong `task_ids`, UI tính lại số hoàn thành thay vì giữ snapshot progress cũ
  lúc chỉ thị mới được tiếp nhận; request gửi nghiệm thu vẫn được backend kiểm tra độc lập.
- Chỉ thị mới có thể chứa lại task sau khi chỉ thị trước đó đã `accepted`; repository
  không còn tạo unique index lịch sử `directed_task_once_unique`. Nếu database cũ còn
  index này, mở PowerShell tại thư mục `backend` và chạy
  `.\\.venv\\Scripts\\python.exe -m scripts.migrate_drop_directed_task_once_index`
  một lần rồi khởi động lại API.
- Danh mục công việc của Lãnh đạo phân biệt `has_active_directive` với lịch sử chỉ thị:
  task đã nghiệm thu (`accepted`) nhưng mở lại vẫn nằm trong bộ lọc “Chưa ra chỉ thị”;
  task còn đang xử lý (`pending`, `acknowledged`, `submitted`, `needs_revision`) vẫn bị
  loại khỏi nhóm có thể phát hành chỉ thị mới.
- Regression đã kiểm tra cả hiển thị lịch sử và khả năng chọn lại task đã nghiệm thu:
  backend `backend\\.venv\\Scripts\\python.exe -m pytest tests/test_task_service.py -q`
  đạt 19 passed; frontend `npm test -- --run src/features/tasks/LeadershipTasksOverview.test.jsx`
  đạt 4 passed.
- Frontend dùng route v1 chuẩn cho hai luồng giao việc quá hạn và yêu cầu xử lý cảnh báo:
  Manager gửi `POST` tới các sub-resource số nhiều; các request mutation vẫn truyền
  `Idempotency-Key`.
- MongoDB được chạy với Replica Set `rs0`. Các bước ghi phương án điều phối, audit, xử lý
  cảnh báo và hoàn tất chỉ thị được commit trong một transaction; lỗi giữa bước sẽ rollback.
- Trạng thái `needs_revision` được hiển thị bằng màu cảnh báo và nhãn “Xử lý lại”, không bị
  hiểu nhầm là trạng thái đã nghiệm thu.
- Kiểm thử hồi quy: `backend\.venv\Scripts\python.exe -m pytest tests/test_api_v1_phase8.py tests/test_coordination_service.py tests/test_task_service.py -q`;
  frontend chạy các test route/state chỉ thị bằng Vitest.
- Flow cá nhân cũ `POST /api/coordination/alerts/{alert_id}/direct` và endpoint chọn đích
  `GET /api/coordination/alerts/{alert_id}/directive-targets` đã được gỡ khỏi backend,
  gồm cả alias tương thích `/api/v1`. Luồng đang dùng là chỉ thị cấp phòng ban và điều phối
  `coordination_directives` đã tồn tại; không tạo bản ghi điều phối cá nhân mới.
- Index legacy `coordination_directives.alert_id_1` đã được drop bằng migration
  `backend/scripts/migrate_drop_legacy_coordination_index.py`; migration không sửa document.
- Quy tắc “đã có chỉ thị” chỉ áp dụng cho chỉ thị đang xử lý
  (`pending`, `acknowledged`, `submitted`, `needs_revision`). Chỉ thị `accepted` vẫn được
  hiển thị như lịch sử nhưng không chặn việc quá hạn đã mở lại khỏi nhóm cần ra chỉ thị mới.

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
- `AUTH_COOKIE_SECURE`: đặt `true` khi chạy HTTPS; local mặc định `false`.
- `AUTH_COOKIE_SAMESITE`, `AUTH_COOKIE_DOMAIN`, `AUTH_COOKIE_MAX_AGE`: chính sách cookie phiên đăng nhập.
- `CSRF_ENABLED`: bật bảo vệ double-submit CSRF cho request thay đổi dữ liệu dùng cookie.
- `LEGACY_BEARER_ENABLED`, `LEGACY_WS_QUERY_TOKEN_ENABLED`: tạm giữ client Bearer/query-token cũ trong giai đoạn chuyển đổi; sẽ tắt cùng một lần sau khi di chuyển toàn bộ client.
- `LEGACY_API_SUNSET`: thời điểm dự kiến ngừng alias `/api`; route `/api/v1` là contract mới. Alias cũ vẫn hoạt động và trả `Deprecation`, `Sunset`, `Link`.
- `REDIS_URL`, `RATE_LIMIT_*`, `TRUSTED_PROXY_IPS`: cấu hình Redis-backed rate limiting. `RATE_LIMIT_ENABLED=true` và `RATE_LIMIT_SHADOW_MODE=true`; các group nằm trong `RATE_LIMIT_ENFORCED_GROUPS` (hiện gồm `login`, `ai_chat`, upload, scan, `mutation`, `read_light`) bị chặn thật khi vượt quota, còn `read_heavy` và các group ngoài danh sách chỉ ghi nhận shadow trong đợt phân loại lại. Các quota canonical gồm `RATE_LIMIT_DEFAULT`, `RATE_LIMIT_OPERATIONAL`, `RATE_LIMIT_READ_HEAVY`, `RATE_LIMIT_MUTATION`, `RATE_LIMIT_DIRECTIVE`, `RATE_LIMIT_LOGIN`, `RATE_LIMIT_UPLOAD_SESSION`, `RATE_LIMIT_UPLOAD_COMPLETION`, `RATE_LIMIT_AI_CHAT`, `RATE_LIMIT_SCAN` và `RATE_LIMIT_WS_HANDSHAKE`; group không cấu hình riêng sẽ fallback về `RATE_LIMIT_DEFAULT`.
- `IDEMPOTENCY_ENABLED`, `IDEMPOTENCY_TTL_SECONDS`: bật lưu/replay response cho các request ghi có `Idempotency-Key` ở nhóm chỉ thị, nghiệm thu và upload session; hiện mặc định bật và yêu cầu Redis sẵn sàng. Header là tùy chọn để tránh breaking traffic cũ; request không có header được xử lý như trước, còn request có header vẫn được claim/replay.
- `AI_API_KEY`: khóa dùng cho các provider Groq/OpenRouter/Gemini hiện có; để trống thì Trợ lý AI trả thông báo an toàn bằng tiếng Việt.
- `AI_PROVIDER`, `AI_FALLBACK_PROVIDER`, `AI_MODEL`: provider chính, provider dự phòng và model tương ứng.
- `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`: thông tin backend dùng để gọi Cloudflare Workers AI khi `AI_PROVIDER=cloudflare`; không đưa các giá trị này xuống frontend.
- `AI_TIMEOUT_SECONDS`, `AI_CONNECT_TIMEOUT_SECONDS`, `AI_FIRST_TOKEN_TIMEOUT_SECONDS`, `AI_IDLE_TIMEOUT_SECONDS`, `AI_TOTAL_TIMEOUT_SECONDS`: timeout kết nối, chờ token đầu tiên, khoảng nghỉ giữa các chunk và deadline tổng; proposal/chat hết deadline sẽ trả fallback an toàn.
- `AI_MAX_COMPLETION_TOKENS`, `AI_TOOL_MAX_COMPLETION_TOKENS`, `AI_SUMMARY_MAX_COMPLETION_TOKENS`: giới hạn output lần lượt cho chat, bộ chọn Data Tool và bản tóm tắt Dashboard. Tool planner mặc định chỉ dùng 256 token vì chỉ cần trả tên tool và tham số; chat vẫn có ngân sách riêng 4096 để dành đủ cho model có reasoning. `AI_SUMMARY_CONTEXT_MAX_CHARS` giới hạn context tổng hợp gửi cho Dashboard.
- `AI_ENABLE_THINKING`: mặc định `true` cho chat Cloudflare; đặt `false` để gửi `chat_template_kwargs.enable_thinking=false` khi cần so sánh. Summary và JSON mode luôn tắt thinking để tránh tiêu hết ngân sách trước khi tạo nội dung.
- `AI_DEBUG_STREAM`: mặc định `false`; chỉ bật tạm thời để ghi raw SSE chunk ở mức DEBUG, vì chunk có thể chứa dữ liệu nhân sự trong môi trường phát triển.
- `AI_FALLBACK_MODEL`: model riêng cho provider dự phòng nếu model chính không tương thích. `AI_RETRY_ATTEMPTS` và `AI_RETRY_BACKOFF_SECONDS` giới hạn retry lỗi transient.
- `AI_PROPOSAL_CACHE_TTL_SECONDS`, `AI_PROPOSAL_CACHE_MAX_ENTRIES`: cache proposal hợp lệ theo snapshot alert/candidates; dùng Redis khi có, fallback in-memory khi Redis lỗi.
- `AI_SUMMARY_CACHE_TTL_SECONDS`, `AI_SUMMARY_CACHE_MAX_ENTRIES`: cache bản tóm tắt Dashboard theo user/phạm vi/ngày và coalescing các request đồng thời; fallback không được cache.
- `AI_RAG_ENABLED`, `AI_EMBEDDING_MODEL`, `AI_VECTOR_INDEX_NAME`, `AI_RAG_TOP_K`: bật
  kho tri thức tùy chọn, model embedding Cloudflare, tên vector index Atlas và số
  đoạn tài liệu tối đa đưa vào prompt. Chỉ bật sau khi đã tạo collection/index và
  quy trình nạp tài liệu được kiểm soát.
- `AI_RAG_LOCAL_FALLBACK_ENABLED`: chỉ bật trong development khi chưa có Atlas;
  hệ thống tính cosine trên tối đa 2.000 chunk sau khi đã lọc scope. Production
  nên để `false` và dùng Atlas `$vectorSearch`.
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

Redis được bật cùng Docker Compose tại `redis://localhost:6379/0` và dùng volume `hrms_redis_data`. Redis là backend dùng chung cho rate limiting và idempotency khi các cờ tương ứng được bật.
Khi backend shutdown/reload, các Redis connection pool được đóng trong FastAPI lifespan.

### AI orchestration, RAG và governance

- Chat dữ liệu dùng AI Data Tools theo luồng: planner chọn một tool chỉ-đọc → registry
  kiểm tra Pydantic/role/scope → repository hiện có đọc MongoDB → model chỉ diễn giải
  kết quả đã rút gọn. Các tool hiện có là hiệu suất phòng ban/nhân viên, cảnh báo mở,
  nhân viên quá tải, ứng viên điều phối, đánh giá tuần phòng ban và công việc quá hạn.
  Manager bị giới hạn ở phòng ban của mình; Leadership dùng được dữ liệu tổng hợp toàn
  công ty. Nếu tool thất bại hoặc không có dữ liệu, hệ thống không fallback sang câu trả
  lời có thể bịa số liệu mà trả thông báo an toàn.
- Với câu hỏi tiếng Việt có ý định rõ như “hiệu suất trong phòng tôi 7 ngày gần đây” hoặc
  “cảnh báo hôm nay”, nếu model không phát sinh `tool_calls`, backend dùng tuyến ánh xạ
  cố định có giới hạn để gọi tool trước khi hỏi model; mọi ngày tháng do model gửi lên
  đều được backend loại bỏ hoặc thay bằng khoảng thời gian người dùng thực sự nêu, tối đa
  90 ngày. Nếu planner chọn sai tool, không chọn được tool hoặc không có dữ liệu, backend
  thử lại một lần bằng tuyến xác định rồi mới trả thông báo an toàn; mọi kiểm tra quyền và
  truy vấn vẫn nằm ở backend.
- Context của follow-up chỉ được dùng lại sau khi đã lưu qua validation; ngày tương lai,
  khoảng quá dài, khoảng đảo chiều hoặc argument lỗi sẽ không tự sửa âm thầm mà yêu cầu
  người dùng nêu lại kỳ dữ liệu. Context cũng được đọc lại theo đúng user và scope phòng ban.
- Nếu người dùng nêu một phòng ban cụ thể, tên đó được truyền vào tool để backend kiểm tra
  đúng scope; route không được âm thầm đổi thành phòng của Manager.
- `POST /api/v1/ai/tool-preview` dùng chung nhóm rate limit `ai_chat`, chỉ cho Manager
  trong scope phòng ban và hiện chỉ thực thi tool đọc candidate. Các thao tác resolve
  cảnh báo/áp dụng điều phối vẫn phải đi qua API nghiệp vụ và thao tác xác nhận của người dùng.
- RAG không nhận toàn bộ MongoDB: chỉ các chunk chính sách đã được nạp và lọc theo scope
  mới được dùng làm context. Không bật `AI_RAG_ENABLED` nếu chưa có vector index phù hợp.
- Audit AI nằm ở collection riêng `ai_audit_logs`, phục vụ truy vết mà không lưu dữ liệu
  prompt/output đầy đủ.
- `GET /api/v1/health` trả fingerprint vận hành an toàn gồm provider/model, trạng thái
  cấu hình provider chính/dự phòng và thời điểm process khởi động; không trả credentials.
- Frontend dùng `VITE_DEV_API_ORIGIN` cho proxy development/preview. Production nên để
  reverse proxy định tuyến `/api` tới đúng một backend chuẩn, tránh chạy song song backend
  cũ ở cổng khác.

### Lộ trình Leadership AI — trạng thái hiện tại

Leadership AI sẽ dùng cùng `AiProviderFactory`/Cloudflare Workers AI và cùng cơ chế
human-in-the-loop của Manager, nhưng context phải ở cấp toàn công ty/phòng ban. AI chỉ
được đọc dữ liệu tổng hợp, phân tích và tạo dự thảo; không tự phát hành chỉ thị, điều phối,
thay đổi ngưỡng hay ghi dữ liệu vào MongoDB.

Rà soát hiện trạng đã xác nhận:

- [x] `get_department_performance` có thể đọc dữ liệu tổng hợp toàn công ty khi scope của
  Leadership là `None`.
- [x] `get_department_weekly_evaluation` đọc đúng collection
  `department_weekly_evaluations` và các điểm tổng hợp do
  `DepartmentEvaluationService`/`DepartmentEvaluationRepository` xây dựng.
- [x] Backend đã có kiểm tra role/scope trong registry và orchestrator; Manager vẫn nhận
  scope phòng ban, Leadership nhận scope toàn công ty.
- [x] Đã tạo contract strict `LeadershipAiContext` cùng các model tổng hợp phòng ban, rủi ro,
  công việc quá hạn và đánh giá Quản lý; builder yêu cầu đúng `role=leadership` và
  `scope=company`, đồng thời từ chối field ngoài contract.
- [x] Đã đăng ký 6 Data Tools chỉ-đọc dành riêng cho Leadership: tổng hợp hiệu suất công ty,
  rủi ro phòng ban, đánh giá Quản lý từ nguồn đánh giá tuần hiện hành, quá hạn theo phòng ban
  và ứng viên điều phối liên phòng ban; có tool so sánh phòng ban riêng.
- [x] Tuyến định tuyến deterministic của Leadership ưu tiên các tool tổng hợp này theo câu hỏi;
  phạm vi phòng ban cụ thể vẫn được backend kiểm tra, không lấy dữ liệu thay thế âm thầm.
- [x] Các tool có dữ liệu cá nhân/chi tiết (`get_employee_performance`, cảnh báo chi tiết,
  quá tải và quá hạn theo người phụ trách) chỉ còn được đăng ký cho Manager; Leadership
  không thể gọi nhầm chúng qua tool planner.
- [x] Có `AiLeadershipContextService` ghép các nguồn tổng hợp thành context strict; lỗi một
  nguồn được ghi nhận ở phần giới hạn và không làm lộ dữ liệu chi tiết.
- [x] Có `POST /api/v1/ai/leadership-proposal` dùng chung `ai_chat`; Manager nhận `403`,
  Leadership chỉ nhận bản nháp JSON đã validate và lọc mã phòng ban thật, cặp phòng ban điều phối
  thật và ngưỡng hợp lệ.
- [x] Dashboard Leadership có thẻ đề xuất: cho sửa bộ lọc cảnh báo, mức độ và ghi chú;
  popup xác nhận rồi gọi trực tiếp API phát hành chỉ thị hiện có với Idempotency-Key.
- [x] Dashboard Leadership có tổng quan rủi ro và so sánh điểm tổng hợp theo phòng ban; đề xuất
  điều phối liên phòng ban hiển thị điểm phù hợp do backend tính và không có nút áp dụng tự động.
- [x] Bổ sung chính sách chatbot: câu hỏi xin chi tiết nhân viên được trả lời theo chính sách
  bảo vệ dữ liệu, không bị định tuyến sang tool chi tiết của Manager.
- [x] Chatbot Leadership có fallback cục bộ cho so sánh phòng ban, đánh giá Quản lý, rủi ro,
  công việc quá hạn và điều phối liên phòng ban; khi AI không diễn giải được, hệ thống vẫn
  trả Kết luận, Bằng chứng, Kỳ dữ liệu và Gợi ý từ dữ liệu đã kiểm tra quyền.
- [x] Khi hỏi về công việc quá hạn, Leadership nhận được tổng số toàn công ty, số liệu theo
  từng phòng ban và số việc chưa gửi chỉ thị; danh mục công việc hỗ trợ thêm bộ lọc
  `focus=not_directed` đúng với luồng phát hành chỉ thị.
- [x] Dashboard, chuông thông báo và danh sách công việc Leadership dùng cùng một định nghĩa
  công việc quá hạn: mọi việc chưa hoàn thành có hạn trước ngày nghiệp vụ hiện tại đều được
  tính, kể cả việc đã nằm trong chỉ thị. `focus=not_directed` chỉ dùng khi cần tìm phần việc
  chưa gửi chỉ thị, không dùng để loại khỏi số liệu tổng.
- [x] Danh sách công việc frontend tự tải hết các trang v1 trước khi đếm, tránh giới hạn
  ngầm ở 100 công việc; Dashboard hiển thị cả tổng số việc quá hạn và số phòng ban bị ảnh hưởng.
- [x] Trung tâm chỉ thị của Manager mặc định giữ lại cả chỉ thị `đang thực hiện` sau khi tiếp
  nhận, có bộ lọc riêng theo trạng thái và không chỉ tính số lượng rồi ẩn bản ghi.
- [x] Các trang Công việc/Cảnh báo dùng tiến độ backend của đúng tập task/cảnh báo trong chỉ thị;
  trang Công việc không trộn các task ngoài chỉ thị vào phần tiến độ.
- [x] Danh mục công việc của Leadership chỉ gắn “đã ra chỉ thị” khi `task_id` thực sự nằm
  trong `department_task_directives.task_ids`; nhãn hiển thị tiếp tục phân biệt chờ tiếp nhận,
  đang thực hiện, chờ nghiệm thu, đã nghiệm thu và cần xử lý lại.
- [x] Trung tâm chỉ thị Leadership mặc định hiển thị toàn bộ trạng thái, bao gồm chỉ thị
  `pending` đang chờ Manager tiếp nhận; bộ lọc “chờ nghiệm thu” vẫn dùng riêng khi cần duyệt.
- [x] Đã kiểm tra read-only MongoDB để đối chiếu hai chiều Leadership/Manager theo
  `target_department_id`, `target_manager_id`, `task_ids` và `alert_ids`; không phát hiện
  liên kết thiếu, lệch phòng ban hoặc lệch người quản lý.
- [ ] Tiến độ lịch sử tại thời điểm nghiệm thu chưa được lưu snapshot; các thay đổi task sau
  nghiệm thu có thể làm tiến độ hiện tại khác 100% dù chỉ thị vẫn ở trạng thái `accepted`.
- [x] Kiểm thử biên live: kỳ lịch sử không có dữ liệu trả `200` kèm thông báo “đã truy cập
  nhưng chưa có dữ liệu”; yêu cầu chi tiết từng nhân viên trả `200` kèm chính sách phạm vi.
- [x] Smoke live trước đó với dữ liệu hiện tại: Leadership có 3 phòng ban tổng hợp, proposal
  có action điều phối thật, chat có nội dung; Manager gọi endpoint Leadership nhận `403`.
- [x] Bổ sung route v1 `GET /api/v1/tasks/leadership-overview`; các khoảng `7d`, `30d`, `90d`
  được xử lý bởi `TaskService` dùng chung, tránh rơi nhầm vào route chi tiết `/{task_id}` và
  trả `422` cho yêu cầu tổng quan của Leadership.
- [x] Bổ sung đủ luồng công việc Lãnh đạo ở v1: danh mục phòng ban
  `GET /api/v1/tasks/departments/{department_id}/portfolio` để đọc nhóm việc quá hạn và
  `POST /api/v1/tasks/department-directives/{department_id}` để phát hành chỉ thị; cả hai
  dùng lại service nghiệp vụ, RBAC, rate limit và cơ chế chống gửi lặp hiện có.
- [ ] Chưa có API nghiệp vụ hiện hành để Leadership áp dụng trực tiếp đề xuất điều phối liên
  phòng ban; bản nháp chỉ hiển thị để xem xét an toàn.
- [ ] Chưa có model/service riêng cho `manager_evaluations`; hiện nguồn đánh giá đã có là
  `department_weekly_evaluations`.

Phần còn lại trước live acceptance là nghiệm thu dữ liệu thật và quyết định có xây API nghiệp vụ
cho điều phối liên phòng ban hay không. Hiện bản nháp điều phối chỉ cung cấp căn cứ cho Leadership;
mọi thao tác đang hỗ trợ đều phải được xác nhận thủ công qua API nghiệp vụ hiện hành.

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

### Checklist GĐ1 — Auth & RBAC

- [x] Backend xác thực bằng HttpOnly cookie; `/api/auth/me` xác nhận session từ MongoDB.
- [x] Bearer header và token query WebSocket vẫn hoạt động tạm thời để tương thích client cũ; cả hai đã được ghi nhận là deprecated.
- [x] Manager nhận scope phòng ban từ tài khoản backend; Leadership nhận scope toàn công ty.
- [x] Cookie mutation có CSRF double-submit; CORS giữ credentials và origin cụ thể.
- [x] Cấu hình từ chối `CORS_ORIGINS=*` khi dùng credentials và bắt buộc `AUTH_COOKIE_SECURE=true` trong production.
- [x] Frontend không lưu access token trong `localStorage`, tự khôi phục session qua `/api/auth/me`.
- [x] `seed_demo_user.py` không còn tạo phòng ban ObjectId ngẫu nhiên cho Manager.

Kiểm tra nhanh cookie session:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\smoke_cookie_auth.py --username demo.manager --password DemoPassword123!
```

Trong giai đoạn tương thích, `backend\scripts\smoke_auth.py` và các smoke script Bearer cũ vẫn được giữ nguyên. Không tắt các cờ `LEGACY_*` cho đến khi hoàn tất lần chuyển đổi client được ghi nhận riêng.

### Checklist GĐ2 — Design System & Shared Layout

- [x] Chuẩn hóa token Tailwind cho màu, typography, khoảng cách, bo góc, bóng và focus.
- [x] Bổ sung component dùng chung `Button`, `FormField`, `Card`, `Badge`, `StatusBadge` và các trạng thái tải/rỗng/lỗi.
- [x] Giữ `MainLayout` làm shell duy nhất; Sidebar lọc menu theo role backend.
- [x] Bổ sung drawer điều hướng mobile, đóng sau khi chọn route và giữ logo WorkMind trong Header.
- [x] `FadeIn`, `SlideIn`, `CounterNumber` và `PageTransition` tôn trọng `prefers-reduced-motion`.
- [x] Login dùng component UI dùng chung, giữ nguyên API/session/RBAC và nội dung tiếng Việt.

### Checklist GĐ5/19 — GET đọc trên `/api/v1`

- [x] Migrate `departments`, `employees`, `tasks`, `alerts` và `overload` theo walking skeleton; giữ factory/service/repository dùng chung với `/api` cũ.
- [x] Bổ sung GET detail cho departments, employees và tasks; không tự thêm alert/overload detail khi API cũ không có GET detail.
- [x] Bổ sung `paginate_aggregate()` dùng `$facet` để lấy `items` và `total` trong một round-trip MongoDB.
- [x] V1 dùng `PageResponse` cho GET list; GET detail trả object trực tiếp, không thêm wrapper `{data: ...}`.
- [x] Chuẩn hóa filter `status`, `department_id`, `from`, `to`, `sort`; scope Manager từ backend luôn thắng filter phòng ban do client gửi.
- [x] Frontend API adapter và smoke script đã bóc `items` để các màn hình hiện tại tiếp tục nhận mảng dữ liệu.
- [x] Không có route `manager-evaluation*`; `department-evaluations` là đánh giá phòng ban hàng tuần, khác module cũ đã gỡ.

#### Bảng chuyển route đọc

| Route cũ | Route v1 | Trạng thái |
| --- | --- | --- |
| `GET /api/departments` và `/{id}` | `GET /api/v1/departments` và `/{id}` | Đã chuyển |
| `GET /api/employees` và `/{id}` | `GET /api/v1/employees` và `/{id}` | Đã chuyển |
| `GET /api/tasks` và `/{id}` | `GET /api/v1/tasks` và `/{id}` | Đã chuyển |
| `GET /api/alerts` | `GET /api/v1/alerts` | Đã chuyển; không có detail cũ |
| `GET /api/overload` | `GET /api/v1/overload` | Đã chuyển; không có detail cũ |
| Dashboard, coordination, performance, department evaluations, thresholds, task/alert read-model | Compatibility alias `/api/v1` | Chưa mở rộng thành router v1 riêng |

Lưu ý: phân trang v1 của departments trước đây là in-memory walking skeleton; trong Giai đoạn 5 đã được chuyển sang `$facet` cùng các collection lớn. Đối với employees, tasks, alerts, overload và các collection hiệu suất trong giai đoạn sau, không được quay lại cách tải toàn bộ collection vào RAM rồi cắt danh sách.

### Checklist Dashboard hiệu suất Lãnh đạo — Đợt A

- [x] Company analytics chỉ được tải một lần theo mỗi khoảng ngày từ
  `PerformanceDashboard`, rồi truyền cùng dữ liệu sang `LeadershipDepartmentInsightCard`; không còn
  request không có khoảng ngày từ `DashboardPage`.
- [x] So sánh nhân viên/phòng ban loại riêng dữ liệu `null`/`undefined` và hiển thị số lượng chưa có
  dữ liệu; điểm thật bằng `0` vẫn được giữ trên biểu đồ.
- [x] Overload v1 hỗ trợ lọc `from`/`to` trước khi phân trang MongoDB. Frontend truyền khoảng bao trùm
  kỳ trước và kỳ hiện tại, đồng thời tải tiếp các trang sau `page_size=100`; alerts dùng cùng cơ chế lọc
  ngày và tải hết trang.
- [x] Kiểm chứng: `backend\\.venv\\Scripts\\python.exe -m pytest tests/test_overload_v1.py tests/test_alerts_v1.py tests/test_overload_detector.py tests/test_alert_service.py tests/test_performance_service.py` — 16 passed;
  `npm run test -- --run src/pages/DashboardPage.test.jsx src/features/performance/PerformanceDashboard.test.jsx src/features/overload/overloadApi.test.js src/features/alerts/alertsApi.test.js src/features/performance/performanceApi.test.js` — 12 passed;
  Ruff, ESLint, Prettier và `git diff --check` đều đạt.

### Checklist Dashboard hiệu quả xử lý chỉ thị theo Quản lý — Đợt B

- [x] Xác minh ba endpoint danh sách chỉ thị v1 dùng payload mảng để giữ tương thích, nhưng vẫn phân trang ẩn bằng `offset`/`limit`; các adapter `listDepartmentTaskDirectives`, `listDepartmentDirectives` và `listDirectives` đã tải tiếp mọi trang trước khi tổng hợp SLA.
- [x] `CoordinationDirectiveResponse` bổ sung `fulfilled_by_name`; service tra tên người dùng khi chỉ thị đã hoàn tất và giữ `null` khi còn chờ xử lý. Không thay đổi route hoặc vòng đời hiện có.
- [x] SLA thuần logic tách khỏi React: nhóm chỉ thị task/alert theo quản lý, tính số đang mở, thời gian tiếp nhận/xử lý trung bình, tỷ lệ yêu cầu làm lại và cam kết trễ; coordination nhóm theo quản lý hoàn tất và giữ riêng tổng pending.
- [x] `ManagerDirectiveSlaCard` chỉ hiển thị cho Leadership trên `/leadership`, có ba tab dùng chung `DIRECTIVE_SOURCE_LABELS`, bảng sắp xếp được và trạng thái rỗng bằng tiếng Việt.
- [x] Ba repository directive dùng sort ổn định `[('issued_at', -1), ('_id', -1)]` trước `skip/limit`; test Mongo thật tạo 5 bản ghi cùng timestamp, đi qua ba repository với `limit=2`, xác nhận đủ/không trùng/không thiếu — `1 passed`.
- [x] Kiểm chứng: full backend `backend\\.venv\\Scripts\\python.exe -m pytest backend/tests -q` — 348 passed, 3 deselected; frontend toàn bộ Vitest — 39 files/120 tests passed; ESLint, build production và Prettier trên các file thay đổi đều đạt. Full `npm run format:check` còn báo 24 file cũ ngoài phạm vi Đợt B. Ba test bị deselect là các test integration cần Mongo/Redis chạy tường minh.

### Checklist Dashboard cấp phòng ban cho Lãnh đạo — Đợt C

- [x] Xác minh `overload_logs` là nguồn đúng cho góc nhìn Rủi ro: `department_id` và `trigger_reason` đã có sẵn trong `OverloadLogResponse`; không dùng `alerts.alert_type` và không bổ sung endpoint/schema.
- [x] `WeeklyPerformanceTrendPoint` bổ sung `quality`; repository tính trung bình `quality_score` song song với `performance_score`, service giữ giá trị thiếu là `null`.
- [x] Nhánh Leadership tải xu hướng và phân tích nhân viên cho cả ba phòng ban song song, hợp nhất theo `week_start`, hiển thị sáu series với màu phòng ban cố định và nét liền/nét đứt theo chỉ số.
- [x] Nhánh Leadership thay bốn card cũ bằng Xu hướng, Khen thưởng, Rủi ro và Tiến độ; tie-break Khen thưởng dùng `employee_code`, phòng ban không có dữ liệu vẫn giữ card và thông báo tiếng Việt.
- [x] `listTasks()` không truyền `department_id`; router v1 nhận `scope=None` cho Leadership nên trả task toàn công ty, sau đó frontend nhóm theo phòng ban và giữ cột 0 cho phòng ban không có task.
- [x] Hai bộ lọc Nhân viên/Phòng ban chỉ ẩn trong nhánh Leadership; block bốn biểu đồ cũ và hành vi chọn dữ liệu của Manager được giữ nguyên.
- [x] Kiểm chứng: backend `351 passed, 3 deselected`; frontend `40 files/125 tests passed`; ESLint, production build, Prettier trên các file thay đổi và `git diff --check` đều đạt. Ba test backend deselect vẫn là integration cần Mongo/Redis chạy tường minh.
- [x] Bố cục card được tách thành ba khu vực nổi bật: Phân tích hiệu suất, Cảnh báo và thời gian xử lý, và So sánh tổng hợp; hai card cảnh báo luôn nằm cùng nhóm lưới responsive, không còn card đơn bị lệch sang một bên.
- [x] Card “Tiến độ công việc theo phòng ban” trải toàn bộ hàng ở breakpoint lớn (`lg:col-span-2`), tránh cột trống do nhóm Leadership có năm card trong lưới hai cột.
- [x] Card “Thời gian xử lý cảnh báo trung bình” dùng `h-fit lg:self-start`, không bị grid kéo cao theo biểu đồ quá tải bên cạnh nên giảm khoảng trống nội bộ.
- [x] Kiểm chứng sau chỉnh grid: `PerformanceDashboard.test.jsx`, `DashboardPage.test.jsx` và `leadershipPerformance.test.js` — 8 tests passed; ESLint, Prettier và production build đạt.
- [x] Kiểm chứng bổ sung cho điều chỉnh bố cục: `PerformanceDashboard.test.jsx` và `DashboardPage.test.jsx` — 4 tests passed; ESLint và production build đạt. Build vẫn chỉ phát cảnh báo chunk lớn hiện hữu.

### Checklist GĐ6/19 — CRUD chính trên `/api/v1`

- [x] Departments: POST, PATCH, DELETE đã dùng lại `DepartmentService` và RBAC Leadership.
- [x] Employees: POST, PATCH, DELETE đã dùng lại `EmployeeService` và scope phòng ban backend.
- [x] Tasks: POST, PATCH, DELETE đã dùng lại nguyên `TaskService`, không tách logic cập nhật trạng thái/completed time.
- [x] 9 endpoint tạo/cập nhật/xóa trả `Location` sau POST thành công và dùng rate-limit group `mutation`.
- [x] Mongo live xác nhận `tasks.seed_key_1` là partial index trước khi migrate task POST.
- [x] `DuplicateKeyError` của ba service đã được map thành 409 từ trước; không phát sinh patch service ở Giai đoạn 6.
- [x] Không thêm Idempotency-Key; chức năng này vẫn để dành cho Giai đoạn 13.

Các POST deprecated cho chuyển trạng thái chỉ thị phòng ban được giữ nguyên như compatibility action, không được coi là CRUD chính của resource tasks.

Kiểm tra backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/check_app.py
```
- [x] Không thay đổi backend, schema MongoDB, API hoặc logic nghiệp vụ.

Kiểm tra frontend Phase 2:

```powershell
Set-Location frontend
npm run test -- --run
npm run lint
npm run build
npm run check:navigation
```

Kết quả gần nhất: Vitest `18 test files, 56 tests passed`, ESLint, Prettier và Vite build đạt.
Full Playwright E2E đạt `8/11` khi chạy liên tục với rate-limit live; 3 test dashboard/cảnh báo
đạt khi chạy focused sau khi reset key rate-limit. Full suite dùng chung user/IP nên có thể
chạm `read_heavy=30/phút`; khi nghiệm thu E2E đầy đủ, dùng Redis test namespace hoặc cấu hình
test riêng.

### Contract API v1 và chống request lặp

- Hạ tầng HTTP hiện có `RequestIdMiddleware` đọc/giữ `X-Request-ID` hợp lệ hoặc tự sinh UUID và trả header này trên mọi response, kể cả CORS preflight.
- `/api/v1` dùng error contract `{code, message, details: object | null, request_id}` qua component `V1ApiError`; `/api` giữ nguyên `ApiError` hiện hành để tương thích client cũ.
- Audit nền tảng đã xác nhận `datetime` được Pydantic/FastAPI serialize ISO-8601 và ObjectId đã được chuyển thành string ở response; hai phần này không bị sửa lại.
- Backend đăng ký cùng một router nghiệp vụ dưới `/api/v1`; `/api` chỉ là alias tương thích, không nhân đôi service/repository.
- Walking skeleton Phase 3 thêm `GET /api/v1/departments?page=1&page_size=20`, dùng `PageResponse` gồm `items`, `page`, `page_size`, `total`, `has_next`; `/api/departments` vẫn trả mảng như trước.
- Endpoint departments v1 hiện cắt trang in-memory sau `service.list(scope)`, chỉ chấp nhận vì số phòng ban ít. Không sao chép cách này cho employees, tasks, alerts hoặc performance_metrics; Giai đoạn 5 phải dùng `skip/limit` trực tiếp tại MongoDB.
- `frontend/src/features/departments/departmentsApi.js` unwrap `items` để các màn hình hiện tại tiếp tục nhận danh sách phẳng trong state.
- Frontend hiện gọi `/api/v1` qua các `*Api.js` tập trung; WebSocket vẫn dùng `/ws/realtime`.
- Các wrapper đọc Tasks/Alerts/Overload dùng `requestCoordinator` để deduplicate
  request đồng thời và giữ cache tối đa rất ngắn; mutation, đổi session và event
  realtime liên quan đều invalidate resource tương ứng. Đây là tối ưu tải, không
  thay thế nguồn dữ liệu realtime.
- Kiểm tra caller bằng `backend\.venv\Scripts\python.exe backend\scripts\check_api_callers.py`; gate này chặn cả URL `/api` legacy và URL `/api/v1` bị đặt ngoài `*Api.js`/hạ tầng được phép.
- `backend\scripts\check_app.py` còn kiểm tra mọi route `/api` và `/api/v1` nghiệp vụ đều có dependency xác thực/RBAC; chỉ health và login/logout là public.
- Các API đọc dạng danh sách v1 nhận `offset`/`limit` (mặc định 100, tối đa 100) và trả `X-Total-Count`, `X-Offset`, `X-Limit`, cùng `Link rel="next"`; `/api` giữ payload cũ.
- Các danh sách chính v1 thực hiện `count/skip/limit` ngay ở Repository; không tải toàn bộ collection rồi mới cắt ở Router.
- Các action mới dùng resource method: `PATCH /alerts/{id}`, `PATCH /threshold-configs/{id}`, `POST /overload/scans`, `PATCH /attachments/upload-sessions/{id}`; action path cũ vẫn giữ tạm.
- Workflow điều phối/chỉ thị dùng sub-resource v1 như `/coordination/alerts/{id}/plans`, `/directives/{id}/fulfillment` và các transition `PATCH` (`acknowledgement`, `submission`, `acceptance`, `revision-request`); flow cá nhân cũ chỉ còn compatibility backend.
- Lỗi HTTP có dạng `{code, message, details, request_id}` và mọi response có `X-Request-ID`.
- OpenAPI đánh dấu toàn bộ alias `/api` là `deprecated`; `/api/v1` là contract successor.
- Request ghi có thể gửi `Idempotency-Key`; cùng key và cùng payload sẽ replay response, khác payload trả `409`.
- Rate limit dùng các group canonical `read_light`, `read_operational`, `read_heavy`, `mutation`, `directive_action`, `login`, `upload_session`, `upload_completion`, `ai_chat`, `scan`, `websocket_handshake`; `health` là bypass. `read_operational` dành cho danh sách tasks/alerts vận hành, tách quota khỏi analytics `read_heavy`. Redis dùng Lua atomic approximate sliding-window counter theo hai bucket. Key chuẩn là `rl:user:{user_id}:{group}`, `rl:ip:{ip}:anonymous:{group}` và cặp login `rl:ip:{ip}:login:{username}` + `rl:ip:{ip}:login`.
- Toàn bộ route nghiệp vụ khai báo group bằng dependency `rate_limit_group("...")`; health, docs và OpenAPI không gắn dependency. `RateLimitMiddleware` chỉ đọc decision từ request state để ghi header, không tự enforcement. WebSocket handshake kiểm tra thủ công theo IP và đóng `1013` khi vượt quota.
- Khi `ENVIRONMENT=production` và bật rate limit, cấu hình memory backend bị từ chối; idempotency bật cũng bắt buộc có `REDIS_URL`.
- Các quota rate limit và TTL idempotency phải là số dương; cấu hình sai bị từ chối ngay lúc khởi động.
- Khi Redis sẵn sàng, chạy smoke multi-instance bằng `backend\.venv\Scripts\python.exe backend\scripts\smoke_redis.py`; smoke này kiểm tra atomic rate-limit và idempotency replay qua hai adapter độc lập.
- Tất cả thời điểm MongoDB được đọc/ghi với timezone UTC; ObjectId chỉ xuất ra qua schema response dạng chuỗi.

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

### Đề xuất xử lý cảnh báo bằng AI cho Manager

- [x] `POST /api/v1/alerts/{alert_id}/ai-proposal` dùng chung nhóm rate limit `ai_chat` (10/phút).
- [x] AI chỉ trả đề xuất; Manager xem, chỉnh sửa rồi gọi trực tiếp luồng xử lý cảnh báo/điều phối hiện có.
- [x] Pydantic kiểm tra schema và giới hạn chuyển 1–2 công việc; backend tiếp tục đối chiếu ứng viên với dữ liệu thật.
- [x] JSON lỗi hoặc action chọn nhân viên ngoài danh sách được xử lý an toàn, không làm hỏng danh sách cảnh báo.
- [x] Đã ghi nhận giới hạn: luồng Leadership tạo “chỉ thị cảnh báo cấp phòng ban” chưa mở trong giai đoạn này.

### Đề xuất xử lý công việc quá hạn bằng AI cho Manager

- [x] `POST /api/v1/tasks/{task_id}/ai-proposal` chỉ cho Manager và dùng chung nhóm
  rate limit `ai_chat`; backend tự kiểm tra scope và công việc vẫn đang quá hạn.
- [x] AI chỉ diễn giải các phương án backend đã tính: giữ người/gia hạn hoặc đổi người/
  gia hạn; schema Pydantic kiểm tra option, điểm và mã nhân viên.
- [x] Manager có thể sửa trạng thái, người phụ trách và deadline trên giao diện trước khi
  bấm “Áp dụng phương án”. Nút này gọi trực tiếp `PATCH /api/v1/tasks/{task_id}`, không
  có endpoint thực thi kế hoạch AI.
- [x] JSON không hợp lệ, option không nằm trong kế hoạch deterministic hoặc không có
  phương án an toàn đều giữ fallback kèm hướng dẫn xử lý thủ công.
- [x] Leadership chưa có nút đề xuất này; đây là rollout riêng cho role Manager trước.

### Xếp hạng phương án xử lý công việc quá hạn

- [x] Backend dùng `TaskActionPlanningService` để tạo nhiều lựa chọn: giữ người và gia
  hạn 1/3/5 ngày, đổi người và đặt lại hạn an toàn, hoặc đổi người kèm gia hạn.
- [x] Không sinh phương án đổi người với deadline cũ đã quá hạn; mọi phương án đang mở
  đều phải đặt hạn mới trong tương lai.
- [x] `fit_score` là điểm phù hợp tương đối 0–100, không phải xác suất bảo đảm hiệu suất.
  Điểm do backend tính từ sức chứa, chất lượng, hiệu suất, khả năng khôi phục deadline,
  kỹ năng và độ tin cậy; AI chỉ diễn giải kết quả.
- [x] Ứng viên phải cùng phòng ban, đang hoạt động, không quá tải, không có việc quá hạn,
  có lịch sử dữ liệu đủ mới và đạt điều kiện chất lượng/kỹ năng. Không đủ dữ liệu thì
  chuyển sang xử lý thủ công.
- [x] Mỗi proposal có `confidence`, `evidence`, `plan_version` và kiểm tra
  `expected_updated_at`; nếu task đã bị sửa trong lúc xem proposal, API trả `409` để tải lại.
- [x] Khi áp dụng proposal, backend từ chối deadline quá khứ hoặc thiếu deadline mới khi
  đổi người; cập nhật còn được kiểm tra theo `updated_at` trong cùng điều kiện repository.
- [x] Dữ liệu tùy chọn `estimated_effort_hours`, `required_skills` và `skills` đã được
  thêm với giá trị mặc định để không phá các bản ghi cũ.

### Kế hoạch Manager AI Copilot v2 — đã chốt hướng bổ sung

Mục tiêu của lộ trình này là nâng Trợ lý AI của Manager từ chatbot đọc số liệu thành
trợ lý vận hành phòng ban: nhận biết xu hướng, giải thích cảnh báo, đưa ra đề xuất có
bằng chứng và hỗ trợ soạn bản nháp. AI vẫn không được tự thay đổi dữ liệu nghiệp vụ.

#### Quyết định kiến trúc

- Tiếp tục dùng Cloudflare Workers AI + model đang cấu hình; chưa fine-tune model và
  chưa gửi toàn bộ MongoDB cho model. Context được tạo bởi Data Tools đã kiểm tra scope.
- Backend là nơi tính toán số liệu, kiểm tra RBAC, lọc dữ liệu và thực thi mutation.
  Model chỉ chọn tool đọc dữ liệu hoặc diễn giải kết quả đã được kiểm tra.
- Manager chỉ đọc được phòng ban của tài khoản; Leadership không dùng luồng này để
  vượt scope Manager. Mọi tool mới phải nhận `department_scope` từ backend, không tin
  `department_id` do client gửi.
- Không tạo endpoint “AI tự thực thi”. Resolve cảnh báo, điều phối công việc và các
  thao tác ghi vẫn gọi API nghiệp vụ hiện có, kèm human approval, audit và idempotency.
- Mọi câu trả lời phải nêu được kỳ dữ liệu/phạm vi; khi provider lỗi, hệ thống trả
  dữ liệu tổng hợp cục bộ đã được kiểm tra quyền hoặc thông báo provider riêng, không
  gọi nhầm là lỗi truy cập dữ liệu.

#### Giai đoạn MC0 — Chuẩn hóa hợp đồng và bộ đánh giá

- [x] Chốt schema chung cho tool đọc: `date_from`, `date_to`, `limit`, tên nhân viên
  hoặc phạm vi phòng ban; giới hạn ngày và số dòng ở Pydantic.
- [x] Chuẩn hóa response gồm `co_du_lieu`, `pham_vi`, `ky_du_lieu`, `tong_quan`,
  `du_lieu` và `nguon_du_lieu`; loại ID kỹ thuật trước prompt.
- [x] Bổ sung test matrix cho Manager đúng phòng, Manager sai phòng, Leadership,
  không có dữ liệu, dữ liệu thiếu ngày và provider trả stream rỗng.
- [x] Ghi nhận baseline: thời gian phản hồi, tỷ lệ tool chọn đúng, tỷ lệ fallback,
  số lần trả lời có số liệu không có trong tool.

Tiêu chí chuyển giai đoạn: contract được review, test RBAC đạt và baseline được lưu
trong CHANGELOG/README; chưa thêm tính năng UI mới ở giai đoạn này.

#### Giai đoạn MC1 — Phân tích hiệu suất và so sánh kỳ

Bổ sung ba tool chỉ-đọc ưu tiên cao:

- [x] `get_performance_trend`: xu hướng hiệu suất/chất lượng theo ngày của phòng ban
  hoặc một nhân viên trong phạm vi được phép.
- [x] `compare_performance_periods`: so sánh kỳ hiện tại với kỳ trước, trả chênh lệch
  tuyệt đối, phần trăm và số ngày có dữ liệu; phần trăm do backend tính.
- [x] `explain_alert`: lấy cảnh báo, các ngày phát hiện, chỉ số liên quan và dữ liệu
  nền tối thiểu để giải thích nguyên nhân; không đọc toàn bộ hồ sơ nhân viên.

Tái sử dụng `PerformanceRepository`, `AlertRepository`, `AiDataToolService` và
`AiToolRegistry`; không tạo truy vấn MongoDB trong prompt. Frontend bổ sung nhóm câu hỏi
gợi ý và hiển thị kết quả theo các khối “Kết luận / Bằng chứng / Kỳ dữ liệu”.

Tiêu chí nghiệm thu:

- [x] “Hiệu suất phòng tôi 7 ngày gần đây thế nào?” trả đúng xu hướng từ Mongo.
- [x] “So với 7 ngày trước thay đổi thế nào?” trả đúng chênh lệch backend tính.
- [x] Manager không thể lấy trend/alert của phòng khác dù sửa payload hoặc tên phòng.
- [x] Không có số liệu thì trả thông báo không đủ dữ liệu, không gọi model tự do để đoán.

#### Giai đoạn MC2 — Bản tin chủ động cho Manager

- [x] Xây `ManagerBriefingService` tạo bản tóm tắt theo ngày từ các aggregate đã
  được kiểm tra: nhân viên cần chú ý, cảnh báo mở, quá tải, việc quá hạn và xu hướng.
- [x] Xếp hạng mức ưu tiên bằng rule backend; AI chỉ diễn giải các mục đã xếp hạng.
- [x] Tái sử dụng cache summary hiện có theo user/phạm vi/ngày; fallback không cache.
- [x] Dashboard hiển thị “Điểm đáng chú ý”, “Bằng chứng” và “Đề xuất tiếp theo”, có
  nút làm mới và ghi thời điểm dữ liệu.

Tiêu chí nghiệm thu: bản tin của Manager không chứa nhân viên ngoài phòng, số liệu
khớp API gốc, không phát sinh request AI khi dữ liệu không đổi trong thời gian cache,
và lỗi provider không làm hỏng Dashboard.

#### Giai đoạn MC3 — Hội thoại nhiều lượt có kiểm soát

- [x] Gắn `conversation_id` và lưu một context tool cuối đã giới hạn trong `ai_conversations`;
  không lưu nguyên prompt/output nhạy cảm ngoài chính sách audit.
- [x] Mỗi câu hỏi tiếp theo phải được ánh xạ lại vào tool và kiểm tra scope; không
  tin kết quả cũ nếu kỳ dữ liệu hoặc quyền đã thay đổi.
- [x] Cho phép các lượt nối tiếp như “Vì sao?”, “So với tuần trước thì sao?” và
  “Nên theo dõi ai?”, nhưng giới hạn context bằng tool result đã rút gọn.
- [x] Khi câu hỏi mơ hồ, UI yêu cầu chọn kỳ/phạm vi thay vì để model tự suy đoán.

Tiêu chí nghiệm thu: hội thoại nối tiếp đúng cùng phòng ban, đổi tài khoản không thể
đọc lại context của người khác, refresh/retry không nhân bản audit bất thường.

#### Giai đoạn MC4 — Đề xuất hành động và bản nháp có human approval

- [x] Mở rộng proposal hiện có để mỗi đề xuất chứa `rationale`, bằng chứng nguồn,
  mức độ ưu tiên và dữ liệu thời điểm tính toán.
- [x] Cho phép tạo bản nháp ghi chú xử lý cảnh báo hoặc bản nháp điều phối; Manager
  được sửa trước khi áp dụng.
- [x] Nút áp dụng tiếp tục gọi `resolveAlert`/`applyCoordination`/`updateTask` hiện có; không
  truyền kế hoạch AI sang một endpoint thực thi mới.
- [x] Chặn candidate không còn hợp lệ, alert đã đóng, scope đã đổi hoặc kế hoạch
  stale; yêu cầu tải lại dữ liệu trước khi xác nhận.

Tiêu chí nghiệm thu: AI không tự ghi dữ liệu, thao tác xác nhận vẫn có RBAC/audit/
Idempotency-Key, proposal sai schema hoặc candidate giả bị loại an toàn.

#### Giai đoạn MC5 — Đo chất lượng và vận hành production

- [x] Ghi nhận trong audit/structured log các trạng thái `tool_selected`, `tool_executed`, `no_data`,
  `provider_fallback`, `timeout`, `empty_output` và `reasoning_truncated`.
- [x] Xây bộ 30–50 câu hỏi tiếng Việt cố định cho Manager, có expected tool và expected
  data constraints; chạy regression trước mỗi thay đổi provider/prompt.
- [x] Kiểm thử tải quota `ai_chat`, circuit breaker, retry, cache và nhiều worker.
- [x] Rà soát prompt injection: không cho người dùng yêu cầu bỏ scope, lộ ID, raw query
  hoặc tự áp dụng mutation.
- [x] Chỉ bật rollout từng phần sau khi test local, acceptance dữ liệu seed và review
  log; production không bật raw SSE debug.

#### Bằng chứng triển khai MC0–MC5 (10/09/2026)

- Contract/tool mới nằm ở `backend/app/models/ai_tools.py`,
  `backend/app/services/ai_data_tool_service.py` và `backend/app/services/ai_tool_service.py`;
  kết quả được tính ở backend, có phạm vi, kỳ dữ liệu, tổng quan và nguồn dữ liệu.
- `ManagerBriefingService` tổng hợp cảnh báo mở, quá tải, việc quá hạn, xu hướng và ứng
  viên còn sức chứa; dữ liệu vẫn lấy theo scope backend trước khi đưa vào prompt.
- Hội thoại chỉ lưu `conversation_id` cùng tool và arguments đã validate cuối cùng; không
  lưu nguyên prompt/output. Context được đọc lại theo đúng `user_id` và `department_id`.
- Proposal MC4 có rationale, bằng chứng, ưu tiên, thời điểm và điều kiện; candidate được
  lọc lại từ danh sách thật. Nút áp dụng vẫn gọi API nghiệp vụ `resolveAlert`/
  `applyCoordination`, không có endpoint thực thi kế hoạch AI.
- Bộ đánh giá Manager có 37 câu tiếng Việt cố định; test hội thoại/scope isolation có
  40 test. Regression backend: `286 passed, 2 deselected`; frontend: `85 passed`.
- Quality gates đạt: `mypy app`, `ruff check`, `npm run lint`, `npm run build`. Build có
  cảnh báo kích thước chunk của Vite nhưng hoàn tất thành công; `AI_DEBUG_STREAM` mặc định
  tắt ở production.

#### Thứ tự triển khai bắt buộc

`MC0 → MC1 → MC2 → MC3 → MC4 → MC5`. Mỗi giai đoạn phải có test riêng, quality gate
và ghi nhận file/route/schema bị ảnh hưởng trước khi chuyển giai đoạn. Không triển khai
MC3/MC4 khi MC1 chưa chứng minh dữ liệu tool đúng và không triển khai Leadership directive
cho tới khi xác định chính xác API nghiệp vụ tương ứng.

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

Kết quả xác nhận gần nhất: backend `145 passed`, compileall và route/caller gate đạt;
frontend `50 passed`, ESLint và Vite production build đạt. `npm run format:check`
còn báo 5 file frontend cũ không thuộc thay đổi API/Auth lần này.

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

Live smoke gần nhất đã chạy với MongoDB Replica Set local: cookie/CSRF/logout, Bearer
compatibility, RBAC phòng ban, pagination v1 và realtime WebSocket đều đạt. Redis
multi-instance cũng đã đạt qua `backend\scripts\smoke_redis.py`; HTTP health đang trả
đúng `X-RateLimit-*`; `/api/health` được bypass có chủ đích.
Smoke WebSocket cookie mới: `backend\scripts\smoke_realtime_cookie.py`; smoke query-token
legacy vẫn nằm ở `backend\scripts\smoke_realtime.py`.

Live validation hiện tại đã seed `960` bản ghi performance cho `16` nhân viên trong `60` ngày
trên MongoDB host; performance và overload smoke đều đạt. Các key `rl:*` trong Redis chỉ được
reset khi chuẩn bị một lượt test live sạch, không ảnh hưởng dữ liệu MongoDB.

Lưu ý môi trường live hiện tại: backend và các script seed đang dùng MongoDB host
`127.0.0.1:27017` vì đây là instance chứa dữ liệu kiểm thử. MongoDB trong Docker vẫn
đang rỗng; không dùng `docker compose exec mongodb` để kết luận số liệu API cho tới khi
có kế hoạch dump/restore và chuyển nguồn dữ liệu rõ ràng. Seed performance hiện hỗ trợ
employee code không có hậu tố số; smoke performance kiểm tra riêng cửa sổ 60 ngày để
không bị ảnh hưởng bởi dữ liệu lịch sử.

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

## 11. Biên bản tối ưu code — 12/09/2026

- [x] Fail-fast cấu hình production: JWT secret, storage credential/HTTPS, rate-limit và malware scanner.
- [x] Cô lập lỗi EventBus, chống subscribe trùng và hủy subscribe theo lifecycle worker.
- [x] Daily review dùng MongoDB transaction cho report, metric và audit; event phát sau commit.
- [x] Resolve alert nguyên tử theo trạng thái mở; upload commit/fail kiểm tra owner.
- [x] AI context query có giới hạn; ngày cache và Dashboard dùng múi giờ `Asia/Ho_Chi_Minh`.
- [x] Seed task idempotent tự sửa `created_by` mồ côi; threshold GET v1 trả contract phân trang chuẩn.
- [x] Verification: backend `364 passed` với 1 cảnh báo thư viện Starlette/httpx, mypy sạch, frontend `143 passed`, ESLint/Prettier/navigation đạt, Vite build đạt.
- [x] Tách bundle theo route bằng `React.lazy/Suspense`; chunk chính giảm từ khoảng `1.13 MB` xuống khoảng `380 kB`, không còn cảnh báo chunk lớn.
- [ ] Browser visual smoke còn chờ browser backend khả dụng.
- [ ] Live threshold index còn chờ giải phóng disk Mongo local; lần kiểm tra trả `OutOfDiskSpace`.

Chi tiết bằng chứng và lệnh kiểm tra nằm trong [optimization baseline](docs/review/optimization-baseline-2026-09-12.md).
# HRMS_AI_Implemented
