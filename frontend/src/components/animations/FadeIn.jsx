import { motion } from 'framer-motion'

function FadeIn({ children, delay = 0, duration = 0.4, className = '', ...props }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration, delay, ease: 'easeOut' }}
      {...props}
    >
      {children}
    </motion.div>
  )
}

export default FadeIn
