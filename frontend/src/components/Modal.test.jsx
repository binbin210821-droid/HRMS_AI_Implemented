import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { describe, expect, it, vi } from 'vitest'

import Modal from './Modal.jsx'

afterEach(cleanup)

describe('Modal', () => {
  it('closes with the visible close button', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="Chi tiết cảnh báo" onClose={onClose}>
        Nội dung
      </Modal>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Đóng cửa sổ' }))

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 1000 })
  })

  it('closes when clicking the modal backdrop', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="Chi tiết cảnh báo" onClose={onClose}>
        Nội dung
      </Modal>,
    )

    fireEvent.mouseDown(screen.getByRole('presentation'))

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 1000 })
  })

  it('closes with Escape while preserving the dialog contract', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="Chi tiết cảnh báo" onClose={onClose}>
        Nội dung
      </Modal>,
    )

    expect(screen.getByRole('dialog', { name: 'Chi tiết cảnh báo' })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1), { timeout: 1000 })
  })
})
