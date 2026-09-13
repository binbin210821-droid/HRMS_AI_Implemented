import { motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './motion.js'

function PageTransition({ children, className = '', ...props }) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <motion.div
      className={className}
      initial={shouldReduceMotion ? false : { opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={shouldReduceMotion ? undefined : { opacity: 0 }}
      transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.page)}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export default PageTransition
