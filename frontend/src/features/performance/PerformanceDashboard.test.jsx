import { describe, expect, it } from 'vitest'

import { buildPerformanceComparison } from './PerformanceDashboard.jsx'

describe('buildPerformanceComparison', () => {
  it('removes only nullish scores while preserving a real zero score', () => {
    const result = buildPerformanceComparison([
      {
        employee_id: 'employee-null',
        full_name: 'Chưa có dữ liệu',
        average_performance_score: null,
      },
      { employee_id: 'employee-zero', full_name: 'Điểm bằng không', average_performance_score: 0 },
      { employee_id: 'employee-normal', full_name: 'Có dữ liệu', average_performance_score: 82.5 },
    ])

    expect(result.missingCount).toBe(1)
    expect(result.items).toEqual([
      {
        employee_id: 'employee-zero',
        full_name: 'Điểm bằng không',
        average_performance_score: 0,
        performance: 0,
      },
      {
        employee_id: 'employee-normal',
        full_name: 'Có dữ liệu',
        average_performance_score: 82.5,
        performance: 82.5,
      },
    ])
  })
})
