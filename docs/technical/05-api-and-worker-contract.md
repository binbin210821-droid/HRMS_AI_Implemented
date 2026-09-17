# API và Cloudflare AI Worker Interface Contract

## 1. API contract hiện hành

- Chuẩn: `/api/v1`; alias `/api` giữ compatibility.
- OpenAPI được FastAPI sinh tại `/openapi.json`; giao diện `/docs`, `/redoc`.
- Frontend runtime hiện gọi `/api/v1/*` qua `frontend/src/services/httpClient.js` và feature APIs.
- Thành công trả response model Pydantic; lỗi v1 đi qua HTTP contract, request ID và mã HTTP chuẩn.

### Mã lỗi HTTP chuẩn

| Mã | Ý nghĩa | Ví dụ trong hệ thống |
|---:|---|---|
| 400 | Request không hợp lệ ở mức giao thức/idempotency | `Idempotency-Key` dài quá 255 ký tự |
| 401 | Chưa xác thực hoặc token không hợp lệ/hết hạn | thiếu cookie/Bearer, token mismatch |
| 403 | Đã đăng nhập nhưng không đủ role/scope | Manager truy cập phòng khác; action Leadership-only |
| 404 | Không tìm thấy resource trong phạm vi được phép | employee/alert/task không tồn tại hoặc ngoài scope |
| 409 | Xung đột trạng thái, idempotency hoặc dữ liệu | stale update, duplicate fingerprint, conflict |
| 422 | Pydantic validation hoặc payload nghiệp vụ thiếu | thiếu item/evidence, điểm ngoài khoảng |
| 429 | Vượt rate limit | login, AI, upload, WebSocket handshake |
| 5xx | Lỗi hạ tầng/provider không dự kiến | Mongo/Redis/storage/AI provider; response không lộ secret |

Response lỗi v1 phải giữ request ID để truy log. `RequestIdMiddleware` và các handler trong `backend/app/core/http_contract.py` ghi request ID vào JSON lỗi và header `X-Request-ID`; message gửi UI dùng tiếng Việt dễ hiểu, không yêu cầu người dùng đọc stack trace.

## 2. Auth contract

### Browser request

1. Login bằng JSON username/password.
2. Server đặt HttpOnly access cookie và CSRF cookie.
3. Mutation gửi CSRF header theo `frontend/src/services/csrf.js`.
4. Bearer header chỉ là compatibility fallback nếu `LEGACY_BEARER_ENABLED=true`.

### WebSocket

- URL hiện tại: `/ws/realtime`.
- Cookie được ưu tiên; query `token` chỉ được phép khi `LEGACY_WS_QUERY_TOKEN_ENABLED=true`.
- Handshake chịu rate limit theo nhóm `websocket_handshake`; server gọi lại `resolve_current_user` từ token đã xác thực và dùng user đã resolve để áp phạm vi khi phát realtime, không tin scope do client tự gửi.

## 3. Endpoint inventory theo nhóm

| Nhóm | Endpoint v1 tiêu biểu | Vai trò |
|---|---|---|
| Auth/health | `/auth/login`, `/auth/me`, `/auth/logout`, `/health` | public/login hoặc authenticated; `/health` được đăng ký dưới cả `/api/v1/health` và alias vận hành `/api/health` |
| Master | `/departments`, `/employees` và `/{id}` | scope + Leadership cho quản trị phòng |
| Performance | `/performance`, `/performance/daily-reviews*`, `/performance/analytics/*`; `/performance/daily-review*` là alias compatibility đang còn được đăng ký | Manager theo phòng; company analytics cho Leadership |
| Alerts/overload | `/alerts`, `/alert-scans`, `/alerts/{id}/resolve`, `/overload`, `/overload-scans` | scope; scan/mutation có rate limit/idempotency phù hợp |
| Tasks | `/tasks`, `/tasks/leadership-overview`, `/tasks/departments/{id}/portfolio`, directive lifecycle | Manager/Leadership theo action |
| Coordination | `/coordination/suggestions`, `/coordination/alerts/{id}/plans` (hiện hành), `/coordination/alerts/{id}/apply` (compatibility), directives/candidates/fulfillment | user xác nhận mutation |
| Evaluations | `/department-evaluations`, weekly reviews, attachment download | Leadership ghi; scope khi đọc |
| AI | `/ai/chat/stream`, `/ai/leadership-proposal`, `/ai/tool-preview`, alert/task proposal | authenticated, scope server-side |
| Attachments | `/upload-sessions*` (v1 hiện hành), `/attachments/upload-sessions*` (compatibility), evaluation/performance download URL | owner/scope + signed URL |

 Danh sách đầy đủ được FastAPI OpenAPI sinh runtime. Catalog tiered ở mục 8 là chỉ mục kiểm soát caller hiện tại, không thay thế OpenAPI.

## 4. AI chat request/stream hiện hành

Request model `AIChatRequest` trong `backend/app/models/ai.py` có `message` bắt buộc (1–2000 ký tự), `mode` tùy chọn (`chat` hoặc `summary`, mặc định `chat`), `refresh` tùy chọn (mặc định `false`) và `conversation_id` tùy chọn (1–64 ký tự):

```json
{
  "message": "Phòng của tôi có cảnh báo nào cần ưu tiên?",
  "mode": "chat",
  "refresh": false,
  "conversation_id": "optional-bounded-id"
}
```

Provider request nội bộ là OpenAI-compatible chat body với `messages`, `model`, `stream=true`, `temperature=0.2`, `max_completion_tokens` theo cấu hình, và `chat_template_kwargs.enable_thinking=false` cho Cloudflare khi ở summary/structured-output hoặc khi cấu hình tắt thinking. Structured output thêm `response_format: {"type":"json_object"}`. Client nhận các event SSE dạng `data: {JSON}\n\n`; parser ở `frontend/src/features/ai/aiApi.js` tách block, đọc dòng `data:` và xử lý các loại `token`, `status`, `conversation`, `error`, `done`. Parser provider ở `backend/app/ai/providers.py` bỏ qua `[DONE]` và trích content từ payload `choices[].delta`.

## 5. Cloudflare trực tiếp — contract đã có bằng chứng

Ba adapter hiện hành (`CloudflareProvider`, `CloudflareToolProvider` trong `backend/app/ai/providers.py` và `backend/app/ai/tool_provider.py`) gọi chat trực tiếp; `CloudflareEmbeddingProvider` trong `backend/app/ai/rag.py` gọi embedding trực tiếp:

```text
POST https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions
Authorization: Bearer {CLOUDFLARE_API_TOKEN}
Content-Type: application/json
```

Embedding gọi:

```text
POST https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{AI_EMBEDDING_MODEL}
Authorization: Bearer {CLOUDFLARE_API_TOKEN}
```

Đây là Cloudflare Workers AI API, chưa phải Worker subdomain riêng. `CLOUDFLARE_API_TOKEN` chỉ được giữ ở backend/runtime secret.

## 6. Hợp đồng Worker mục tiêu nếu tách Worker riêng

> Phần này là target contract cần implement/approve; không mô tả artifact đang có.

### FastAPI → Worker

```http
POST {AI_WORKER_BASE_URL}/v1/chat
X-WorkMind-Worker-Token: {AI_WORKER_SHARED_SECRET}
Content-Type: application/json
```

```json
{
  "request_id": "request-id-from-fastapi",
  "model": "optional-worker-controlled-model",
  "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
  "stream": true,
  "temperature": 0.2,
  "max_completion_tokens": 4096,
  "metadata": {"scope": "department"}
}
```

### Worker → FastAPI

- Streaming: `Content-Type: text/event-stream`, mỗi event chứa một text delta; kết thúc bằng `[DONE]`.
- Non-stream JSON: `{"text":"...","provider":"cloudflare","model":"...","request_id":"..."}`.
- Error JSON: `{"error":{"code":"rate_limited|timeout|provider_unavailable|invalid_request","message":"...","retryable":true,"request_id":"..."}}`.

### Policy bắt buộc

- Worker không tin `scope` do browser gửi; FastAPI đã quyết định scope và Worker không được mở rộng dữ liệu.
- Secret chỉ ở FastAPI/Worker secret store; không đưa vào Vite bundle.
- Timeout budget phải nhỏ hơn API request budget; retry tối đa theo policy, tránh nhân request khi client retry.
- 429/5xx/timeout: FastAPI fallback provider hoặc friendly error; không tạo mutation.
- Rate limit tại FastAPI (`RATE_LIMIT_AI_CHAT`) và tại Worker/provider nếu Worker được triển khai.
- Log chỉ lưu request id, provider, latency, status, không lưu token/secret/raw prompt nhạy cảm.

## 7. Hướng dẫn bổ sung ảnh minh chứng

Phần này hướng dẫn lập hồ sơ ảnh cho API contract hiện hành và ranh giới Cloudflare AI. Mỗi ảnh nên có thời điểm chụp, môi trường (`local` hoặc `production`) và mã evidence tương ứng. Không chụp token, cookie, JWT, connection string, secret header hoặc dữ liệu nhân sự thật.

### 7.1. API routing và OpenAPI

Chụp một trong các bằng chứng sau:

- Mở `https://<production-origin>/docs` hoặc đường dẫn docs đang được bật, sau đó chụp danh sách route có prefix `/api/v1`.
- Mở `https://<production-origin>/openapi.json`, tìm các path `/api/v1/health`, `/api/v1/auth/login` và một endpoint nghiệp vụ đã xác minh.
- Nếu production tắt Swagger/Redoc, dùng kết quả kiểm tra route hoặc file OpenAPI được tạo trong môi trường kiểm thử; ghi rõ đây là evidence static/runtime nào.

Nên chụp riêng health check để thể hiện route production đang sử dụng:

```bash
curl -i --max-time 15 http://127.0.0.1:80/api/v1/health
```

Ảnh cần giữ status HTTP, response health và URL; không cần hiển thị header chứa cookie hoặc token.

Tên evidence gợi ý: `api-01-routing-openapi-v1.png` và `api-02-health-v1.png`.

### 7.2. Auth, cookie và CSRF

Sử dụng DevTools của trình duyệt trong môi trường test hoặc staging:

1. Mở tab **Network**, thực hiện login bằng tài khoản test.
2. Chụp request login và response status, che username nếu cần.
3. Mở **Application/Storage → Cookies**, chụp tên cookie và các cờ `HttpOnly`, `Secure`, `SameSite`; che toàn bộ giá trị cookie.
4. Thực hiện một mutation bằng tài khoản test, chụp request có CSRF header nhưng che giá trị header.

Không dùng ảnh chứa access token, refresh token, JWT hoặc cookie value thật. Nếu cần chứng minh Bearer compatibility, chỉ chụp tên cờ cấu hình và status kết quả trong môi trường kiểm thử, không chụp token.

Tên evidence gợi ý: `api-03-auth-cookie-flags.png` và `api-04-csrf-request.png`.

### 7.3. Request ID và mã lỗi HTTP

Trong DevTools hoặc terminal, tạo request test hợp lệ và một số request lỗi an toàn, ví dụ thiếu xác thực hoặc payload validation sai:

```bash
curl -i http://127.0.0.1:80/api/v1/health
curl -i -X POST http://127.0.0.1:80/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Chụp response thể hiện status HTTP, trường `request_id` nếu có và header `X-Request-ID`. Không chụp mật khẩu hoặc thông tin tài khoản thật. Các mã 401/403/404/409/422/429/5xx nên được chứng minh bằng test case tương ứng hoặc log runtime, không dùng một ảnh duy nhất để suy diễn tất cả mã lỗi.

Tên evidence gợi ý: `api-05-error-request-id.png`.

### 7.4. WebSocket realtime

Trong DevTools → **Network → WS**, mở kết nối đến `/ws/realtime` bằng tài khoản test và chụp:

- URL path `/ws/realtime`;
- trạng thái kết nối thành công;
- một event realtime đã được phép theo scope;
- không hiển thị cookie, query token hoặc nội dung dữ liệu nhạy cảm.

Nếu kiểm tra rate limit handshake, chụp log/status của các lần thử trong môi trường test và ghi rõ đây là kiểm thử giới hạn, không tạo ảnh hưởng lên production.

Tên evidence gợi ý: `api-06-websocket-realtime.png`.

### 7.5. AI chat streaming và SSE parser

Chụp bằng DevTools hoặc terminal một phiên AI chat bằng dữ liệu tổng hợp:

- request đến endpoint `/api/v1/ai/chat/stream`;
- response `Content-Type: text/event-stream`;
- các event `data:` gồm `status`, `token`, `conversation`, `done` hoặc `error` nếu có;
- request ID và trạng thái hoàn tất nếu hệ thống hiển thị.

Không đưa prompt chứa thông tin nhân sự thật vào ảnh. Nếu response có tên nhân viên hoặc department scope, thay bằng dữ liệu test trước khi lưu evidence.

Tên evidence gợi ý: `api-07-ai-sse-stream.png`.

### 7.6. Cloudflare Workers AI gọi trực tiếp

Ảnh minh chứng nên được lấy từ một trong hai nguồn:

- Cloudflare dashboard/usage thể hiện model hoặc AI inference đã phát sinh request.
- Backend log/runtime thể hiện provider, model, request ID, latency và status; phải che URL đầy đủ nếu URL có account identifier nhạy cảm.

Không chụp `Authorization: Bearer ...`, `CLOUDFLARE_API_TOKEN` hoặc giá trị secret. Chỉ cần chứng minh backend là nơi gọi Cloudflare Workers AI trực tiếp, không ghi nhận Worker subdomain riêng nếu Worker đó chưa được triển khai.

Tên evidence gợi ý: `api-08-cloudflare-ai-runtime.png`.

### 7.7. Worker riêng — chỉ là target contract

Mục 6 là thiết kế đề xuất, không phải artifact đã triển khai. Vì vậy không tạo ảnh “đã triển khai Worker” nếu chưa có `AI_WORKER_BASE_URL`, endpoint Worker và log deployment thực tế.

Nếu sau này triển khai, cần bổ sung riêng:

- URL Worker và trạng thái deployment;
- request FastAPI → Worker với header secret đã che giá trị;
- response streaming/non-stream và request ID;
- log timeout, rate limit hoặc fallback.

Tên evidence gợi ý: `api-09-worker-target-after-implementation.png`.

### 7.8. Quy tắc lưu hồ sơ ảnh

- Dùng mã evidence trong tên file và liên kết mã đó với mục 1–5 tương ứng.
- Phân biệt rõ `source/static evidence`, `direct runtime evidence` và `browser/UI evidence`.
- Không commit ảnh chứa secret vào Git; lưu trong hồ sơ bàn giao hoặc kho bằng chứng được kiểm soát quyền truy cập.
- Trước khi gửi ảnh, kiểm tra lại URL, header, cookie, JWT, request body, response body và log để loại bỏ dữ liệu nhạy cảm.

## 8. Áp dụng tiered contract cho 62 frontend callers

### 8.1 Quy tắc cập nhật

1. Thêm hoặc sửa route phải sửa Pydantic model, response_model, Field description hoặc docstring trước; sau đó kiểm tra lại openapi.json, docs và redoc.
2. Chỉ viết tay logic mà OpenAPI không thể biểu diễn: RBAC/scope, side-effect, idempotency, status transition, pagination header, signed upload và SSE lifecycle.
3. CRUD và list dùng pattern ở mục 8.2; không sao chép request/response/error contract cho từng endpoint.
4. Mỗi thay đổi API về sau chỉ thêm một dòng vào Changelog với before, after, caller và kiểm thử ảnh hưởng.

### 8.2 Pattern chuẩn

#### CRUD resource

Áp dụng cho departments và employees:

| Method | Contract chung | Schema |
|---|---|---|
| GET collection | page, page_size, sort và filter riêng | PageResponse<ResourceResponse> |
| POST collection | JSON create model | 201 ResourceResponse |
| PATCH item | JSON update model | 200 ResourceResponse |
| DELETE item | Không có body | 204 |

#### List có phân trang

Các list page-based trả items, page, page_size, total, has_next. Các list resource-based trả array và đưa thông tin phân trang vào X-Total-Count, X-Offset, X-Limit, Link. Đây là lý do frontend có cả unwrapPageItems và fetchAllOffsetPages.

#### Mutation chung

Ngoài login, POST/PATCH/DELETE nhận Idempotency-Key tùy chọn. Browser mutation dùng cookie phiên và X-CSRF-Token. Lỗi v1 dùng V1ApiError gồm code, message, details, request_id; response có X-Request-ID.

### 8.3 Endpoint catalog

Mỗi dòng có thể đại diện nhiều method trên cùng resource; tổng số method-route của catalog là 62.

#### Auth, health và master data

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 1 | GET | /api/v1/health | Không có | HealthResponse | Public |
| 1 | POST | /api/v1/auth/login | LoginRequest: username, password | 200 TokenResponse và cookie | Public |
| 1 | GET | /api/v1/auth/me | Cookie hoặc Bearer | CurrentUser | Auth |
| 1 | POST | /api/v1/auth/logout | Không có | 204 | Auth |
| 2 | GET | /api/v1/departments | page, page_size, sort | PageResponse<DepartmentResponse> | Auth + scope |
| 1 | POST | /api/v1/departments | DepartmentCreate | 201 DepartmentResponse | Leadership |
| 1 | PATCH | /api/v1/departments/{department_id} | DepartmentUpdate | DepartmentResponse | Leadership |
| 1 | DELETE | /api/v1/departments/{department_id} | Không có | 204 | Leadership |
| 2 | GET | /api/v1/employees | department_id, is_active, page, page_size, sort | PageResponse<EmployeeResponse> | Auth + scope |
| 1 | POST | /api/v1/employees | EmployeeCreate | 201 EmployeeResponse | Auth + scope |
| 1 | PATCH | /api/v1/employees/{employee_id} | EmployeeUpdate | EmployeeResponse | Auth + scope |
| 1 | DELETE | /api/v1/employees/{employee_id} | Không có | 204 | Auth + scope |

#### Alerts, overload và dashboard

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 2 | GET | /api/v1/alerts | status, alert_type, from, to, department_id, severity, page, page_size, sort | PageResponse<AlertResponse> | Auth + scope |
| 1 | PATCH | /api/v1/alerts/{alert_id} | AlertResolveV1Request: status=resolved, resolution_note | AlertResponse | Auth + scope |
| 1 | POST | /api/v1/alert-scans | Không có | AlertResponse[] | Auth + scope; tạo/cập nhật cảnh báo |
| 3 | GET | /api/v1/alerts/department-summary | offset, limit | DepartmentAlertSummaryResponse[] | Auth + scope |
| 1 | POST | /api/v1/alerts/{alert_id}/ai-proposal | Không có | AiAlertProposalResponse | Manager + scope; advisory-only |
| 2 | GET | /api/v1/overload | from, to, page, page_size, sort | PageResponse<OverloadLogResponse> | Auth + scope |
| 3 | GET | /api/v1/dashboard/attention-summary | Không có | AttentionSummaryResponse | Auth + scope |

#### Performance và analytics

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 2 | GET | /api/v1/performance | employee_id, department_id, start_date, end_date | PerformanceMetricResponse[] | Auth + scope |
| 1 | GET | /api/v1/performance/daily-review (compat; canonical: /api/v1/performance/daily-reviews/{employee_id}/{date}) | employee_id, date | DailyPerformanceReviewResponse | Manager + scope |
| 1 | POST | /api/v1/performance/daily-review (compat; canonical: /api/v1/performance/daily-reviews) | DailyPerformanceReviewCreate | DailyPerformanceReviewResponse | Manager + scope |
| 1 | PATCH | /api/v1/performance/daily-review (compat; canonical: /api/v1/performance/daily-reviews/{employee_id}/{date}) | DailyPerformanceReviewCreate | DailyPerformanceReviewResponse | Manager + scope |
| 2 | GET | /api/v1/performance/daily-review/{employee_id}/{date}/attachments/{attachment_id}/download-url (compat; canonical: /api/v1/performance/daily-reviews/{employee_id}/{date}/attachments/{attachment_id}/download-url) | Không có | DailyReviewDownloadUrlResponse | Manager + scope |
| 3 | GET | /api/v1/performance/analytics/employee/{employee_id} | start_date, end_date | EmployeePerformanceAnalyticsResponse | Auth + scope |
| 3 | GET | /api/v1/performance/analytics/department/{department_id} | start_date, end_date | DepartmentPerformanceAnalyticsResponse | Auth + scope |
| 3 | GET | /api/v1/performance/analytics/department/{department_id}/weekly-trend | start_date, end_date | DepartmentWeeklyPerformanceTrendResponse | Auth + scope |
| 3 | GET | /api/v1/performance/analytics/company | start_date, end_date | CompanyPerformanceAnalyticsResponse | Leadership |

Daily review mutation có employee_id, date và items[]. Mỗi item có task_id, score, note, missing_reason và change_reason. Đây là một Tier 1 workflow nên side-effect evidence, tính điểm và ghi performance metric phải được ghi trong docstring/service contract, không cố nhồi vào OpenAPI schema.

Các dòng daily-review singular trong catalog là compatibility surface đang được frontend hiện tại gọi. Canonical v1 là nhóm daily-reviews plural được đăng ký native trong OpenAPI. Không gỡ singular alias cho đến khi caller inventory, test và Changelog xác nhận frontend đã chuyển sang plural.

#### Tasks và task directives

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 2 | GET | /api/v1/tasks | employee_id, department_id, status, overdue_only, from, to, page, page_size, sort | PageResponse<TaskResponse> | Auth + scope |
| 1 | POST | /api/v1/tasks | TaskCreate | 201 TaskResponse | Manager + scope |
| 1 | PATCH | /api/v1/tasks/{task_id} | TaskUpdate | TaskResponse | Manager + scope |
| 1 | DELETE | /api/v1/tasks/{task_id} | Không có | 204 | Manager + scope |
| 3 | GET | /api/v1/tasks/leadership-overview | range | LeadershipTaskOverviewResponse | Leadership |
| 3 | GET | /api/v1/tasks/departments/{department_id}/portfolio | range, focus | DepartmentTaskPortfolioResponse | Leadership |
| 2 | GET | /api/v1/tasks/department-directives | status, offset, limit | DepartmentTaskDirectiveResponse[] | Auth + scope |
| 1 | POST | /api/v1/tasks/department-directives/{department_id} | IssueDepartmentTaskDirectiveRequest | 201 DepartmentTaskDirectiveResponse | Leadership |
| 1 | POST | /api/v1/tasks/department-directives/{directive_id}/acknowledgements | action_note, commitment_date | 201 DepartmentTaskDirectiveResponse | Auth + scope |
| 1 | POST | /api/v1/tasks/department-directives/{directive_id}/submissions | completion_note | 201 DepartmentTaskDirectiveResponse | Auth + scope |
| 1 | POST | /api/v1/tasks/department-directives/{directive_id}/acceptances | note | 201 DepartmentTaskDirectiveResponse | Leadership |
| 1 | POST | /api/v1/tasks/department-directives/{directive_id}/revision-requests | note | 201 DepartmentTaskDirectiveResponse | Leadership |
| 1 | POST | /api/v1/tasks/{task_id}/ai-proposal | Không có | OverdueTaskPlanningResponse | Manager + scope; advisory-only |

#### Coordination và alert directives

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 2 | GET | /api/v1/coordination/suggestions | offset, limit | CoordinationSuggestionResponse[] | Auth + scope |
| 1 | POST | /api/v1/coordination/alerts/{alert_id}/plans | ApplyCoordinationRequest | 201 CoordinationPlanResponse | Auth + scope; ghi plan |
| 2 | GET | /api/v1/coordination/directives | status, offset, limit | CoordinationDirectiveResponse[] | Auth + scope |
| 2 | GET | /api/v1/coordination/directives/{directive_id}/candidates | offset, limit | WorkloadCandidateResponse[] | Auth + scope |
| 1 | POST | /api/v1/coordination/directives/{directive_id}/fulfillments | FulfillDirectiveRequest | 201 CoordinationPlanResponse | Auth + scope; ghi plan |
| 2 | GET | /api/v1/coordination/department-directives | status, offset, limit | DepartmentAlertDirectiveResponse[] | Auth + scope |
| 1 | POST | /api/v1/coordination/department-directives/{department_id} | IssueDepartmentAlertDirectiveRequest | 201 DepartmentAlertDirectiveResponse | Leadership |
| 1 | POST | /api/v1/alerts/department-directives/{directive_id}/acknowledgements | commitment_date, note | 201 DepartmentAlertDirectiveResponse | Auth + scope |
| 1 | POST | /api/v1/alerts/department-directives/{directive_id}/submissions | completion_note | 201 DepartmentAlertDirectiveResponse | Auth + scope |
| 1 | POST | /api/v1/alerts/department-directives/{directive_id}/acceptances | note | 201 DepartmentAlertDirectiveResponse | Leadership |
| 1 | POST | /api/v1/alerts/department-directives/{directive_id}/revision-requests | note | 201 DepartmentAlertDirectiveResponse | Leadership |

#### Evaluations và direct upload

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 1 | GET | /api/v1/department-evaluations/weekly-reviews/{department_id}/{week_start} | Không có | DepartmentWeeklyReviewResponse | Leadership |
| 2 | GET | /api/v1/department-evaluations | department_id, offset, limit | DepartmentWeeklyEvaluationListResponse | Auth + scope |
| 2 | GET | /api/v1/department-evaluations/{evaluation_id} | Không có | DepartmentWeeklyEvaluationResponse | Auth + scope |
| 2 | GET | /api/v1/department-evaluations/{evaluation_id}/attachments/{attachment_id}/download-url | Không có | DepartmentEvaluationDownloadUrlResponse | Leadership + scope |
| 1 | PATCH | /api/v1/department-evaluations/{evaluation_id} | multipart payload + files[] | DepartmentWeeklyEvaluationResponse | Leadership |
| 1 | POST | /api/v1/upload-sessions | CreateUploadSessionRequest | 201 UploadSessionResponse | Auth + scope |
| 1 | POST | /api/v1/upload-sessions/{session_id}/completions | Không có | CompleteUploadSessionResponse | Auth + owner |
| 1 | DELETE | /api/v1/upload-sessions/{session_id} | Không có | 204 | Auth + owner |

#### AI

| Tier | Method | Path | Request/query | Response | Quyền |
|---:|---|---|---|---|---|
| 1 | POST | /api/v1/ai/chat/stream | AIChatRequest | text/event-stream | Auth + scope |
| 1 | POST | /api/v1/ai/leadership-proposal | Không có | AiLeadershipProposalResponse | Leadership; advisory-only |

### 8.4 Caller mismatch đang mở

Frontend createDepartmentEvaluation hiện gọi POST /api/v1/department-evaluations/weekly-review. Backend v1 chỉ có POST /api/v1/department-evaluations/weekly-evaluations. Đây là 404 caller mismatch, không phải một contract hợp lệ trong 62 dòng catalog. Cần sửa caller hoặc khôi phục alias có chủ đích, sau đó cập nhật OpenAPI test và Changelog.

scanOverloadLogs hiện chỉ là function được export trong frontend API wrapper, chưa được UI gọi; không tính vào 62.

### 8.5 Nền tảng contract: response, tier, RBAC và scope

#### A1. Response thành công

REST v1 không dùng envelope toàn cục dạng success/data. Với response thành công, backend trả thẳng response_model đã khai báo. Riêng các endpoint list có phân trang theo page dùng chính PageResponse<T> làm envelope; các endpoint list tương thích dùng mảng JSON bare kèm header phân trang.

Ví dụ response bare:

~~~json
{
  "id": "dept_123",
  "name": "Kinh doanh",
  "code": "KD",
  "specialty": "Bán hàng",
  "description": null,
  "is_active": true,
  "created_at": "2026-09-16T09:32:11Z",
  "updated_at": "2026-09-16T09:32:11Z"
}
~~~

Client xác định thành công bằng HTTP status code và response schema; không kiểm tra một field success không tồn tại trong contract.

#### A2. Định nghĩa tier

| Tier | Tiêu chí áp dụng | Mức đặc tả bắt buộc |
|---|---|---|
| Tier 1 | Mutation hoặc critical path như login, auth/me, daily review, workflow directive, upload và AI | Request, response, mọi status code có thể trả, ví dụ JSON, RBAC/scope, side-effect và business rule đặc thù |
| Tier 2 | GET collection/CRUD list theo pattern chuẩn, có filter hoặc phân trang | Tham chiếu pattern ở mục 8.2; catalog ghi path, query/filter và response schema; chỉ ghi thêm khác biệt |
| Tier 3 | Read-only analytics, dashboard hoặc overview tổng hợp | Catalog ghi path, query chính, response schema và quyền; không bắt buộc ví dụ riêng |

Tier chỉ quyết định mức viết tài liệu, không làm thay đổi mức kiểm tra runtime, RBAC hay response_model của endpoint.

#### A3. RBAC và scope

Ứng dụng hiện chỉ có hai role trong model UserRole: manager và leadership. Không có role thứ ba tên Auth; trong catalog, Auth chỉ có nghĩa là đã xác thực.

| Role | Quyền và phạm vi |
|---|---|
| Leadership | Phạm vi toàn công ty khi endpoint cho phép; xem dữ liệu mọi phòng ban, thực hiện các thao tác quản trị/duyệt được route cho phép |
| Manager | Chỉ đọc/ghi dữ liệu thuộc department_id được gán trong DB; thực hiện nghiệp vụ quản lý trong phòng mình theo route permission |
| Auth trong catalog | Nhãn rút gọn cho điều kiện đã xác thực; vẫn phải thỏa scope và các điều kiện role riêng của endpoint |

Leadership có phạm vi rộng hơn Manager nhưng không phải một hierarchy số được suy ra tự động. Mỗi route vẫn phải khai báo dependency role/scope phù hợp.

Scope được server resolve từ current_user và bản ghi user trong DB; không tin department_id do client tự gửi. Leadership nhận scope toàn công ty (giá trị scope nội bộ là None), còn Manager bắt buộc có department_id hợp lệ và query được lọc theo phòng ban đó. Quy tắc này áp dụng cho REST và WebSocket; với WebSocket, department scope được xác định từ user sau handshake.

### 8.6 Error code contract thật của V1ApiError

V1ApiError luôn có code, message, details dạng object hoặc null và request_id. code hiện hành được chuẩn hóa theo các giá trị sau:

| HTTP | code | Ý nghĩa | Phạm vi |
|---:|---|---|---|
| 400 | bad_request | Request không hợp lệ, gồm Idempotency-Key dài quá 255 ký tự trong dependency route hiện tại | REST v1 hiện hành |
| 401 | unauthorized | Thiếu hoặc không xác thực được cookie/Bearer | REST v1 hiện hành |
| 403 | forbidden | Đã xác thực nhưng sai role hoặc scope | REST v1 hiện hành |
| 404 | not_found | Không tìm thấy resource hoặc route | REST v1 hiện hành |
| 409 | conflict | Xung đột trạng thái hoặc idempotency trong dependency route hiện tại | REST v1 hiện hành |
| 422 | validation_error | Request không qua được validation | REST v1 hiện hành |
| 429 | rate_limit_exceeded | Vượt rate limit; details có thể chứa retry_after_seconds | REST v1 hiện hành |
| 500 và lỗi HTTP khác do HTTPException | http_error | Lỗi HTTP chưa có mapping code riêng, ví dụ dependency trả 503 | REST v1 hiện hành |
| 500 do exception không xử lý được | internal_error | Lỗi hệ thống không được expose chi tiết | REST v1 hiện hành |
| 429 | rate_limit_exceeded | Vượt rate limit | Rate limiter structured response |
| 503 | rate_limit_unavailable | Rate limiter backend không sẵn sàng ở nhóm fail-closed | Rate limiter structured response |

IdempotencyMiddleware còn định nghĩa invalid_idempotency_key, idempotency_key_conflict, idempotency_request_in_progress và idempotency_unavailable. Tuy nhiên main app hiện gắn idempotency qua dependency opt-in trên từng route, không gắn class IdempotencyMiddleware toàn cục; vì vậy các lỗi dependency tương ứng được HTTP contract v1 chuẩn hóa thành bad_request, conflict hoặc http_error như bảng trên. Frontend không được suy đoán code qua message.

REST V1ApiError hiện không có field retryable. Khi cần retry, client dùng HTTP status, Retry-After và details.retry_after_seconds; quyết định retry phụ thuộc từng nhóm lỗi.

### 8.7 Ánh xạ phân trang theo endpoint

| Endpoint | Query chính | Kiểu response và phân trang |
|---|---|---|
| GET /api/v1/departments | page, page_size, sort | Body PageResponse<DepartmentResponse> |
| GET /api/v1/employees | page, page_size, sort, filter | Body PageResponse<EmployeeResponse> |
| GET /api/v1/alerts | page, page_size, sort, filter | Body PageResponse<AlertResponse> |
| GET /api/v1/overload | page, page_size, sort, from, to | Body PageResponse<OverloadLogResponse> |
| GET /api/v1/tasks | page, page_size, sort, filter | Body PageResponse<TaskResponse> |
| GET /api/v1/department-evaluations | department_id; page/page_size hoặc offset/limit | Body DepartmentWeeklyEvaluationListResponse, có items/page/page_size/total/has_next; v1 đồng thời phát header X-Total-Count/X-Offset/X-Limit và Link |
| GET /api/v1/alerts/department-summary | offset, limit | Mảng bare; X-Total-Count, X-Offset, X-Limit và Link nếu còn trang |
| GET /api/v1/tasks/department-directives | offset, limit, status | Mảng bare; header phân trang |
| GET /api/v1/coordination/suggestions | offset, limit | Mảng bare; header phân trang |
| GET /api/v1/coordination/directives | offset, limit, status | Mảng bare; header phân trang |
| GET /api/v1/coordination/directives/{directive_id}/candidates | offset, limit | Mảng bare; header phân trang |
| GET /api/v1/coordination/department-directives | offset, limit, status | Mảng bare; header phân trang |
| GET /api/v1/performance | employee_id, department_id, start_date, end_date, offset, limit | Mảng bare PerformanceMetricResponse; header phân trang; frontend hiện không truyền offset/limit và dùng mặc định backend |
| Các endpoint analytics/overview còn lại | Bộ lọc riêng | Không phân trang theo contract hiện tại |

ListQueryParams dùng page mặc định 1, page_size mặc định 20, tối đa 100. Endpoint department-evaluations có page_size legacy mặc định 12 ở route chung, nhưng khi gọi qua v1 sẽ ưu tiên offset/limit với limit mặc định 100. get_pagination dùng offset mặc định 0, limit mặc định 100, tối đa 100. Không suy ra kiểu phân trang chỉ từ tên response; phải theo mapping này và OpenAPI hiện hành.

### 8.8 Cơ chế Idempotency-Key

| Thuộc tính | Contract đã xác nhận |
|---|---|
| Header | Idempotency-Key, tùy chọn; thiếu header thì route xử lý bình thường |
| Độ dài | Tối đa 255 ký tự; vượt giới hạn trả 400 với code bad_request trong dependency route |
| Route áp dụng | Chỉ các mutation đã gắn dependency: daily review, task directive, alert directive, coordination fulfillment, upload session và upload completion; không mặc nhiên áp dụng cho mọi POST/PATCH/DELETE |
| Claim pending | TTL 30 giây; dùng để chặn request đồng thời cùng key |
| Bản ghi hoàn tất | TTL theo IDEMPOTENCY_TTL_SECONDS, mặc định 86400 giây (24 giờ) |
| Cùng key và cùng request body | Nếu đã hoàn tất, trả lại status/body/header của response gốc và thêm Idempotency-Replayed: true; X-Request-ID của request hiện tại vẫn được gắn lại |
| Cùng key nhưng khác body | Trả 409 với code conflict trong main app hiện tại |
| Cùng key khi request trước đang xử lý | Trả 409 với code conflict; client thử lại sau thời gian ngắn |
| Key hết hạn | Claim cũ bị loại bỏ, key có thể được dùng lại như request mới |
| Lưu trạng thái | RedisIdempotencyStore khi cấu hình và khởi tạo được Redis; nếu store không sẵn sàng, request có key trả 503 với code http_error |
| Phạm vi key | Key được scope theo route scope và identity người dùng, không dùng chung tùy ý giữa user/route |

Khi IDempotency bị tắt bằng killswitch, dependency không đọc header và không chạm Redis. Khi handler lỗi và dependency còn kiểm soát được luồng, claim được release; nếu tiến trình chết, pending TTL 30 giây là giới hạn an toàn còn lại. Frontend chỉ nên gửi cùng key khi retry cùng một request body.

### 8.9 Chính sách deprecation và compatibility alias

| Alias/legacy surface | Canonical hoặc chính sách hiện hành | Trạng thái | Sunset/owner |
|---|---|---|---|
| /api/* (trừ auth/health ngoại lệ header) | /api/v1/* | Compatibility; middleware thêm Deprecation: true, Sunset và Link successor-version | Sunset mặc định 2027-03-01T00:00:00Z; owner cá nhân chưa cấu hình |
| /api/health | /api/v1/health | Compatibility alias | Cùng legacy_api_sunset; owner chưa cấu hình |
| /api/v1/coordination/alerts/{id}/apply | /api/v1/coordination/alerts/{id}/plans | Deprecated trong OpenAPI; frontend hiện đã dùng canonical | Chưa có ngày gỡ riêng; owner chưa cấu hình |
| /api/v1/attachments/upload-sessions/{id}/complete | /api/v1/upload-sessions/{id}/completions | Deprecated trong OpenAPI; frontend hiện đã dùng canonical | Chưa có ngày gỡ riêng; owner chưa cấu hình |
| /api/v1/performance/daily-review* | /api/v1/performance/daily-reviews* là native plural route | Compatibility surface còn tồn tại; frontend hiện đang gọi singular | Chưa có sunset riêng trong code; owner chưa cấu hình |
| /api/v1/attachments/upload-sessions* | /api/v1/upload-sessions* | Compatibility prefix v1 còn tồn tại; frontend gọi root prefix | Chưa có sunset riêng trong code; owner chưa cấu hình |
| Bearer khi LEGACY_BEARER_ENABLED=true | Cookie phiên + CSRF cho mutation | Flag-gated compatibility | Chưa có sunset trong code; owner chưa cấu hình |
| WS query token khi LEGACY_WS_QUERY_TOKEN_ENABLED=true | Cookie qua WebSocket handshake | Flag-gated compatibility | Chưa có sunset trong code; owner chưa cấu hình |

Legacy /api được log qua LegacyApiUsageMiddleware nhưng không bị chặn. Các v1 alias không tự nhận Sunset chỉ vì có chữ compatibility; muốn gỡ phải bổ sung ngày, owner, caller inventory, OpenAPI/test gate và Changelog. Owner mặc định ở cấp bàn giao nên là nhóm platform/backend cùng frontend caller owner, nhưng chưa gán tên người trong code.

### 8.10 Ví dụ JSON cho pattern chuẩn

CRUD create:

~~~json
{
  "name": "Kinh doanh",
  "code": "KD",
  "specialty": "Bán hàng",
  "description": "Phòng phụ trách hoạt động kinh doanh",
  "is_active": true
}
~~~

Response 201 là DepartmentResponse bare:

~~~json
{
  "id": "dept_123",
  "name": "Kinh doanh",
  "code": "KD",
  "specialty": "Bán hàng",
  "description": "Phòng phụ trách hoạt động kinh doanh",
  "is_active": true,
  "created_at": "2026-09-16T09:32:11Z",
  "updated_at": "2026-09-16T09:32:11Z"
}
~~~

Page-based list:

~~~json
{
  "items": [
    {
      "id": "dept_123",
      "name": "Kinh doanh",
      "code": "KD",
      "specialty": "Bán hàng",
      "description": null,
      "is_active": true,
      "created_at": "2026-09-16T09:32:11Z",
      "updated_at": "2026-09-16T09:32:11Z"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 42,
  "has_next": true
}
~~~

Offset-based list:

~~~text
GET /api/v1/coordination/suggestions?offset=0&limit=20

HTTP/1.1 200 OK
X-Total-Count: 42
X-Offset: 0
X-Limit: 20
Link: </api/v1/coordination/suggestions?offset=20&limit=20>; rel="next"

[{"id":"sug_1","employee_id":"emp_456","status":"pending"}]
~~~

Lỗi V1ApiError:

~~~json
{
  "code": "validation_error",
  "message": "Dữ liệu không hợp lệ",
  "details": {
    "errors": [
      {
        "type": "value_error",
        "loc": ["body", "score"],
        "msg": "Giá trị không hợp lệ"
      }
    ]
  },
  "request_id": "req_abc123"
}
~~~

Response lỗi luôn có X-Request-ID cùng giá trị request_id. Nội dung message trong ví dụ chỉ minh họa; code mới là giá trị để frontend switch-case.

### 8.11 WebSocket message contract

Endpoint /ws/realtime xác thực cookie trước; query token chỉ được chấp nhận khi LEGACY_WS_QUERY_TOKEN_ENABLED bật. Cookie và query token cùng có mặt nhưng khác nhau thì đóng socket với code 1008. Thiếu hoặc token không hợp lệ cũng đóng 1008; bị rate limit đóng 1013.

Message runtime server gửi về client là object JSON sau, hiện chưa có Pydantic/OpenAPI schema riêng:

~~~json
{
  "topic": "alerts",
  "operation": "update",
  "data": {
    "id": "alert_123",
    "employee_id": "emp_456",
    "department_id": "dept_123",
    "status": "open"
  }
}
~~~

| topic hợp lệ | Nguồn thay đổi |
|---|---|
| alerts | alerts.changed |
| performance_metrics | performance_metrics.changed |
| tasks | tasks.changed |
| department_directives | department_directives.changed |
| task_directives | task_directives.changed |
| task_execution_reports | task_execution_reports.changed |
| department_evaluations | department_evaluations.changed |

operation lấy từ MongoDB change stream operationType, thường là insert, update, replace hoặc delete. data là fullDocument/fullDocumentBeforeChange nếu có, nếu không thì documentKey; ObjectId được chuyển thành string và datetime thành ISO string. Server không gửi field scope/timestamp bổ sung trong payload hiện tại.

Leadership nhận event toàn công ty. Manager chỉ nhận event có department_id hoặc target_department_id trùng phòng ban của mình. Client có thể gửi text để giữ kết nối, nhưng nội dung client gửi hiện bị bỏ qua; không có client-to-server event schema nghiệp vụ.

### 8.12 Giới hạn vận hành và Known Issues

#### Rate limit

Các rate limit dưới đây dùng cửa sổ 60 giây. Giá trị là cấu hình hiện hành trong .env.example; nếu Settings được override bằng môi trường thì runtime có thể khác và phải ghi evidence khi triển khai.

| Nhóm | Giới hạn/60 giây |
|---|---:|
| login | 10 |
| ai_chat | 10 |
| upload_session | 10 |
| upload_completion | 30 |
| scan | 5 |
| mutation | 30 |
| directive | 20 |
| read_light/read_operational | 120 |
| read_heavy | 30 |
| websocket_handshake | 10 |
| health | bypass |

Rate-limit response 429 có Retry-After, X-RateLimit-Limit, X-RateLimit-Remaining và X-RateLimit-Reset. RATE_LIMIT_SHADOW_MODE và RATE_LIMIT_FAIL_MODE vẫn là các biến cần xác nhận riêng ở môi trường production; mặc định trong code/example là shadow và fail-open.

#### File và upload

- Kích thước file tối đa: 10 MiB (10485760 bytes).
- Mỗi evaluation tối đa 5 file.
- MIME được cho phép: PDF, DOC/DOCX, XLS/XLSX, PPT/PPTX, PNG, JPEG và text/plain; service còn kiểm tra extension/MIME tương ứng và checksum SHA-256.
- Signed download URL có TTL 900 giây; upload URL có TTL 600 giây; upload session có TTL 900 giây.
- STORAGE_DIRECT_UPLOAD_ENABLED mặc định false; khi tắt, tạo upload session trả 503.

#### Known Issues

| ID | Vấn đề | Owner chịu trách nhiệm | Deadline | Tác động/điều kiện đóng |
|---|---|---|---|---|
| FE-API-001 | Frontend POST /api/v1/department-evaluations/weekly-review nhưng backend hiện có POST /api/v1/department-evaluations/weekly-evaluations | Frontend department-evaluations owner + Backend API owner; cá nhân chưa được repo xác định | Trước khi đóng contract; ngày cụ thể chưa được repo xác định | Sửa caller hoặc khôi phục alias có chủ đích; chạy caller/OpenAPI/runtime test |
| API-DEP-001 | Một số v1 compatibility alias chưa có sunset riêng | Platform/API owner; cá nhân chưa được repo xác định | Trước khi retire alias; ngày cụ thể chưa được repo xác định | Xác định canonical, owner, ngày gỡ và kiểm tra caller/test trước khi retire |
| API-IDEM-001 | Code idempotency structured trong IdempotencyMiddleware khác code generic của dependency route đang dùng trong main app | Backend platform/API contract owner; cá nhân chưa được repo xác định | Trước khi chốt error contract; ngày cụ thể chưa được repo xác định | Hoặc thống nhất handler code, hoặc ghi rõ contract generic trong OpenAPI/test |
| WS-CONTRACT-001 | WebSocket payload là runtime dict, chưa có Pydantic/OpenAPI schema | Backend realtime owner; cá nhân chưa được repo xác định | Trước khi chốt WS versioning; ngày cụ thể chưa được repo xác định | Thêm schema/versioning hoặc giữ bảng runtime contract và test topic/scope |

Bốn issue vẫn ở trạng thái Open, chưa được coi là đã đóng. Code hiện tại không chứa mapping tên người hoặc ngày cam kết nên tài liệu không tự gán giá trị “thật”. Closure gate bắt buộc điền owner cá nhân và deadline ISO cụ thể cho từng dòng, sau đó cập nhật Status/Changelog và chạy lại caller, OpenAPI cùng runtime evidence liên quan.

## 9. Changelog

| Ngày | Thay đổi | Kiểm chứng |
|---|---|---|
| 2026-09-16 | Áp dụng tier 1/2/3, CRUD/list pattern, catalog 62 frontend route-method, common error/auth contract và ghi nhận evaluation caller mismatch. | backend/scripts/check_api_callers.py đạt; backend/scripts/check_app.py sinh và kiểm tra OpenAPI route hiện tại. |
| 2026-09-16 | Bổ sung response bare/envelope, định nghĩa tier, RBAC/scope, error code enum, mapping pagination, Idempotency-Key, deprecation policy, JSON examples, WebSocket message contract, rate/file limits và Known Issues theo code hiện tại. | Đối chiếu backend/app/core/http_contract.py, pagination.py, infrastructure/idempotency.py, core/api_deprecation.py, realtime/connection_manager.py, model Pydantic và .env.example. |

Từ lần sau, không viết lại catalog này. Chỉ thêm diff vào bảng trên theo mẫu: route-method, before, after, caller bị ảnh hưởng, schema/model, business side-effect và test đã chạy.
