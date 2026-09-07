import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './ProtectedRoute.jsx'
import { useAuthStore } from '../stores/authStore.js'

function renderRoute(allowedRoles) {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route
          path="/private"
          element={
            <ProtectedRoute allowedRoles={allowedRoles}>
              <p>Trang riêng tư</p>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<p>Trang đăng nhập</p>} />
        <Route path="/unauthorized" element={<p>Không có quyền</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => useAuthStore.getState().logout())

  it('redirects unauthenticated users to login', () => {
    renderRoute(['manager'])
    expect(screen.getByText('Trang đăng nhập')).toBeInTheDocument()
  })

  it('redirects an authenticated user with the wrong role', () => {
    useAuthStore.setState({ isAuthenticated: true, role: 'manager' })
    renderRoute(['leadership'])
    expect(screen.getByText('Không có quyền')).toBeInTheDocument()
  })

  it('renders the protected content for an allowed role', () => {
    useAuthStore.setState({ isAuthenticated: true, role: 'manager' })
    renderRoute(['manager'])
    expect(screen.getByText('Trang riêng tư')).toBeInTheDocument()
  })
})
