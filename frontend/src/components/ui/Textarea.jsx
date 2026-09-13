import { forwardRef } from 'react'

const Textarea = forwardRef(function Textarea({ className = '', invalid = false, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={`form-input min-h-24 resize-y ${invalid ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : ''} ${className}`}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
})

export default Textarea
