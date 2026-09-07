import { useEffect, useRef, useState } from 'react'

import { FadeIn, SlideIn } from '../../components/animations/index.js'
import { AiAssistantIcon } from '../../components/icons/WorkMindIcons.jsx'
import { useAuthStore } from '../../stores/authStore.js'
import { streamAiChat } from './aiApi.js'

const WELCOME_MESSAGE =
  'Xin chào! Tôi có thể giúp bạn đọc các chỉ số hiệu suất và cảnh báo trong phạm vi được phép.'

function AiAssistantWidget() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState([
    { id: 'welcome', role: 'assistant', content: WELCOME_MESSAGE },
  ])
  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef(null)

  useEffect(() => {
    return () => abortControllerRef.current?.abort()
  }, [])

  if (!isAuthenticated) return null

  function closeAssistant() {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    setIsOpen(false)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const trimmedMessage = message.trim()
    if (!trimmedMessage || isLoading) return

    const assistantId = `assistant-${Date.now()}`
    setMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: trimmedMessage },
      { id: assistantId, role: 'assistant', content: '' },
    ])
    setMessage('')
    setIsLoading(true)
    const controller = new AbortController()
    abortControllerRef.current = controller

    try {
      await streamAiChat(trimmedMessage, {
        signal: controller.signal,
        onToken: (token) => {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantId ? { ...item, content: item.content + token } : item,
            ),
          )
        },
      })
    } catch (error) {
      if (error.name !== 'AbortError') {
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId
              ? {
                  ...item,
                  content:
                    error.message || 'Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút.',
                }
              : item,
          ),
        )
      }
    } finally {
      abortControllerRef.current = null
      setIsLoading(false)
    }
  }

  return (
    <div className="fixed bottom-5 right-5 z-40 flex flex-col items-end gap-3">
      {isOpen && (
        <SlideIn direction="up">
          <section
            aria-label="Trợ lý AI"
            className="flex h-[min(32rem,calc(100vh-7rem))] w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
          >
            <div className="flex items-center justify-between bg-brand-700 px-4 py-3 text-white">
              <div>
                <h2 className="!text-base !font-semibold !text-white">Trợ lý AI</h2>
                <p className="!text-xs !text-brand-100">Giải thích số liệu bằng tiếng Việt</p>
              </div>
              <button
                type="button"
                aria-label="Đóng Trợ lý AI"
                className="rounded-lg px-2 py-1 text-xl leading-none text-brand-100 hover:bg-brand-600 hover:text-white"
                onClick={closeAssistant}
              >
                ×
              </button>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3" aria-live="polite">
              {messages.map((item) => (
                <FadeIn key={item.id}>
                  <div
                    className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-6 ${
                      item.role === 'user'
                        ? 'ml-auto rounded-br-sm bg-brand-600 text-white'
                        : 'rounded-bl-sm border border-slate-200 bg-white text-slate-700'
                    }`}
                  >
                    {item.content || (isLoading ? 'Đang phân tích…' : '')}
                  </div>
                </FadeIn>
              ))}
            </div>

            <form
              className="flex gap-2 border-t border-slate-200 bg-white p-3"
              onSubmit={handleSubmit}
            >
              <label className="sr-only" htmlFor="ai-message">
                Câu hỏi cho Trợ lý AI
              </label>
              <input
                id="ai-message"
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none ring-brand-200 focus:border-brand-500 focus:ring-2"
                placeholder="Ví dụ: Ai cần được theo dõi?"
                disabled={isLoading}
              />
              <button
                type="submit"
                className="rounded-xl bg-brand-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={isLoading || !message.trim()}
              >
                Gửi
              </button>
            </form>
          </section>
        </SlideIn>
      )}
      <button
        type="button"
        aria-label={isOpen ? 'Đóng Trợ lý AI' : 'Mở Trợ lý AI'}
        className="flex items-center gap-2 rounded-full bg-brand-700 px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-brand-800"
        onClick={() => setIsOpen((current) => !current)}
      >
        <AiAssistantIcon
          size={18}
          aria-hidden="true"
          style={{
            '--wm-icon': '#ffffff',
            '--wm-icon-soft': '#dbeafe',
            '--wm-icon-mid': '#93c5fd',
          }}
        />
        Trợ lý AI
      </button>
    </div>
  )
}

export default AiAssistantWidget
