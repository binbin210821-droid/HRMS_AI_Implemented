import { describe, expect, it } from 'vitest'

import {
  getAdjacentDate,
  getMonthDates,
  getTaskDateKey,
  getWeekDates,
  groupTasksByDate,
  toDateKey,
} from './calendarUtils.js'

describe('calendar utilities', () => {
  it('creates a Monday-first week and a complete month grid', () => {
    const date = new Date(2026, 8, 2)

    expect(getWeekDates(date)).toHaveLength(7)
    expect(getWeekDates(date)[0].getDay()).toBe(1)
    expect(getMonthDates(date)).toHaveLength(42)
  })

  it('groups tasks by their date without timezone shifts', () => {
    const task = { id: 'task-1', due_date: '2026-09-02' }
    const grouped = groupTasksByDate([task])

    expect(getTaskDateKey(task)).toBe('2026-09-02')
    expect(grouped['2026-09-02']).toEqual([task])
  })

  it('moves month, week and day views by the expected amount', () => {
    const date = new Date(2026, 8, 2)

    expect(toDateKey(getAdjacentDate('month', date, 1))).toBe('2026-10-01')
    expect(toDateKey(getAdjacentDate('week', date, 1))).toBe('2026-09-09')
    expect(toDateKey(getAdjacentDate('day', date, -1))).toBe('2026-09-01')
  })
})
