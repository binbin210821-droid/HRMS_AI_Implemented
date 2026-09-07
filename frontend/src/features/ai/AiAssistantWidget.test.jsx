import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AiAssistantWidget from './AiAssistantWidget.jsx'
import { streamAiChat } from './aiApi.js'
import { useAuthStore } from '../../stores/authStore.js'

vi.mock('./aiApi.js', () => ({
  streamAiChat: vi.fn(),
}))

describe('AiAssistantWidget', () => {
  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: true, role: 'manager' })
    streamAiChat.mockImplementation(async (_message, options) => {
      options.onToken('Đây là câu trả lời tiếng Việt.')
    })
  })

  it('opens the drawer and renders streamed Vietnamese text', async () => {
    render(<AiAssistantWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))
    fireEvent.change(screen.getByLabelText('Câu hỏi cho Trợ lý AI'), {
      target: { value: 'Ai cần theo dõi?' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Gửi' }))

    await waitFor(() =>
      expect(screen.getByText('Đây là câu trả lời tiếng Việt.')).toBeInTheDocument(),
    )
    expect(streamAiChat).toHaveBeenCalledWith(
      'Ai cần theo dõi?',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })
})
