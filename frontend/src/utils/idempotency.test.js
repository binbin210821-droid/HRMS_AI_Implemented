import { afterEach, describe, expect, it, vi } from 'vitest'

import { generateIdempotencyKey } from './idempotency.js'

afterEach(() => vi.unstubAllGlobals())

describe('generateIdempotencyKey', () => {
  it('delegates key generation to crypto.randomUUID', () => {
    vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValue('key-1') })

    expect(generateIdempotencyKey()).toBe('key-1')
    expect(crypto.randomUUID).toHaveBeenCalledOnce()
  })

  it('uses crypto.getRandomValues when randomUUID is unavailable', () => {
    vi.stubGlobal('crypto', {
      getRandomValues: vi.fn((bytes) => {
        bytes.fill(1)
        return bytes
      }),
    })

    expect(generateIdempotencyKey()).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-41[0-9a-f]{2}-81[0-9a-f]{2}-[0-9a-f]{12}$/,
    )
    expect(crypto.getRandomValues).toHaveBeenCalledOnce()
  })

  it('still returns a key when the browser has no crypto API', () => {
    vi.stubGlobal('crypto', undefined)

    expect(generateIdempotencyKey()).toMatch(/^idempotency-[a-z0-9]+-[a-z0-9]+-[a-z0-9]+$/)
  })
})
