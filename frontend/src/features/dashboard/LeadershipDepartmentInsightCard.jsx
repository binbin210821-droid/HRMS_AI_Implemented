import { FadeIn, StaggerList } from '../../components/animations/index.js'

function LeadershipDepartmentInsightCard({ departments = [] }) {
  const visibleDepartments = departments.filter((item) => item.metric_days > 0)
  if (!visibleDepartments.length) return null

  return (
    <FadeIn className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-lg font-bold text-slate-900">So sánh nhanh giữa các phòng ban</h2>
      <p className="mt-1 text-sm leading-6 text-slate-600">
        Điểm dưới đây là số liệu tổng hợp, không hiển thị thông tin chi tiết từng nhân viên.
      </p>
      <StaggerList className="mt-4 grid gap-3 md:grid-cols-2">
        {visibleDepartments.map((department) => (
          <div
            key={department.department_id}
            className="rounded-xl border border-slate-100 bg-slate-50 p-4"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="font-semibold text-slate-900">{department.department_name}</p>
              <span className="rounded-full bg-brand-100 px-2.5 py-1 text-xs font-semibold text-brand-800">
                {department.average_performance_score == null
                  ? 'Chưa đủ dữ liệu'
                  : `${Number(department.average_performance_score).toFixed(1)} điểm`}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-600">
              Chất lượng gần đây:{' '}
              {department.average_quality_score == null
                ? '—'
                : `${Number(department.average_quality_score).toFixed(1)}/100`}
            </p>
          </div>
        ))}
      </StaggerList>
    </FadeIn>
  )
}

export default LeadershipDepartmentInsightCard
