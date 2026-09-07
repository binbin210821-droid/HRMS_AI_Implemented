const PRIORITY_LABELS = { low: 'Thấp', medium: 'Trung bình', high: 'Cao' }
const STATUS_LABELS = {
  todo: 'Chưa bắt đầu',
  in_progress: 'Đang thực hiện',
  done: 'Đã hoàn thành',
}

function TaskEventChip({ task, colorMode, onClick, onDragStart }) {
  const colorPresentation = getTaskColorPresentation(task, colorMode)

  function handleDragStart(event) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', task.id)
    onDragStart?.(task)
  }

  return (
    <button
      type="button"
      draggable
      className={`task-event-chip ${colorPresentation.className}`}
      title={`${task.title} — ${task.employee_name} — ${colorPresentation.label}`}
      onClick={(event) => {
        event.stopPropagation()
        onClick(task)
      }}
      onDragStart={handleDragStart}
    >
      <span className="truncate font-semibold">{task.title}</span>
      <span className="truncate text-[10px] opacity-80">{task.employee_name}</span>
    </button>
  )
}

function getTaskColorPresentation(task, colorMode) {
  if (task.status === 'done') {
    return { className: 'task-status-done', label: 'Đã hoàn thành' }
  }

  if (task.is_overdue) {
    return { className: 'task-status-overdue', label: 'Quá hạn' }
  }

  if (colorMode === 'status') {
    return {
      className: `task-status-${task.status}`,
      label: STATUS_LABELS[task.status],
    }
  }

  return {
    className: `priority-${task.priority || 'low'}`,
    label: PRIORITY_LABELS[task.priority] || PRIORITY_LABELS.low,
  }
}

export default TaskEventChip
