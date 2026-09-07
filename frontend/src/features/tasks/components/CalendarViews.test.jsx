import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DayView, MonthGrid } from './CalendarViews.jsx'
import { getTaskDateKey } from './calendarUtils.js'
import TaskEventChip from './TaskEventChip.jsx'

function makeTask(id) {
  return {
    id,
    title: `Công việc ${id}`,
    employee_name: 'Nguyễn Văn A',
    employee_code: 'KD-NV-001',
    due_date: '2026-09-02',
    created_at: '2026-09-01T08:00:00Z',
    priority: 'high',
    status: 'in_progress',
    description: 'Mô tả công việc cần theo dõi.',
    subtasks: ['Kiểm tra yêu cầu'],
    is_overdue: false,
  }
}

describe('calendar task popup', () => {
  afterEach(cleanup)

  it('opens a detailed popup when a day has more than three tasks', async () => {
    const user = userEvent.setup()
    const date = new Date(2026, 8, 2)
    const tasks = [makeTask('1'), makeTask('2'), makeTask('3'), makeTask('4')]
    const groupedTasks = { [getTaskDateKey({ due_date: date })]: tasks }
    const onTaskClick = vi.fn()

    render(
      <MonthGrid
        dates={[date]}
        currentDate={date}
        groupedTasks={groupedTasks}
        colorMode="priority"
        onTaskClick={onTaskClick}
        onEmptyDayClick={vi.fn()}
        onTaskDrop={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '+1 khác' }))

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Công việc 4')).toBeInTheDocument()
    expect(within(screen.getByRole('dialog')).getAllByText('Nguyễn Văn A')).toHaveLength(4)

    expect(within(screen.getByRole('dialog')).getByText('Công việc')).toBeInTheDocument()
    expect(within(screen.getByRole('dialog')).getByText('Thời hạn còn lại')).toBeInTheDocument()

    await user.click(
      within(screen.getByRole('dialog')).getByRole('button', { name: 'Công việc 1' }),
    )

    expect(onTaskClick).toHaveBeenCalledWith(tasks[0])
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('renders the day view with the requested task columns', () => {
    render(
      <DayView
        date={new Date(2026, 8, 2)}
        tasks={[makeTask('1')]}
        colorMode="priority"
        onTaskClick={vi.fn()}
        onEmptyDayClick={vi.fn()}
        onTaskDrop={vi.fn()}
      />,
    )

    expect(screen.getByText('Công việc')).toBeInTheDocument()
    expect(screen.getByText('Nhân viên đảm nhận')).toBeInTheDocument()
    expect(screen.getByText('Thời hạn còn lại')).toBeInTheDocument()
    expect(screen.getByText('Ngày tạo')).toBeInTheDocument()
    expect(screen.getByText('Ngày hết hạn')).toBeInTheDocument()
  })

  it('opens task editing when clicking a row in the popup table', async () => {
    const user = userEvent.setup()
    const date = new Date(2026, 8, 2)
    const tasks = [makeTask('1'), makeTask('2'), makeTask('3'), makeTask('4')]
    const onTaskClick = vi.fn()

    render(
      <MonthGrid
        dates={[date]}
        currentDate={date}
        groupedTasks={{ [getTaskDateKey({ due_date: date })]: tasks }}
        colorMode="priority"
        onTaskClick={onTaskClick}
        onEmptyDayClick={vi.fn()}
        onTaskDrop={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '+1 khác' }))
    const popup = screen.getByRole('dialog')
    const taskRows = within(popup).getAllByRole('row')
    await user.click(taskRows[1])

    expect(onTaskClick).toHaveBeenCalledWith(tasks[0])
  })

  it('uses distinct status colors for completed, overdue, and in-progress tasks', () => {
    const completedTask = { ...makeTask('done'), status: 'done' }
    const overdueTask = { ...makeTask('overdue'), is_overdue: true }
    const inProgressTask = makeTask('in-progress')

    const { container } = render(
      <>
        <TaskEventChip task={completedTask} colorMode="priority" onClick={vi.fn()} />
        <TaskEventChip task={overdueTask} colorMode="status" onClick={vi.fn()} />
        <TaskEventChip task={inProgressTask} colorMode="status" onClick={vi.fn()} />
      </>,
    )

    expect(container.querySelector('.task-status-done')).toBeInTheDocument()
    expect(container.querySelector('.task-status-overdue')).toBeInTheDocument()
    expect(container.querySelector('.task-status-in_progress')).toBeInTheDocument()
  })
})
