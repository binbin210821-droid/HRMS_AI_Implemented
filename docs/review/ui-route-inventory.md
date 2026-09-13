# Frontend route và Network UI-only inventory

Ngày ghi nhận: 2026-09-12

## Route hiện tại

Nguồn đối chiếu: `frontend/src/App.jsx` và
`frontend/src/components/layout/navigation.js`.

| Role/phạm vi | Route | Trạng thái UI-only smoke |
| --- | --- | --- |
| Chung | `/login` | Đã kiểm tra desktop/mobile |
| Manager | `/manager` | Đã kiểm tra role smoke |
| Manager | `/manager/performance` | Đã kiểm tra role smoke |
| Manager | `/manager/alerts` | Đã kiểm tra role smoke |
| Manager | `/manager/tasks` | Đã kiểm tra role smoke |
| Manager | `/manager/directives` | Đã kiểm tra role smoke |
| Manager | `/manager/employees` | Đã kiểm tra role smoke |
| Manager | `/manager/analytics`, `/manager/overload` | Redirect giữ nguyên |
| Leadership | `/leadership` | Đã kiểm tra role smoke |
| Leadership | `/leadership/alerts` | Đã kiểm tra role smoke |
| Leadership | `/leadership/tasks` | Đã kiểm tra role smoke |
| Leadership | `/leadership/department-evaluations` | Đã kiểm tra role smoke |
| Leadership | `/leadership/directives` | Đã kiểm tra role smoke |
| Leadership | `/leadership/departments` | Đã kiểm tra role smoke |
| Leadership | `/leadership/performance`, `/leadership/overload`, `/leadership/managers`, `/leadership/employees`, `/leadership/users` | Đã kiểm tra redirect |
| Chung | `/manager/:section`, `/leadership/:section` | Route fallback giữ nguyên; component coverage |
| Chung | `/unauthorized`, `/` | Đã kiểm tra trang không có quyền và home redirect |

## Network boundary trong smoke

- Các request `GET`/`HEAD` được trả response mock tối thiểu theo resource để
  render trạng thái không có dữ liệu.
- `POST` tới `/api/v1/ai/chat/stream` được trả SSE `done` giả lập, vì đây là
  luồng AI streaming được phép kiểm thử; không gửi dữ liệu ra cloud.
- Mọi `POST`, `PATCH`, `PUT`, `DELETE` nghiệp vụ khác đều bị abort và được
  assert không xuất hiện trong role smoke.
- WebSocket `/ws/realtime` có thể báo `403` khi backend không chạy; lỗi này
  được ghi nhận là giới hạn môi trường UI-only, không bỏ qua lỗi JavaScript của
  ứng dụng.

## Giới hạn bằng chứng

- Inventory này chứng minh route/UI render, redirect/fallback và boundary request trong mock; không
  chứng minh dữ liệu thật, RBAC backend, SSE provider thật hoặc workflow mutation.
- `npm run test:e2e` hiện chưa được chạy trong đợt UI-only vì suite hiện hữu có
  thao tác ghi dữ liệu nghiệp vụ. Cần một phiên nghiệm thu riêng khi backend và
  MongoDB sẵn sàng, theo đúng quyền và fixture đã phê duyệt.
