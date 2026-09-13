import { useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { Navigate, useNavigate } from 'react-router-dom'

import { getCurrentUser, login } from '../features/auth/authApi.js'
import { useAuthStore } from '../stores/authStore.js'
import { Button, Card, FormField, Input } from '../components/ui/index.js'
import { FadeIn } from '../components/animations/index.js'

function LoginPage() {
  const navigate = useNavigate()
  const { isAuthenticated, isInitializing, setUser } = useAuthStore()
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (isInitializing) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
        <p role="status" className="text-sm text-slate-600">
          Đang kiểm tra phiên đăng nhập...
        </p>
      </main>
    )
  }

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
      await login({ username, password: form.password })
      const user = await getCurrentUser()
      setUser(user)
      const role = user.role
      navigate(role === 'leadership' ? '/leadership' : '/manager', { replace: true })
    } catch (requestError) {
      setError(requestError.message || 'Đăng nhập không thành công. Vui lòng thử lại.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 py-12">
      <FadeIn className="w-full max-w-md">
        <Card as="section" className="w-full p-8">
          <p className="text-sm font-semibold uppercase tracking-wide text-brand-600">WorkMind</p>
          <h1 className="mt-2 text-3xl font-bold text-slate-900">Đăng nhập</h1>
          <p className="mt-2 text-sm text-slate-600">
            Đăng nhập để xem dữ liệu theo đúng phạm vi của bạn.
          </p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            <FormField id="username" label="Tên đăng nhập" required>
              <Input
                name="username"
                value={form.username}
                onChange={updateField}
                autoComplete="username"
                required
              />
            </FormField>

            <FormField id="password" label="Mật khẩu" required>
              <Input
                type="password"
                name="password"
                value={form.password}
                onChange={updateField}
                autoComplete="current-password"
                required
              />
            </FormField>

            <AnimatePresence initial={false}>
              {error && (
                <FadeIn key="login-error" className="text-sm text-red-600" role="alert">
                  {error}
                </FadeIn>
              )}
            </AnimatePresence>

            <Button className="w-full" type="submit" loading={isSubmitting}>
              {isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </Button>
          </form>
        </Card>
      </FadeIn>
    </main>
  )
}

export default LoginPage
