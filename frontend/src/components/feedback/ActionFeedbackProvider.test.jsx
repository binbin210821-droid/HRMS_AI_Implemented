import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import ActionFeedbackProvider, { useActionFeedback } from './ActionFeedbackProvider.jsx'

afterEach(() => {
  cleanup()
})

function FeedbackFixture() {
  const { confirmAction, notifyActionSuccess, notifyActionError } = useActionFeedback()

  return (
    <div>
      <button
        type="button"
        onClick={async () => {
          const confirmed = await confirmAction({
            title: 'Xác nhận đổi hạn',
            description: 'Hạn công việc sẽ được cập nhật.',
            details: ['Công việc: Báo cáo tháng', 'Hạn mới: 12/09/2026'],
          })
          if (confirmed) {
            notifyActionSuccess({
              title: 'Đã thay đổi deadline',
              message: 'Công việc đã được cập nhật thành công.',
              details: ['Hạn mới: 12/09/2026'],
            })
          }
        }}
      >
        Thay đổi deadline
      </button>
      <button
        type="button"
        onClick={() =>
          notifyActionError({
            title: 'Chưa thực hiện',
            message: 'Không thể cập nhật công việc.',
          })
        }
      >
        Báo lỗi
      </button>
      <button
        type="button"
        onClick={async () => {
          const confirmed = await confirmAction({
            title: 'Xác nhận cập nhật',
            details: ['Công việc: Báo cáo tháng', 'Hạn mới: 12/09/2026'],
          })
          if (confirmed) {
            notifyActionError({
              title: 'Chưa cập nhật',
              message: 'Máy chủ tạm thời không phản hồi.',
            })
          }
        }}
      >
        Thay đổi thất bại
      </button>
    </div>
  )
}

function renderFixture() {
  return render(
    <ActionFeedbackProvider>
      <FeedbackFixture />
    </ActionFeedbackProvider>,
  )
}

describe('ActionFeedbackProvider', () => {
  it('shows the exact action details and a success result after confirmation', async () => {
    renderFixture()

    fireEvent.click(screen.getByRole('button', { name: 'Thay đổi deadline' }))
    expect(await screen.findByRole('dialog')).toHaveTextContent('Báo cáo tháng')
    expect(screen.getByText('Hạn mới: 12/09/2026')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Xác nhận thực hiện' }))

    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent('Đã thay đổi deadline'),
    )
    expect(screen.getByRole('status')).toHaveTextContent('Hạn mới: 12/09/2026')
  })

  it('closes without applying when the user cancels', async () => {
    renderFixture()

    fireEvent.click(screen.getByRole('button', { name: 'Thay đổi deadline' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Hủy' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows a failure result with the returned error information', async () => {
    renderFixture()

    fireEvent.click(screen.getByRole('button', { name: 'Báo lỗi' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Chưa thực hiện')
    expect(screen.getByRole('alert')).toHaveTextContent('Không thể cập nhật công việc.')
  })

  it('keeps the confirmed action details when the action fails', async () => {
    renderFixture()

    fireEvent.click(screen.getByRole('button', { name: 'Thay đổi thất bại' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Xác nhận thực hiện' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Chưa cập nhật'))
    expect(screen.getByRole('alert')).toHaveTextContent('Báo cáo tháng')
    expect(screen.getByRole('alert')).toHaveTextContent('Hạn mới: 12/09/2026')
  })
})
