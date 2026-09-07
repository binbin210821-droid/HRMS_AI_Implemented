import { render, screen } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import Sidebar from './Sidebar.jsx'
import { useAuthStore } from '../../stores/authStore.js'

function renderSidebar(role) {
  useAuthStore.setState({ isAuthenticated: true, role })
  return render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  )
}

describe('Sidebar role navigation', () => {
  beforeEach(() => useAuthStore.getState().logout())
  afterEach(cleanup)

  it('only shows manager navigation to a manager', () => {
    renderSidebar('manager')
    expect(screen.getByRole('link', { name: 'Nhân viên phòng ban' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Công việc & deadline' })).toHaveAttribute(
      'href',
      '/manager/tasks',
    )
    expect(screen.getByRole('link', { name: 'Trung tâm chỉ thị' })).toHaveAttribute(
      'href',
      '/manager/directives',
    )
    expect(screen.queryByRole('link', { name: 'Cảnh báo quá tải' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Quản lý phòng ban' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nhân viên toàn công ty' })).not.toBeInTheDocument()
  })

  it('shows company-wide navigation to leadership', () => {
    renderSidebar('leadership')
    expect(screen.getByRole('link', { name: 'Phòng ban & nhân viên' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Công việc & deadline' })).toHaveAttribute(
      'href',
      '/leadership/tasks',
    )
    expect(screen.getByRole('link', { name: 'Trung tâm chỉ thị' })).toHaveAttribute(
      'href',
      '/leadership/directives',
    )
    expect(screen.queryByRole('link', { name: 'Quản lý tài khoản' })).not.toBeInTheDocument()
    expect(
      screen.queryByRole('link', { name: 'Cảnh báo quá tải toàn công ty' }),
    ).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nhân viên phòng ban' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Nhân viên toàn công ty' })).not.toBeInTheDocument()
  })
})
