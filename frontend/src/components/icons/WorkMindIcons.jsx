const IconBase = ({ children, size = 24, title, className, ...props }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    width={size}
    height={size}
    fill="none"
    className={className}
    role={title ? 'img' : undefined}
    aria-hidden={title ? undefined : true}
    {...props}
  >
    {title && <title>{title}</title>}
    {children}
  </svg>
)

const colors = {
  primary: 'var(--wm-icon, #2563eb)',
  soft: 'var(--wm-icon-soft, #dbeafe)',
  mid: 'var(--wm-icon-mid, #93c5fd)',
}

function AssetIcon({ src, size = 24, title, className }) {
  return (
    <span
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      title={title}
      className={className}
      style={{
        display: 'block',
        width: size,
        height: size,
        flexShrink: 0,
        backgroundColor: 'currentColor',
        WebkitMaskImage: `url("${src}")`,
        maskImage: `url("${src}")`,
        WebkitMaskPosition: 'center',
        maskPosition: 'center',
        WebkitMaskRepeat: 'no-repeat',
        maskRepeat: 'no-repeat',
        WebkitMaskSize: 'contain',
        maskSize: 'contain',
      }}
    />
  )
}

export const CompanyIcon = (props) => <AssetIcon src="/icons/company-employees.svg" {...props} />

export const DepartmentsIcon = (props) => (
  <AssetIcon src="/icons/department-management.svg" {...props} />
)

export const DashboardIcon = (props) => (
  <IconBase {...props}>
    <rect x="3" y="3" width="18" height="18" rx="5" fill={colors.soft} />
    <rect x="5.5" y="5.5" width="5.25" height="5.25" rx="1.6" fill={colors.primary} />
    {[
      [13.25, 5.5],
      [5.5, 13.25],
      [13.25, 13.25],
    ].map(([x, y]) => (
      <rect
        key={`${x}-${y}`}
        x={x}
        y={y}
        width="5.25"
        height="5.25"
        rx="1.6"
        stroke={colors.primary}
        strokeWidth="1.7"
      />
    ))}
  </IconBase>
)

export const PerformanceIcon = (props) => (
  <IconBase {...props} stroke={colors.primary} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="7" cy="7" r="2.4" fill={colors.soft} strokeWidth="1.7" />
    <path d="M3.8 15.2c.7-2.7 2-4 3.2-4s2.5 1.3 3.2 4" strokeWidth="1.7" />
    <path d="m12 15 3.1-3.2 2.1 1.5 3.1-4.2M17.7 9.1h2.6v2.6" strokeWidth="1.9" />
    <path d="M12 19.2h8.4" stroke={colors.mid} strokeWidth="1.7" />
  </IconBase>
)

export const AlertIcon = (props) => (
  <IconBase {...props} strokeLinecap="round" strokeLinejoin="round">
    <path
      d="M10.1 4.7 3.4 16.3A2.1 2.1 0 0 0 5.2 19.5h13.6a2.1 2.1 0 0 0 1.8-3.2L13.9 4.7a2.2 2.2 0 0 0-3.8 0Z"
      fill={colors.soft}
      stroke={colors.primary}
      strokeWidth="1.7"
    />
    <path d="M12 9v4.2" stroke={colors.primary} strokeWidth="2" />
    <circle cx="12" cy="16.4" r="1" fill={colors.primary} />
  </IconBase>
)

export const EmployeesIcon = (props) => (
  <IconBase {...props} stroke={colors.primary} strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="7" r="2.6" fill={colors.primary} strokeWidth="1.6" />
    <circle cx="5.5" cy="9.2" r="2" fill={colors.soft} strokeWidth="1.6" />
    <circle cx="18.5" cy="9.2" r="2" fill={colors.soft} strokeWidth="1.6" />
    <path
      d="M7.7 18c.6-3.8 2.2-5.6 4.3-5.6s3.7 1.8 4.3 5.6M2.8 17c.4-2.7 1.4-4 2.7-4 .8 0 1.5.4 2 1.2M21.2 17c-.4-2.7-1.4-4-2.7-4-.8 0-1.5.4-2 1.2"
      strokeWidth="1.7"
    />
    <path d="M7.8 20h8.4" stroke={colors.mid} strokeWidth="1.7" />
  </IconBase>
)

export const TasksIcon = (props) => (
  <IconBase {...props} strokeLinecap="round" strokeLinejoin="round">
    <rect
      x="3.5"
      y="4"
      width="14"
      height="16"
      rx="4"
      fill={colors.soft}
      stroke={colors.primary}
      strokeWidth="1.7"
    />
    <path d="m7 11 1.7 1.7 3.6-4M7 16h4.1" stroke={colors.primary} strokeWidth="1.8" />
    <circle cx="17.5" cy="16.5" r="4" fill="#fff" stroke={colors.primary} strokeWidth="1.7" />
    <path d="M17.5 14.2v2.5l1.6 1" stroke={colors.primary} strokeWidth="1.7" />
  </IconBase>
)

export const DirectivesIcon = (props) => (
  <IconBase {...props} strokeLinecap="round" strokeLinejoin="round">
    <path
      d="M5 3.5h10.5L19 7v13.5H5z"
      fill={colors.soft}
      stroke={colors.primary}
      strokeWidth="1.7"
    />
    <path d="M15.5 3.5V7H19M8 11h8M8 15h5" stroke={colors.primary} strokeWidth="1.7" />
    <circle cx="17.5" cy="17.5" r="3.2" fill="#fff" stroke={colors.primary} strokeWidth="1.6" />
    <path d="m16.2 17.5.9.9 1.8-2" stroke={colors.primary} strokeWidth="1.5" />
  </IconBase>
)

export const AiAssistantIcon = (props) => (
  <IconBase {...props} strokeLinecap="round" strokeLinejoin="round">
    <path
      d="M12 2.8c.7 4.5 2.7 6.5 7.2 7.2-4.5.7-6.5 2.7-7.2 7.2-.7-4.5-2.7-6.5-7.2-7.2 4.5-.7 6.5-2.7 7.2-7.2Z"
      fill={colors.primary}
      stroke={colors.primary}
      strokeWidth="1.2"
    />
    <path
      d="M19 15.8c.25 1.7 1 2.45 2.7 2.7-1.7.25-2.45 1-2.7 2.7-.25-1.7-1-2.45-2.7-2.7 1.7-.25 2.45 1 2.7-2.7Z"
      fill={colors.mid}
      stroke={colors.primary}
      strokeWidth="1"
    />
    <circle
      cx="5.2"
      cy="18.3"
      r="1.5"
      fill={colors.soft}
      stroke={colors.primary}
      strokeWidth="1.4"
    />
  </IconBase>
)
