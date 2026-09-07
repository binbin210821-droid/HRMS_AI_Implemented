import { useNavigate } from 'react-router-dom'

import { ROLE_LABELS } from './navigation.js'
import { useAuthStore } from '../../stores/authStore.js'
import NotificationBell from '../../features/notifications/NotificationBell.jsx'
import WorkMindLogo from '../brand/WorkMindLogo.jsx'

function Header() {
  const navigate = useNavigate()
  const { claims, role, logout } = useAuthStore()

  function handleLogout() {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header className="fixed inset-x-0 top-0 z-30 h-16 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="flex h-full items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <WorkMindLogo />
          <span className="hidden h-7 w-px bg-slate-200 sm:block" aria-hidden="true" />
          <p className="hidden !text-[0.9rem] !font-medium !leading-5 !text-slate-500 sm:block">
            Quản trị hiệu suất
          </p>
        </div>

        <div className="flex items-center gap-3 sm:gap-5">
          <NotificationBell />
          <div className="hidden text-right sm:block">
            <p className="!text-[1.0625rem] !font-semibold !leading-6 !text-slate-800">
              {claims?.full_name || claims?.username || 'Người dùng'}
            </p>
            <p className="!text-[0.9rem] !leading-5 !text-slate-500">{ROLE_LABELS[role]}</p>
          </div>
          <div className="flex h-[2.7rem] w-[2.7rem] items-center justify-center rounded-full bg-brand-100 text-[1.0625rem] font-bold text-brand-700">
            {(claims?.full_name || claims?.username || 'U').charAt(0).toUpperCase()}
          </div>
          <button
            type="button"
            className="rounded-lg px-2.5 py-2.5 text-[1.0625rem] font-medium text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
            onClick={handleLogout}
          >
            Đăng xuất
          </button>
        </div>
      </div>
    </header>
  )
}

export default Header
