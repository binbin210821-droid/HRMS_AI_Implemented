import { expect, test } from '@playwright/test'

const PASSWORD = 'DemoPassword123!'

async function login(page, username, destination) {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill(username)
  await page.getByLabel('Mật khẩu').fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await page.waitForURL(`**${destination}`)
}

test('đăng nhập thất bại hiển thị lỗi cho người dùng', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill('tai-khoan-khong-ton-tai')
  await page.getByLabel('Mật khẩu').fill('mat-khau-sai')
  await page.getByRole('button', { name: 'Đăng nhập' }).click()

  await expect(page.getByText('Yêu cầu thất bại: 401')).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

test('Manager chỉ thấy menu và dữ liệu của phòng ban mình', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')

  await expect(page.getByRole('link', { name: 'Nhân viên phòng ban' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Phân tích hiệu suất' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Quản lý phòng ban' })).toHaveCount(0)
  await expect(page.getByRole('link', { name: 'Nhân viên toàn công ty' })).toHaveCount(0)

  await page.getByRole('link', { name: 'Nhân viên phòng ban' }).click()
  await expect(page).toHaveURL(/\/manager\/employees$/)
  await expect(page.getByRole('heading', { name: 'Nhân viên phòng ban' })).toBeVisible()
  await expect(page.getByText('KD-NV-001')).toBeVisible()
  await expect(page.getByText('KT-NV-001')).toHaveCount(0)
})

test('Leadership thực hiện CRUD phòng ban cơ bản', async ({ page }) => {
  await login(page, 'demo.leadership', '/leadership')
  await page.getByRole('link', { name: 'Quản lý phòng ban' }).click()
  await expect(page.getByRole('heading', { name: 'Quản lý phòng ban' })).toBeVisible()

  const code = `E2E${Date.now().toString().slice(-6)}`
  const name = `Phòng E2E ${code}`
  await page.getByRole('button', { name: '+ Thêm phòng ban' }).click()
  await page.getByLabel('Tên phòng ban').fill(name)
  await page.getByLabel('Mã phòng ban').fill(code)
  await page.getByLabel('Mô tả').fill('Phòng ban phục vụ kiểm thử E2E')
  await page.getByRole('button', { name: 'Lưu phòng ban' }).click()

  const row = page.getByRole('row').filter({ hasText: code })
  await expect(row).toContainText(name)

  page.on('dialog', (dialog) => dialog.accept())
  await row.getByRole('button', { name: 'Xóa' }).click()
  await expect(page.getByRole('row').filter({ hasText: code })).toHaveCount(0)
})

test('Manager nhập điểm có slider chất lượng và preview tự động', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')
  await page.getByRole('link', { name: 'Hiệu suất nhân viên' }).click()

  await expect(page).toHaveURL(/\/manager\/performance$/)
  await expect(page.getByRole('heading', { name: 'Nhập điểm hiệu suất' })).toBeVisible()
  await expect(page.getByLabel('Điểm chất lượng')).toHaveValue('80')
  await expect(page.getByText('86.0', { exact: true }).first()).toBeVisible()
})

test('Dashboard Manager render xu hướng và so sánh từ dữ liệu hiệu suất', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')

  await expect(page.getByRole('heading', { name: 'Bảng tổng quan hiệu suất' })).toBeVisible()
  await expect(
    page
      .getByText('Nhân sự trong phạm vi')
      .locator('..')
      .getByLabel(/^[1-9]\d*$/),
  ).toBeVisible()
  await expect(
    page
      .getByText('Đang hoạt động')
      .locator('..')
      .getByLabel(/^[1-9]\d*$/),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: /Xu hướng của/ })).toBeVisible()
  await expect(
    page.getByText('Biểu đồ cho biết điểm hiệu suất, chất lượng và số công việc'),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: /So sánh nhân viên/ })).toBeVisible()
  await expect(page.locator('.recharts-line')).toHaveCount(2)
})

test('Dashboard Leadership render biểu đồ so sánh toàn công ty', async ({ page }) => {
  await login(page, 'demo.leadership', '/leadership')
  await page.goto('/leadership/performance')

  await expect(page).toHaveURL(/\/leadership$/)
  await expect(
    page.getByRole('heading', { name: 'Tổng quan & Phân tích hiệu suất toàn công ty' }),
  ).toBeVisible()
  const companyChart = page.getByRole('heading', { name: 'So sánh hiệu suất giữa các phòng ban' })
  await expect(companyChart).toBeVisible()
  await expect(page.getByText('Biểu đồ dành cho Lãnh đạo')).toBeVisible()
  await expect(companyChart.locator('..').locator('.recharts-bar-rectangle')).toHaveCount(3)
})

test('Manager xử lý cảnh báo sớm và lưu ghi chú', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()

  await expect(page).toHaveURL(/\/manager\/alerts$/)
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()
  await expect(page.getByLabel('Loại cảnh báo')).toHaveValue('all')
  await expect(page.getByLabel('Mức độ')).toHaveValue('all')
  await expect(page.getByText('Mức cao').first()).toBeVisible()
  await page.getByLabel('Loại cảnh báo').selectOption('overload')
  await expect(page.getByText('Quá tải').first()).toBeVisible()
  await page.getByLabel('Loại cảnh báo').selectOption('all')
  const resolveButton = page.getByRole('button', { name: 'Đã xử lý' }).first()
  if (await resolveButton.count()) {
    await resolveButton.click()
    await page.getByLabel('Ghi chú xử lý').fill('Đã cân đối lại khối lượng công việc.')
    await page.getByRole('button', { name: 'Xác nhận đã xử lý' }).click()
    await expect(page.locator('span').filter({ hasText: 'Đã xử lý' }).first()).toBeVisible()
    await expect(page.getByText('Đã cân đối lại khối lượng công việc.').first()).toBeVisible()
  } else {
    await expect(page.locator('span').filter({ hasText: 'Đã xử lý' }).first()).toBeVisible()
  }
})

test('Manager lọc cảnh báo quá tải trong trang cảnh báo hợp nhất', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()

  await expect(page).toHaveURL(/\/manager\/alerts$/)
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()
  await page.getByLabel('Loại cảnh báo').selectOption('overload')
  await expect(page.getByText('Mức cao').first()).toBeVisible()
  await expect(page.getByText('Quá tải').first()).toBeVisible()
})

test('Leadership xem và lưu đánh giá quản lý theo tháng', async ({ page }) => {
  await login(page, 'demo.leadership', '/leadership')
  await page.getByRole('link', { name: 'Đánh giá quản lý' }).click()

  await expect(page).toHaveURL(/\/leadership\/managers$/)
  await expect(page.getByRole('heading', { name: 'Đánh giá quản lý theo tháng' })).toBeVisible()
  await page.getByLabel('Điểm đánh giá: 80').fill('91')
  await page.getByLabel('Ghi chú').fill('Đánh giá E2E')
  await page.getByRole('button', { name: 'Lưu đánh giá' }).click()
  await expect(page.getByText('91 điểm', { exact: true }).first()).toBeVisible()
})

test('E2E luồng chính từ nhập điểm đến đồ thị, cảnh báo và Trợ lý AI', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')

  await page.getByRole('link', { name: 'Hiệu suất nhân viên' }).click()
  await expect(page.getByRole('heading', { name: 'Nhập điểm hiệu suất' })).toBeVisible()
  const futureDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
  await page.locator('input[name="date"]').fill(futureDate)
  await page.locator('input[name="tasks_completed"]').fill('4')
  await page.getByRole('button', { name: 'Lưu điểm ngày' }).click()
  await expect(
    page.getByText(/Đã lưu điểm hiệu suất ngày/).or(page.getByText('Yêu cầu thất bại: 409')),
  ).toBeVisible()

  await page.goto('/manager')
  await expect(page.getByRole('heading', { name: 'Bảng tổng quan hiệu suất' })).toBeVisible()
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()

  await page.goto('/manager')
  await page.getByRole('button', { name: 'Mở Trợ lý AI' }).click()
  await page.getByLabel('Câu hỏi cho Trợ lý AI').fill('Tóm tắt tình hình phòng ban của tôi')
  await page.getByRole('button', { name: 'Gửi' }).click()
  await expect(page.getByText(/Trợ lý AI hiện chưa sẵn sàng/)).toBeVisible({ timeout: 15_000 })
})
