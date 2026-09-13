import { useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './animations/motion.js'

function Modal({ title, description, onClose, children, className = '' }) {
  const shouldReduceMotion = useReducedMotion()
  const [isClosing, setIsClosing] = useState(false)
  const closeTimerRef = useRef(null)

  useEffect(() => () => window.clearTimeout(closeTimerRef.current), [])

  function requestClose() {
    if (isClosing) return
    setIsClosing(true)
    if (shouldReduceMotion) {
      onClose()
      return
    }
    closeTimerRef.current = window.setTimeout(() => {
      const closeResult = onClose()
      if (closeResult === false) setIsClosing(false)
    }, MOTION.modalContent * 1000)
  }

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        event.preventDefault()
        requestClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  })

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4"
      role="presentation"
      initial={shouldReduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: isClosing ? 0 : 1 }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.modalOverlay)}
      onMouseDown={(event) => event.target === event.currentTarget && requestClose()}
    >
      <motion.section
        className={`max-h-[90vh] w-full overflow-y-auto rounded-xl bg-white p-5 shadow-xl sm:p-6 ${className || 'max-w-lg'}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        initial={shouldReduceMotion ? false : { opacity: 0, y: 12, scale: 0.98 }}
        animate={isClosing ? { opacity: 0, y: 8, scale: 0.98 } : { opacity: 1, y: 0, scale: 1 }}
        transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.modalContent)}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="modal-title" className="text-slate-900">
              {title}
            </h2>
            {description && <p className="mt-1 !text-sm !text-slate-500">{description}</p>}
          </div>
          <button
            type="button"
            className="rounded-lg px-2 py-1 text-xl leading-none text-slate-400 hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            aria-label="Đóng cửa sổ"
            onClick={requestClose}
          >
            ×
          </button>
        </div>
        <div className="mt-5">{children}</div>
      </motion.section>
    </motion.div>
  )
}

export default Modal
