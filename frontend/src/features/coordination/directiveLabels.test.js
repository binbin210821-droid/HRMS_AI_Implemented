import { describe, expect, it } from 'vitest'

import { getDirectiveActionLabel, getDirectiveStatusClass } from './directiveLabels.js'

describe('directiveLabels', () => {
  it('gắn nhãn riêng cho Manager cần xử lý lại', () => {
    expect(getDirectiveActionLabel('task', 'manager', 'needs_revision')).toBe(
      'Xử lý lại giao việc quá hạn',
    )
    expect(getDirectiveActionLabel('alert', 'manager', 'needs_revision')).toBe(
      'Xử lý lại yêu cầu cảnh báo',
    )
  })

  it('phân biệt màu cần xử lý lại với trạng thái đã nghiệm thu', () => {
    expect(getDirectiveStatusClass('task', 'needs_revision')).toContain('bg-amber-50')
    expect(getDirectiveStatusClass('task', 'needs_revision')).not.toBe(
      getDirectiveStatusClass('task', 'accepted'),
    )
  })
})
