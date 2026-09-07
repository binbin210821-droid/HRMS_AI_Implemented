import { animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { useEffect } from 'react'

function CounterNumber({ value, duration = 0.8, className = '' }) {
  const numericValue = Number(value)
  const count = useMotionValue(Number.isFinite(numericValue) ? 0 : value)
  const formattedCount = useTransform(count, (latest) =>
    Number.isFinite(numericValue) ? Math.round(latest).toLocaleString('vi-VN') : value,
  )

  useEffect(() => {
    if (!Number.isFinite(numericValue)) return undefined

    const controls = animate(count, numericValue, { duration, ease: 'easeOut' })
    return () => controls.stop()
  }, [count, duration, numericValue])

  return (
    <motion.span className={className} aria-label={String(value)}>
      {formattedCount}
    </motion.span>
  )
}

export default CounterNumber
