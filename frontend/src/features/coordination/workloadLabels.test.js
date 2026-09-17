import { describe, expect, it } from 'vitest'

import {
  formatActiveTaskTitles,
  formatCandidateWorkload,
  getCandidateTransferLimit,
  getCandidateWorkload,
} from './workloadLabels.js'

describe('workloadLabels', () => {
  it('shows completed, active, reserved and total daily workload', () => {
    const candidate = {
      tasks_completed: 2,
      active_task_count: 1,
      reserved_coordination_count: 1,
      workload_count: 4,
      active_task_titles: ['Kế hoạch kéo dài'],
    }

    expect(getCandidateWorkload(candidate)).toEqual({
      completed: 2,
      active: 1,
      reserved: 1,
      total: 4,
      available: 0,
      titles: ['Kế hoạch kéo dài'],
    })
    expect(formatCandidateWorkload(candidate)).toBe(
      'tổng 4 việc trong ngày · đã hoàn thành 2 · đang đảm nhiệm 1 · còn nhận thêm 0 · đã giữ chỗ 1',
    )
    expect(formatActiveTaskTitles(candidate)).toBe('Việc đang đảm nhiệm: Kế hoạch kéo dài')
  })

  it('derives total workload for older API responses', () => {
    expect(formatCandidateWorkload({ tasks_completed: 2, active_task_count: 2 })).toBe(
      'tổng 4 việc trong ngày · đã hoàn thành 2 · đang đảm nhiệm 2 · còn nhận thêm 0',
    )
  })

  it('limits a transfer to the remaining daily capacity', () => {
    expect(getCandidateTransferLimit({ tasks_completed: 2, active_task_count: 1 })).toBe(1)
  })
})
