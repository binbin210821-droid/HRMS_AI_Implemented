import { forwardRef } from 'react'

const Table = forwardRef(function Table({ className = '', ...props }, ref) {
  return (
    <div className="w-full overflow-x-auto rounded-control border border-slate-200">
      <table ref={ref} className={`w-full text-left text-sm ${className}`} {...props} />
    </div>
  )
})

const TableHeader = forwardRef(function TableHeader({ className = '', ...props }, ref) {
  return <thead ref={ref} className={`bg-slate-50 ${className}`} {...props} />
})

const TableBody = forwardRef(function TableBody({ className = '', ...props }, ref) {
  return <tbody ref={ref} className={`divide-y divide-slate-100 ${className}`} {...props} />
})

const TableFooter = forwardRef(function TableFooter({ className = '', ...props }, ref) {
  return (
    <tfoot ref={ref} className={`border-t border-slate-200 bg-slate-50 ${className}`} {...props} />
  )
})

const TableRow = forwardRef(function TableRow({ className = '', ...props }, ref) {
  return (
    <tr
      ref={ref}
      className={`transition duration-motion-micro ease-motion-standard hover:bg-brand-50/40 ${className}`}
      {...props}
    />
  )
})

const TableHead = forwardRef(function TableHead({ className = '', ...props }, ref) {
  return (
    <th
      ref={ref}
      scope="col"
      className={`px-4 py-3 text-xs font-bold uppercase tracking-wide text-slate-500 ${className}`}
      {...props}
    />
  )
})

const TableCell = forwardRef(function TableCell({ className = '', ...props }, ref) {
  return (
    <td ref={ref} className={`px-4 py-3 align-middle text-slate-700 ${className}`} {...props} />
  )
})

function TableCaption({ className = '', ...props }) {
  return (
    <caption className={`px-4 py-3 text-left text-sm text-slate-500 ${className}`} {...props} />
  )
}

export { Table, TableBody, TableCaption, TableCell, TableFooter, TableHead, TableHeader, TableRow }
