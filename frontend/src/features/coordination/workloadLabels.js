export const DAILY_WORKLOAD_CAPACITY = 4
export const MAX_COORDINATION_TRANSFER_TASKS = 2

export function getCandidateWorkload(candidate = {}) {
  const completed = Number(candidate.tasks_completed) || 0
  const active = Number(candidate.active_task_count) || 0
  const reserved = Number(candidate.reserved_coordination_count) || 0
  const reportedTotal = Number(candidate.workload_count)
  const total = Number.isFinite(reportedTotal) ? reportedTotal : completed + active + reserved
  const reportedAvailable = Number(candidate.available_capacity)
  const available = Number.isFinite(reportedAvailable)
    ? Math.max(0, reportedAvailable)
    : Math.max(0, DAILY_WORKLOAD_CAPACITY - total)

  return {
    completed,
    active,
    reserved,
    total,
    available,
    titles: Array.isArray(candidate.active_task_titles) ? candidate.active_task_titles : [],
  }
}

export function getCandidateTransferLimit(candidate, requested = MAX_COORDINATION_TRANSFER_TASKS) {
  const capacity = Number(requested)
  const safeCapacity = Number.isFinite(capacity) ? Math.max(0, capacity) : DAILY_WORKLOAD_CAPACITY
  return Math.min(getCandidateWorkload(candidate).available, safeCapacity)
}

export function formatCandidateWorkload(candidate) {
  const workload = getCandidateWorkload(candidate)
  const details = [
    `tổng ${workload.total} việc trong ngày`,
    `đã hoàn thành ${workload.completed}`,
    `đang đảm nhiệm ${workload.active}`,
    `còn nhận thêm ${workload.available}`,
  ]
  if (workload.reserved > 0) details.push(`đã giữ chỗ ${workload.reserved}`)
  return details.join(' · ')
}

export function formatActiveTaskTitles(candidate) {
  const titles = getCandidateWorkload(candidate).titles
  return titles.length ? `Việc đang đảm nhiệm: ${titles.join(', ')}` : ''
}
