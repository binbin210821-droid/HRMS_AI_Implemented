import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import FormField from './FormField.jsx'

describe('FormField', () => {
  it('connects the label, help text and Vietnamese validation message', () => {
    render(
      <FormField id="department" label="Phòng ban" required helpText="Chọn phòng ban phụ trách">
        <input className="form-input" />
      </FormField>,
    )

    expect(screen.getByLabelText(/Phòng ban/)).toHaveAttribute('id', 'department')
    expect(screen.getByText('Chọn phòng ban phụ trách')).toHaveAttribute('id', 'department-help')
  })

  it('marks an invalid control and exposes the error to assistive technology', () => {
    render(
      <FormField id="username" label="Tên đăng nhập" error="Vui lòng nhập tên đăng nhập.">
        <input />
      </FormField>,
    )

    const input = screen.getByLabelText('Tên đăng nhập')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('aria-describedby', 'username-error')
    expect(screen.getByRole('alert')).toHaveTextContent('Vui lòng nhập tên đăng nhập.')
  })
})
