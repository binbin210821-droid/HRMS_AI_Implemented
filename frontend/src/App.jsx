import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/ProtectedRoute.jsx'
import AlertsPage from './pages/AlertsPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import DepartmentEvaluationsPage from './pages/DepartmentEvaluationsPage.jsx'
import DirectivesPage from './pages/DirectivesPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import DepartmentsPage from './pages/DepartmentsPage.jsx'
import EmployeesPage from './pages/EmployeesPage.jsx'
import PerformanceEntryPage from './pages/PerformanceEntryPage.jsx'
import TasksPage from './pages/TasksPage.jsx'
import UnauthorizedPage from './pages/UnauthorizedPage.jsx'
import WorkspaceSectionPage from './pages/WorkspaceSectionPage.jsx'
import { useAuthStore } from './stores/authStore.js'

function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  )
}

function RoleHomeRedirect() {
  const { isAuthenticated, role } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={role === 'leadership' ? '/leadership' : '/manager'} replace />
}

export default App
