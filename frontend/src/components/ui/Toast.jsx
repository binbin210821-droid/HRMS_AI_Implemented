const VARIANTS = {
  success: {
    container: 'border-emerald-200 bg-emerald-50',
    title: 'text-emerald-900',
    message: 'text-emerald-800',
    icon: '✓',
  },
  error: {
    container: 'border-red-200 bg-red-50',
    title: 'text-red-900',
    message: 'text-red-800',
    icon: '!',
  },
  info: {
    container: 'border-brand-100 bg-brand-50',
    title: 'text-brand-700',
    message: 'text-slate-700',
    icon: 'i',
  },
}

function Toast({ title, message, variant = 'info', onDismiss, className = '' }) {
  const styles = VARIANTS[variant] || VARIANTS.info
  const isError = variant === 'error'

  return (
    <div
      className={`flex items-start gap-3 rounded-card border p-4 shadow-elevated ${styles.container} ${className}`}
      role={isError ? 'alert' : 'status'}
      aria-live="polite"
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/70 text-sm font-bold"
        aria-hidden="true"
      >
        {styles.icon}
      </span>
      <div className="min-w-0 flex-1">
        {title && <p className={`font-bold ${styles.title}`}>{title}</p>}
        {message && <p className={`mt-1 text-sm leading-6 ${styles.message}`}>{message}</p>}
      </div>
      {onDismiss && (
        <button
          type="button"
          className="rounded-lg px-2 py-1 text-lg leading-none text-slate-500 transition hover:bg-black/5 hover:text-slate-800"
          aria-label="Đóng thông báo"
          onClick={onDismiss}
        >
          ×
        </button>
      )}
    </div>
  )
}

export default Toast
