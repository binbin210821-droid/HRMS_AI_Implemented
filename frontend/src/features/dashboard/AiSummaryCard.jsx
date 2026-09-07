import { useCallback, useEffect, useRef, useState } from 'react'

import { streamAiChat } from '../ai/aiApi.js'
import { AiAssistantIcon } from '../../components/icons/WorkMindIcons.jsx'

const SUMMARY_PROMPT =
  'Hãy tóm tắt ngắn gọn tình hình nhân sự và các điểm cần lưu ý trong phạm vi tôi đang quản lý hôm nay.'

function AiSummaryCard() {
  const [content, setContent] = useState('')
  const [error, setError] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [hasReceivedToken, setHasReceivedToken] = useState(false)
  const abortControllerRef = useRef(null)
  const hasStartedRef = useRef(false)
  const isMountedRef = useRef(false)
  const unmountTimerRef = useRef(null)

  const requestSummary = useCallback(async () => {
    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller
    setContent('')
    setError('')
    setHasReceivedToken(false)
    setIsLoading(true)

    try {
      await streamAiChat(SUMMARY_PROMPT, {
        signal: controller.signal,
        onToken: (token) => {
          if (!isMountedRef.current) return
          setHasReceivedToken(true)
          setContent((current) => current + token)
        },
      })
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
  }, [])

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

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="!text-caption !font-semibold !uppercase !tracking-wider !text-brand-600">
            Hỗ trợ chủ động
          </p>
          <h2 className="mt-2 text-xl font-bold text-slate-900">
            <AiAssistantIcon
              className="mr-2 inline-block align-[-3px]"
              size={22}
              title="Trợ lý AI"
            />
            AI tóm tắt hôm nay
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Tóm tắt nhanh các điểm đáng lưu ý trong phạm vi bạn quản lý.
          </p>
        </div>
        <button
          type="button"
          className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-brand-400 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => void requestSummary()}
          disabled={isLoading}
        >
          Làm mới
        </button>
      </div>

      <div
        className="mt-5 rounded-xl border border-brand-100 bg-brand-50/60 p-4"
        aria-live="polite"
      >
        {error ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            <span>{error}</span>
            <button
              type="button"
              className="rounded-lg bg-red-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-red-700"
              onClick={() => void requestSummary()}
            >
              Thử lại
            </button>
          </div>
        ) : isLoading && !hasReceivedToken ? (
          <p className="text-sm text-slate-600">Đang phân tích…</p>
        ) : (
          <p className="whitespace-pre-line text-sm leading-7 text-slate-700">
            {content || 'Chưa có nội dung tóm tắt.'}
            {isLoading && <span className="ml-1 animate-pulse text-brand-600">▌</span>}
          </p>
        )}
      </div>
    </section>
  )
}

export default AiSummaryCard
