import { useState } from 'react'

import Modal from '../../../components/Modal.jsx'
import TaskEventChip from './TaskEventChip.jsx'
import {
  formatCalendarDate,
  getTaskDateKey,
  isToday,
  parseCalendarDate,
  WEEKDAY_LABELS,
} from './calendarUtils.js'

const MAX_VISIBLE_TASKS = 3
const PRIORITY_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }
const STATUS_LABELS = {
  todo: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Đã hoàn thành',
}

function getTaskStatusPresentation(task) {
  return {
    className:
      task.status === 'done'
        ? 'task-status-done'
        : task.is_overdue
          ? 'task-status-overdue'
          : `task-status-${task.status}`,
    label:
      task.status === 'done'
        ? 'Đã hoàn thành'
        : task.is_overdue
          ? 'Quá hạn'
          : STATUS_LABELS[task.status],
  }
}

export function MonthGrid({
  dates,
  currentDate,
  groupedTasks,
  colorMode,
  onTaskClick,
  onEmptyDayClick,
  onTaskDrop,
}) {
  return (
    <div className="hidden overflow-visible rounded-xl border border-slate-200 sm:block">
      <div className="grid grid-cols-7 border-b border-slate-200 bg-slate-50">
        {WEEKDAY_LABELS.map((label) => (
          <div
            key={label}
            className="px-2 py-3 text-center text-xs font-semibold uppercase text-slate-500"
          >
            {label}
          </div>
        ))}
      </div>
      <div className="grid grid-cols-7">
        {dates.map((date) => (
          <DayCell
            key={date.toISOString()}
            date={date}
            tasks={groupedTasks[getTaskDateKey({ due_date: date })] || []}
            isOutsideMonth={date.getMonth() !== currentDate.getMonth()}
            colorMode={colorMode}
            onTaskClick={onTaskClick}
            onEmptyDayClick={onEmptyDayClick}
            onTaskDrop={onTaskDrop}
          />
        ))}
      </div>
    </div>
  )
}

export function WeekGrid({
  dates,
  groupedTasks,
  colorMode,
  onTaskClick,
  onEmptyDayClick,
  onTaskDrop,
}) {
  return (
    <div className="hidden overflow-x-auto rounded-xl border border-slate-200 sm:block">
      <div className="grid min-w-[840px] grid-cols-7 bg-slate-50">
        {dates.map((date) => (
          <div
            key={date.toISOString()}
            className="border-b border-l border-slate-200 px-3 py-3 first:border-l-0"
          >
            <p className="text-xs font-semibold uppercase text-slate-500">
              {formatCalendarDate(date, { weekday: 'short' })}
            </p>
            <p
              className={`mt-1 text-lg font-bold ${isToday(date) ? 'text-brand-700' : 'text-slate-800'}`}
            >
              {date.getDate()}
            </p>
          </div>
        ))}
      </div>
      <div className="grid min-w-[840px] grid-cols-7">
        {dates.map((date) => (
          <DayCell
            key={date.toISOString()}
            date={date}
            tasks={groupedTasks[getTaskDateKey({ due_date: date })] || []}
            colorMode={colorMode}
            onTaskClick={onTaskClick}
            onEmptyDayClick={onEmptyDayClick}
            onTaskDrop={onTaskDrop}
            className="min-h-[360px]"
          />
        ))}
      </div>
    </div>
  )
}

export function DayView({ date, tasks, colorMode, onTaskClick, onEmptyDayClick, onTaskDrop }) {
  return (
    <div className="rounded-xl border border-slate-200">
      <div className="border-b border-slate-200 bg-slate-50 px-4 py-5 text-center">
        <p className="text-xs font-semibold uppercase text-slate-500">
          {formatCalendarDate(date, { weekday: 'long' })}
        </p>
        <p
          className={`mt-1 text-2xl font-bold ${isToday(date) ? 'text-brand-700' : 'text-slate-800'}`}
        >
          {formatCalendarDate(date, { day: 'numeric', month: 'long' })}
        </p>
      </div>
      <DayCell
        date={date}
        tasks={tasks}
        colorMode={colorMode}
        onTaskClick={onTaskClick}
        onEmptyDayClick={onEmptyDayClick}
        onTaskDrop={onTaskDrop}
        className="min-h-[420px] border-0"
        forceExpanded
      />
    </div>
  )
}

function DayCell({
  date,
  tasks,
  isOutsideMonth = false,
  colorMode,
  onTaskClick,
  onEmptyDayClick,
  onTaskDrop,
  className = '',
  forceExpanded = false,
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const hasOverdueTask = tasks.some((task) => task.is_overdue && task.status !== 'done')
  const remainingCount = tasks.length - MAX_VISIBLE_TASKS
  const showPopup = !forceExpanded && isExpanded && remainingCount > 0
  const visibleTasks = forceExpanded ? tasks : tasks.slice(0, MAX_VISIBLE_TASKS)

  function handleDrop(event) {
    event.preventDefault()
    const taskId = event.dataTransfer.getData('text/plain')
    if (taskId) onTaskDrop?.(taskId, date)
  }

  function handleTaskClick(task) {
    // Giữ popup ngày mở phía dưới modal chỉnh sửa để nút Hủy quay lại đúng ngữ cảnh.
    onTaskClick(task)
  }

  return (
    <div
      className={`calendar-day-cell ${isOutsideMonth ? 'calendar-day-outside' : ''} ${isToday(date) ? 'calendar-day-today' : ''} ${hasOverdueTask ? 'calendar-day-overdue' : ''} ${className}`}
      onClick={() => onEmptyDayClick(date)}
      onDragOver={(event) => event.preventDefault()}
      onDrop={handleDrop}
    >
      <div
        className={
          forceExpanded
            ? 'flex flex-col items-center gap-2 border-b border-slate-100 pb-5 text-center'
            : 'flex items-center justify-between gap-2'
        }
      >
        <span
          className={`${
            forceExpanded ? 'text-4xl leading-none' : 'text-sm'
          } font-bold ${isToday(date) ? 'text-brand-700' : 'text-slate-800'}`}
        >
          {date.getDate()}
        </span>
        {tasks.length > 0 && (
          <span
            className={
              forceExpanded
                ? 'rounded-full bg-brand-50 px-3 py-1 text-sm font-semibold text-brand-700'
                : 'text-[10px] font-medium text-slate-400'
            }
          >
            {tasks.length} {forceExpanded ? 'công việc trong ngày' : 'việc'}
          </span>
        )}
      </div>
      <div className={forceExpanded ? 'mx-auto mt-5 w-full max-w-6xl' : 'mt-2 space-y-1'}>
        {forceExpanded ? (
          <DayTaskTable tasks={tasks} colorMode={colorMode} onTaskClick={handleTaskClick} />
        ) : (
          visibleTasks.map((task) => (
            <TaskEventChip
              key={task.id}
              task={task}
              colorMode={colorMode}
              onClick={handleTaskClick}
            />
          ))
        )}
        {!forceExpanded && remainingCount > 0 && !isExpanded && (
          <button
            type="button"
            className="w-full rounded-md px-2 py-1 text-left text-xs font-semibold text-brand-600 hover:bg-brand-50"
            onClick={(event) => {
              event.stopPropagation()
              setIsExpanded(true)
            }}
          >
            +{remainingCount} khác
          </button>
        )}
      </div>
      {showPopup && (
        <div onClick={(event) => event.stopPropagation()}>
          <Modal
            title={`Công việc ngày ${formatCalendarDate(date, { day: 'numeric', month: 'long', year: 'numeric' })}`}
            description={`Có ${tasks.length} công việc trong ngày này. Chọn một công việc để xem và chỉnh sửa.`}
            className="max-w-6xl"
            onClose={() => setIsExpanded(false)}
          >
            <DayTaskTable tasks={tasks} colorMode={colorMode} onTaskClick={handleTaskClick} />
          </Modal>
        </div>
      )}
      {tasks.length === 0 && <p className="mt-8 text-center text-xs text-slate-400">Thêm việc</p>}
    </div>
  )
}

function DayTaskTable({ tasks, colorMode, onTaskClick }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full min-w-[820px] table-fixed text-center">
        <thead className="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
          <tr>
            <th className="w-[27%] px-4 py-4">Công việc</th>
            <th className="w-[21%] px-4 py-4">Nhân viên đảm nhận</th>
            <th className="w-[18%] px-4 py-4">Thời hạn còn lại</th>
            <th className="w-[17%] px-4 py-4">Ngày tạo</th>
            <th className="w-[17%] px-4 py-4">Ngày hết hạn</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {tasks.map((task) => (
            <tr
              key={task.id}
              className="cursor-pointer transition hover:bg-brand-50/40"
              onClick={(event) => {
                event.stopPropagation()
                onTaskClick(task)
              }}
            >
              <td className="px-4 py-4">
                <button
                  type="button"
                  className="mx-auto block max-w-full truncate text-base font-bold text-slate-800 hover:text-brand-700"
                  title={task.title}
                  onClick={(event) => {
                    event.stopPropagation()
                    onTaskClick(task)
                  }}
                >
                  {task.title}
                </button>
                {(() => {
                  const statusPresentation = getTaskStatusPresentation(task)

                  const statusClass =
                    task.status === 'done' || task.is_overdue
                      ? statusPresentation.className
                      : colorMode === 'priority'
                        ? `priority-${task.priority || 'low'}`
                        : statusPresentation.className
                  const statusLabel =
                    task.status === 'done' || task.is_overdue
                      ? statusPresentation.label
                      : colorMode === 'priority'
                        ? PRIORITY_LABELS[task.priority] || PRIORITY_LABELS.low
                        : statusPresentation.label

                  return <span className={`mt-1 ${statusClass}`}>{statusLabel}</span>
                })()}
              </td>
              <td className="px-4 py-4 text-sm font-semibold text-slate-700">
                {task.employee_name}
              </td>
              <td className={`px-4 py-4 text-sm font-bold ${getRemainingClass(task)}`}>
                {getRemainingLabel(task)}
              </td>
              <td className="px-4 py-4 text-sm text-slate-600">
                {formatTaskDate(task.created_at)}
              </td>
              <td
                className={`px-4 py-4 text-sm font-semibold ${task.is_overdue ? 'text-red-600' : 'text-slate-700'}`}
              >
                {formatTaskDate(task.due_date)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatTaskDate(value) {
  if (!value) return '—'
  return formatCalendarDate(value, { day: '2-digit', month: '2-digit', year: 'numeric' })
}

function getRemainingLabel(task) {
  if (task.status === 'done') return 'Đã hoàn thành'
  const remainingDays = getRemainingDays(task.due_date)
  if (remainingDays === 0) return 'Hôm nay'
  if (remainingDays > 0) return `Còn ${remainingDays} ngày`
  return `Quá ${Math.abs(remainingDays)} ngày`
}

function getRemainingClass(task) {
  if (task.status === 'done') return 'text-emerald-600'
  return getRemainingDays(task.due_date) < 0 ? 'text-red-600' : 'text-brand-700'
}

function getRemainingDays(value) {
  const dueDate = parseCalendarDate(value)
  const today = parseCalendarDate(new Date())
  return Math.round((dueDate.getTime() - today.getTime()) / (24 * 60 * 60 * 1000))
}
