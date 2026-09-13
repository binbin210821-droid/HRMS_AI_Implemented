import { expect, test } from '@playwright/test'

async function openLoginWithoutBackend(page, screenshotPath) {
  const apiRequests = []
  const consoleErrors = []

  await page.route('**/api/**', async (route) => {
    const method = route.request().method()
    apiRequests.push({ method, url: route.request().url() })
    if (method === 'GET' || method === 'HEAD') {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'UI-only mock response' }),
      })
      return
    }
    await route.abort()
  })
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })

  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Đăng nhập' })).toBeVisible()
  await expect(page.getByLabel('Tên đăng nhập')).toBeVisible()
  await expect(page.getByLabel('Mật khẩu')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Đăng nhập' })).toBeVisible()
  await expect(page.locator('main > div').first()).toHaveCSS('opacity', '1')

  expect(apiRequests.every(({ method }) => method === 'GET')).toBe(true)
  const applicationConsoleErrors = consoleErrors.filter(
    (message) => !message.startsWith('Failed to load resource:'),
  )
  expect(applicationConsoleErrors).toEqual([])
  await page.waitForTimeout(100)
  await page.screenshot({ path: screenshotPath, fullPage: true, animations: 'disabled' })
}

test('UI-only desktop không phát sinh request ghi dữ liệu', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await openLoginWithoutBackend(page, '../docs/review/ui-baseline-login-desktop.png')
})

test('UI-only mobile giữ bố cục đăng nhập và không phát sinh request ghi dữ liệu', async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await openLoginWithoutBackend(page, '../docs/review/ui-baseline-login-mobile.png')
})
