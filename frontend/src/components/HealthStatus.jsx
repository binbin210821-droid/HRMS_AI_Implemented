import { useHealth } from '../hooks/useHealth.js'
import { FadeIn } from './animations/index.js'

function HealthStatus() {
  const { data, error, isLoading } = useHealth()

  return (
    <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-base font-semibold text-slate-900">Trạng thái hệ thống</h2>
      {isLoading && <FadeIn className="mt-2 text-sm text-slate-500">Đang kiểm tra...</FadeIn>}
      {error && (
        <FadeIn className="mt-2 text-sm text-red-600" role="alert">
          Chưa kết nối được tới máy chủ.
        </FadeIn>
      )}
      {data && (
        <FadeIn className="mt-2 flex items-center gap-2 text-sm font-medium text-emerald-600">
          <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
          Hệ thống đang hoạt động
        </FadeIn>
      )}
    </div>
  )
}

export default HealthStatus
