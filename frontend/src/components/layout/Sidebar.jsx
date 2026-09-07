import { NavLink } from 'react-router-dom'

import {
  AiAssistantIcon,
  AlertIcon,
  CompanyIcon,
  DashboardIcon,
  DepartmentsIcon,
  DirectivesIcon,
  EmployeesIcon,
  PerformanceIcon,
  TasksIcon,
} from '../icons/WorkMindIcons.jsx'
import { getNavigationItems } from './navigation.js'
import { useAuthStore } from '../../stores/authStore.js'

const ICONS = {
  alert: AlertIcon,
  assistant: AiAssistantIcon,
  company: CompanyIcon,
  dashboard: DashboardIcon,
  departments: DepartmentsIcon,
  directives: DirectivesIcon,
  employees: EmployeesIcon,
  performance: PerformanceIcon,
  tasks: TasksIcon,
}

function Sidebar() {
  const role = useAuthStore((state) => state.role)
  const navigationItems = getNavigationItems(role)

  return (
    <aside className="fixed bottom-0 left-0 top-16 z-20 hidden w-64 border-r border-slate-200 bg-white md:block">
      <nav className="space-y-1 p-4" aria-label="Điều hướng chính">
        <p className="mb-3 px-3 !text-caption !font-semibold !uppercase !tracking-wider !text-slate-400">
          Không gian làm việc
        </p>
        {navigationItems.map((item) => {
          const Icon = ICONS[item.icon] || DashboardIcon

          return (
            <NavLink
              key={item.key}
              to={item.href}
              end={item.key === 'overview'}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
                ].join(' ')
              }
              style={({ isActive }) => ({
                '--wm-icon': isActive ? '#2563eb' : '#475569',
                '--wm-icon-soft': isActive ? '#dbeafe' : '#f1f5f9',
                '--wm-icon-mid': isActive ? '#93c5fd' : '#94a3b8',
              })}
            >
              <span className="flex h-9 w-9 items-center justify-center" aria-hidden="true">
                <Icon size={33} title={item.label} />
              </span>
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>
    </aside>
  )
}

export default Sidebar
