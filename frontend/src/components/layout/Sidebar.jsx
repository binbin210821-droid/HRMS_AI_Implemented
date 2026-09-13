import { NavLink } from 'react-router-dom'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'

import { MOTION, motionTransition } from '../animations/motion.js'

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
import { Button } from '../ui/index.js'

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

function NavigationLinks({ navigationItems, onNavigate }) {
  return (
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
            onClick={onNavigate}
            className={({ isActive }) =>
              [
                'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition duration-motion-micro ease-motion-standard',
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
  )
}

function Sidebar({ isOpen = false, onClose = () => {} }) {
  const role = useAuthStore((state) => state.role)
  const navigationItems = getNavigationItems(role)
  const shouldReduceMotion = useReducedMotion()

  return (
    <>
      <aside className="fixed bottom-0 left-0 top-16 z-20 hidden w-64 border-r border-slate-200 bg-white md:block">
        <NavigationLinks navigationItems={navigationItems} />
      </aside>
      <AnimatePresence initial={false}>
        {isOpen && (
          <>
            <motion.div
              key="mobile-sidebar-backdrop"
              className="fixed inset-0 z-40 bg-slate-950/40 md:hidden"
              aria-hidden="true"
              initial={shouldReduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={shouldReduceMotion ? undefined : { opacity: 0 }}
              transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.standard)}
              onClick={onClose}
            />
            <motion.aside
              key="mobile-sidebar"
              id="main-navigation-mobile"
              className="fixed bottom-0 left-0 top-16 z-50 w-72 border-r border-slate-200 bg-white shadow-elevated md:hidden"
              aria-label="Menu điều hướng trên thiết bị di động"
              initial={shouldReduceMotion ? false : { opacity: 0, x: -24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={shouldReduceMotion ? undefined : { opacity: 0, x: -24 }}
              transition={shouldReduceMotion ? { duration: 0 } : motionTransition(MOTION.standard)}
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                <p className="text-sm font-semibold text-slate-800">Menu làm việc</p>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="px-2 py-1 text-xl leading-none"
                  aria-label="Đóng menu điều hướng"
                  onClick={onClose}
                >
                  ×
                </Button>
              </div>
              <NavigationLinks navigationItems={navigationItems} onNavigate={onClose} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  )
}

export default Sidebar
