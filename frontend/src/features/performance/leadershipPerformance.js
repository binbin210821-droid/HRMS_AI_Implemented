export const LEADERSHIP_DEPARTMENT_COLORS = ['#2563eb', '#16a34a', '#ea580c']
const DEPARTMENT_COLOR_BY_CODE = {
  CSKH: '#2563eb',
  KD: '#16a34a',
  KT: '#ea580c',
}

export const TASK_STATUS_LABELS = {
  done: 'Đã hoàn thành',
  in_progress: 'Đang thực hiện',
  todo: 'Chưa bắt đầu',
}

export const OVERLOAD_REASON_LABELS = {
  quality_drop: 'Sụt chất lượng',
  task_volume: 'Khối lượng công việc',
}

function departmentKey(value) {
  return String(value ?? '')
}

function departmentColor(department, index) {
  return (
    DEPARTMENT_COLOR_BY_CODE[String(department.code || '').toUpperCase()] ||
    LEADERSHIP_DEPARTMENT_COLORS[index % LEADERSHIP_DEPARTMENT_COLORS.length]
  )
}

function compareEmployeeCode(first, second) {
  return String(first.employee_code || '').localeCompare(String(second.employee_code || ''), 'vi', {
    numeric: true,
    sensitivity: 'base',
  })
}

export function buildDepartmentTrendSeries(departments = []) {
  return departments.map((department, index) => {
    const key = departmentKey(department.id)
    return {
      departmentId: key,
      departmentName: department.name,
      color: departmentColor(department, index),
      performanceKey: `performance_${key}`,
      qualityKey: `quality_${key}`,
    }
  })
}

export function mergeDepartmentWeeklyTrends(departments = [], responses = []) {
  const series = buildDepartmentTrendSeries(departments)
  const rows = new Map()

  series.forEach((item, index) => {
    const response = responses[index]
    ;(response?.weeks || []).forEach((week) => {
      if (!week?.week_start) return
      const row = rows.get(week.week_start) || {
        weekStart: week.week_start,
        weekLabel: week.week_label || week.week_start,
      }
      if (!rows.has(week.week_start)) {
        series.forEach((item) => {
          row[item.performanceKey] = null
          row[item.qualityKey] = null
        })
      }
      row[item.performanceKey] = week.performance ?? null
      row[item.qualityKey] = week.quality ?? null
      rows.set(week.week_start, row)
    })
  })

  return [...rows.values()].sort((first, second) =>
    String(first.weekStart).localeCompare(String(second.weekStart)),
  )
}

export function selectDepartmentTopEmployees(departments = [], responses = []) {
  return departments.map((department, index) => {
    const candidates = (responses[index]?.employees || [])
      .filter((employee) => employee.average_performance_score != null)
      .sort(
        (first, second) =>
          second.average_performance_score - first.average_performance_score ||
          compareEmployeeCode(first, second),
      )

    return {
      departmentId: departmentKey(department.id),
      departmentName: department.name,
      color: departmentColor(department, index),
      employee: candidates[0] || null,
    }
  })
}

export function groupOverloadReasonsByDepartment(logs = [], departments = []) {
  const rows = departments.map((department, index) => ({
    departmentId: departmentKey(department.id),
    departmentName: department.name,
    color: departmentColor(department, index),
    task_volume: 0,
    quality_drop: 0,
  }))
  const byDepartment = new Map(rows.map((row) => [row.departmentId, row]))

  logs.forEach((log) => {
    const row = byDepartment.get(departmentKey(log.department_id))
    if (!row) return
    ;(log.trigger_reason || []).forEach((reason) => {
      if (reason === 'task_volume' || reason === 'quality_drop') row[reason] += 1
    })
  })

  return rows
}

export function groupTasksByDepartment(tasks = [], departments = []) {
  const rows = departments.map((department, index) => ({
    departmentId: departmentKey(department.id),
    departmentName: department.name,
    color: departmentColor(department, index),
    todo: 0,
    in_progress: 0,
    done: 0,
  }))
  const byDepartment = new Map(rows.map((row) => [row.departmentId, row]))

  tasks.forEach((task) => {
    const row = byDepartment.get(departmentKey(task.department_id))
    if (!row) return
    if (task.status === 'todo' || task.status === 'in_progress' || task.status === 'done') {
      row[task.status] += 1
    }
  })

  return rows
}
