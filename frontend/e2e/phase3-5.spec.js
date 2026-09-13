import { expect, test } from '@playwright/test'

const PASSWORD = 'DemoPassword123!'
const sessionCookiesByUser = new Map()

async function login(page, username, destination) {
  const cachedCookies = sessionCookiesByUser.get(username)
  if (cachedCookies) {
    await page.context().addCookies(cachedCookies)
  } else {
    await page.goto('/login')
    await page.getByLabel('Tên đăng nhập').fill(username)
    await page.getByLabel('Mật khẩu').fill(PASSWORD)
    await page.getByRole('button', { name: 'Đăng nhập' }).click()
    await page.waitForURL(`**${destination}`)
    sessionCookiesByUser.set(username, await page.context().cookies())
    return
  }
  await page.goto(destination)
  await page.waitForURL(`**${destination}`)
}

test('đăng nhập thất bại hiển thị lỗi cho người dùng', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill('tai-khoan-khong-ton-tai')
  await page.getByLabel('Mật khẩu').fill('mat-khau-sai')
  await page.getByRole('button', { name: 'Đăng nhập' }).click()

  await expect(page.getByText('Tên đăng nhập hoặc mật khẩu không đúng')).toBeVisible()
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

test('Manager sử dụng được menu điều hướng trên màn hình mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page, 'demo.manager', '/manager')

  const openMenu = page.getByRole('button', { name: 'Mở menu điều hướng' })
  await expect(openMenu).toBeVisible()
  await openMenu.click()

  const mobileMenu = page.locator('#main-navigation-mobile')
  await expect(mobileMenu).toBeVisible()
  await mobileMenu.getByRole('link', { name: 'Nhân viên phòng ban' }).click()
  await expect(page).toHaveURL(/\/manager\/employees$/)
  await expect(mobileMenu).toBeHidden()
})

test('Leadership thực hiện CRUD phòng ban cơ bản', async ({ page }) => {
  await login(page, 'demo.leadership', '/leadership')
  await page.getByRole('link', { name: 'Phòng ban & nhân viên' }).click()
  await expect(page.getByRole('heading', { name: 'Phòng ban & nhân viên' })).toBeVisible()

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
  await expect(page.getByRole('heading', { name: 'Nghiệm thu bằng chứng công việc' })).toBeVisible()
  await expect(page.getByLabel('Nhân viên')).toBeVisible()
  await expect(page.getByLabel('Ngày đánh giá')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Lịch sử gần đây' })).toBeVisible()
})

test('Dashboard Manager render xu hướng và so sánh từ dữ liệu hiệu suất', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')

  await expect(page.getByRole('heading', { name: 'Bảng tổng quan hiệu suất' })).toBeVisible()
  await expect(page.getByText('Nhân sự trong phạm vi').locator('..')).toContainText(/\d+/, {
    timeout: 10_000,
  })
  await expect(page.getByText('Đang hoạt động', { exact: true }).locator('..')).toContainText(
    /\d+/,
    { timeout: 10_000 },
  )
  await expect(page.getByRole('heading', { name: /Xu hướng của/ })).toBeVisible()
  await expect(
    page.getByText('Biểu đồ cho biết điểm hiệu suất, chất lượng và số công việc'),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: /So sánh nhân viên/ })).toBeVisible()
  const trendChart = page.getByRole('heading', { name: /Xu hướng của/ }).locator('xpath=../..')
  await expect(trendChart.locator('.recharts-line')).toHaveCount(2)
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
  await expect(companyChart.locator('xpath=../..').locator('.recharts-bar-rectangle')).toHaveCount(
    3,
  )
})

test('Manager xử lý cảnh báo sớm và lưu ghi chú', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()

  await expect(page).toHaveURL(/\/manager\/alerts$/)
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()
  await expect(page.getByLabel('Loại cảnh báo')).toHaveValue('all')
  await expect(page.getByText('mức cao', { exact: false }).first()).toBeVisible()
  await page.getByLabel('Loại cảnh báo').selectOption('overload')
  await expect(page.getByText('Quá tải').first()).toBeVisible()
  await page.getByLabel('Loại cảnh báo').selectOption('all')
  await expect(page.locator('article').first()).toBeVisible({ timeout: 10_000 })
  const resolveButton = page
    .locator('article')
    .getByRole('button', { name: 'Đã xử lý', exact: true })
    .first()
  if (await resolveButton.count()) {
    await resolveButton.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await dialog.locator('textarea').fill('Đã cân đối lại khối lượng công việc.')
    await dialog.getByRole('button', { name: 'Xác nhận đã xử lý' }).click()
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

test('Leadership xem màn hình đánh giá phòng ban theo tuần', async ({ page }) => {
  await login(page, 'demo.leadership', '/leadership')
  await page.getByRole('link', { name: 'Đánh giá quản lý' }).click()

  await expect(page).toHaveURL(/\/leadership\/department-evaluations$/)
  await expect(page.getByRole('heading', { name: 'Đánh giá phòng ban theo tuần' })).toBeVisible()
  await expect(page.getByLabel('Phòng ban', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Thứ Hai bắt đầu tuần')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Lịch sử đánh giá tuần' })).toBeVisible()
})

test('E2E luồng chính từ nhập điểm đến đồ thị và cảnh báo', async ({ page }) => {
  await login(page, 'demo.manager', '/manager')

  await page.getByRole('link', { name: 'Hiệu suất nhân viên' }).click()
  await expect(page.getByRole('heading', { name: 'Nghiệm thu bằng chứng công việc' })).toBeVisible()
  await expect(page.getByLabel('Nhân viên')).toBeVisible()
  await expect(page.getByLabel('Ngày đánh giá')).toBeVisible()

  await page.goto('/manager')
  await expect(page.getByRole('heading', { name: 'Bảng tổng quan hiệu suất' })).toBeVisible()
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()
})

test('production build không chặn request vận hành khi chuyển trang và nhận realtime', async ({
  page,
}) => {
  await page.addInitScript(() => {
    const NativeWebSocket = window.WebSocket
    const sockets = []
    class TrackedWebSocket extends NativeWebSocket {
      constructor(...args) {
        super(...args)
        sockets.push(this)
      }
    }
    Object.defineProperties(TrackedWebSocket, {
      CONNECTING: { value: NativeWebSocket.CONNECTING },
      OPEN: { value: NativeWebSocket.OPEN },
      CLOSING: { value: NativeWebSocket.CLOSING },
      CLOSED: { value: NativeWebSocket.CLOSED },
    })
    window.WebSocket = TrackedWebSocket
    window.__trackedRealtimeSockets = sockets
  })

  const operationalResponses = []
  page.on('response', (response) => {
    const url = new URL(response.url())
    if (
      response.request().method() === 'GET' &&
      (url.pathname === '/api/v1/alerts' || url.pathname === '/api/v1/tasks')
    ) {
      operationalResponses.push({
        path: url.pathname,
        url: response.url(),
        status: response.status(),
        limit: response.headers()['x-ratelimit-limit'],
      })
    }
  })

  await login(page, 'demo.manager', '/manager')
  await page.getByRole('link', { name: 'Cảnh báo ngưỡng bất lợi' }).click()
  await expect(page).toHaveURL(/\/manager\/alerts$/)
  await expect(page.getByRole('heading', { name: 'Cảnh báo hiệu suất' })).toBeVisible()

  await page.getByRole('link', { name: 'Công việc & deadline' }).click()
  await expect(page).toHaveURL(/\/manager\/tasks$/)
  await expect(page.getByRole('heading', { name: 'Công việc & deadline' })).toBeVisible()

  await expect.poll(() => operationalResponses.length).toBeGreaterThan(0)
  expect(operationalResponses.every((item) => item.status !== 429)).toBe(true)
  expect(operationalResponses.every((item) => item.limit === '120')).toBe(true)

  // Chờ các request khởi tạo của trang Tasks hoàn tất trước khi đo burst realtime.
  await page.waitForTimeout(1000)
  operationalResponses.length = 0
  await expect
    .poll(() => page.evaluate(() => window.__trackedRealtimeSockets?.length || 0))
    .toBeGreaterThan(0)

  await page.evaluate(() => {
    const message = JSON.stringify({
      topic: 'alerts',
      operation: 'insert',
      data: {
        _id: 'e2e-realtime-alert',
        alert_type: 'overload',
        severity: 'medium',
        employee_id: 'e2e-employee',
        department_id: 'e2e-department',
        status: 'open',
      },
    })
    for (const socket of window.__trackedRealtimeSockets || []) {
      for (let index = 0; index < 5; index += 1) {
        socket.dispatchEvent(new MessageEvent('message', { data: message }))
      }
    }
  })

  await page.waitForTimeout(1800)
  const refreshedRequests = operationalResponses.filter((item) => item.path === '/api/v1/alerts')
  const requestCounts = new Map()
  for (const response of refreshedRequests) {
    const key = response.url
    requestCounts.set(key, (requestCounts.get(key) || 0) + 1)
  }
  expect(refreshedRequests.length).toBeGreaterThan(0)
  expect(
    [...requestCounts.values()].every((count) => count <= 1),
    [...requestCounts],
  ).toBe(true)
  expect(operationalResponses.some((item) => item.path === '/api/v1/tasks')).toBe(false)
  expect(refreshedRequests.every((item) => item.status !== 429)).toBe(true)
})
