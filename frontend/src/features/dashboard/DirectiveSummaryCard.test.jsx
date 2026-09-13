import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import DirectiveSummaryCard from './DirectiveSummaryCard.jsx'
import { listDepartmentDirectives, listDirectives } from '../coordination/coordinationApi.js'
import { listDepartmentTaskDirectives } from '../tasks/tasksApi.js'

const navigateMock = vi.hoisted(() => vi.fn())

vi.mock('react-router-dom', () => ({
  useNavigate: () => navigateMock,
}))

vi.mock('../../hooks/useRealtimeUpdates.js', () => ({
  REALTIME_COALESCE_DELAY: 250,
  useRealtimeUpdates: vi.fn(),
}))

vi.mock('../coordination/coordinationApi.js', () => ({
  listDepartmentDirectives: vi.fn(),
  listDirectives: vi.fn(),
}))

vi.mock('../tasks/tasksApi.js', () => ({
  listDepartmentTaskDirectives: vi.fn(),
}))

describe('DirectiveSummaryCard', () => {
  afterEach(() => {
    cleanup()
  })

  beforeEach(() => {
    navigateMock.mockReset()
    listDepartmentDirectives.mockResolvedValue([{ status: 'pending' }])
    listDepartmentTaskDirectives.mockResolvedValue([{ status: 'submitted' }])
    listDirectives.mockResolvedValue([{ status: 'fulfilled' }])
  })

  it('tổng hợp chỉ thị cho Leadership và điều hướng đến trung tâm tương ứng', async () => {
    render(<DirectiveSummaryCard role="leadership" />)

    const card = await screen.findByRole('button', { name: 'Mở trang yêu cầu và điều phối' })
    await waitFor(() => expect(card).toHaveTextContent('Tổng yêu cầu và điều phối'))
    expect(card).toHaveTextContent('3')
    expect(card).toHaveTextContent('Yêu cầu xử lý cảnh báo')
    expect(card).toHaveTextContent('Giao việc quá hạn')
    expect(card).toHaveTextContent('Điều phối liên phòng ban')

    fireEvent.click(card)
    expect(navigateMock).toHaveBeenCalledWith('/leadership/directives')
  })

  it('đổi nhãn trạng thái pending theo vai trò Manager', async () => {
    render(<DirectiveSummaryCard role="manager" />)

    const card = await screen.findByRole('button', { name: 'Mở trang yêu cầu và điều phối' })
    await waitFor(() => expect(card).toHaveTextContent('Đang chờ xử lý cảnh báo'))

    fireEvent.click(card)
    expect(navigateMock).toHaveBeenCalledWith('/manager/directives')
  })
})
