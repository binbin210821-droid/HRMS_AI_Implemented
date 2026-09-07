import { useState } from 'react'

import { FadeIn } from './animations/index.js'
import { useRealtimeUpdates } from '../hooks/useRealtimeUpdates.js'

function RealtimeAlertNotice() {
  const [hasNewAlert, setHasNewAlert] = useState(false)

  useRealtimeUpdates('alerts', () => {
    setHasNewAlert(true)
  })

  if (!hasNewAlert) return null

  return (
    <FadeIn className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4" role="status">
      <p className="font-semibold text-amber-900">Có cảnh báo mới</p>
      <p className="mt-1 text-sm text-amber-800">
        Dữ liệu cảnh báo vừa được cập nhật theo thời gian thực.
      </p>
    </FadeIn>
  )
}

export default RealtimeAlertNotice
