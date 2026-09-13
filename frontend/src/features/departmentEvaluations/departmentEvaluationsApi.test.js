import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import {
  createDepartmentEvaluation,
  updateDepartmentEvaluation,
  getWeeklyDepartmentReview,
} from './departmentEvaluationsApi.js'

describe('departmentEvaluationsApi idempotency', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
    httpClientMock.mockResolvedValue({})
  })

  it('passes the same caller-owned key to create and update requests', async () => {
    const key = 'weekly-evaluation-key'
    await createDepartmentEvaluation({ department_id: 'department-1' }, [], key)
    await updateDepartmentEvaluation('evaluation-1', { assessment_note: 'Cập nhật' }, [], key)

    expect(httpClientMock.mock.calls).toHaveLength(2)
    for (const [, options] of httpClientMock.mock.calls) {
      expect(options).toEqual(expect.objectContaining({ idempotencyKey: key }))
    }
  })

  it('uses the canonical v1 weekly review resource route', async () => {
    await getWeeklyDepartmentReview('department/1', '2026-09-12')

    expect(httpClientMock).toHaveBeenCalledWith(
      '/api/v1/department-evaluations/weekly-reviews/department%2F1/2026-09-12',
    )
  })
})
