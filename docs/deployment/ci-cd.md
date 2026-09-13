# CI/CD cho WorkMind

## Luồng triển khai

```text
Pull Request -> CI quality + integration + security
Merge main  -> CI lại + build image kiểm tra
Tag vX.Y.Z  -> push image lên GHCR -> chờ duyệt Environment production -> deploy SSH
```

## Các workflow trong repository

- `.github/workflows/ci.yml`: Ruff, Mypy, compile, pytest, kiểm tra contract, frontend
  lint/format/test/build, UI-only E2E, live E2E có backend + dữ liệu seed, MongoDB Replica Set +
  Redis integration và build thử image.
- `.github/workflows/security.yml`: Dependency Review trên Pull Request và CodeQL định kỳ.
- `.github/workflows/cd.yml`: build/push hai image lên GHCR và deploy production có approval.

## Thiết lập GitHub

1. Push repository lên GitHub.
2. Vào `Settings -> Environments`, tạo `production`.
3. Bật `Required reviewers`, chọn người duyệt deploy và giới hạn deployment branch/tag nếu cần.
4. Thêm Environment variable `APP_URL`.
5. Thêm Environment secrets:

   - `SSH_HOST`
   - `SSH_USER`
   - `SSH_PRIVATE_KEY`
   - `SSH_KNOWN_HOSTS`
   - `DEPLOY_PATH`

6. Vào `Settings -> Actions -> General`, cho phép workflow dùng Actions cần thiết và giữ
   `GITHUB_TOKEN` ở quyền tối thiểu.
7. Vào `Settings -> Rules -> Rulesets` hoặc branch protection của `main`, bắt buộc các check:
   `Backend quality`, `Frontend quality`, `Frontend live E2E`, `MongoDB and Redis integration`,
   `Container build`.

## Chuẩn bị máy production

Máy chủ cần có Docker Engine, Docker Compose v2 và SSH public key của GitHub Actions. Tạo thư
mục deploy, copy `docker-compose.production.yml` vào đó, rồi tạo `.env.production` trên server.

`.env.production` không được commit. Tối thiểu phải cấu hình:

```text
ENVIRONMENT=production
MONGO_URI=<MongoDB production có auth và replica set phù hợp>
DATABASE_NAME=hrms
REDIS_URL=<Redis production>
JWT_SECRET=<secret riêng tối thiểu 32 ký tự>
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=https://<domain-frontend>
STORAGE_PUBLIC_ENDPOINT_URL=https://<storage-domain>
STORAGE_INTERNAL_ENDPOINT_URL=<endpoint nội bộ>
STORAGE_ACCESS_KEY=<credential riêng>
STORAGE_SECRET_KEY=<credential riêng>
MALWARE_SCANNER_ENABLED=true
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_SHADOW_MODE=false
```

Nếu GHCR để private, đăng nhập GHCR một lần trên server bằng token chỉ có quyền
`read:packages`. Không dùng Personal Access Token có quyền ghi repository.

## Cách phát hành

```powershell
git add -A
git diff --cached --check
git commit -m "chore: establish CI/CD pipeline"
git push origin main

git tag v0.1.0
git push origin v0.1.0
```

Push `main` chỉ chạy CI. Push tag `vX.Y.Z` mới kích hoạt CD production; workflow sẽ dừng ở
Environment approval nếu `production` đã bật required reviewer.

## Migration database

Workflow không tự động chạy migration MongoDB. Trước production:

1. Backup database.
2. Chạy migration trên staging.
3. Kiểm tra index và data integrity.
4. Duyệt deploy production.
5. Chạy migration idempotent bằng lệnh có kiểm soát và ghi nhận vào `CHANGELOG.md`.

## Kiểm tra local trước khi push

```powershell
docker compose -f docker-compose.ci.yml config
docker build -t hrms-backend:ci ./backend
docker build -t hrms-frontend:ci ./frontend
git diff --check
```

Không dùng `git clean -fdx` trong workspace có `.env`, `.venv` hoặc `node_modules`.
