import { FadeIn } from '../animations/index.js'
import Button from './Button.jsx'

export function LoadingState({ message = 'Đang tải dữ liệu...' }) {
  return (
    <FadeIn
      className="flex items-center gap-2 text-sm text-ink-600"
      role="status"
      aria-live="polite"
    >
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-brand-600 border-t-transparent"
        aria-hidden="true"
      />
      {message}
    </FadeIn>
  )
}

export function EmptyState({ title = 'Chưa có dữ liệu', description = '' }) {
  return (
    <FadeIn className="rounded-control bg-surface-muted p-6 text-center">
      <p className="font-semibold text-ink-900">{title}</p>
      {description && <p className="mt-1 text-sm text-ink-600">{description}</p>}
    </FadeIn>
  )
}

export function ErrorState({ message = 'Không thể tải dữ liệu.', onRetry }) {
  return (
    <FadeIn
      className="rounded-control border border-red-200 bg-red-50 p-4 text-sm text-red-700"
      role="alert"
    >
      <p>{message}</p>
      {onRetry && (
        <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Thử lại
        </Button>
      )}
    </FadeIn>
  )
}
