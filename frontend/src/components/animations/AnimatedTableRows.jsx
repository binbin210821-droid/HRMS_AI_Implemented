import { Children, Fragment } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from './motion.js'

function AnimatedTableRows({ children }) {
  const shouldReduceMotion = useReducedMotion()
  const rows = Children.toArray(children).flatMap((child) =>
    child.type === Fragment ? Children.toArray(child.props.children) : [child],
  )

  return (
    <AnimatePresence initial={false} mode="popLayout">
      {rows.map((row, index) => {
        if (!row) return null

        const { children: rowChildren, ...rowProps } = row.props

        return (
          <motion.tr
            key={row.key ?? index}
            {...rowProps}
            layout="position"
            initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={shouldReduceMotion ? undefined : { opacity: 0, y: -8 }}
            transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.standard)}
          >
            {rowChildren}
          </motion.tr>
        )
      })}
    </AnimatePresence>
  )
}

export default AnimatedTableRows
