import { animate, motion, useMotionValue, useReducedMotion, useTransform } from 'framer-motion'
import { useEffect } from 'react'

function CounterNumber({ value, duration = 0.8, className = '' }) {
  const numericValue = Number(value)
  const shouldReduceMotion = useReducedMotion()
  const count = useMotionValue(Number.isFinite(numericValue) ? 0 : value)
  const displayValue = Number.isFinite(numericValue)
    ? Math.round(numericValue).toLocaleString('vi-VN')
    : value
  const formattedCount = useTransform(count, (latest) =>
    Number.isFinite(numericValue) ? Math.round(latest).toLocaleString('vi-VN') : displayValue,
  )

  useEffect(() => {
    if (!Number.isFinite(numericValue) || shouldReduceMotion) return undefined

    const controls = animate(count, numericValue, { duration, ease: 'easeOut' })
    return () => controls.stop()
  }, [count, duration, numericValue, shouldReduceMotion])

  if (shouldReduceMotion) {
    return (
      <span className={className} aria-label={String(value)}>
        {displayValue}
      </span>
    )
  }

  return (
    <motion.span className={className} aria-label={String(value)}>
      {formattedCount}
    </motion.span>
  )
}

export default CounterNumber
