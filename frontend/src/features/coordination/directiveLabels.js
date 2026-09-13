export const DIRECTIVE_SOURCE_LABELS = {
  alert: 'Yêu cầu xử lý cảnh báo',
  task: 'Giao việc quá hạn',
  coordination: 'Điều phối liên phòng ban',
}

const DIRECTIVE_STATUS_LABELS = {
  alert: {
    pending: 'Đang chờ xử lý cảnh báo',
    acknowledged: 'Đã tiếp nhận yêu cầu cảnh báo',
    submitted: 'Chờ nghiệm thu xử lý cảnh báo',
    accepted: 'Đã nghiệm thu xử lý cảnh báo',
    needs_revision: 'Cần xử lý lại cảnh báo',
    fulfilled: 'Đã hoàn tất xử lý cảnh báo',
  },
  task: {
    pending: 'Đang chờ nhận việc quá hạn',
    acknowledged: 'Đã tiếp nhận việc quá hạn',
    submitted: 'Chờ nghiệm thu việc quá hạn',
    accepted: 'Đã nghiệm thu việc quá hạn',
    needs_revision: 'Cần xử lý lại việc quá hạn',
    fulfilled: 'Đã hoàn tất việc quá hạn',
  },
  coordination: {
    pending: 'Đang chờ điều phối liên phòng ban',
    acknowledged: 'Đã tiếp nhận điều phối liên phòng ban',
    submitted: 'Chờ nghiệm thu điều phối liên phòng ban',
    accepted: 'Đã nghiệm thu điều phối liên phòng ban',
    needs_revision: 'Cần xử lý lại điều phối liên phòng ban',
    fulfilled: 'Đã hoàn tất điều phối liên phòng ban',
  },
}

const DIRECTIVE_ACTION_LABELS = {
  alert: {
    managerPending: 'Xử lý yêu cầu cảnh báo',
    managerNeedsRevision: 'Xử lý lại yêu cầu cảnh báo',
    leadershipSubmitted: 'Nghiệm thu xử lý cảnh báo',
    accepted: 'Xem lại kết quả nghiệm thu',
    default: 'Xem yêu cầu xử lý cảnh báo',
  },
  task: {
    managerPending: 'Tiếp nhận giao việc quá hạn',
    managerNeedsRevision: 'Xử lý lại giao việc quá hạn',
    leadershipSubmitted: 'Nghiệm thu giao việc quá hạn',
    accepted: 'Xem lại kết quả nghiệm thu',
    default: 'Xem giao việc quá hạn',
  },
  coordination: {
    managerPending: 'Tiếp nhận điều phối liên phòng ban',
    managerNeedsRevision: 'Xử lý lại điều phối liên phòng ban',
    leadershipSubmitted: 'Nghiệm thu điều phối liên phòng ban',
    accepted: 'Xem lại kết quả nghiệm thu',
    default: 'Xem điều phối liên phòng ban',
  },
}

export function getDirectiveSourceLabel(source) {
  return DIRECTIVE_SOURCE_LABELS[source] || 'Yêu cầu và điều phối'
}

export function getDirectiveStatusLabel(source, status) {
  return DIRECTIVE_STATUS_LABELS[source]?.[status] || 'Đang theo dõi yêu cầu'
}

export function getDirectiveStatusClass(_source, status) {
  if (status === 'needs_revision') return 'bg-amber-50 text-amber-800 ring-1 ring-amber-200'
  if (status === 'pending') return 'bg-amber-50 text-amber-700'
  if (status === 'submitted') return 'bg-blue-50 text-blue-700'
  if (status === 'acknowledged') return 'bg-sky-50 text-sky-700'
  if (status === 'accepted' || status === 'fulfilled') return 'bg-emerald-50 text-emerald-700'
  return 'bg-slate-100 text-slate-700'
}

export function getDirectiveActionLabel(source, role, status) {
  const labels = DIRECTIVE_ACTION_LABELS[source] || DIRECTIVE_ACTION_LABELS.coordination
  if (role === 'manager' && status === 'pending') return labels.managerPending
  if (role === 'manager' && status === 'needs_revision') return labels.managerNeedsRevision
  if (role === 'leadership' && status === 'submitted') return labels.leadershipSubmitted
  if (status === 'accepted') return labels.accepted
  return labels.default
}
