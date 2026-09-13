const OPEN_LIFECYCLE_STATUSES = new Set(['pending', 'acknowledged', 'needs_revision'])
const COMMITMENT_TRACKING_STATUSES = new Set(['acknowledged', 'needs_revision'])

function asDate(value) {
  if (!value) return null
  const date = value instanceof Date ? new Date(value.getTime()) : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function durationHours(start, end) {
  const startDate = asDate(start)
  const endDate = asDate(end)
  if (!startDate || !endDate) return null
  const hours = (endDate.getTime() - startDate.getTime()) / 3_600_000
  return hours >= 0 ? hours : null
}

function average(values) {
  return values.length > 0 ? values.reduce((sum, value) => sum + value, 0) / values.length : null
}

function dateKey(value) {
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) return value.slice(0, 10)
  const date = asDate(value)
  return date ? date.toISOString().slice(0, 10) : null
}

function managerKey(directive) {
  return directive.target_manager_id || 'unknown-manager'
}

function managerName(directive) {
  return directive.target_manager_name || 'Quản lý chưa xác định'
}

export function buildLifecycleDirectiveSla(directives = [], today = new Date()) {
  const groups = new Map()
  const todayKey = dateKey(today)

  for (const directive of directives) {
    const key = managerKey(directive)
    if (!groups.has(key)) {
      groups.set(key, {
        manager_id: key,
        manager_name: managerName(directive),
        total_count: 0,
        open_count: 0,
        acknowledgement_hours: [],
        processing_hours: [],
        submitted_count: 0,
        revision_count: 0,
        overdue_commitment_count: 0,
      })
    }

    const group = groups.get(key)
    group.total_count += 1
    if (OPEN_LIFECYCLE_STATUSES.has(directive.status)) group.open_count += 1

    const acknowledgement = durationHours(directive.issued_at, directive.acknowledged_at)
    if (acknowledgement !== null) group.acknowledgement_hours.push(acknowledgement)

    const processing = durationHours(directive.acknowledged_at, directive.submitted_at)
    if (processing !== null) group.processing_hours.push(processing)

    if (directive.submitted_at) group.submitted_count += 1
    if (directive.revision_requested_at) group.revision_count += 1

    const commitmentKey = dateKey(directive.commitment_date)
    if (
      COMMITMENT_TRACKING_STATUSES.has(directive.status) &&
      commitmentKey &&
      todayKey &&
      commitmentKey < todayKey &&
      !directive.submitted_at
    ) {
      group.overdue_commitment_count += 1
    }
  }

  return [...groups.values()].map((group) => ({
    manager_id: group.manager_id,
    manager_name: group.manager_name,
    total_count: group.total_count,
    open_count: group.open_count,
    average_acknowledgement_hours: average(group.acknowledgement_hours),
    average_processing_hours: average(group.processing_hours),
    revision_rate:
      group.submitted_count > 0 ? (group.revision_count / group.submitted_count) * 100 : null,
    overdue_commitment_count: group.overdue_commitment_count,
  }))
}

export function buildCoordinationDirectiveSla(directives = []) {
  const groups = new Map()
  let pending_count = 0

  for (const directive of directives) {
    if (directive.status === 'pending') {
      pending_count += 1
      continue
    }
    if (!directive.fulfilled_by) continue

    const key = directive.fulfilled_by
    if (!groups.has(key)) {
      groups.set(key, {
        manager_id: key,
        manager_name: directive.fulfilled_by_name || 'Quản lý chưa xác định',
        fulfillment_hours: [],
        fulfilled_count: 0,
      })
    }

    const group = groups.get(key)
    group.fulfilled_count += 1
    const fulfillment = durationHours(directive.issued_at, directive.fulfilled_at)
    if (fulfillment !== null) group.fulfillment_hours.push(fulfillment)
  }

  return {
    rows: [...groups.values()].map((group) => ({
      manager_id: group.manager_id,
      manager_name: group.manager_name,
      fulfilled_count: group.fulfilled_count,
      average_fulfillment_hours: average(group.fulfillment_hours),
    })),
    pending_count,
  }
}
