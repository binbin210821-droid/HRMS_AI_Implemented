# UI-only baseline

Ngày ghi nhận: 2026-09-12

## Phạm vi bảo vệ

- Không sửa `backend/**` trong đợt chuẩn hóa giao diện.
- Không sửa URL API, HTTP method, query params, request body, response mapping,
  store dữ liệu, hook lấy dữ liệu hoặc logic nghiệp vụ.
- Kiểm thử UI ghi dữ liệu bị loại khỏi baseline; chỉ chạy các scenario đọc-only
  khi dịch vụ local sẵn sàng.

## Hiện trạng frontend

- React 19 + Vite + Tailwind CSS 3.4.
- Đã có Framer Motion, Recharts, Zustand và Playwright.
- Đã có các component dùng chung ban đầu trong `src/components/ui`:
  `Button`, `Card`, `FormField`, `Badge`, `StatusBadge` và các state message.
- Design token hiện nằm trong `tailwind.config.js` và `src/index.css`.

## Kết quả kiểm tra baseline

| Kiểm tra | Kết quả |
| --- | --- |
| `npm test -- --run` | Đạt: 40 file, 127 test |
| `npm run lint` | Đạt |
| `npm run build` | Đạt; cảnh báo bundle JS sau minify khoảng 1.14 MB |
| Playwright tích hợp | Chưa khả dụng trong phiên kiểm tra |
| Playwright CLI đọc-only | Đạt sau khi frontend local được khởi động |

Vitest và Vite từng bị sandbox chặn quyền đọc file cấu hình; chạy lại ngoài
sandbox đã đạt. Cảnh báo bundle được giữ làm mốc hiệu năng, không xử lý bằng
cách nâng cấp hoặc thay đổi API.

## Giai đoạn 1-2 đã thực hiện

- Bổ sung các primitive UI thuần frontend trong `src/components/ui`:
  `Input`, `Select`, `Textarea`, `Skeleton`, `Table` và `Toast`.
- Xuất các primitive qua `src/components/ui/index.js`.
- Áp dụng `Input`, `Select`, `Button` và `Table` cho `LoginPage` và
  `EmployeesPage` mà không thay đổi API call, payload, route hoặc store dữ liệu.
- Áp dụng tiếp `Button` cho Header/Sidebar và các primitive bảng cho
  `DepartmentsPage`, bao gồm bảng nhân viên mở rộng theo phòng ban.
- Áp dụng các primitive form/bảng và `Button` cho `TasksPage` và
  `AlertsPage`; chỉ thay đổi lớp trình bày và không thay đổi các handler/API.
- Bổ sung `Dialog` dùng lại modal hiện có, `Tooltip` có liên kết trợ năng, và
  chuẩn hóa nút retry trong `ErrorState`.
- Bổ sung kiểm thử component cho khả năng truy cập, bảng responsive, toast,
  skeleton và các trạng thái loading/empty/error.
- Áp dụng tiếp các primitive cho `PerformanceEntryPage`,
  `DepartmentEvaluationsPage`, `LeadershipTasksOverview`,
  `PerformanceDashboard` và `AiAssistantWidget`; riêng input file ẩn vẫn giữ
  native control để không ảnh hưởng upload.

## Kết quả sau đợt primitive đầu tiên

| Kiểm tra | Kết quả |
| --- | --- |
| `npm test -- --run src/components/ui` | Đạt: 3 file, 7 test |
| `npm test -- --run` | Đạt: 41 file, 131 test |
| `npm run lint` | Đạt |
| `npm run build` | Đạt; cảnh báo bundle JS khoảng 1.14 MB vẫn giữ nguyên dạng cảnh báo |

## Kết quả sau chuẩn hóa Header, Sidebar và Phòng ban

| Kiểm tra | Kết quả |
| --- | --- |
| Test UI/layout liên quan | Đạt: 4 file, 10 test |
| Full frontend regression | Đạt: 41 file, 131 test |
| `npm run lint` | Đạt |
| `npm run build` | Đạt; cảnh báo bundle vẫn ở mức khoảng 1.14 MB |

## Kết quả chuẩn hóa Công việc, Cảnh báo và smoke UI

| Kiểm tra | Kết quả |
| --- | --- |
| Test tập trung Tasks/Alerts/Coordination/UI | Đạt: 16 file, 50 test |
| `npx playwright test e2e/ui-only-smoke.spec.js` | Đạt: 2/2 (desktop 1440px và mobile 375px) |
| Screenshot baseline | Đã tạo desktop và mobile sau khi animation hoàn tất |

Smoke Playwright xác nhận các màn hình chưa đăng nhập không tạo request ghi dữ
liệu; các request đọc được mô phỏng phản hồi 401. Đây là kiểm tra trình bày và
ranh giới request, không thay thế nghiệm thu live workflow.

## Gate hiện tại sau khi hoàn thiện bộ UI dùng chung

| Kiểm tra | Kết quả |
| --- | --- |
| `npm test -- --run` | Đạt: 42 file, 136 test |
| `npm run lint` | Đạt, không warning |
| `npm run build` | Đạt; cảnh báo bundle JS khoảng 1.14 MB |
| Prettier trên các file UI thuộc phạm vi | Đạt |

Đợt này đã bổ sung đủ nhóm trạng thái loading/empty/error, tooltip trợ năng và
dialog dùng lại modal hiện có. Các phần UI còn lại tiếp tục được áp dụng theo
từng nhóm màn hình trong các đợt kế tiếp, vẫn theo ranh giới UI-only.

## Kiểm thử Playwright UI-only

- `npx playwright test e2e/ui-only-smoke.spec.js e2e/ui-only-role-smoke.spec.js`
  đạt 11/11: desktop/mobile, route chính của Manager và Leadership, route dữ liệu
  nền, redirect, fallback, menu mobile, điều hướng bằng bàn phím và panel Trợ lý
  AI. Hai test xác nhận nút ẩn/hiện và không gọi lại SSE khi chuyển từ Tổng quan
  sang Công việc rồi quay lại; một test xác nhận phiên ChatAI vẫn giữ nguyên khi
  điều hướng và khi Đóng/Mở cửa sổ chat.
- Role smoke đã kiểm tra Manager (`Tổng quan`, `Nhân viên phòng ban`, `Hiệu
  suất`, `Cảnh báo`, `Công việc`, `Trung tâm chỉ thị`) và Leadership (`Tổng
  quan`, `Phòng ban & nhân viên`, `Cảnh báo toàn công ty`, `Công việc`, `Đánh
  giá phòng ban`, `Trung tâm chỉ thị`); đồng thời xác nhận nội dung hiển thị
  không lộ ID kỹ thuật.
- Test chặn request API ghi dữ liệu; các request đọc được trả về phản hồi 401
  giả lập để kiểm tra trạng thái chưa đăng nhập mà không cần backend/MongoDB.
- Role smoke dùng dữ liệu GET mock và mock riêng SSE AI; mọi request ghi dữ liệu
  nghiệp vụ đều bị chặn, không gửi dữ liệu lên AI cloud. Lỗi WebSocket 403 do
  backend không chạy được phân loại
  là lỗi môi trường kiểm thử, không phải lỗi console của ứng dụng.
- Kết quả không bao gồm nghiệm thu live dữ liệu hoặc kiểm thử workflow nghiệp vụ;
  các test đó cần dịch vụ backend/MongoDB local và phải được chạy riêng theo
  quyền kiểm thử đã phê duyệt.

## Ranh giới thay đổi

- Đợt này chỉ thêm/chỉnh frontend UI primitive, test UI-only và tài liệu baseline.
- Không thực hiện chỉnh sửa backend, API contract, route, payload, store dữ liệu
  hoặc hook gọi dữ liệu.
- Worktree có nhiều thay đổi backend/frontend tồn tại từ trước; các thay đổi đó
  không thuộc đợt chuẩn hóa primitive này và không bị hoàn nguyên.
