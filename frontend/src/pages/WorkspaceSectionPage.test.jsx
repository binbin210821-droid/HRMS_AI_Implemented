import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspaceSectionPage from './WorkspaceSectionPage.jsx'

vi.mock('../stores/authStore.js', () => ({
  useAuthStore: () => ({ role: 'manager' }),
}))

vi.mock('../components/layout/MainLayout.jsx', () => ({
  default: ({ children }) => <main>{children}</main>,
}))

vi.mock('../components/animations/index.js', () => ({
  FadeIn: ({ children }) => <div>{children}</div>,
}))

describe('WorkspaceSectionPage', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
  })

  it('redirects the hidden assistant page to the role overview', () => {
    render(
      <MemoryRouter initialEntries={['/manager/assistant']}>
        <Routes>
          <Route path="/manager/:section" element={<WorkspaceSectionPage />} />
          <Route path="/manager" element={<p>Tổng quan</p>} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('Tổng quan')).toBeInTheDocument()
    expect(screen.queryByText('Trợ lý AI')).not.toBeInTheDocument()
  })
})
