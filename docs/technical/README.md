# Bộ tài liệu kỹ thuật WorkMind

> Phiên bản rà soát: 2026-09-14. Phạm vi: checkout hiện tại của `HRMS_v2`.

Bộ tài liệu này được trích xuất từ source/config hiện có, không phải bản thiết kế giả định. Mỗi tài liệu phân biệt:

- **Đã có bằng chứng**: thấy trực tiếp trong mã nguồn, workflow, compose hoặc README.
- **Cần xác nhận runtime**: cần giá trị môi trường, tài khoản cloud, log hoặc kiểm thử triển khai thật.
- **Cần bổ sung**: chưa thấy artifact tương ứng trong checkout.

## Mục lục

| Tài liệu | Nội dung | Trạng thái |
|---|---|---|
| [01 — SRS](01-srs.md) | Phạm vi, actor, yêu cầu chức năng/phi chức năng, tiêu chí nghiệm thu | Đã phác thảo từ README và module hiện hành |
| [02 — Use Case & Traceability](02-use-cases-and-traceability.md) | Use case, SSD AI, ma trận Use Case → endpoint → collection | Đã phác thảo; cần chốt business owner |
| [03 — System Architecture](03-system-architecture.md) | Luồng React/Vite, Nginx, FastAPI, MongoDB, Redis, storage, AI và realtime | Hiện trạng có bằng chứng; AWS/Worker/domain còn placeholder |
| [04 — MongoDB Data Specs](04-mongodb-data-spec.md) | Collection, Pydantic model, reference, index và Atlas security | Schema/index trích được; Atlas runtime cần xác nhận |
| [05 — API & AI Worker Contract](05-api-and-worker-contract.md) | OpenAPI, auth, lỗi, AI streaming và hợp đồng Worker mục tiêu | API v1 hiện có; Worker riêng chưa có |
| [06 — CI/CD, Secrets & Runbook](06-cicd-secrets-operations.md) | GitHub Actions, secret matrix, vận hành, log, rollback | CI/CD/rollback có; CloudWatch/wrangler cần bổ sung |
| [07 — Domain & SSL Readiness](07-domain-ssl-readiness.md) | Checklist đổi từ IP/AWS DNS sang domain HTTPS | Chưa cấu hình domain |

## Nguồn bằng chứng chính

- `README.md`, `docs/deployment/ci-cd.md`, `.env.example`.
- `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/app/api/v1/`.
- `backend/app/models/`, `backend/app/repositories/`, `backend/app/services/`, `backend/app/ai/`, `backend/app/realtime/`.
- `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `.github/workflows/security.yml`.
- `docker-compose.yml`, `docker-compose.production.yml`, `backend/Dockerfile`, `frontend/Dockerfile`.

## Khoảng trống cần xử lý trước production

1. Ghi nhận AWS account/region/EC2 hostname hoặc Elastic IP, security group, CloudWatch log group và storage/IAM thật.
2. Quyết định Cloudflare AI chạy trực tiếp từ FastAPI hay qua một Worker riêng; nếu qua Worker, thêm source, deployment và secret contract cho Worker.
3. Tạo Atlas project/cluster/database user/network access và chốt danh sách index production.
4. Mua/cấu hình domain, TLS, DNS, `CORS_ORIGINS`, auth cookie domain và các URL frontend/backend.
5. Chạy kiểm thử authenticated trên môi trường staging và lưu kết quả vào release/change record.

