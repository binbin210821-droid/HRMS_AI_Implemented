import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from '../animations/motion.js'

const DEFAULT_ACTION_FEEDBACK = {
  confirmAction: async () => true,
  notifyActionSuccess: () => {},
  notifyActionError: () => {},
}

const ActionFeedbackContext = createContext(DEFAULT_ACTION_FEEDBACK)

export function useActionFeedback() {
  return useContext(ActionFeedbackContext)
}

function ActionConfirmDialog({ request, onComplete }) {
  const shouldReduceMotion = useReducedMotion()
  const [isClosing, setIsClosing] = useState(false)
  const closeTimerRef = useRef(null)
  const confirmButtonRef = useRef(null)

  useEffect(() => {
    confirmButtonRef.current?.focus()
    return () => window.clearTimeout(closeTimerRef.current)
  }, [])

  function finish(value) {
    if (isClosing) return
    setIsClosing(true)
    const delay = shouldReduceMotion ? 0 : MOTION.modalContent * 1000
    closeTimerRef.current = window.setTimeout(() => onComplete(value), delay)
  }

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') finish(false)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  })

  const details = Array.isArray(request.details) ? request.details.filter(Boolean) : []
  const confirmLabel = request.confirmLabel || 'Xác nhận thực hiện'
  const isDanger = request.variant === 'danger'

  return (
    <motion.div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/45 p-4"
      role="presentation"
      initial={shouldReduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: isClosing ? 0 : 1 }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.modalOverlay)}
      onMouseDown={(event) => event.target === event.currentTarget && finish(false)}
    >
      <motion.section
        className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl ring-1 ring-slate-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="action-confirm-title"
        aria-describedby="action-confirm-description"
        initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
        animate={isClosing ? { opacity: 0, y: 8, scale: 0.98 } : { opacity: 1, y: 0, scale: 1 }}
        transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.modalContent)}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span
            className={`mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg ${
              isDanger ? 'bg-red-100 text-red-700' : 'bg-brand-100 text-brand-700'
            }`}
            aria-hidden="true"
          >
            {isDanger ? '!' : '?'}
          </span>
          <div className="min-w-0">
            <h2 id="action-confirm-title" className="!text-xl !font-bold !text-slate-900">
              {request.title || 'Xác nhận thao tác'}
            </h2>
            <p id="action-confirm-description" className="mt-2 text-sm leading-6 text-slate-600">
              {request.description || 'Bạn có chắc muốn thực hiện thao tác này không?'}
            </p>
          </div>
        </div>

        {details.length > 0 && (
          <div className="mt-4 rounded-xl bg-slate-50 p-4">
            <p className="text-xs font-bold uppercase tracking-wide text-slate-500">
              Thông tin thao tác
            </p>
            <ul className="mt-2 space-y-1.5 text-sm leading-6 text-slate-700">
              {details.map((detail) => (
                <li key={detail} className="flex gap-2">
                  <span className="text-brand-600" aria-hidden="true">
                    •
                  </span>
                  <span>{detail}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button type="button" className="secondary-button" onClick={() => finish(false)}>
            {request.cancelLabel || 'Hủy'}
          </button>
          <button
            ref={confirmButtonRef}
            type="button"
            className={isDanger ? 'primary-button bg-red-600 hover:bg-red-700' : 'primary-button'}
            onClick={() => finish(true)}
          >
            {confirmLabel}
          </button>
        </div>
      </motion.section>
    </motion.div>
  )
}

function ActionResultToast({ result, onDismiss }) {
  const shouldReduceMotion = useReducedMotion()
  const isError = result.status === 'error'

  return (
    <motion.div
      className={`fixed right-4 top-4 z-[80] w-[min(28rem,calc(100vw-2rem))] rounded-2xl border p-4 shadow-xl ${
        isError ? 'border-red-200 bg-red-50' : 'border-emerald-200 bg-emerald-50'
      }`}
      role={isError ? 'alert' : 'status'}
      aria-live="polite"
      initial={shouldReduceMotion ? false : { opacity: 0, y: -12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={shouldReduceMotion ? undefined : { opacity: 0, y: -8, scale: 0.98 }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.standard)}
    >
      <div className="flex items-start gap-3">
        <span
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${
            isError ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'
          }`}
          aria-hidden="true"
        >
          {isError ? '!' : '✓'}
        </span>
        <div className="min-w-0 flex-1">
          <p className={`font-bold ${isError ? 'text-red-900' : 'text-emerald-900'}`}>
            {result.title}
          </p>
          <p className={`mt-1 text-sm leading-6 ${isError ? 'text-red-800' : 'text-emerald-800'}`}>
            {result.message}
          </p>
          {result.details?.length > 0 && (
            <ul
              className={`mt-2 space-y-1 text-xs leading-5 ${isError ? 'text-red-700' : 'text-emerald-700'}`}
            >
              {result.details.map((detail) => (
                <li key={detail}>• {detail}</li>
              ))}
            </ul>
          )}
        </div>
        <button
          type="button"
          className="rounded-lg px-2 py-1 text-lg leading-none text-slate-500 transition duration-motion-micro hover:bg-black/5 hover:text-slate-800"
          aria-label="Đóng thông báo kết quả"
          onClick={onDismiss}
        >
          ×
        </button>
      </div>
    </motion.div>
  )
}

export default function ActionFeedbackProvider({ children }) {
  const [confirmation, setConfirmation] = useState(null)
  const [result, setResult] = useState(null)
  const confirmationResolverRef = useRef(null)
  const confirmedDetailsRef = useRef([])
  const resultTimerRef = useRef(null)

  useEffect(
    () => () => {
      window.clearTimeout(resultTimerRef.current)
      confirmationResolverRef.current?.(false)
    },
    [],
  )

  const confirmAction = useCallback((request = {}) => {
    if (confirmationResolverRef.current) confirmationResolverRef.current(false)
    return new Promise((resolve) => {
      confirmationResolverRef.current = resolve
      setConfirmation(request)
    })
  }, [])

  const completeConfirmation = useCallback(
    (confirmed) => {
      const resolve = confirmationResolverRef.current
      const request = confirmation
      confirmationResolverRef.current = null
      setConfirmation(null)
      confirmedDetailsRef.current = confirmed && request?.details ? request.details : []
      resolve?.(confirmed)
    },
    [confirmation],
  )

  const notify = useCallback((status, payload = {}) => {
    window.clearTimeout(resultTimerRef.current)
    const nextResult = {
      status,
      title: payload.title || (status === 'error' ? 'Chưa thực hiện được' : 'Đã thực hiện'),
      message: payload.message || '',
      details: Array.isArray(payload.details)
        ? payload.details.filter(Boolean)
        : confirmedDetailsRef.current,
    }
    confirmedDetailsRef.current = []
    setResult(nextResult)
    resultTimerRef.current = window.setTimeout(() => setResult(null), payload.duration || 6500)
  }, [])

  const notifyActionSuccess = useCallback((payload) => notify('success', payload), [notify])
  const notifyActionError = useCallback((payload) => notify('error', payload), [notify])

  const value = { confirmAction, notifyActionSuccess, notifyActionError }

  return (
    <ActionFeedbackContext.Provider value={value}>
      {children}
      <AnimatePresence initial={false}>
        {confirmation && (
          <ActionConfirmDialog
            key="action-confirmation"
            request={confirmation}
            onComplete={completeConfirmation}
          />
        )}
        {result && (
          <ActionResultToast
            key="action-result"
            result={result}
            onDismiss={() => setResult(null)}
          />
        )}
      </AnimatePresence>
    </ActionFeedbackContext.Provider>
  )
}
