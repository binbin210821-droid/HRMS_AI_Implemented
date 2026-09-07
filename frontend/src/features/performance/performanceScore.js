export function taskVolumeScore(tasksCompleted) {
  const safeTasks = Math.max(0, Number(tasksCompleted) || 0)
  return Math.min(Math.min(safeTasks / 4, 1.5) * 100, 100)
}

export function calculatePerformanceScore(tasksCompleted, qualityScore) {
  const quality = Math.min(Math.max(Number(qualityScore) || 0, 0), 100)
  return quality * 0.7 + taskVolumeScore(tasksCompleted) * 0.3
}
