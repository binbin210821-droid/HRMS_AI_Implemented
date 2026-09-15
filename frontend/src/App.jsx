import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute.jsx'
import AiAssistantWidget from './features/ai/AiAssistantWidget.jsx'
import { useAuthStore } from './stores/authStore.js'

const AlertsPage = lazy(() => import('./pages/AlertsPage.jsx'))
const DashboardPage = lazy(() => import('./pages/DashboardPage.jsx'))
const DepartmentEvaluationsPage = lazy(() => import('./pages/DepartmentEvaluationsPage.jsx'))
const DirectivesPage = lazy(() => import('./pages/DirectivesPage.jsx'))
const LoginPage = lazy(() => import('./pages/LoginPage.jsx'))
const DepartmentsPage = lazy(() => import('./pages/DepartmentsPage.jsx'))
const EmployeesPage = lazy(() => import('./pages/EmployeesPage.jsx'))
const PerformanceEntryPage = lazy(() => import('./pages/PerformanceEntryPage.jsx'))
const TasksPage = lazy(() => import('./pages/TasksPage.jsx'))
const UnauthorizedPage = lazy(() => import('./pages/UnauthorizedPage.jsx'))
const WorkspaceSectionPage = lazy(() => import('./pages/WorkspaceSectionPage.jsx'))

function App() {
  const initializeSession = useAuthStore((state) => state.initializeSession)

  useEffect(() => {
    void initializeSession()
  }, [initializeSession])

  return (
    <BrowserRouter>
      <AiAssistantWidget />
      <Suspense fallback={<p className="p-6 text-sm text-ink-600">Đang tải trang...</p>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/manager"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <DashboardPage title="Tổng quan & Phân tích hiệu suất" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/employees"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <EmployeesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/analytics"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <Navigate to="/manager" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/alerts"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <AlertsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/performance"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <PerformanceEntryPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/overload"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <Navigate to="/manager/alerts" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/tasks"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <TasksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/directives"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <DirectivesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <DashboardPage title="Tổng quan & Phân tích hiệu suất toàn công ty" />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/performance"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <Navigate to="/leadership" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/alerts"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <AlertsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/departments"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <DepartmentsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/employees"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <Navigate to="/leadership/departments" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/overload"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <Navigate to="/leadership/alerts" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/managers"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <Navigate to="/leadership/department-evaluations" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/department-evaluations"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <DepartmentEvaluationsPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/users"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <Navigate to="/leadership" replace />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/tasks"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <TasksPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/directives"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <DirectivesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manager/:section"
            element={
              <ProtectedRoute allowedRoles={['manager']}>
                <WorkspaceSectionPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leadership/:section"
            element={
              <ProtectedRoute allowedRoles={['leadership']}>
                <WorkspaceSectionPage />
              </ProtectedRoute>
            }
          />
          <Route path="/unauthorized" element={<UnauthorizedPage />} />
          <Route path="/" element={<RoleHomeRedirect />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

function RoleHomeRedirect() {
  const { isAuthenticated, isInitializing, role } = useAuthStore()
  if (isInitializing) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={role === 'leadership' ? '/leadership' : '/manager'} replace />
}

export default App
