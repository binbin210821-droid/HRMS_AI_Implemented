import { motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './motion.js'

function FadeIn({ children, delay = 0, duration = MOTION.content, className = '', ...props }) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      className={className}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={shouldReduceMotion ? undefined : { opacity: 0, y: 8 }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(duration, delay)}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export default FadeIn
