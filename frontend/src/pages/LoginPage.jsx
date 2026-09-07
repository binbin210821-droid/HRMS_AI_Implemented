import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { login } from '../features/auth/authApi.js'
import { useAuthStore } from '../stores/authStore.js'

function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated, login: saveSession } = useAuthStore()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (isAuthenticated) return <Navigate to="/" replace />

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const username = form.username.trim()
    if (!username || !form.password) {
      setError('Vui lòng nhập tên đăng nhập và mật khẩu.')
      return
    }

    setError('')
    setIsSubmitting(true)
    try {
      const response = await login({ username, password: form.password })
      saveSession(response)
      const role = useAuthStore.getState().role
      navigate(role === 'leadership' ? '/leadership' : '/manager', { replace: true })
    } catch (requestError) {
      setError(requestError.message || 'Đăng nhập không thành công. Vui lòng thử lại.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
      <section className="w-full max-w-md rounded-2xl bg-white p-8 shadow-sm ring-1 ring-slate-200">
        <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">WorkMind</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">Đăng nhập</h1>
        <p className="mt-2 text-sm text-slate-600">
          Đăng nhập để xem dữ liệu theo đúng phạm vi của bạn.
        </p>

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700">
            Tên đăng nhập
            <input
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
              name="username"
              value={form.username}
              onChange={updateField}
              autoComplete="username"
              required
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Mật khẩu
            <input
              className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2.5 outline-none transition focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
              type="password"
              name="password"
              value={form.password}
              onChange={updateField}
              autoComplete="current-password"
              required
            />
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
      </section>
    </main>
  )
}

export default LoginPage
