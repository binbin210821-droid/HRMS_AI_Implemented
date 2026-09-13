const VARIANTS = {
  neutral: 'bg-slate-100 text-slate-700',
  info: 'bg-brand-50 text-brand-700',
  success: 'bg-emerald-50 text-emerald-700',
  warning: 'bg-amber-50 text-amber-700',
  danger: 'bg-red-50 text-red-700',
}

function Badge({ children, variant = 'neutral', className = '', ...props }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold transition duration-motion-micro ease-motion-standard ${VARIANTS[variant] || VARIANTS.neutral} ${className}`}
      {...props}
    >
      {children}
    </span>
  )
}

export default Badge
