import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  buildDepartmentTrendSeries,
  groupOverloadReasonsByDepartment,
  groupTasksByDepartment,
  mergeDepartmentWeeklyTrends,
  OVERLOAD_REASON_LABELS,
  selectDepartmentTopEmployees,
  TASK_STATUS_LABELS,
} from './leadershipPerformance.js'

function ChartCard({ title, description, className = '', children }) {
  return (
    <section
      className={`w-full min-w-0 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200 sm:p-6 ${className}`}
    >
      <h2 className="text-slate-900">{title}</h2>
      <p className="mt-2 text-base leading-7 text-ink-600">{description}</p>
      <div className="mt-5 w-full min-w-0">{children}</div>
    </section>
  )
}

function EmptyChart() {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
      Chưa có dữ liệu trong khoảng thời gian này.
    </div>
  )
}

function LoadingChart({ message }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-xl bg-slate-50 text-sm text-slate-500">
      {message}
    </div>
  )
}

function ErrorChart({ message }) {
  return <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{message}</p>
}

function DepartmentTrendChart({ data, series, metric }) {
  const isQuality = metric === 'quality'

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="weekLabel" tick={{ fontSize: 12 }} />
        <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value, name) => [
            value == null ? 'Chưa có dữ liệu' : Number(value).toFixed(1),
            name,
          ]}
          labelFormatter={(label) => `Tuần bắt đầu từ ${label}`}
        />
        <Legend />
        {series.map((item) => (
          <Bar
            key={isQuality ? item.qualityKey : item.performanceKey}
            dataKey={isQuality ? item.qualityKey : item.performanceKey}
            name={`${item.departmentName} — ${isQuality ? 'Chất lượng' : 'Hiệu suất'}`}
            fill={item.color}
            radius={[6, 6, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}

function DepartmentTrendCard({
  data,
  series,
  metric,
  title,
  description,
  weeklyError,
  weeklyLoading,
}) {
  return (
    <ChartCard title={title} description={description}>
      {weeklyError ? (
        <ErrorChart message={weeklyError} />
      ) : weeklyLoading ? (
        <LoadingChart message="Đang tải xu hướng các phòng ban..." />
      ) : data.length ? (
        <DepartmentTrendChart data={data} series={series} metric={metric} />
      ) : (
        <EmptyChart />
      )}
    </ChartCard>
  )
}

function LeadershipPerformanceCharts({
  departments = [],
  weeklyResponses = [],
  weeklyLoading,
  weeklyError,
  departmentResponses = [],
  departmentLoading,
  departmentError,
  overloadLogs = [],
  tasks = [],
  tasksLoading,
  tasksError,
}) {
  const trendSeries = buildDepartmentTrendSeries(departments)
  const sortedTrendData = mergeDepartmentWeeklyTrends(departments, weeklyResponses)
  const awardCards = selectDepartmentTopEmployees(departments, departmentResponses)
  const overloadData = groupOverloadReasonsByDepartment(overloadLogs, departments)
  const taskData = groupTasksByDepartment(tasks, departments)

  return (
    <>
      <DepartmentTrendCard
        data={sortedTrendData}
        series={trendSeries}
        metric="performance"
        title="Xu hướng hiệu suất theo phòng ban"
        description="So sánh điểm hiệu suất trung bình của các phòng ban theo từng tuần."
        weeklyError={weeklyError}
        weeklyLoading={weeklyLoading}
      />

      <DepartmentTrendCard
        data={sortedTrendData}
        series={trendSeries}
        metric="quality"
        title="Xu hướng chất lượng theo phòng ban"
        description="So sánh điểm chất lượng trung bình của các phòng ban theo từng tuần."
        weeklyError={weeklyError}
        weeklyLoading={weeklyLoading}
      />

      <ChartCard
        title="Khen thưởng — nhân viên xuất sắc nhất"
        description="Mỗi thẻ chọn nhân viên có điểm hiệu suất trung bình cao nhất trong phòng ban ở khoảng thời gian đang xem."
      >
        {departmentError ? (
          <ErrorChart message={departmentError} />
        ) : departmentLoading ? (
          <LoadingChart message="Đang tải kết quả nổi bật..." />
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {awardCards.map((card) => (
              <div
                key={card.departmentId}
                className="rounded-xl border border-slate-200 bg-slate-50 p-4"
              >
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
                    className="h-3 w-3 rounded-full"
                    style={{ backgroundColor: card.color }}
                  />
                  <p className="font-semibold text-slate-900">{card.departmentName}</p>
                </div>
                {card.employee ? (
                  <>
                    <p className="mt-4 text-sm text-slate-600">Xuất sắc nhất trong kỳ</p>
                    <p className="mt-1 font-bold text-slate-900">{card.employee.full_name}</p>
                    <p className="mt-2 text-2xl font-bold text-brand-700">
                      {Number(card.employee.average_performance_score).toFixed(1)} điểm
                    </p>
                  </>
                ) : (
                  <p className="mt-4 text-sm text-slate-500">
                    Chưa đủ dữ liệu trong khoảng thời gian này.
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </ChartCard>

      <ChartCard
        title="Rủi ro quá tải theo nguyên nhân"
        description="Đếm số lần ghi nhận quá tải theo hai nguyên nhân thực tế trong nhật ký quá tải: khối lượng công việc và sụt chất lượng."
      >
        {overloadData.length ? (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={overloadData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="departmentName" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar
                dataKey="task_volume"
                name={OVERLOAD_REASON_LABELS.task_volume}
                fill="#dc2626"
                radius={[6, 6, 0, 0]}
              />
              <Bar
                dataKey="quality_drop"
                name={OVERLOAD_REASON_LABELS.quality_drop}
                fill="#f97316"
                radius={[6, 6, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart />
        )}
      </ChartCard>

      <ChartCard
        className="lg:col-span-2"
        title="Tiến độ công việc theo phòng ban"
        description="Mỗi cột thể hiện tổng số công việc của một phòng ban, chia theo đã hoàn thành, đang thực hiện và chưa bắt đầu."
      >
        {tasksError ? (
          <ErrorChart message={tasksError} />
        ) : tasksLoading ? (
          <LoadingChart message="Đang tải tiến độ công việc..." />
        ) : taskData.length ? (
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={taskData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="departmentName" tick={{ fontSize: 12 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="done" name={TASK_STATUS_LABELS.done} stackId="tasks" fill="#16a34a" />
              <Bar
                dataKey="in_progress"
                name={TASK_STATUS_LABELS.in_progress}
                stackId="tasks"
                fill="#f59e0b"
              />
              <Bar dataKey="todo" name={TASK_STATUS_LABELS.todo} stackId="tasks" fill="#94a3b8" />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart />
        )}
      </ChartCard>
    </>
  )
}

export default LeadershipPerformanceCharts
