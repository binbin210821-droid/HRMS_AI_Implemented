import { useHealth } from '../hooks/useHealth.js'

function HealthStatus() {
  const { data, error, isLoading } = useHealth()

  return (
    <div className="mt-8 rounded-xl border border-slate-200 bg-slate-50 p-5">
      <h2 className="text-lg font-semibold text-slate-900">Kiểm tra kết nối hệ thống</h2>
      <p className="mt-1 text-sm text-slate-600">
        Kiểm tra nhanh cho biết giao diện đã gọi được tới máy chủ và cơ sở dữ liệu hay chưa.
      </p>
      {isLoading && <p className="mt-4 text-sm text-slate-500">Đang kiểm tra...</p>}
      {error && <p className="mt-4 text-sm text-red-600">Chưa kết nối được tới máy chủ.</p>}
      {data && (
        <p className="mt-4 text-sm font-medium text-emerald-600">
          Hệ thống đang hoạt động. Kiểm tra lúc {new Date(data.timestamp).toLocaleString('vi-VN')}.
        </p>
      )}
    </div>
  )
}

export default HealthStatus
