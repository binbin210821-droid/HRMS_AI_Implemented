import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiAssistantWidget from './AiAssistantWidget.jsx'
import { streamAiChat } from './aiApi.js'
import { useAuthStore } from '../../stores/authStore.js'

vi.mock('./aiApi.js', () => ({
  streamAiChat: vi.fn(),
}))

describe('AiAssistantWidget', () => {
  afterEach(cleanup)

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
    const sendButton = screen
      .getAllByRole('button', { name: 'Gửi' })
      .find((button) => !button.disabled)
    fireEvent.click(sendButton)

    await waitFor(() =>
      expect(screen.getByText('Đây là câu trả lời tiếng Việt.')).toBeInTheDocument(),
    )
    expect(streamAiChat).toHaveBeenCalledWith(
      'Ai cần theo dõi?',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('formats compact markdown-like AI lists into readable lines', async () => {
    streamAiChat.mockImplementationOnce(async (_message, options) => {
      options.onToken(
        'Hiệu suất phòng Kinh doanh: * **Nguyễn Gia Bảo:** Hiệu suất 86.84, chất lượng 88.86. * **Nhân viên Kinh doanh 4:** Hiệu suất 85.6.',
      )
    })
    render(<AiAssistantWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))
    fireEvent.change(screen.getByLabelText('Câu hỏi cho Trợ lý AI'), {
      target: { value: 'Hiệu suất phòng tôi thế nào?' },
    })
    const sendButton = screen
      .getAllByRole('button', { name: 'Gửi' })
      .find((button) => !button.disabled)
    fireEvent.click(sendButton)

    await waitFor(() => expect(screen.getByText('Nguyễn Gia Bảo:')).toBeInTheDocument())
    expect(screen.getByText('Nhân viên Kinh doanh 4:')).toBeInTheDocument()
    expect(screen.getAllByText(/Hiệu suất/).length).toBeGreaterThan(1)
  })

  it('shows manager-focused performance questions before the first request', () => {
    render(<AiAssistantWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))

    expect(screen.getByText('Hiệu suất phòng tôi 7 ngày gần đây thế nào?')).toBeInTheDocument()
    fireEvent.click(
      screen.getByText('So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?'),
    )
    expect(screen.getByLabelText('Câu hỏi cho Trợ lý AI')).toHaveValue(
      'So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?',
    )
  })

  it('keeps the new conversation button distinct from the header background', () => {
    render(<AiAssistantWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))

    const newConversationButton = screen.getByRole('button', {
      name: 'Bắt đầu cuộc trò chuyện mới',
    })
    expect(newConversationButton).toHaveClass('bg-white', 'text-brand-700')
    expect(newConversationButton).toHaveClass('hover:bg-brand-50')
    const panel = screen.getByLabelText('Trợ lý AI')
    expect(within(panel).getByRole('button', { name: 'Đóng Trợ lý AI' })).toHaveClass(
      'h-9',
      'w-9',
      'text-white',
    )
  })

  it('tiếp tục nhận câu trả lời khi đóng rồi mở lại trong lúc AI đang trả lời', async () => {
    let requestOptions
    let resolveRequest
    streamAiChat.mockImplementationOnce((_message, options) => {
      requestOptions = options
      return new Promise((resolve) => {
        resolveRequest = resolve
      })
    })

    render(<AiAssistantWidget />)
    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))
    fireEvent.change(screen.getByLabelText('Câu hỏi cho Trợ lý AI'), {
      target: { value: 'Ai cần được theo dõi?' },
    })
    fireEvent.click(
      screen.getAllByRole('button', { name: 'Gửi' }).find((button) => !button.disabled),
    )

    await waitFor(() => expect(requestOptions).toBeDefined())
    const panel = screen.getByLabelText('Trợ lý AI')
    fireEvent.click(within(panel).getByRole('button', { name: 'Đóng Trợ lý AI' }))

    expect(requestOptions.signal.aborted).toBe(false)
    await waitFor(() => expect(screen.queryByLabelText('Trợ lý AI')).not.toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))
    expect(screen.getByLabelText('Trợ lý AI')).toBeInTheDocument()
    requestOptions.onToken('Câu trả lời tiếp tục sau khi mở lại.')
    resolveRequest()

    expect(await screen.findByText('Câu trả lời tiếp tục sau khi mở lại.')).toBeInTheDocument()
  })

  it('shows company-level questions for Leadership', () => {
    useAuthStore.setState({ isAuthenticated: true, role: 'leadership' })
    render(<AiAssistantWidget />)

    fireEvent.click(screen.getByRole('button', { name: 'Mở Trợ lý AI' }))

    expect(screen.getByText('Phòng ban nào đang có rủi ro cần ưu tiên?')).toBeInTheDocument()
    expect(screen.queryByText('Ai đang có dấu hiệu cần theo dõi?')).not.toBeInTheDocument()
  })
})
