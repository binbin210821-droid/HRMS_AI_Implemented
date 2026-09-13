import { motion, useReducedMotion } from 'framer-motion'

import { AiAssistantIcon } from '../icons/WorkMindIcons.jsx'
import { MOTION } from './motion.js'

function AiLoadingIndicator({ label = 'AI đang phân tích…', compact = false, className = '' }) {
  const shouldReduceMotion = useReducedMotion()
  const dotTransition = shouldReduceMotion
    ? { duration: 0 }
    : { duration: MOTION.loadingDots, repeat: Infinity, ease: 'easeInOut' }

  return (
    <motion.div
      role="status"
      aria-label={label}
      className={`flex items-center gap-2 text-sm font-medium text-brand-700 ${
        compact ? 'py-0.5' : 'rounded-xl bg-brand-50 px-3 py-2.5'
      } ${className}`}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        shouldReduceMotion ? { duration: 0 } : { duration: MOTION.loadingIntro, ease: 'easeOut' }
      }
    >
      <motion.span
        className="shrink-0"
        aria-hidden="true"
        animate={shouldReduceMotion ? undefined : { rotate: [0, 8, -8, 0], scale: [1, 1.08, 1] }}
        transition={
          shouldReduceMotion ? { duration: 0 } : { duration: MOTION.loadingIcon, repeat: Infinity }
        }
      >
        <AiAssistantIcon size={compact ? 15 : 17} />
      </motion.span>
      <span>{label}</span>
      <span className="ml-0.5 flex items-center gap-1" aria-hidden="true">
        {[0, 1, 2].map((index) => (
          <motion.span
            key={index}
            className="h-1.5 w-1.5 rounded-full bg-brand-500"
            animate={shouldReduceMotion ? undefined : { opacity: [0.3, 1, 0.3], y: [0, -3, 0] }}
            transition={{ ...dotTransition, delay: index * 0.14 }}
          />
        ))}
      </span>
    </motion.div>
  )
}

export default AiLoadingIndicator
