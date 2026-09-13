import { getNavigationItems } from '../src/components/layout/navigation.js'

const managerItems = getNavigationItems('manager')
const leadershipItems = getNavigationItems('leadership')
const managerLabels = new Set(managerItems.map((item) => item.label))
const leadershipLabels = new Set(leadershipItems.map((item) => item.label))

if (managerItems.length !== 6) {
  throw new Error(`Manager phải có 6 mục menu, nhận được ${managerItems.length}`)
}

if (managerLabels.has('Quản lý tài khoản') || managerLabels.has('Quản lý phòng ban')) {
  throw new Error('Manager đang thấy menu chỉ dành cho Leadership')
}

if (managerLabels.has('Trợ lý AI')) {
  throw new Error('Manager không được thấy menu Trợ lý AI')
}

if (leadershipLabels.has('Quản lý tài khoản')) {
  throw new Error('Leadership không được thấy menu quản lý tài khoản')
}

if (leadershipLabels.has('Trợ lý AI')) {
  throw new Error('Leadership không được thấy menu Trợ lý AI')
}

for (const label of [
  'Tổng quan',
  'Phòng ban & nhân viên',
  'Cảnh báo ngưỡng toàn công ty',
  'Trung tâm chỉ thị',
  'Đánh giá quản lý',
  'Công việc & deadline',
]) {
  if (!leadershipLabels.has(label)) {
    throw new Error(`Leadership thiếu menu: ${label}`)
  }
}

if (leadershipItems.length !== 6) {
  throw new Error(`Leadership phải có 6 mục menu, nhận được ${leadershipItems.length}`)
}

if (!managerLabels.has('Trung tâm chỉ thị')) {
  throw new Error('Manager thiếu menu: Trung tâm chỉ thị')
}

console.log('Navigation role check passed: manager=6, leadership=6')
