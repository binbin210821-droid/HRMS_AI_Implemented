# WorkMind Icon Set

Bộ 6 icon SVG dành cho sidebar HRMS WorkMind, thiết kế ở `viewBox="0 0 24 24"`.

## Sử dụng với ReactJS

```jsx
import { workMindMenuItems } from "./WorkMindIcons";

{workMindMenuItems.map(({ label, icon: Icon, path }) => (
  <a href={path} className="sidebar-item" key={path}>
    <Icon size={22} title={label} />
    <span>{label}</span>
  </a>
))}
```

Có thể đổi màu toàn bộ icon bằng CSS variables:

```css
.sidebar-item {
  --wm-icon: #475569;
  --wm-icon-soft: #f1f5f9;
  --wm-icon-mid: #94a3b8;
}

.sidebar-item.active {
  --wm-icon: #2563eb;
  --wm-icon-soft: #dbeafe;
  --wm-icon-mid: #93c5fd;
}
```

Các file trong `icons/` dùng trực tiếp trong thẻ `<img>` hoặc import bằng SVG loader.
