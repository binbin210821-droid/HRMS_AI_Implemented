import { beforeEach, describe, expect, it, vi } from 'vitest'

const httpClientMock = vi.hoisted(() => vi.fn())

vi.mock('../../services/httpClient.js', () => ({ default: httpClientMock }))

import { getDepartmentWeeklyTrend, listPerformance } from './performanceApi.js'

describe('performanceApi', () => {
  beforeEach(() => {
    httpClientMock.mockReset()
  })

  it('unwraps the paginated v1 response into the array expected by callers', async () => {
    httpClientMock.mockResolvedValue({
      items: [{ id: 'metric-1', performance_score: 85 }],
      page: 1,
      page_size: 20,
      total: 1,
      has_next: false,
    })

    await expect(
      listPerformance({
        departmentId: 'department-1',
        startDate: '2026-09-01',
        endDate: '2026-09-09',
      }),
    ).resolves.toEqual([{ id: 'metric-1', performance_score: 85 }])

    expect(httpClientMock).toHaveBeenCalledWith(
      '/api/v1/performance?department_id=department-1&start_date=2026-09-01&end_date=2026-09-09',
    )
  })

  it('returns an empty array when the response has no items', async () => {
    httpClientMock.mockResolvedValue({})

    await expect(listPerformance()).resolves.toEqual([])
  })

  it('keeps compatibility with the live v1 array response', async () => {
    httpClientMock.mockResolvedValue([{ id: 'metric-1', performance_score: 85 }])

    await expect(listPerformance({ employeeId: 'employee-1' })).resolves.toEqual([
      { id: 'metric-1', performance_score: 85 },
    ])
  })

  it('requests the department weekly trend endpoint with the selected date range', async () => {
    const response = {
      department_id: 'department-1',
      department_name: 'Kinh doanh',
      weeks: [
        {
          week_start: '2026-09-07',
          week_label: '07/09',
          performance: 86.2,
          quality: 88.4,
        },
      ],
      overall_average: 86.15,
    }
    httpClientMock.mockResolvedValue(response)

    await expect(
      getDepartmentWeeklyTrend('department-1', {
        startDate: '2026-09-01',
        endDate: '2026-09-09',
      }),
    ).resolves.toEqual(response)
    expect(httpClientMock).toHaveBeenCalledWith(
      '/api/v1/performance/analytics/department/department-1/weekly-trend?start_date=2026-09-01&end_date=2026-09-09',
    )
  })
})
