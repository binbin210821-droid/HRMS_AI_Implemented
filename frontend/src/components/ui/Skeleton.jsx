function Skeleton({ className = '', ...props }) {
  return (
    <span
      className={`block animate-pulse rounded-md bg-slate-200 ${className}`}
      aria-hidden="true"
      {...props}
    />
  )
}

export default Skeleton
