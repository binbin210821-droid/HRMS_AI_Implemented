# MongoDB Atlas Data Specifications

## 1. Quy ước dữ liệu

- Driver: request path dùng Motor async; một số script/repository dùng PyMongo; model validation bằng Pydantic.
- ID nội bộ: đa số document nghiệp vụ dùng BSON `ObjectId`, nhưng `ai_conversations._id` và `attachment_upload_sessions._id` là chuỗi; response thường serialize ID thành string.
- Ngày nghiệp vụ dùng `Asia/Ho_Chi_Minh`; `BusinessClock` chuyển mốc ngày nghiệp vụ sang UTC trước khi query/lưu timestamp.
- Manager query bị gắn `department_id` ở repository/service; Leadership dùng scope `None` để xem toàn công ty.
- Docker Compose local cấu hình MongoDB replica set `rs0`. MongoDB Compass đã kết nối Atlas; backend production đã được xác nhận trỏ đúng Atlas qua `MONGO_URI`. Network Access/RBAC, Change Streams, regular indexes, Atlas Vector Search index và Backup/PITR đã được xác minh theo runtime evidence do chủ dự án cung cấp. Giá trị URI, IP, username/role và thông tin backup cụ thể không lưu trong tài liệu.

## 2. Collection và document shape chính

| Collection | Model/source | Trường chính hoặc quan hệ |
|---|---|---|
| `users` | `backend/app/models/user.py`, `backend/app/repositories/user_repository.py` | `username`, `password_hash`, `full_name`, `role`, `department_id?`, `is_active`, `created_at`; role manager/leadership. Model hiện không có `updated_at`. |
| `departments` | `backend/app/models/department.py`, `backend/app/repositories/department_repository.py` | `name`, `code`, `specialty`, `description`, `is_active`, timestamps; employee reference qua `employees.department_id`. |
| `employees` | `backend/app/models/employee.py`, `backend/app/repositories/employee_repository.py` | `employee_code`, `full_name`, `email?`, `phone?`, `position`, `skills[]`, `department_id`, `is_active`, timestamps. |
| `performance_metrics` | `backend/app/models/performance.py`, `backend/app/repositories/performance_repository.py` | `employee_id`, `date`, `tasks_completed`, `quality_score`, `reviewed_by`, `performance_score`, `note`, evidence/review counters, timestamps. |
| `tasks` | `backend/app/models/task.py`, `backend/app/repositories/task_repository.py` | title, description/subtasks, estimated effort, required skills, employee/department, priority/status, due/completed, creator, timestamps; cùng model file có task directives. |
| `task_execution_reports` | `backend/app/models/task_execution.py`, `backend/app/repositories/task_execution_repository.py` | task/employee/department/work date, result/progress/outcome, attachments, manager review/evidence/missing reason, timestamps. |
| `alerts` | `backend/app/models/alert.py`, `backend/app/repositories/alert_repository.py` | type/severity/status, employee/department, message/action, detected dates, unique fingerprint, resolution. |
| `overload_logs` | `backend/app/models/overload.py`, `backend/app/repositories/overload_repository.py` | employee/department/date, `trigger_reason[]`, task/quality/baseline values, created time. |
| `threshold_configs` | `backend/app/models/threshold.py`, `backend/app/repositories/threshold_repository.py` | department?, consecutive days, quality drop, status, proposer/approver, timestamps. |
| `department_weekly_evaluations` | `backend/app/models/department_evaluation.py`, `backend/app/repositories/department_evaluation_repository.py` | department/week, score fields, note, evidence snapshot, attachments, evaluator, evaluation timing, timestamps. |
| `department_alert_directives` | `backend/app/models/coordination.py`, `backend/app/repositories/coordination_repository.py` | alert directive lifecycle, target department, selected alert summary, acknowledgement/commitment/completion/revision fields. |
| `department_task_directives` | `backend/app/models/task.py`, `backend/app/repositories/task_repository.py` | overdue/at-risk task directive lifecycle, target/status/focus and acknowledgement fields. |
| `coordination_plans` | `backend/app/models/coordination.py`, `backend/app/repositories/coordination_repository.py` | alert link, source/target department and employee, tasks to transfer, mode/note, timestamps; unique alert plan. |
| `coordination_directives` | `backend/app/models/coordination.py`, `backend/app/repositories/coordination_repository.py` | cross-department directive, source/target, tasks/note, status and fulfilment lifecycle. |
| `audit_logs` | `backend/app/repositories/task_repository.py`, `backend/app/repositories/coordination_repository.py` | action, actor, scope/context, created time; AI governance separately hashes/summarizes prompt/output and does not store raw content. |
| `ai_conversations` | `backend/app/repositories/ai_conversation_repository.py` | string `conversation_id` as `_id`, user, department scope, last tool name/arguments, timestamps; bounded continuity context. |
| `ai_audit_logs` | `backend/app/ai/governance.py` | provider/model/action/request metadata, bounded input/output summaries and hashes, status, actor/scope and timestamp. |
| `ai_knowledge_chunks` | `backend/app/ai/rag.py`, `backend/app/models/ai_rag.py` | approved knowledge chunks, string document/chunk IDs, optional department scope, embedding and metadata; RAG optional. |
| `attachment_upload_sessions` | `backend/app/models/attachment.py`, `backend/app/repositories/attachment_upload_repository.py` | string `_id`, owner/scope, target/week/task/work date, storage key, expiry/status, checksum/size/MIME. |

## 3. Reference và integrity

- `employees.department_id → departments._id`.
- `users.department_id → departments._id` với `null` cho Leadership.
- `performance_metrics.employee_id → employees._id`; reviewer là `users._id`.
- `tasks.employee_id → employees._id`; `tasks.department_id → departments._id`.
- `alerts`, `overload_logs`, directives và evaluations giữ `department_id` để query scope nhanh; service vẫn kiểm tra entity liên quan.
- Attachment metadata nằm trong evaluation/report và upload session; object thật nằm storage và chỉ trả signed URL.
- Đây là reference ở tầng application, không phải foreign key do MongoDB cưỡng chế. Các service/repository có kiểm tra entity và department scope trong các flow tương ứng; ví dụ task phải khớp employee/department, upload phải khớp department/task, evaluation phải khớp department/manager.

## 4. Index hiện thấy trong code và Atlas

| Collection | Index hiện có trong repository/service |
|---|---|
| `alerts` | unique `fingerprint`; `(department_id, status)`. |
| `overload_logs` | unique `(employee_id, date, trigger_reason)`; `(department_id, date)`. |
| `performance_metrics` | unique composite `(employee_id, date)` do `PerformanceRepository.ensure_indexes` tạo; đã đối chiếu với regular indexes trên Atlas. |
| `threshold_configs` | `(department_id, status, updated_at)`; `(created_at)`. |
| `tasks` | unique partial `seed_key`; employee/status; department/due date; directive lifecycle indexes. |
| `task_execution_reports` | employee/work date, department/work date, unique/partial seed-key path. |
| `coordination_plans` | unique `alert_id`; department/created time; directive status/target. |
| `department_weekly_evaluations` | department/week và các index repository tạo. |
| `attachment_upload_sessions` | index thường trên `expires_at` (không phải TTL index), cùng owner/status và unique storage-key/status paths; cleanup hết hạn do repository/service xử lý. |
| `ai_knowledge_chunks` | Atlas Vector Search index `ai_knowledge_embedding` đã được tạo và xác nhận ở trạng thái sẵn sàng truy vấn; definition khớp code: vector path `embedding`, cosine, filter `department_id`, dimensions 1024. |

Các regular indexes đã được đối chiếu bằng `listIndexes()` trên Atlas. Bảng vẫn phải được cập nhật nếu query/sort hoặc `ensure_indexes()` thay đổi; không coi việc tạo index thủ công là thay thế cho migration/idempotent index path trong code.

## 5. Atlas security/network checklist

> Trạng thái xác minh runtime: backend production đã trỏ đúng MongoDB Atlas. Network Access và RBAC, Change Streams, regular indexes, Atlas Vector Search index và Backup/PITR đã được chủ dự án xác nhận đạt. Không ghi URI, credential, IP allowlist, database username/role cụ thể hoặc thông tin backup nhạy cảm vào tài liệu.

- Database user riêng cho application; RBAC đã được xác minh theo quyền được cấp trên database `DATABASE_NAME`.
- Password trong URI phải URL-encode; không commit URI hoặc in ra log.
- Network Access đã được xác minh theo đường kết nối production; không ghi IP/NAT/private endpoint cụ thể vào tài liệu.
- Kết nối Atlas và replica set/Atlas SRV target đã được xác minh; thông tin TLS/authSource cụ thể không lưu trong repo.
- Backup/point-in-time recovery và retention đã được xác minh trong Atlas project theo evidence runtime; không ghi thông tin retention/backup location nhạy cảm.
- Change Streams đã được smoke test và hoạt động với replica set/Atlas production.
- Atlas Vector Search index đã sẵn sàng truy vấn; RAG chỉ sử dụng index khi `AI_RAG_ENABLED=true`, local fallback vẫn mặc định tắt.

Ảnh hoặc run log chứng minh các trạng thái trên nên được lưu ngoài repository theo mã evidence, che connection string, credential, IP nhạy cảm và thông tin người dùng.

## 6. Hướng dẫn bổ sung ảnh minh chứng

Phần này dùng để hoàn thiện hồ sơ xác minh MongoDB Atlas/Compass. Mỗi ảnh nên hiển thị rõ tên project, cluster, database hoặc collection liên quan và thời điểm chụp. Không chụp hoặc chia sẻ connection string, mật khẩu, API key, token, IP allowlist đầy đủ hay thông tin cá nhân không cần thiết.

### 6.1. Backend production đang trỏ đúng Atlas

Chụp một trong các bằng chứng sau:

- MongoDB Atlas: trang cluster/Database Deployments thể hiện cluster đang hoạt động.
- EC2: lệnh kiểm tra biến môi trường nhưng chỉ in trạng thái đã cấu hình, không in giá trị bí mật:

  ```bash
  docker compose -f /opt/workmind/docker-compose.production.yml config >/tmp/workmind-compose-check.txt
  grep -E 'MONGO_URI|MONGODB_URI|DATABASE_NAME' /opt/workmind/.env.production | sed -E 's/(=.*)/=<redacted>/'
  ```

- EC2: log hoặc health response cho thấy backend đang khởi động và kết nối được database. Nếu log có hostname/URI, che phần nhạy cảm trước khi lưu ảnh.

Tên evidence gợi ý: `mongodb-01-production-atlas-connection.png`.

### 6.2. Network Access và RBAC

- Atlas → **Security → Database & Network Access → Network Access**: chụp allowlist hoặc private connection đang dùng. Che IP nếu cần.
- Atlas → **Database Access**: chụp database user và role được cấp; che username nếu đó là thông tin nhạy cảm, tuyệt đối không chụp password.
- Nếu có trang role details, chụp phần database/collection scope để chứng minh quyền không vượt quá nhu cầu của application.

Tên evidence gợi ý:

- `mongodb-02-network-access.png`
- `mongodb-03-database-user-rbac.png`

### 6.3. Change Streams

Change Streams không nhất thiết có một màn hình trạng thái riêng. Cần lưu bằng chứng kết hợp:

1. Atlas cluster là replica set/cluster hỗ trợ Change Streams.
2. EC2 hoặc log runtime cho thấy worker Change Stream đã khởi động.
3. Tạo một thay đổi test ở collection phù hợp, sau đó chụp log/event hoặc giao diện nhận cập nhật realtime.

Ví dụ lệnh quan sát log:

```bash
docker compose -f /opt/workmind/docker-compose.production.yml logs --tail=200 backend
```

Không đưa dữ liệu nhân sự thật vào ảnh. Nếu dùng bản ghi test, có thể che `_id`, email và nội dung nghiệp vụ.

Tên evidence gợi ý: `mongodb-04-change-stream-runtime.png`.

### 6.4. Regular indexes và `listIndexes()`

Trong MongoDB Compass hoặc `mongosh`, chọn database `hrms`, collection cần kiểm tra và mở tab **Indexes**. Chụp danh sách index, gồm tên, key pattern, unique/partial option nếu có.

Có thể dùng lệnh sau trong `mongosh`:

```javascript
use hrms
db.getCollectionNames()
db.tasks.listIndexes().toArray()
db.performance_metrics.listIndexes().toArray()
db.alerts.listIndexes().toArray()
db.overload_logs.listIndexes().toArray()
```

Đối chiếu key pattern với mục 4 của tài liệu và với `ensure_indexes()` trong repository tương ứng. Nếu chụp kết quả JSON, chỉ cần giữ phần index definition; không cần hiển thị dữ liệu document.

Tên evidence gợi ý: `mongodb-05-regular-indexes-listindexes.png`.

### 6.5. Atlas Vector Search index

Vào Atlas → **Search & Vector Search**, chọn database `hrms` và collection `ai_knowledge_chunks`. Chụp màn hình thể hiện:

- index name: `ai_knowledge_embedding`;
- trạng thái `READY` hoặc trạng thái truy vấn tương đương;
- collection/database đúng;
- số lượng document được index nếu Atlas hiển thị.

Nếu cần chứng minh definition, mở phần JSON definition và chụp các trường không nhạy cảm như `embedding`, dimensions `1024`, similarity `cosine` và filter `department_id`. Không chụp credential hoặc dữ liệu embedding đầy đủ.

Tên evidence gợi ý: `mongodb-06-atlas-vector-search-ready.png`.

### 6.6. Backup/PITR

Vào Atlas → **Backup** hoặc **Backup & Restore** của cluster. Chụp trạng thái backup/PITR và retention hiện tại nếu gói dịch vụ hỗ trợ. Nếu gói hiện tại không hỗ trợ hoặc chưa bật backup, chụp trạng thái đó và ghi rõ `chưa cấu hình`/`không khả dụng theo gói`, không đánh dấu là đã đạt.

Không chụp thông tin thanh toán, project credential hoặc dữ liệu backup download. Nếu đã thực hiện restore test, lưu thêm ảnh thời điểm restore và kết quả kiểm tra dữ liệu sau restore.

Tên evidence gợi ý:

- `mongodb-07-backup-pitr-status.png`
- `mongodb-08-backup-restore-test.png` nếu có.

### 6.7. Quy tắc lưu hồ sơ ảnh

- Đặt mã evidence trong tên file và liên kết mã đó với mục xác minh tương ứng.
- Ghi ngày giờ, môi trường (`production`/`local`) và người thực hiện trong sổ evidence bên ngoài repository.
- Có thể lưu ảnh trong thư mục hồ sơ bàn giao riêng; không commit ảnh chứa secret vào Git.
- Trước khi gửi ảnh, kiểm tra lại các vùng có thể lộ `MONGO_URI`, password, token Cloudflare, IP công khai hoặc username database.
