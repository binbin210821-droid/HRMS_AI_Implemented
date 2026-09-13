import { useMemo, useState } from 'react'

import { FadeIn } from '../../../components/animations/index.js'

import { DayView, MonthGrid, WeekGrid } from './CalendarViews.jsx'
import {
  getAdjacentDate,
  getCalendarRangeLabel,
  getMonthDates,
  getWeekDates,
  groupTasksByDate,
  parseCalendarDate,
  toDateKey,
} from './calendarUtils.js'

const VIEW_LABELS = { month: 'Tháng', week: 'Tuần', day: 'Ngày' }

function CalendarView({ tasks, onTaskClick, onEmptyDayClick, onTaskDrop }) {
  const [view, setView] = useState('month')
  const [currentDate, setCurrentDate] = useState(new Date())
  const [colorMode, setColorMode] = useState('priority')
  const groupedTasks = useMemo(() => groupTasksByDate(tasks), [tasks])
  const monthDates = useMemo(() => getMonthDates(currentDate), [currentDate])
  const weekDates = useMemo(() => getWeekDates(currentDate), [currentDate])

  function moveDate(direction) {
    setCurrentDate(getAdjacentDate(view, currentDate, direction))
  }

  function goToday() {
    setCurrentDate(new Date())
  }

  function handleDrop(taskId, date) {
    const nextDate = toDateKey(date)
    const task = tasks.find((item) => item.id === taskId)
    if (task && task.due_date !== nextDate) onTaskDrop?.(task, nextDate)
  }

  function handleEmptyDayClick(date) {
    onEmptyDayClick?.(toDateKey(date))
  }

  return (
    <section className="mt-6 rounded-xl border border-slate-200 bg-white p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="secondary-button !px-3 !py-2"
            onClick={() => moveDate(-1)}
            aria-label="Khoảng thời gian trước"
          >
            ‹
          </button>
          <button type="button" className="secondary-button !px-3 !py-2" onClick={goToday}>
            Hôm nay
          </button>
          <button
            type="button"
            className="secondary-button !px-3 !py-2"
            onClick={() => moveDate(1)}
            aria-label="Khoảng thời gian sau"
          >
            ›
          </button>
        </div>
        <h2 className="!text-lg !font-bold capitalize text-slate-900">
          {getCalendarRangeLabel(view, currentDate)}
        </h2>
        <div className="flex rounded-xl bg-slate-100 p-1" role="group" aria-label="Khung nhìn lịch">
          {Object.entries(VIEW_LABELS).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition duration-motion-micro ease-motion-standard ${view === value ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
              onClick={() => setView(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <p className="text-sm text-slate-500">
          Bấm vào công việc để chỉnh sửa; kéo thả sang ngày khác để đổi deadline.
        </p>
        <label className="flex items-center gap-2 text-xs font-semibold text-slate-600">
          Tô màu theo:
          <select
            className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs"
            value={colorMode}
            onChange={(event) => setColorMode(event.target.value)}
          >
            <option value="priority">Ưu tiên</option>
            <option value="status">Trạng thái</option>
          </select>
        </label>
      </div>

      {tasks.length === 0 && (
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-500">
          Chưa có công việc phù hợp.
        </p>
      )}

      <FadeIn key={`${view}-${toDateKey(currentDate)}`} className="mt-4">
        {view === 'month' && (
          <MonthGrid
            dates={monthDates}
            currentDate={parseCalendarDate(currentDate)}
            groupedTasks={groupedTasks}
            colorMode={colorMode}
            onTaskClick={onTaskClick}
            onEmptyDayClick={handleEmptyDayClick}
            onTaskDrop={handleDrop}
          />
        )}
        {view === 'week' && (
          <WeekGrid
            dates={weekDates}
            groupedTasks={groupedTasks}
            colorMode={colorMode}
            onTaskClick={onTaskClick}
            onEmptyDayClick={handleEmptyDayClick}
            onTaskDrop={handleDrop}
          />
        )}
        {view === 'day' && (
          <DayView
            date={currentDate}
            tasks={groupedTasks[toDateKey(currentDate)] || []}
            colorMode={colorMode}
            onTaskClick={onTaskClick}
            onEmptyDayClick={handleEmptyDayClick}
            onTaskDrop={handleDrop}
          />
        )}
        {view !== 'day' && (
          <div className="sm:hidden">
            <DayView
              date={currentDate}
              tasks={groupedTasks[toDateKey(currentDate)] || []}
              colorMode={colorMode}
              onTaskClick={onTaskClick}
              onEmptyDayClick={handleEmptyDayClick}
              onTaskDrop={handleDrop}
            />
          </div>
        )}
      </FadeIn>
    </section>
  )
}

export default CalendarView
