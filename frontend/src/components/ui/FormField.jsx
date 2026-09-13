import { cloneElement, isValidElement } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from '../animations/motion.js'

function FormField({ id, label, error, helpText, required = false, children, className = '' }) {
  const shouldReduceMotion = useReducedMotion()
  const describedBy = [helpText && `${id}-help`, error && `${id}-error`].filter(Boolean).join(' ')
  const control = isValidElement(children)
    ? cloneElement(children, {
        id: children.props.id || id,
        'aria-invalid': error ? 'true' : undefined,
        'aria-describedby': describedBy || undefined,
      })
    : children

  return (
    <div className={className}>
      <label className="block text-sm font-semibold text-slate-700" htmlFor={id}>
        {label}
        {required && (
          <span className="ml-1 text-danger" aria-hidden="true">
            *
          </span>
        )}
      </label>
      <div className="mt-2">{control}</div>
      {helpText && (
        <p id={`${id}-help`} className="mt-1 text-xs text-slate-500">
          {helpText}
        </p>
      )}
      <AnimatePresence initial={false}>
        {error && (
          <motion.p
            key={`${id}-error`}
            id={`${id}-error`}
            className="mt-1 text-xs font-medium text-danger"
            role="alert"
            initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
            animate={
              shouldReduceMotion
                ? { opacity: 1, y: 0 }
                : { opacity: 1, y: 0, x: [0, -3, 3, -2, 2, 0] }
            }
            exit={shouldReduceMotion ? undefined : { opacity: 0, y: 8 }}
            transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.standard)}
          >
            {error}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}

export default FormField
