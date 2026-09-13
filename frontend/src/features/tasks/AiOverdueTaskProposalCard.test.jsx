import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiOverdueTaskProposalCard from './AiOverdueTaskProposalCard.jsx'
import { getOverdueTaskActionProposal } from '../ai/aiApi.js'
import { updateTask } from './tasksApi.js'

vi.mock('../ai/aiApi.js', () => ({ getOverdueTaskActionProposal: vi.fn() }))
vi.mock('./tasksApi.js', () => ({ updateTask: vi.fn() }))

const task = {
  id: 'task-1',
  title: 'Hoàn thiện báo cáo',
  status: 'in_progress',
  due_date: '2026-09-01',
  is_overdue: true,
  updated_at: '2026-09-10T08:00:00Z',
}

describe('AiOverdueTaskProposalCard', () => {
  afterEach(() => {
    cleanup()
    window.sessionStorage.clear()
  })

  beforeEach(() => {
    getOverdueTaskActionProposal.mockReset()
    updateTask.mockReset()
  })

  it('loads an editable proposal and applies it through the existing task API', async () => {
    getOverdueTaskActionProposal.mockResolvedValue({
      task_id: 'task-1',
      summary: 'Đã tính 2 phương án.',
      plan_version: 'plan-1',
      data_as_of: '2026-09-10',
      options: [
        {
          option_id: 'option-1',
          type: 'keep_and_extend',
          due_date: '2026-09-15',
          fit_score: 78,
          confidence: 0.8,
          rationale: 'Công việc vẫn đang được thực hiện.',
        },
      ],
    })
    updateTask.mockResolvedValue({})

    render(<AiOverdueTaskProposalCard task={task} role="manager" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI cách xử lý' }))

    const dateInput = await screen.findByDisplayValue('2026-09-15')
    fireEvent.change(dateInput, { target: { value: '2026-09-20' } })
    fireEvent.click(screen.getByRole('button', { name: 'Áp dụng phương án' }))

    await waitFor(() =>
      expect(updateTask).toHaveBeenCalledWith('task-1', {
        status: 'in_progress',
        due_date: '2026-09-20',
        expected_updated_at: '2026-09-10T08:00:00Z',
        planning_version: 'plan-1',
      }),
    )
  })

  it('does not render for non-manager or non-overdue tasks', () => {
    const { rerender } = render(<AiOverdueTaskProposalCard task={task} role="leadership" />)
    expect(screen.queryByRole('button', { name: 'Hỏi AI cách xử lý' })).not.toBeInTheDocument()

    rerender(<AiOverdueTaskProposalCard task={{ ...task, is_overdue: false }} role="manager" />)
    expect(screen.queryByRole('button', { name: 'Hỏi AI cách xử lý' })).not.toBeInTheDocument()
  })

  it('giữ đề xuất và cho phép ẩn hiện khi quay lại trang Công việc', async () => {
    getOverdueTaskActionProposal.mockResolvedValue({
      task_id: 'task-1',
      summary: 'Gia hạn sau khi rà soát.',
      plan_version: 'plan-1',
      options: [
        {
          option_id: 'option-1',
          type: 'keep_and_extend',
          due_date: '2026-09-15',
          fit_score: 78,
          confidence: 0.8,
          rationale: 'Công việc vẫn đang được thực hiện.',
        },
      ],
    })

    const { unmount } = render(<AiOverdueTaskProposalCard task={task} role="manager" />)
    fireEvent.click(screen.getByRole('button', { name: 'Hỏi AI cách xử lý' }))
    await screen.findByDisplayValue('2026-09-15')

    fireEvent.click(screen.getByRole('button', { name: 'Ẩn gợi ý AI' }))
    expect(screen.getByText('Gợi ý AI đang tạm ẩn.')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('2026-09-15')).not.toBeInTheDocument()

    unmount()
    render(<AiOverdueTaskProposalCard task={task} role="manager" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Hiện gợi ý AI' }))
    expect(await screen.findByText('Gia hạn sau khi rà soát.')).toBeInTheDocument()
    expect(getOverdueTaskActionProposal).toHaveBeenCalledTimes(1)
  })
})
