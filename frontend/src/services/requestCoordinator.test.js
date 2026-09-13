import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearRequestCoordinator,
  coordinatedRequest,
  invalidateResource,
} from './requestCoordinator.js'

describe('requestCoordinator', () => {
  beforeEach(() => clearRequestCoordinator())

  it('deduplicates concurrent requests and short-lived repeated reads', async () => {
    const loader = vi.fn().mockResolvedValue({ items: [1] })

    const first = coordinatedRequest('alerts', '/api/v1/alerts', loader, { ttlMs: 1000 })
    const second = coordinatedRequest('alerts', '/api/v1/alerts', loader, { ttlMs: 1000 })

    await expect(Promise.all([first, second])).resolves.toEqual([{ items: [1] }, { items: [1] }])
    await expect(
      coordinatedRequest('alerts', '/api/v1/alerts', loader, { ttlMs: 1000 }),
    ).resolves.toEqual({ items: [1] })
    expect(loader).toHaveBeenCalledOnce()
  })

  it('invalidates only the affected resource', async () => {
    const alertsLoader = vi.fn().mockResolvedValue(['alert'])
    const tasksLoader = vi.fn().mockResolvedValue(['task'])

    await coordinatedRequest('alerts', 'all', alertsLoader)
    await coordinatedRequest('tasks', 'all', tasksLoader)
    invalidateResource('alerts')
    await coordinatedRequest('alerts', 'all', alertsLoader)
    await coordinatedRequest('tasks', 'all', tasksLoader)

    expect(alertsLoader).toHaveBeenCalledTimes(2)
    expect(tasksLoader).toHaveBeenCalledOnce()
  })
})
