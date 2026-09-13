import { cloneElement, isValidElement, useId } from 'react'

function Tooltip({ label, children, className = '' }) {
  const tooltipId = useId()
  const trigger = isValidElement(children)
    ? cloneElement(children, { 'aria-describedby': tooltipId })
    : children

  return (
    <span className={`group relative inline-flex ${className}`}>
      {trigger}
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-30 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity duration-motion-micro group-hover:opacity-100 group-focus-within:opacity-100"
      >
        {label}
      </span>
    </span>
  )
}

export default Tooltip
