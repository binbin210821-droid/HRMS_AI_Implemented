import { useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'

import { AiLoadingIndicator, FadeIn, SlideIn } from '../../components/animations/index.js'
import { AiAssistantIcon } from '../../components/icons/WorkMindIcons.jsx'
import { Button, Input } from '../../components/ui/index.js'
import { useAuthStore } from '../../stores/authStore.js'
import { streamAiChat } from './aiApi.js'

const WELCOME_MESSAGE =
  'Xin chào! Tôi có thể giúp bạn đọc các chỉ số hiệu suất và cảnh báo trong phạm vi được phép.'

const MANAGER_SUGGESTED_QUESTIONS = [
  'Hiệu suất phòng tôi 7 ngày gần đây thế nào?',
  'So với tuần trước điểm hiệu suất phòng tôi thay đổi thế nào?',
  'Ai đang có dấu hiệu cần theo dõi?',
  'Giải thích cảnh báo đang mở của phòng tôi',
]

const LEADERSHIP_SUGGESTED_QUESTIONS = [
  'Phòng ban nào đang có rủi ro cần ưu tiên?',
  'So sánh hiệu suất trung bình giữa các phòng ban gần đây',
  'Tình hình công việc quá hạn theo từng phòng ban thế nào?',
  'Đánh giá các Quản lý gần đây ra sao?',
]

function renderInlineText(text, keyPrefix) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={`${keyPrefix}-bold-${index}`}>{part.slice(2, -2)}</strong>
    }
    return <span key={`${keyPrefix}-text-${index}`}>{part}</span>
  })
}

function AiMessageContent({ content }) {
  const normalized = content.replace(/\\\*/g, '*').replace(/(?:^|\s)\*\s+(?=\*\*)/g, '\n• ')
  const lines = normalized
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

  return (
    <div className="space-y-1.5">
      {lines.map((line, index) => {
        const bullet = line.match(/^(?:•|[-*])\s+(.*)$/)
        const section = line.match(/^(Kết luận|Bằng chứng|Kỳ dữ liệu|Đề xuất):\s*(.*)$/)
        if (bullet) {
          return (
            <div key={`line-${index}`} className="flex items-start gap-2">
              <span className="mt-0.5 text-brand-500" aria-hidden="true">
                •
              </span>
              <span>{renderInlineText(bullet[1], `line-${index}`)}</span>
            </div>
          )
        }
        if (section) {
          return (
            <p key={`line-${index}`} className="rounded-lg bg-slate-50 px-2 py-1.5">
              <strong>{section[1]}:</strong> {renderInlineText(section[2], `line-${index}`)}
            </p>
          )
        }
        return <p key={`line-${index}`}>{renderInlineText(line, `line-${index}`)}</p>
      })}
    </div>
  )
}

function AiAssistantWidget() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const role = useAuthStore((state) => state.role)
  const [isOpen, setIsOpen] = useState(false)
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState([
    { id: 'welcome', role: 'assistant', content: WELCOME_MESSAGE },
  ])
  const [conversationId, setConversationId] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const abortControllerRef = useRef(null)

  useEffect(() => {
    return () => abortControllerRef.current?.abort()
  }, [])

  if (!isAuthenticated) return null

  function closeAssistant() {
    setIsOpen(false)
  }

  function startNewConversation() {
    abortControllerRef.current?.abort()
    setIsLoading(false)
    setConversationId(null)
    setMessages([{ id: `welcome-${Date.now()}`, role: 'assistant', content: WELCOME_MESSAGE }])
    setMessage('')
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
        conversationId,
        onConversation: setConversationId,
        onStatus: (status) => {
          setMessages((current) =>
            current.map((item) => (item.id === assistantId ? { ...item, status } : item)),
          )
        },
        onToken: (token) => {
          setMessages((current) =>
            current.map((item) =>
              item.id === assistantId
                ? { ...item, content: item.content + token, status: '' }
                : item,
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
      <AnimatePresence initial={false}>
        {isOpen && (
          <SlideIn direction="up" key="ai-assistant-panel">
            <section
              aria-label="Trợ lý AI"
              className="flex h-[min(32rem,calc(100vh-7rem))] w-[min(24rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
            >
              <div className="flex items-center justify-between bg-brand-700 px-4 py-3 text-white">
                <div>
                  <h2 className="!text-base !font-semibold !text-white">Trợ lý AI</h2>
                  <p className="!text-xs !text-brand-100">Giải thích số liệu bằng tiếng Việt</p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    aria-label="Bắt đầu cuộc trò chuyện mới"
                    className="min-h-9 rounded-lg border-white/80 bg-white px-3 py-1 text-xs text-brand-700 shadow-none hover:border-brand-50 hover:bg-brand-50 hover:text-brand-800 focus-visible:ring-white"
                    onClick={startNewConversation}
                  >
                    Mới
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    aria-label="Đóng Trợ lý AI"
                    className="h-9 w-9 rounded-lg p-0 text-xl leading-none text-white shadow-none hover:bg-brand-600 hover:text-white focus-visible:ring-white"
                    onClick={closeAssistant}
                  >
                    ×
                  </Button>
                </div>
              </div>

              <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-3" aria-live="polite">
                <AnimatePresence initial={false} mode="popLayout">
                  {messages.map((item) => (
                    <FadeIn key={item.id}>
                      <div
                        className={`max-w-[90%] rounded-2xl px-3 py-2 text-sm leading-6 ${
                          item.role === 'user'
                            ? 'ml-auto rounded-br-sm bg-brand-600 text-white'
                            : 'rounded-bl-sm border border-slate-200 bg-white text-slate-700'
                        }`}
                      >
                        {item.content ? (
                          <AiMessageContent content={item.content} />
                        ) : (
                          <AiLoadingIndicator
                            label={
                              item.status || (isLoading ? 'Đang phân tích…' : 'Đang chuẩn bị…')
                            }
                            compact
                          />
                        )}
                      </div>
                    </FadeIn>
                  ))}
                </AnimatePresence>
                {(role === 'manager' || role === 'leadership') &&
                  messages.length === 1 &&
                  !isLoading && (
                    <FadeIn
                      className="space-y-2"
                      aria-label={`Câu hỏi gợi ý cho ${role === 'leadership' ? 'Lãnh đạo' : 'Quản lý'}`}
                    >
                      <p className="text-xs font-semibold text-slate-500">Gợi ý cho bạn</p>
                      <div className="flex flex-col items-start gap-2">
                        {(role === 'leadership'
                          ? LEADERSHIP_SUGGESTED_QUESTIONS
                          : MANAGER_SUGGESTED_QUESTIONS
                        ).map((question) => (
                          <Button
                            key={question}
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="min-h-9 max-w-full rounded-full border border-brand-200 bg-brand-50 px-3 py-1.5 text-left text-xs leading-5 text-brand-700 shadow-none hover:border-brand-300 hover:bg-brand-100 hover:text-brand-800"
                            onClick={() => setMessage(question)}
                          >
                            {question}
                          </Button>
                        ))}
                      </div>
                    </FadeIn>
                  )}
              </div>

              <form
                className="flex gap-2 border-t border-slate-200 bg-white p-3"
                onSubmit={handleSubmit}
              >
                <label className="sr-only" htmlFor="ai-message">
                  Câu hỏi cho Trợ lý AI
                </label>
                <Input
                  id="ai-message"
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  className="min-h-11 min-w-0 flex-1 rounded-xl border-slate-300 px-3 py-2 text-sm ring-brand-200 focus:border-brand-500 focus:ring-2"
                  placeholder="Ví dụ: Ai cần được theo dõi?"
                  disabled={isLoading}
                />
                <Button
                  type="submit"
                  className="min-h-11 min-w-16 rounded-xl px-3 py-2 text-sm"
                  loading={isLoading}
                  disabled={isLoading || !message.trim()}
                >
                  Gửi
                </Button>
              </form>
            </section>
          </SlideIn>
        )}
      </AnimatePresence>
      <Button
        type="button"
        size="lg"
        aria-label={isOpen ? 'Đóng Trợ lý AI' : 'Mở Trợ lý AI'}
        className="rounded-full bg-brand-700 px-4 py-3 text-sm shadow-lg hover:bg-brand-800"
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
      </Button>
    </div>
  )
}

export default AiAssistantWidget
