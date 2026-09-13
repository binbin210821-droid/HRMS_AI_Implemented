import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiAlertProposalCard from './AiAlertProposalCard.jsx'
import { getAlertActionProposal } from '../ai/aiApi.js'
import { applyCoordination } from '../coordination/coordinationApi.js'
import { resolveAlert } from './alertsApi.js'

vi.mock('../ai/aiApi.js', () => ({ getAlertActionProposal: vi.fn() }))
vi.mock('../coordination/coordinationApi.js', () => ({ applyCoordination: vi.fn() }))
vi.mock('./alertsApi.js', () => ({ resolveAlert: vi.fn() }))

const alert = {
  id: 'alert-1',
  status: 'open',
  employee_name: 'Nguyễn An',
}

const candidate = {
  employee_id: 'employee-2',
  employee_code: 'KD-NV-002',
  employee_name: 'Trần Bình',
  tasks_completed: 1,
  quality_score: 92,
}

describe('AiAlertProposalCard', () => {
  afterEach(() => {
    cleanup()
    window.sessionStorage.clear()
  })

  beforeEach(() => {
    getAlertActionProposal.mockReset()
    applyCoordination.mockReset()
    resolveAlert.mockReset()
  })

  it('prefills an AI resolution proposal and applies the edited note', async () => {
    getAlertActionProposal.mockResolvedValue({
      alert_id: 'alert-1',
      summary: 'Nên ghi nhận xử lý.',
      actions: [
        {
          type: 'resolve_alert',
          resolution_note: 'Đã rà soát và phân bổ lại việc.',
          rationale: 'Chất lượng có dấu hiệu giảm.',
        },
      ],
    })
    resolveAlert.mockResolvedValue({ ...alert, status: 'resolved' })

    render(<AiAlertProposalCard alert={alert} coordination={{}} role="manager" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất phương án' }))

    const note = await screen.findByDisplayValue('Đã rà soát và phân bổ lại việc.')
    fireEvent.change(note, { target: { value: 'Đã xử lý sau khi trao đổi.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }))

    await waitFor(() =>
      expect(resolveAlert).toHaveBeenCalledWith('alert-1', 'Đã xử lý sau khi trao đổi.'),
    )
  })

  it('prefills a real candidate for a coordination proposal', async () => {
    getAlertActionProposal.mockResolvedValue({
      alert_id: 'alert-1',
      summary: 'Có thể chuyển bớt việc.',
      actions: [
        {
          type: 'apply_coordination',
          target_employee_id: candidate.employee_id,
          tasks_to_transfer: 2,
          note: 'Chuyển việc ưu tiên thấp.',
          rationale: 'Nhân viên còn sức chứa.',
        },
      ],
    })
    applyCoordination.mockResolvedValue({})

    render(
      <AiAlertProposalCard
        alert={alert}
        coordination={{ candidates: [candidate] }}
        role="manager"
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất phương án' }))
    await screen.findByDisplayValue('Chuyển việc ưu tiên thấp.')
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng' }))

    await waitFor(() =>
      expect(applyCoordination).toHaveBeenCalledWith(
        'alert-1',
        {
          target_employee_id: 'employee-2',
          tasks_to_transfer: 2,
          note: 'Chuyển việc ưu tiên thấp.',
        },
        expect.any(String),
      ),
    )
  })

  it('giữ đề xuất và cho phép ẩn hiện khi quay lại trang Cảnh báo', async () => {
    getAlertActionProposal.mockResolvedValue({
      alert_id: 'alert-1',
      summary: 'Nên tiếp tục theo dõi.',
      actions: [
        {
          type: 'resolve_alert',
          resolution_note: 'Đã rà soát.',
          rationale: 'Cần xác nhận lại tình hình.',
        },
      ],
    })

    const { unmount } = render(
      <AiAlertProposalCard alert={alert} coordination={{}} role="manager" />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI đề xuất phương án' }))
    await screen.findByDisplayValue('Đã rà soát.')

    fireEvent.click(screen.getByRole('button', { name: 'Ẩn gợi ý AI' }))
    expect(screen.getByText('Gợi ý AI đang tạm ẩn.')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('Đã rà soát.')).not.toBeInTheDocument()

    unmount()
    render(<AiAlertProposalCard alert={alert} coordination={{}} role="manager" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Hiện gợi ý AI' }))
    expect(await screen.findByText('Nên tiếp tục theo dõi.')).toBeInTheDocument()
    expect(getAlertActionProposal).toHaveBeenCalledTimes(1)
  })
})
