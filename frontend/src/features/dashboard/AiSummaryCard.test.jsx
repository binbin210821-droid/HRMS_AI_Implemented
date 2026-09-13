import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AiSummaryCard from './AiSummaryCard.jsx'
import { streamAiSummary } from '../ai/aiApi.js'

vi.mock('../ai/aiApi.js', () => ({
  streamAiSummary: vi.fn(),
}))

const summary = `Dưới đây là tóm tắt hiệu suất của phòng ban bạn:

**Tổng quan:**
* **Số nhân viên:** 6
* **Điểm hiệu suất trung bình:** 82.7
* **Điểm chất lượng trung bình:** 85.84

**Tình trạng vận hành:**
* **Cảnh báo:** Không có cảnh báo nào được ghi nhận.
* **Quá tải:** Có 14 lần ghi nhận quá tải.

**Xu hướng hiệu suất gần đây:**
Hiệu suất đã cải thiện trong những ngày gần nhất.

**Gợi ý hành động:**
* Kiểm tra lại khối lượng công việc.
* Duy trì đà tăng trưởng hiệu suất.`

describe('AiSummaryCard', () => {
  afterEach(() => {
    cleanup()
    window.sessionStorage.clear()
  })

  beforeEach(() => {
    streamAiSummary.mockReset()
    streamAiSummary.mockImplementation(async (_prompt, options) => {
      options.onToken(summary)
    })
  })

  it('trình bày phản hồi Markdown thành các nhóm thông tin dễ đọc', async () => {
    render(<AiSummaryCard />)

    expect(await screen.findByRole('heading', { name: 'Tổng quan' })).toBeInTheDocument()
    expect(screen.getByText('6')).toBeInTheDocument()
    expect(screen.getByText('82.7')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Gợi ý hành động' })).toBeInTheDocument()
    expect(screen.getByText('Kiểm tra lại khối lượng công việc.')).toBeInTheDocument()
    expect(screen.queryByText('**Tổng quan:**')).not.toBeInTheDocument()
  })

  it('giữ được thao tác làm mới summary', async () => {
    render(<AiSummaryCard />)
    await screen.findByRole('heading', { name: 'Tổng quan' })

    fireEvent.click(screen.getByRole('button', { name: /Làm mới/i }))

    await waitFor(() => expect(streamAiSummary).toHaveBeenCalledTimes(2))
    expect(streamAiSummary).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({ forceRefresh: true, signal: expect.any(AbortSignal) }),
    )
  })

  it('cho phép ẩn hiện và giữ lại tóm tắt khi rời trang rồi quay lại', async () => {
    const { unmount } = render(<AiSummaryCard />)
    await screen.findByRole('heading', { name: 'Tổng quan' })

    fireEvent.click(screen.getByRole('button', { name: 'Ẩn gợi ý AI' }))
    expect(screen.getByText(/Gợi ý AI đang tạm ẩn/)).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Tổng quan' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Hiện gợi ý AI' }))
    expect(screen.getByRole('heading', { name: 'Tổng quan' })).toBeInTheDocument()

    unmount()
    render(<AiSummaryCard />)

    expect(await screen.findByRole('heading', { name: 'Tổng quan' })).toBeInTheDocument()
    expect(streamAiSummary).toHaveBeenCalledTimes(1)
  })

  it('tách được các card khi AI trả các mục trên cùng một đoạn văn', async () => {
    streamAiSummary.mockImplementation(async (_prompt, options) => {
      options.onToken(
        'Tổng quan: Có 6 nhân viên. Tình trạng vận hành: Có 2 nhân viên cần theo dõi. Xu hướng gần đây: Hiệu suất đang cải thiện. Gợi ý hành động: Rà soát lại khối lượng công việc.',
      )
    })

    render(<AiSummaryCard />)

    expect(await screen.findByRole('heading', { name: 'Tổng quan' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Tình trạng vận hành' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Xu hướng gần đây' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Gợi ý hành động' })).toBeInTheDocument()
    expect(screen.getByText('Rà soát lại khối lượng công việc.')).toBeInTheDocument()
  })
})
