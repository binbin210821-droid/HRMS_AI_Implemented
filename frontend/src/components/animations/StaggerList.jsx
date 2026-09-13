import { Children } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './motion.js'

function StaggerList({ children, className = '', delayStep = 0.06 }) {
  const shouldReduceMotion = useReducedMotion()

  return (
    <div className={className}>
      <AnimatePresence initial={false} mode="popLayout">
        {Children.map(children, (child, index) => {
          if (child === null || child === undefined) return null

          return (
            <motion.div
              key={child.key ?? index}
              layout
              initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={shouldReduceMotion ? undefined : { opacity: 0, y: -8 }}
              transition={
                shouldReduceMotion
                  ? { duration: 0 }
                  : motionTransition(MOTION.content, index * delayStep)
              }
            >
              {child}
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}

export default StaggerList
