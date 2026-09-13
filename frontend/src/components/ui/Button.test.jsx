import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import Button from './Button.jsx'

describe('Button', () => {
  it('exposes the shared variant and loading contract', () => {
    render(
      <Button variant="secondary" size="sm" loading>
        Lưu thay đổi
      </Button>,
    )

    const button = screen.getByRole('button', { name: 'Lưu thay đổi' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button.className).toContain('bg-white')
    expect(button.className).toContain('text-xs')
  })
})
