import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import LeadershipAiProposalCard from './LeadershipAiProposalCard.jsx'
import { getLeadershipActionProposal } from '../ai/aiApi.js'
import { issueDepartmentDirective } from '../coordination/coordinationApi.js'
import { listDepartments } from '../departments/departmentsApi.js'

vi.mock('../ai/aiApi.js', () => ({ getLeadershipActionProposal: vi.fn() }))
vi.mock('../coordination/coordinationApi.js', () => ({ issueDepartmentDirective: vi.fn() }))
vi.mock('../departments/departmentsApi.js', () => ({ listDepartments: vi.fn() }))

describe('LeadershipAiProposalCard', () => {
  afterEach(() => {
    cleanup()
    window.sessionStorage.clear()
  })

  beforeEach(() => {
    getLeadershipActionProposal.mockReset()
    issueDepartmentDirective.mockReset()
    listDepartments.mockReset()
  })

  it('hiển thị đề xuất và gọi API chỉ thị sau khi người dùng chỉnh sửa', async () => {
    getLeadershipActionProposal.mockResolvedValue({
      summary: 'Nên theo dõi phòng Kinh doanh.',
      actions: [
        {
          type: 'issue_department_directive',
          department_id: 'department-1',
          department_name: 'Kinh doanh',
          alert_type: 'overload',
          severity: 'high',
          note: 'Rà soát trong ngày.',
          rationale: 'Có nhiều việc quá hạn.',
          evidence: ['3 việc quá hạn'],
        },
      ],
    })
    listDepartments.mockResolvedValue([{ id: 'department-1', name: 'Kinh doanh' }])
    issueDepartmentDirective.mockResolvedValue({ id: 'directive-1' })

    render(<LeadershipAiProposalCard role="leadership" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất' }))

    const note = await screen.findByDisplayValue('Rà soát trong ngày.')
    fireEvent.change(note, { target: { value: 'Gửi kế hoạch trước 17 giờ.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Xem lại và phát hành' }))

    await waitFor(() =>
      expect(issueDepartmentDirective).toHaveBeenCalledWith(
        'department-1',
        { alert_type: 'overload', severity: 'high', note: 'Gửi kế hoạch trước 17 giờ.' },
        expect.any(String),
      ),
    )
  })

  it('không hiển thị với Manager', () => {
    const { container } = render(<LeadershipAiProposalCard role="manager" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('hiển thị đề xuất điều phối liên phòng ban nhưng không tự tạo nút áp dụng', async () => {
    getLeadershipActionProposal.mockResolvedValue({
      summary: 'Có thể cân nhắc hỗ trợ giữa hai phòng ban.',
      actions: [
        {
          type: 'cross_department_coordination',
          source_department_name: 'Kinh doanh',
          target_department_name: 'Bán hàng',
          action: 'transfer_work',
          tasks_to_transfer: 1,
          fit_score: 77,
          available_employee_count: 2,
          rationale: 'Phòng Bán hàng còn khả năng nhận thêm việc.',
          evidence: ['Có 2 người đang ở mức tải an toàn'],
        },
      ],
    })
    listDepartments.mockResolvedValue([])

    render(<LeadershipAiProposalCard role="leadership" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất' }))

    expect(await screen.findByText('Kinh doanh → Bán hàng')).toBeInTheDocument()
    expect(screen.getByText('Mức độ phù hợp:').parentElement).toHaveTextContent('77/100')
    expect(screen.queryByRole('button', { name: 'Xem lại và phát hành' })).not.toBeInTheDocument()
  })

  it('giữ đề xuất liên phòng ban khi quay lại Tổng quan', async () => {
    getLeadershipActionProposal.mockResolvedValue({
      summary: 'Có thể cân nhắc hỗ trợ giữa hai phòng ban.',
      actions: [
        {
          type: 'cross_department_coordination',
          source_department_name: 'Kinh doanh',
          target_department_name: 'Bán hàng',
          action: 'transfer_work',
          fit_score: 77,
          available_employee_count: 2,
          rationale: 'Phòng Bán hàng còn khả năng nhận thêm việc.',
        },
      ],
    })
    listDepartments.mockResolvedValue([])

    const { unmount } = render(<LeadershipAiProposalCard role="leadership" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất' }))
    await screen.findByText('Kinh doanh → Bán hàng')
    fireEvent.click(screen.getByRole('button', { name: 'Ẩn gợi ý AI' }))

    unmount()
    render(<LeadershipAiProposalCard role="leadership" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Hiện gợi ý AI' }))
    expect(await screen.findByText('Kinh doanh → Bán hàng')).toBeInTheDocument()
    expect(getLeadershipActionProposal).toHaveBeenCalledTimes(1)
  })
})
