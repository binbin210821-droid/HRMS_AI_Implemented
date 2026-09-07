function WorkMindLogo({ className = '', compact = false }) {
  return (
    <img
      src="/workmind-logo.png"
      alt="WorkMind HRMS"
      className={`object-contain object-left ${compact ? 'h-[3.375rem] w-[3.375rem]' : 'h-[3.375rem] w-auto max-w-[14.25rem]'} ${className}`}
    />
  )
}

export default WorkMindLogo
