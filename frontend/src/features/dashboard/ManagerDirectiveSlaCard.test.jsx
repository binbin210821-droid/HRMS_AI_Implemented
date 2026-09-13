import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ManagerDirectiveSlaCard from './ManagerDirectiveSlaCard.jsx'
import { listDepartmentDirectives, listDirectives } from '../coordination/coordinationApi.js'
import { listDepartmentTaskDirectives } from '../tasks/tasksApi.js'

vi.mock('../coordination/coordinationApi.js', () => ({
  listDepartmentDirectives: vi.fn(),
  listDirectives: vi.fn(),
}))

vi.mock('../tasks/tasksApi.js', () => ({
  listDepartmentTaskDirectives: vi.fn(),
}))

describe('ManagerDirectiveSlaCard', () => {
  afterEach(() => cleanup())

  beforeEach(() => {
    vi.clearAllMocks()
    listDepartmentTaskDirectives.mockResolvedValue([
      {
        target_manager_id: 'manager-1',
        target_manager_name: 'Nguyễn An',
        status: 'acknowledged',
        issued_at: '2026-09-10T08:00:00Z',
        acknowledged_at: '2026-09-10T10:00:00Z',
      },
    ])
    listDepartmentDirectives.mockResolvedValue([])
    listDirectives.mockResolvedValue([])
  })

  it('shows three source tabs and lifecycle metrics for leadership', async () => {
    render(<ManagerDirectiveSlaCard role="leadership" />)

    expect(await screen.findByText('Nguyễn An')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Giao việc quá hạn' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: 'Yêu cầu xử lý cảnh báo' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Điều phối liên phòng ban' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('tab', { name: 'Yêu cầu xử lý cảnh báo' }))
    expect(screen.getByText('Chưa có dữ liệu chỉ thị để tổng hợp.')).toBeInTheDocument()
  })

  it('shows fulfilled coordination rows and the separate pending total', async () => {
    listDirectives.mockResolvedValue([
      {
        status: 'pending',
        issued_at: '2026-09-10T08:00:00Z',
      },
      {
        status: 'fulfilled',
        fulfilled_by: 'manager-2',
        fulfilled_by_name: 'Trần Bình',
        issued_at: '2026-09-10T08:00:00Z',
        fulfilled_at: '2026-09-10T12:00:00Z',
      },
    ])

    render(<ManagerDirectiveSlaCard role="leadership" />)
    fireEvent.click(await screen.findByRole('tab', { name: 'Điều phối liên phòng ban' }))

    expect(await screen.findByText('Trần Bình')).toBeInTheDocument()
    expect(screen.getByText(/Đang chờ xử lý:/)).toHaveTextContent('1')
  })

  it('does not render for manager role', () => {
    const { container } = render(<ManagerDirectiveSlaCard role="manager" />)
    expect(container).toBeEmptyDOMElement()
    expect(listDepartmentTaskDirectives).not.toHaveBeenCalled()
  })
})
