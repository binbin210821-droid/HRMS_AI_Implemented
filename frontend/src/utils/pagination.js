export function unwrapPageItems(response, resourceName) {
  if (response?.has_next === true) {
    console.warn(
      `[${resourceName}] Danh sách đã vượt page_size=20; cần bổ sung cơ chế tải nhiều trang.`,
    )
  }

  return response?.items ?? []
}

export async function fetchAllOffsetPages(loadPage, { limit = 100 } = {}) {
  const items = []
  let offset = 0
  let hasFullPage = true

  while (hasFullPage) {
    const response = await loadPage({ offset, limit })
    const pageItems = Array.isArray(response) ? response : (response?.items ?? [])
    items.push(...pageItems)

    hasFullPage = pageItems.length === limit
    if (!hasFullPage) return items
    offset += pageItems.length
  }

  return items
}
