import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence } from 'framer-motion'

import { streamAiSummary } from '../ai/aiApi.js'
import AiSuggestionToggle from '../ai/AiSuggestionToggle.jsx'
import {
  makeAiSuggestionKey,
  readAiSuggestion,
  writeAiSuggestion,
} from '../ai/aiSuggestionStorage.js'
import { AiLoadingIndicator, FadeIn } from '../../components/animations/index.js'
import {
  AiAssistantIcon,
  AlertIcon,
  EmployeesIcon,
  PerformanceIcon,
  TasksIcon,
} from '../../components/icons/WorkMindIcons.jsx'
import { Button } from '../../components/ui/index.js'
import { useAuthStore } from '../../stores/authStore.js'

const SUMMARY_PROMPT =
  'Hãy tóm tắt ngắn gọn tình hình nhân sự và các điểm cần lưu ý trong phạm vi tôi đang quản lý hôm nay.'

const SECTION_META = [
  {
    match: 'tổng quan',
    label: 'Tổng quan',
    description: 'Các chỉ số chính trong phạm vi bạn quản lý.',
    icon: EmployeesIcon,
    iconClassName: 'bg-brand-100 text-brand-700',
  },
  {
    match: 'tình trạng',
    label: 'Tình trạng vận hành',
    description: 'Những điểm cần được theo dõi trong hôm nay.',
    icon: AlertIcon,
    iconClassName: 'bg-amber-100 text-amber-700',
  },
  {
    match: 'xu hướng',
    label: 'Xu hướng gần đây',
    description: 'Diễn biến hiệu suất trong những ngày gần nhất.',
    icon: PerformanceIcon,
    iconClassName: 'bg-emerald-100 text-emerald-700',
  },
  {
    match: 'gợi ý',
    label: 'Gợi ý hành động',
    description: 'Các việc nên ưu tiên xem xét tiếp theo.',
    icon: TasksIcon,
    iconClassName: 'bg-violet-100 text-violet-700',
  },
]

function cleanMarkdown(value) {
  return value
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/__(.*?)__/g, '$1')
    .trim()
}

function getSectionMeta(title) {
  const normalizedTitle = title.toLocaleLowerCase('vi-VN')
  return (
    SECTION_META.find((section) => normalizedTitle.includes(section.match)) || {
      label: cleanMarkdown(title),
      description: 'Thông tin được Trợ lý AI tổng hợp.',
      icon: AiAssistantIcon,
      iconClassName: 'bg-brand-100 text-brand-700',
    }
  )
}

function splitInlineSections(content) {
  const sectionNames =
    'Tổng quan|Tình trạng vận hành|Xu hướng(?: hiệu suất)? gần đây|Gợi ý hành động'
  const sectionHeading = new RegExp(`\\*{0,2}(${sectionNames})\\*{0,2}\\s*:`, 'gi')

  return content.replace(sectionHeading, '\n**$1:**\n')
}

function parseSummary(content) {
  const lines = splitInlineSections(content.replace(/\r/g, '')).split('\n')
  const intro = []
  const sections = []
  let currentSection = null

  const flushSection = () => {
    if (currentSection && (currentSection.items.length || currentSection.paragraphs.length)) {
      sections.push(currentSection)
    }
  }

  lines.forEach((line) => {
    const trimmedLine = line.trim()
    if (!trimmedLine) return

    const headingMatch = trimmedLine.match(/^\*\*(.+?)\*\*\s*:?$/)
    if (headingMatch) {
      flushSection()
      currentSection = { title: headingMatch[1], items: [], paragraphs: [] }
      return
    }

    const bulletMatch = trimmedLine.match(/^(?:[*-]|•)\s+(.+)$/)
    const target = currentSection ? currentSection.items : intro
    const value = bulletMatch ? bulletMatch[1] : trimmedLine
    const labeledValue = value.match(/^\*\*(.+?)\*\*\s*:?\s*(.*)$/)

    if (currentSection && bulletMatch) {
      currentSection.items.push(
        labeledValue
          ? { label: cleanMarkdown(labeledValue[1]), value: cleanMarkdown(labeledValue[2]) }
          : { label: '', value: cleanMarkdown(value) },
      )
    } else if (currentSection) {
      currentSection.paragraphs.push(cleanMarkdown(value))
    } else {
      target.push(cleanMarkdown(value))
    }
  })

  flushSection()
  return { intro, sections }
}

function SectionHeader({ section }) {
  const meta = getSectionMeta(section.title)
  const Icon = meta.icon

  return (
    <div className="flex items-start gap-3">
      <span className={`mt-0.5 rounded-xl p-2 ${meta.iconClassName}`}>
        <Icon size={18} aria-hidden="true" />
      </span>
      <div>
        <h3 className="text-sm font-bold text-slate-900">{meta.label}</h3>
        <p className="mt-0.5 text-xs text-slate-500">{meta.description}</p>
      </div>
    </div>
  )
}

function SummaryContent({ content }) {
  const { intro, sections } = parseSummary(content)

  if (!sections.length) {
    return <p className="text-sm leading-7 text-slate-700">{intro.join(' ')}</p>
  }

  return (
    <div className="space-y-5">
      {intro.length > 0 && (
        <p className="text-sm font-medium leading-6 text-slate-700">{intro.join(' ')}</p>
      )}

      <AnimatePresence initial={false} mode="popLayout">
        {sections.map((section, sectionIndex) => {
          const isOverview = getSectionMeta(section.title).match === 'tổng quan'
          const isActionSection = getSectionMeta(section.title).match === 'gợi ý'

          return (
            <FadeIn
              key={`${section.title}-${sectionIndex}`}
              className="rounded-2xl border border-slate-200/80 bg-white/80 p-4 shadow-sm"
              delay={sectionIndex * 0.06}
              layout
            >
              <SectionHeader section={section} />

              {section.paragraphs.length > 0 && (
                <div className="mt-4 space-y-2 text-sm leading-7 text-slate-700">
                  {section.paragraphs.map((paragraph, index) => (
                    <p key={`${paragraph}-${index}`}>{paragraph}</p>
                  ))}
                </div>
              )}

              {section.items.length > 0 && (
                <div
                  className={
                    isOverview
                      ? 'mt-4 grid gap-3 sm:grid-cols-3'
                      : isActionSection
                        ? 'mt-4 space-y-2.5'
                        : 'mt-4 divide-y divide-slate-100 rounded-xl border border-slate-100'
                  }
                >
                  {section.items.map((item, index) => {
                    if (isOverview) {
                      return (
                        <div key={`${item.label}-${index}`} className="rounded-xl bg-slate-50 p-3">
                          <p className="text-xs font-medium text-slate-500">
                            {item.label || 'Thông tin'}
                          </p>
                          <p className="mt-1 text-xl font-bold tracking-tight text-slate-900">
                            {item.value}
                          </p>
                        </div>
                      )
                    }

                    if (isActionSection) {
                      return (
                        <div
                          key={`${item.value}-${index}`}
                          className="flex items-start gap-3 rounded-xl bg-violet-50/70 px-3 py-2.5 text-sm leading-6 text-slate-700"
                        >
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-600 text-xs font-bold text-white">
                            {index + 1}
                          </span>
                          <span>{item.value}</span>
                        </div>
                      )
                    }

                    return (
                      <div
                        key={`${item.label}-${index}`}
                        className="flex flex-col gap-1 px-3 py-2.5 text-sm sm:flex-row sm:items-start sm:justify-between sm:gap-4"
                      >
                        <span className="font-semibold text-slate-700">
                          {item.label || 'Chi tiết'}
                        </span>
                        <span className="leading-6 text-slate-600 sm:max-w-[70%] sm:text-right">
                          {item.value}
                        </span>
                      </div>
                    )
                  })}
                </div>
              )}
            </FadeIn>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

function AiSummaryCard() {
  const role = useAuthStore((state) => state.role) || 'unknown'
  const storageKey = makeAiSuggestionKey('overview-summary', role)
  const cachedSuggestion = readAiSuggestion(storageKey)
  const [content, setContent] = useState(() => cachedSuggestion?.content || '')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [hasReceivedToken, setHasReceivedToken] = useState(Boolean(cachedSuggestion?.content))
  const [lastUpdatedAt, setLastUpdatedAt] = useState(() =>
    cachedSuggestion?.updatedAt ? new Date(cachedSuggestion.updatedAt) : null,
  )
  const [isVisible, setIsVisible] = useState(cachedSuggestion?.isVisible ?? true)
  const abortControllerRef = useRef(null)
  const hasStartedRef = useRef(Boolean(cachedSuggestion?.content))
  const isMountedRef = useRef(false)
  const unmountTimerRef = useRef(null)

  const requestSummary = useCallback(
    async (forceRefresh = false) => {
      abortControllerRef.current?.abort()
      const controller = new AbortController()
      abortControllerRef.current = controller
      setContent('')
      setError('')
      setHasReceivedToken(false)
      setIsLoading(true)
      let streamedContent = ''

      try {
        await streamAiSummary(SUMMARY_PROMPT, {
          signal: controller.signal,
          forceRefresh,
          onToken: (token) => {
            if (!isMountedRef.current) return
            streamedContent += token
            setHasReceivedToken(true)
            setContent(streamedContent)
          },
        })
        if (isMountedRef.current) {
          const updatedAt = new Date()
          setLastUpdatedAt(updatedAt)
          if (streamedContent) {
            writeAiSuggestion(storageKey, {
              ...readAiSuggestion(storageKey),
              content: streamedContent,
              updatedAt: updatedAt.toISOString(),
              isVisible,
            })
          }
        }
      } catch (requestError) {
        if (requestError.name !== 'AbortError' && isMountedRef.current) {
          setError(
            requestError.message || 'Trợ lý AI hiện chưa sẵn sàng. Vui lòng thử lại sau ít phút.',
          )
        }
      } finally {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null
          if (isMountedRef.current) setIsLoading(false)
        }
      }
    },
    [isVisible, storageKey],
  )

  useEffect(() => {
    isMountedRef.current = true
    if (unmountTimerRef.current) {
      window.clearTimeout(unmountTimerRef.current)
      unmountTimerRef.current = null
    }

    if (!hasStartedRef.current) {
      hasStartedRef.current = true
      void requestSummary()
    }

    return () => {
      isMountedRef.current = false
      unmountTimerRef.current = window.setTimeout(() => {
        if (!isMountedRef.current) abortControllerRef.current?.abort()
        unmountTimerRef.current = null
      }, 0)
    }
  }, [requestSummary])

  function toggleVisibility() {
    setIsVisible((current) => {
      const next = !current
      writeAiSuggestion(storageKey, {
        ...readAiSuggestion(storageKey),
        content,
        updatedAt: lastUpdatedAt?.toISOString(),
        isVisible: next,
      })
      return next
    })
  }

  return (
    <section className="overflow-hidden rounded-2xl bg-white shadow-card ring-1 ring-slate-200">
      <div className="bg-gradient-to-br from-brand-50 via-white to-indigo-50/70 p-6 pb-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-caption font-semibold uppercase tracking-wider text-brand-700">
              <AiAssistantIcon size={16} title="Trợ lý AI" />
              Trợ lý AI
            </div>
            <h2 className="mt-2 text-xl font-bold tracking-tight text-slate-900">
              AI tóm tắt hôm nay
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Tóm tắt nhanh các điểm đáng lưu ý trong phạm vi bạn quản lý.
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            <AiSuggestionToggle isVisible={isVisible} onToggle={toggleVisibility} />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => void requestSummary(true)}
              disabled={isLoading}
            >
              <span aria-hidden="true" className={isLoading ? 'animate-spin' : ''}>
                ↻
              </span>
              {isLoading ? 'Đang cập nhật' : 'Làm mới'}
            </Button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 px-2.5 py-1 font-medium ring-1 ring-brand-100">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
            Phạm vi quản lý của bạn
          </span>
          <span>AI chỉ gợi ý — hãy kiểm tra trước khi hành động.</span>
          {lastUpdatedAt && (
            <>
              <span>•</span>
              <span>
                Cập nhật lúc{' '}
                {lastUpdatedAt.toLocaleTimeString('vi-VN', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </>
          )}
        </div>
      </div>

      {isVisible ? (
        <div
          className="border-t border-slate-100 bg-slate-50/70 p-4 sm:p-5"
          aria-live="polite"
          aria-busy={isLoading}
        >
          {error ? (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <span>{error}</span>
              <Button
                type="button"
                variant="danger"
                size="sm"
                onClick={() => void requestSummary()}
              >
                Thử lại
              </Button>
            </div>
          ) : isLoading && !hasReceivedToken ? (
            <div className="space-y-3" role="status" aria-label="Đang phân tích tóm tắt AI">
              <AiLoadingIndicator label="AI đang phân tích dữ liệu…" />
              <div className="h-4 w-2/5 animate-pulse rounded bg-slate-200" />
              <div className="h-20 animate-pulse rounded-xl bg-white ring-1 ring-slate-200" />
              <div className="h-16 animate-pulse rounded-xl bg-white ring-1 ring-slate-200" />
            </div>
          ) : (
            <>
              {content ? <SummaryContent content={content} /> : <p>Chưa có nội dung tóm tắt.</p>}
              {isLoading && (
                <AiLoadingIndicator label="AI đang hoàn thiện tóm tắt…" compact className="mt-3" />
              )}
            </>
          )}
        </div>
      ) : (
        <div className="border-t border-slate-100 bg-slate-50/70 px-4 py-4 text-sm text-slate-600 sm:px-5">
          Gợi ý AI đang tạm ẩn. Bạn có thể hiện lại bất cứ lúc nào bằng nút “Hiện gợi ý AI”.
        </div>
      )}
    </section>
  )
}

export default AiSummaryCard
