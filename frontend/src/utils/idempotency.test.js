import { afterEach, describe, expect, it, vi } from 'vitest'

import { generateIdempotencyKey } from './idempotency.js'

afterEach(() => vi.unstubAllGlobals())

describe('generateIdempotencyKey', () => {
  it('delegates key generation to crypto.randomUUID', () => {
    vi.stubGlobal('crypto', { randomUUID: vi.fn().mockReturnValue('key-1') })

    expect(generateIdempotencyKey()).toBe('key-1')
    expect(crypto.randomUUID).toHaveBeenCalledOnce()
  })
})
