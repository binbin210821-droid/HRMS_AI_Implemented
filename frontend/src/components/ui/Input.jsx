import { forwardRef } from 'react'

const Input = forwardRef(function Input({ className = '', invalid = false, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={`form-input ${invalid ? 'border-red-400 focus:border-red-500 focus:ring-red-100' : ''} ${className}`}
      aria-invalid={invalid || undefined}
      {...props}
    />
  )
})

export default Input
