import { motion } from 'framer-motion'

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
  duration = 0.45,
  className = '',
  ...props
}) {
  const offset = offsets[direction] || offsets.up

  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, ...offset }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration, delay, ease: 'easeOut' }}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export default SlideIn
