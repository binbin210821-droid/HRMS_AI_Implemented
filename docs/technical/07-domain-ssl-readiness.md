# Domain & SSL Readiness Checklist

> Trạng thái hiện tại: chưa cấu hình domain chính thức. Production compose/workflow chỉ chứng minh được host SSH, port frontend và health check nội bộ; chưa có DNS certificate/Cloudflare zone runtime trong repo.

## 1. Giá trị cần chốt

| Hạng mục | Placeholder | Nguồn thay đổi |
|---|---|---|
| Public application origin | `https://<APP_DOMAIN>` | GitHub `APP_URL`, tài liệu vận hành |
| API origin nếu tách riêng | `https://api.<APP_DOMAIN>` hoặc same-origin | Nginx/CORS/frontend config |
| Worker origin | `https://<worker>.<account>.workers.dev` hoặc custom subdomain | Worker contract, FastAPI runtime |
| AWS/EC2 public endpoint nếu chốt AWS/EC2 | `<ELASTIC_IP_OR_HOSTNAME>` | DNS A/CNAME, security group sau khi chốt hạ tầng |
| Storage public endpoint | `https://<storage-domain>` | `STORAGE_PUBLIC_ENDPOINT_URL` |
| Cookie domain | `<APP_DOMAIN>` hoặc để host-only | `AUTH_COOKIE_DOMAIN` |

## 2. DNS plan

- [ ] Chọn canonical host, ví dụ `app.<domain>`.
- [ ] Nếu Nginx/EC2 nhận traffic trực tiếp: A record `app` → Elastic IP; cập nhật khi IP đổi.
- [ ] Nếu dùng AWS load balancer: A/ALIAS tới LB; không trỏ trực tiếp instance private IP.
- [ ] Nếu tách API: CNAME/A `api` → API endpoint/LB và quyết định CORS chính xác.
- [ ] Nếu dùng Worker custom domain: route/CNAME theo Cloudflare account; giữ `workers.dev` làm fallback chỉ khi policy cho phép.
- [ ] TTL thấp trong cutover, sau đó tăng theo vận hành.
- [ ] Xác nhận DNS propagation từ ít nhất hai mạng ngoài AWS.

## 3. TLS/HTTPS plan

- [ ] Cấp certificate cho mọi hostname public (app/api/worker nếu cần).
- [ ] Chọn termination tại Cloudflare, ALB hoặc Nginx; chỉ một nơi là canonical TLS boundary.
- [ ] Redirect HTTP → HTTPS.
- [ ] Kiểm tra WebSocket upgrade qua HTTPS (`wss://`) và SSE không bị buffering timeout ở proxy.
- [ ] Cấu hình renewal/monitoring trước ngày hết hạn.
- [ ] Bật `AUTH_COOKIE_SECURE=true` sau khi HTTPS đã hoạt động; kiểm tra SameSite/cross-subdomain.

## 4. Biến môi trường cần đổi từ local/IP

- [ ] `CORS_ORIGINS=https://<APP_DOMAIN>`; không wildcard.
- [ ] `AUTH_COOKIE_SECURE=true`.
- [ ] `AUTH_COOKIE_DOMAIN` chỉ đặt khi thật sự cần chia sẻ cookie giữa subdomain.
- [ ] `STORAGE_PUBLIC_CORS_ORIGINS=https://<APP_DOMAIN>`.
- [ ] `STORAGE_PUBLIC_ENDPOINT_URL=https://<storage-domain>`.
- [ ] `VITE_DEV_API_ORIGIN` không phải cấu hình production; production frontend dùng same-origin/proxy hiện tại.
- [ ] Nếu tách API: thêm và kiểm soát biến frontend base URL bằng cách được phê duyệt; không đặt secret trong `VITE_*`.
- [ ] Nếu tách Worker: thêm `AI_WORKER_BASE_URL` và `AI_WORKER_SHARED_SECRET` ở backend/Worker secret store.
- [ ] Nếu dùng OpenRouter, cập nhật `HTTP-Referer` provider theo URL chính thức khi domain được chốt; code hiện tại đang gửi giá trị development `http://localhost:5173`.

## 5. Go/no-go trước khi public

- [ ] DNS đúng endpoint và không còn public IP cũ trong docs/config.
- [ ] TLS A+ hoặc tiêu chuẩn tổ chức đạt; certificate renewal tested.
- [ ] CORS preflight và CSRF mutation qua domain thật.
- [ ] Login cookie được đặt đúng domain/secure/samesite.
- [ ] Authenticated Manager/Leadership smoke không vượt scope.
- [ ] WebSocket/SSE hoạt động qua proxy thật.
- [ ] Nếu hạ tầng đích là AWS, Atlas chỉ allow egress IP/private network tương ứng của hạ tầng đó; giá trị AWS account/region/Elastic IP/network cụ thể vẫn phải được chốt và xác minh runtime.
- [ ] CloudWatch/container logs và alerting đã có owner; nếu Worker tách riêng thì `wrangler tail` đã được kiểm tra.
- [ ] Rollback tag đã được thử ở staging.
