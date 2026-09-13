import { render, screen, within } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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
    expect(screen.queryByRole('link', { name: 'Trợ lý AI' })).not.toBeInTheDocument()
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
    expect(screen.queryByRole('link', { name: 'Trợ lý AI' })).not.toBeInTheDocument()
  })

  it('opens the mobile navigation and closes it after selecting a route', async () => {
    const onClose = vi.fn()
    useAuthStore.setState({ isAuthenticated: true, role: 'manager' })
    render(
      <MemoryRouter>
        <Sidebar isOpen onClose={onClose} />
      </MemoryRouter>,
    )

    const mobileMenu = screen.getByRole('complementary', {
      name: 'Menu điều hướng trên thiết bị di động',
    })
    expect(mobileMenu).toBeVisible()
    within(mobileMenu).getByRole('link', { name: 'Nhân viên phòng ban' }).click()
    expect(onClose).toHaveBeenCalled()
  })
})
