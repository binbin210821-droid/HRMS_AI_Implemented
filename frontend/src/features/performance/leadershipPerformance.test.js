import { describe, expect, it } from 'vitest'

import {
  buildDepartmentTrendSeries,
  groupOverloadReasonsByDepartment,
  groupTasksByDepartment,
  mergeDepartmentWeeklyTrends,
  selectDepartmentTopEmployees,
} from './leadershipPerformance.js'

const departments = [
  { id: 'cskh', name: 'Chăm sóc khách hàng' },
  { id: 'kd', name: 'Kinh doanh' },
  { id: 'kt', name: 'Kỹ thuật' },
]

describe('leadershipPerformance helpers', () => {
  it('merges three department trends into six metric series and keeps missing weeks null', () => {
    const series = buildDepartmentTrendSeries(departments)
    const rows = mergeDepartmentWeeklyTrends(departments, [
      {
        weeks: [
          { week_start: '2026-09-01', week_label: '01/09', performance: 80, quality: 90 },
          { week_start: '2026-09-08', week_label: '08/09', performance: 82, quality: 91 },
        ],
      },
      { weeks: [{ week_start: '2026-09-01', week_label: '01/09', performance: 70, quality: 75 }] },
      { weeks: [{ week_start: '2026-09-08', week_label: '08/09', performance: 88, quality: 89 }] },
    ])

    expect(series).toHaveLength(3)
    expect(series.flatMap((item) => [item.performanceKey, item.qualityKey])).toHaveLength(6)
    expect(rows).toEqual([
      {
        weekStart: '2026-09-01',
        weekLabel: '01/09',
        performance_cskh: 80,
        quality_cskh: 90,
        performance_kd: 70,
        quality_kd: 75,
        performance_kt: null,
        quality_kt: null,
      },
      {
        weekStart: '2026-09-08',
        weekLabel: '08/09',
        performance_cskh: 82,
        quality_cskh: 91,
        performance_kd: null,
        quality_kd: null,
        performance_kt: 88,
        quality_kt: 89,
      },
    ])
    expect(rows[0].performance_kt).toBeNull()
    expect(rows[1].quality_kd).toBeNull()
  })

  it('selects the highest performer and uses employee_code as the stable tie-breaker', () => {
    const cards = selectDepartmentTopEmployees(departments, [
      {
        employees: [
          { employee_code: 'CSKH-002', full_name: 'B', average_performance_score: 90 },
          { employee_code: 'CSKH-001', full_name: 'A', average_performance_score: 90 },
        ],
      },
      { employees: [{ employee_code: 'KD-001', full_name: 'C', average_performance_score: null }] },
      { employees: [{ employee_code: 'KT-001', full_name: 'D', average_performance_score: 80 }] },
    ])

    expect(cards[0].employee.full_name).toBe('A')
    expect(cards[1].employee).toBeNull()
    expect(cards[2].employee.full_name).toBe('D')
  })

  it('counts overload reasons for every department, including departments with zero logs', () => {
    expect(
      groupOverloadReasonsByDepartment(
        [
          { department_id: 'cskh', trigger_reason: ['task_volume'] },
          { department_id: 'cskh', trigger_reason: ['quality_drop', 'task_volume'] },
          { department_id: 'kt', trigger_reason: ['quality_drop'] },
        ],
        departments,
      ),
    ).toMatchObject([
      { departmentId: 'cskh', task_volume: 2, quality_drop: 1 },
      { departmentId: 'kd', task_volume: 0, quality_drop: 0 },
      { departmentId: 'kt', task_volume: 0, quality_drop: 1 },
    ])
  })

  it('groups all task statuses and preserves an empty department column', () => {
    expect(
      groupTasksByDepartment(
        [
          { department_id: 'cskh', status: 'done' },
          { department_id: 'cskh', status: 'todo' },
          { department_id: 'kd', status: 'in_progress' },
        ],
        departments,
      ),
    ).toMatchObject([
      { departmentId: 'cskh', done: 1, todo: 1, in_progress: 0 },
      { departmentId: 'kd', done: 0, todo: 0, in_progress: 1 },
      { departmentId: 'kt', done: 0, todo: 0, in_progress: 0 },
    ])
  })
})
