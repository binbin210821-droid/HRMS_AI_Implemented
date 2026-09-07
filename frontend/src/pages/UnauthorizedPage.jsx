import { Link } from 'react-router-dom'

function UnauthorizedPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <section className="rounded-2xl bg-white p-8 text-center shadow-sm ring-1 ring-slate-200">
        <h1 className="text-2xl font-bold text-slate-900">Bạn không có quyền truy cập</h1>
        <p className="mt-2 text-slate-600">
          Hãy quay lại màn hình chính hoặc liên hệ người quản trị.
        </p>
        <Link
          className="mt-5 inline-block font-semibold text-brand-600 hover:text-brand-700"
          to="/"
        >
          Về trang chính
        </Link>
      </section>
    </main>
  )
}

export default UnauthorizedPage
