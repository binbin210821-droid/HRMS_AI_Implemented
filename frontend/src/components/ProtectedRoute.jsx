import { Navigate, useLocation } from 'react-router-dom'

import { FadeIn } from './animations/index.js'
import { useAuthStore } from '../stores/authStore.js'

function ProtectedRoute({ children, allowedRoles = [] }) {
  const location = useLocation()
  const { isAuthenticated, isInitializing, role } = useAuthStore()

  if (isInitializing) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
        <FadeIn role="status" className="text-sm text-slate-600">
          Đang kiểm tra phiên đăng nhập...
        </FadeIn>
      </main>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(role)) {
    return <Navigate to="/unauthorized" replace />
  }

  return children
}

export default ProtectedRoute
