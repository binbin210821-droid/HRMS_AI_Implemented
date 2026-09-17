const DAY_IN_MS = 24 * 60 * 60 * 1000

export function parseCalendarDate(value) {
  if (value instanceof Date) return new Date(value.getFullYear(), value.getMonth(), value.getDate())
  if (!value) return new Date()
  const [year, month, day] = String(value).slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function addDays(date, amount) {
  return new Date(parseCalendarDate(date).getTime() + amount * DAY_IN_MS)
}

export function toDateKey(date) {
  const parsed = parseCalendarDate(date)
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const day = String(parsed.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function startOfWeek(date) {
  const parsed = parseCalendarDate(date)
  const mondayOffset = (parsed.getDay() + 6) % 7
  return addDays(parsed, -mondayOffset)
}

export function startOfMonth(date) {
  const parsed = parseCalendarDate(date)
  return new Date(parsed.getFullYear(), parsed.getMonth(), 1)
}

export function getMonthDates(date) {
  const firstDay = startOfMonth(date)
  const firstCell = startOfWeek(firstDay)
  return Array.from({ length: 42 }, (_, index) => addDays(firstCell, index))
}

export function getWeekDates(date) {
  const firstDay = startOfWeek(date)
  return Array.from({ length: 7 }, (_, index) => addDays(firstDay, index))
}

export function getTaskDateKey(task) {
  return toDateKey(task.due_date)
}

export function groupTasksByDate(tasks) {
  return tasks.reduce((groups, task) => {
    const start = parseCalendarDate(task.created_at || task.due_date)
    const end = parseCalendarDate(task.due_date)
    const firstDate = start <= end ? start : end
    const lastDate = start <= end ? end : start

    for (let date = firstDate; date <= lastDate; date = addDays(date, 1)) {
      const key = toDateKey(date)
      groups[key] = groups[key] ? [...groups[key], task] : [task]
    }
    return groups
  }, {})
}

export function isToday(date) {
  return toDateKey(date) === toDateKey(new Date())
}

export function isPastCalendarDate(date) {
  return toDateKey(date) < toDateKey(new Date())
}

export function formatCalendarDate(date, options = {}) {
  return new Intl.DateTimeFormat('vi-VN', options).format(parseCalendarDate(date))
}

export function getCalendarRangeLabel(view, date) {
  if (view === 'month') {
    return formatCalendarDate(date, { month: 'long', year: 'numeric' })
  }
  if (view === 'day') {
    return formatCalendarDate(date, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  }

  const dates = getWeekDates(date)
  const first = formatCalendarDate(dates[0], { day: 'numeric', month: 'short' })
  const last = formatCalendarDate(dates[6], { day: 'numeric', month: 'short', year: 'numeric' })
  return `${first} – ${last}`
}

export function getAdjacentDate(view, date, direction) {
  if (view === 'month') {
    const parsed = parseCalendarDate(date)
    return new Date(parsed.getFullYear(), parsed.getMonth() + direction, 1)
  }
  return addDays(date, view === 'week' ? direction * 7 : direction)
}

export const WEEKDAY_LABELS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']
