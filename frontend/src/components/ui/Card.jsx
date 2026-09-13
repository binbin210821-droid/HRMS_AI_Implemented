function Card({
  as: Element = 'section',
  title,
  description,
  children,
  className = '',
  interactive = false,
  ...props
}) {
  return (
    <Element
      className={`rounded-card bg-white p-5 shadow-card ring-1 ring-slate-200 sm:p-6 ${interactive ? 'transition duration-motion-standard ease-motion-standard hover:-translate-y-0.5 hover:shadow-elevated' : ''} ${className}`}
      {...props}
    >
      {(title || description) && (
        <header className="mb-4">
          {title && <h2 className="text-slate-900">{title}</h2>}
          {description && <p className="mt-1 text-sm text-ink-600">{description}</p>}
        </header>
      )}
      {children}
    </Element>
  )
}

export default Card
