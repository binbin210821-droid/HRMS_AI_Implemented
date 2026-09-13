import { expect, test } from '@playwright/test'

const DEPARTMENT = {
  id: 'dept-kd',
  name: 'Kinh doanh',
  code: 'KD',
}

const EMPLOYEE = {
  id: 'employee-1',
  full_name: 'Nguyễn Văn An',
  employee_code: 'KD-001',
  position: 'Chuyên viên kinh doanh',
  department_id: DEPARTMENT.id,
  is_active: true,
}

function userForRole(role) {
  return {
    id: role === 'manager' ? 'user-manager' : 'user-leadership',
    username: role,
    full_name: role === 'manager' ? 'Nguyễn Quản lý' : 'Trần Lãnh đạo',
    role,
    department_id: role === 'manager' ? DEPARTMENT.id : null,
    department_name: role === 'manager' ? DEPARTMENT.name : null,
  }
}

function responseFor(pathname, role) {
  if (pathname.endsWith('/auth/me')) return userForRole(role)
  if (pathname.endsWith('/health')) return { status: 'ok' }
  if (pathname.includes('/departments')) return { items: [DEPARTMENT], has_next: false }
  if (pathname.includes('/employees')) return { items: [EMPLOYEE], has_next: false }
  if (pathname.endsWith('/dashboard/attention-summary')) {
    return {
      total: 0,
      early_warning_count: 0,
      overload_count: 0,
      overdue_task_count: 0,
      items: [],
    }
  }
  if (pathname.includes('/alerts/department-summary')) return []
  if (pathname.includes('/alerts')) return { items: [], has_next: false }
  if (pathname.includes('/overload')) return { items: [], has_next: false }
  if (pathname.includes('/tasks/leadership-overview')) {
    return { departments: [], trend: [], tasks: [] }
  }
  if (pathname.includes('/tasks')) return { items: [], has_next: false }
  if (pathname.includes('/performance/daily-review')) {
    return { employee: EMPLOYEE, date: '2026-09-12', tasks: [] }
  }
  if (pathname.includes('/performance/analytics')) {
    return { employees: [], departments: [], weeks: [], metrics: [] }
  }
  if (pathname.endsWith('/performance')) return []
  if (pathname.includes('/department-evaluations/weekly-reviews')) {
    return {
      department_name: DEPARTMENT.name,
      department_code: DEPARTMENT.code,
      week_start: '2026-09-07',
      week_end: '2026-09-13',
      can_evaluate: false,
      directives: {
        total_count: 0,
        accepted_count: 0,
        needs_revision_count: 0,
        completed_count: 0,
        items: [],
        on_time_rate: null,
        with_commitment_count: 0,
        late_count: 0,
        overdue_count: 0,
      },
      stability: {
        status: 'insufficient_data',
        current: {},
        previous: {},
        deltas: {},
      },
    }
  }
  if (pathname.includes('/department-evaluations')) {
    return { items: [], has_next: false, total: 0 }
  }
  if (pathname.includes('/coordination/suggestions')) return []
  if (pathname.includes('/coordination')) return { items: [], has_next: false }
  return { items: [], has_next: false }
}

async function installReadOnlyApi(page, role) {
  const requests = []
  const consoleErrors = []

  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const method = request.method()
    requests.push({ method, url: request.url() })

    const pathname = new URL(request.url()).pathname
    if (pathname.endsWith('/ai/chat/stream')) {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"type":"token","content":"Tổng quan: Có 1 nhân viên."}\n\ndata: {"type":"done"}\n\n',
      })
      return
    }

    if (method !== 'GET' && method !== 'HEAD') {
      await route.abort()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(responseFor(pathname, role)),
    })
  })

  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  return { requests, consoleErrors }
}

async function assertRoleOverview(page) {
  await expect(page.getByRole('heading', { name: /Tổng quan/ }).first()).toBeVisible()
  await expect(page.getByRole('link', { name: 'Tổng quan' })).toBeVisible()
  await expect(page.getByText('Bảng tổng quan hiệu suất')).toBeVisible()
  await expect(page.locator('main > div').first()).toHaveCSS('opacity', '1')
  await expect(page.getByAltText('WorkMind HRMS').locator('..')).toHaveClass(/gap-2/)

  const summaryGrid = page.locator('main .mt-8.grid').first()
  await expect(summaryGrid).toHaveClass(/sm:grid-cols-2/)
  const attentionWrapper = summaryGrid.locator(':scope > div').nth(2)
  await expect(attentionWrapper).toHaveClass(/sm:col-span-2/)
  const attentionButton = attentionWrapper.getByRole('button')
  await expect(attentionButton).toHaveClass(/flex-col/)
  await expect(attentionButton).toHaveClass(/items-center/)
  await expect(attentionButton).not.toContainText('Di chuột hoặc chọn thẻ')
}

const ROLE_ROUTES = {
  manager: [
    { path: '/manager', heading: /Tổng quan/ },
    { path: '/manager/employees', heading: 'Nhân viên phòng ban' },
    { path: '/manager/performance', heading: 'Nghiệm thu bằng chứng công việc' },
    { path: '/manager/alerts', heading: 'Cảnh báo hiệu suất' },
    { path: '/manager/tasks', heading: 'Công việc & deadline' },
    { path: '/manager/directives', heading: 'Trung tâm chỉ thị' },
    { path: '/manager/analytics', heading: /Tổng quan/, url: /\/manager$/ },
    { path: '/manager/overload', heading: /Cảnh báo hiệu suất/, url: /\/manager\/alerts$/ },
  ],
  leadership: [
    { path: '/leadership', heading: /Tổng quan/ },
    { path: '/leadership/alerts', heading: 'Cảnh báo toàn công ty' },
    { path: '/leadership/departments', heading: 'Phòng ban & nhân viên' },
    { path: '/leadership/tasks', heading: 'Công việc & deadline' },
    { path: '/leadership/department-evaluations', heading: 'Đánh giá phòng ban theo tuần' },
    { path: '/leadership/directives', heading: 'Trung tâm chỉ thị' },
    { path: '/leadership/performance', heading: /Tổng quan/, url: /\/leadership$/ },
    {
      path: '/leadership/overload',
      heading: 'Cảnh báo toàn công ty',
      url: /\/leadership\/alerts$/,
    },
    {
      path: '/leadership/managers',
      heading: 'Đánh giá phòng ban theo tuần',
      url: /\/leadership\/department-evaluations$/,
    },
    {
      path: '/leadership/employees',
      heading: 'Phòng ban & nhân viên',
      url: /\/leadership\/departments$/,
    },
    { path: '/leadership/users', heading: /Tổng quan/, url: /\/leadership$/ },
  ],
}

for (const role of ['manager', 'leadership']) {
  test(`UI-only ${role} giữ bố cục Tổng quan và không tạo request ghi dữ liệu`, async ({
    page,
  }) => {
    const { requests, consoleErrors } = await installReadOnlyApi(page, role)
    for (const [index, route] of ROLE_ROUTES[role].entries()) {
      await page.goto(route.path)
      await expect(page.getByRole('heading', { name: route.heading }).first()).toBeVisible()
      if (route.url) await expect(page).toHaveURL(route.url)
      const visibleText = await page.locator('body').innerText()
      expect(visibleText).not.toContain(DEPARTMENT.id)
      expect(visibleText).not.toContain(EMPLOYEE.id)
      if (index === 0) {
        await assertRoleOverview(page)
        await page.screenshot({
          path: `../docs/review/ui-baseline-${role}-overview.png`,
          fullPage: true,
          animations: 'disabled',
        })
      }
    }

    const dataWriteRequests = requests.filter(
      ({ method, url }) =>
        method !== 'GET' && method !== 'HEAD' && !url.includes('/api/v1/ai/chat/stream'),
    )
    expect(dataWriteRequests).toEqual([])
    const applicationConsoleErrors = consoleErrors.filter(
      (message) =>
        !message.startsWith('Failed to load resource:') &&
        !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
    )
    expect(applicationConsoleErrors).toEqual([])
  })

  test(`UI-only ${role} hỗ trợ mở menu bằng bàn phím trên mobile`, async ({ page }) => {
    const { requests, consoleErrors } = await installReadOnlyApi(page, role)
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(`/${role}`)

    const menuButton = page.getByRole('button', { name: 'Mở menu điều hướng' })
    await menuButton.focus()
    await page.keyboard.press('Enter')
    const mobileMenu = page.getByRole('complementary', {
      name: 'Menu điều hướng trên thiết bị di động',
    })
    await expect(mobileMenu).toBeVisible()

    const closeButton = page.getByRole('button', { name: 'Đóng menu điều hướng' })
    await closeButton.focus()
    await page.keyboard.press('Enter')
    await expect(mobileMenu).not.toBeVisible()

    expect(
      requests.filter(
        ({ method, url }) =>
          method !== 'GET' && method !== 'HEAD' && !url.includes('/api/v1/ai/chat/stream'),
      ),
    ).toEqual([])
    expect(
      consoleErrors.filter(
        (message) =>
          !message.startsWith('Failed to load resource:') &&
          !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
      ),
    ).toEqual([])
  })

  test(`UI-only ${role} lưu gợi ý AI và không gọi lại khi quay về Tổng quan`, async ({ page }) => {
    const { requests, consoleErrors } = await installReadOnlyApi(page, role)
    await page.goto(`/${role}`)
    await expect(page.getByText('Có 1 nhân viên.')).toBeVisible()

    const summaryRequestCount = requests.filter(
      ({ method, url }) => method === 'POST' && url.includes('/api/v1/ai/chat/stream'),
    ).length
    await page.getByRole('button', { name: 'Ẩn gợi ý AI' }).first().click()
    await expect(page.getByText('Gợi ý AI đang tạm ẩn.').first()).toBeVisible()

    await page.goto(`/${role}/tasks`)
    await expect(page.getByRole('heading', { name: 'Công việc & deadline' })).toBeVisible()
    await page.goto(`/${role}`)
    await expect(page.getByRole('button', { name: 'Hiện gợi ý AI' }).first()).toBeVisible()
    expect(
      requests.filter(
        ({ method, url }) => method === 'POST' && url.includes('/api/v1/ai/chat/stream'),
      ),
    ).toHaveLength(summaryRequestCount)

    await page.getByRole('button', { name: 'Hiện gợi ý AI' }).first().click()
    await expect(page.getByText('Có 1 nhân viên.')).toBeVisible()
    expect(
      consoleErrors.filter(
        (message) =>
          !message.startsWith('Failed to load resource:') &&
          !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
      ),
    ).toEqual([])
  })
}

test('UI-only giữ redirect trang chủ và trang không có quyền', async ({ page }) => {
  const { consoleErrors } = await installReadOnlyApi(page, 'manager')

  await page.goto('/')
  await expect(page).toHaveURL(/\/manager$/)
  await page.goto('/unauthorized')
  await expect(page.getByRole('heading', { name: 'Bạn không có quyền truy cập' })).toBeVisible()

  expect(
    consoleErrors.filter(
      (message) =>
        !message.startsWith('Failed to load resource:') &&
        !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
    ),
  ).toEqual([])
})

test('UI-only Trợ lý AI có thao tác header và nhập liệu dễ nhận biết', async ({ page }) => {
  const { requests, consoleErrors } = await installReadOnlyApi(page, 'manager')
  await page.goto('/manager')
  await page.getByRole('button', { name: 'Mở Trợ lý AI' }).click()

  const panel = page.locator('section[aria-label="Trợ lý AI"]')
  await expect(panel).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Bắt đầu cuộc trò chuyện mới' })).toHaveClass(
    /bg-white/,
  )
  await expect(panel.getByRole('button', { name: 'Đóng Trợ lý AI' })).toHaveClass(
    /h-9.*w-9.*text-white/,
  )
  await expect(panel.getByLabel('Câu hỏi cho Trợ lý AI')).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Gửi' })).toBeDisabled()

  expect(
    requests.filter(
      ({ method, url }) =>
        method !== 'GET' && method !== 'HEAD' && !url.includes('/api/v1/ai/chat/stream'),
    ),
  ).toEqual([])
  expect(
    consoleErrors.filter(
      (message) =>
        !message.startsWith('Failed to load resource:') &&
        !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
    ),
  ).toEqual([])
  await page.screenshot({
    path: '../docs/review/ui-baseline-ai-assistant.png',
    animations: 'disabled',
  })
})

test('UI-only Trợ lý AI giữ phiên khi chuyển trang và đóng mở lại', async ({ page }) => {
  const { consoleErrors } = await installReadOnlyApi(page, 'manager')
  await page.goto('/manager')
  await page.getByRole('button', { name: 'Mở Trợ lý AI' }).click()

  const panel = page.locator('section[aria-label="Trợ lý AI"]')
  await page.getByLabel('Câu hỏi cho Trợ lý AI').fill('Ai cần được theo dõi?')
  await panel.getByRole('button', { name: 'Gửi' }).click()
  await expect(panel.getByText('Tổng quan: Có 1 nhân viên.')).toBeVisible()

  await page.getByRole('link', { name: 'Công việc' }).first().click()
  await expect(page).toHaveURL(/\/manager\/tasks$/)
  await expect(panel).toBeVisible()
  await expect(panel.getByText('Tổng quan: Có 1 nhân viên.')).toBeVisible()

  await panel.getByRole('button', { name: 'Đóng Trợ lý AI' }).click()
  await expect(panel).not.toBeVisible()
  await page.getByRole('button', { name: 'Mở Trợ lý AI' }).click()
  await expect(panel).toBeVisible()
  await expect(panel.getByText('Tổng quan: Có 1 nhân viên.')).toBeVisible()

  expect(
    consoleErrors.filter(
      (message) =>
        !message.startsWith('Failed to load resource:') &&
        !message.includes("WebSocket connection to 'ws://127.0.0.1:5173/ws/realtime' failed"),
    ),
  ).toEqual([])
})
