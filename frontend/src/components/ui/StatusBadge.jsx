import Badge from './Badge.jsx'

const STATUS_LABELS = {
  active: 'Đang hoạt động',
  inactive: 'Không hoạt động',
  pending: 'Đang chờ xử lý',
  resolved: 'Đã xử lý',
  overdue: 'Quá hạn',
  completed: 'Đã hoàn thành',
}

const STATUS_VARIANTS = {
  active: 'success',
  inactive: 'neutral',
  pending: 'warning',
  resolved: 'success',
  overdue: 'danger',
  completed: 'success',
}

function StatusBadge({ status, label, className = '' }) {
  const normalizedStatus = String(status || '').toLowerCase()
  return (
    <Badge variant={STATUS_VARIANTS[normalizedStatus] || 'neutral'} className={className}>
      {label || STATUS_LABELS[normalizedStatus] || status || 'Chưa xác định'}
    </Badge>
  )
}

export default StatusBadge
