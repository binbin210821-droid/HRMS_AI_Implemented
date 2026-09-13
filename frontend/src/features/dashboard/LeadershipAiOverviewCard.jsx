import { FadeIn, StaggerList } from '../../components/animations/index.js'

function LeadershipAiOverviewCard({ summary, isLoading = false }) {
  if (isLoading) return null

  const items = [
    [
      'Phòng ban có dấu hiệu sớm',
      summary?.early_warning_department_count ?? 0,
      'bg-amber-50 text-amber-900',
    ],
    ['Phòng ban quá tải', summary?.overloaded_department_count ?? 0, 'bg-red-50 text-red-900'],
    [
      'Phòng ban có việc quá hạn',
      summary?.overdue_department_count ?? 0,
      'bg-rose-50 text-rose-900',
    ],
  ]

  return (
    <FadeIn className="mt-6 rounded-2xl border border-violet-100 bg-violet-50/60 p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-violet-700">
        Góc nhìn Lãnh đạo
      </p>
      <h2 className="mt-1 text-lg font-bold text-violet-950">Toàn cảnh vận hành</h2>
      <p className="mt-1 text-sm leading-6 text-violet-900/80">
        Tóm tắt rủi ro ở cấp phòng ban để bạn ưu tiên xử lý đúng nơi.
      </p>
      <StaggerList className="mt-4 grid gap-3 sm:grid-cols-3">
        {items.map(([label, value, className]) => (
          <div key={label} className={`rounded-xl p-4 ${className}`}>
            <p className="text-xs font-semibold">{label}</p>
            <p className="mt-2 text-2xl font-bold">{value}</p>
          </div>
        ))}
      </StaggerList>
    </FadeIn>
  )
}

export default LeadershipAiOverviewCard
