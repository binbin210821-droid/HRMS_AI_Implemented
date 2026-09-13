import { motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './motion.js'

const offsets = {
  left: { x: -24, y: 0 },
  right: { x: 24, y: 0 },
  up: { x: 0, y: 24 },
  down: { x: 0, y: -24 },
}

function SlideIn({
  children,
  direction = 'up',
  delay = 0,
  duration = MOTION.content,
  className = '',
  ...props
}) {
  const offset = offsets[direction] || offsets.up
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      className={className}
      initial={shouldReduceMotion ? false : { opacity: 0, ...offset }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={shouldReduceMotion ? undefined : { opacity: 0, ...offset }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(duration, delay)}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export default SlideIn
