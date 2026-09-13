import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  EmptyState,
  ErrorState,
  Input,
  LoadingState,
  Select,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
  Toast,
  Tooltip,
} from './index.js'

describe('shared UI primitives', () => {
  it('keeps form controls accessible and exposes invalid state', () => {
    render(
      <>
        <Input aria-label="Tên nhân viên" invalid />
        <Select aria-label="Phòng ban" invalid />
        <Textarea aria-label="Ghi chú" invalid />
      </>,
    )

    expect(screen.getByLabelText('Tên nhân viên')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Phòng ban')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Ghi chú')).toHaveAttribute('aria-invalid', 'true')
  })

  it('renders a responsive table with semantic column headers', () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Nhân viên</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Nguyễn Văn An</TableCell>
          </TableRow>
        </TableBody>
      </Table>,
    )

    expect(screen.getByRole('columnheader', { name: 'Nhân viên' })).toHaveAttribute('scope', 'col')
    expect(screen.getByRole('cell', { name: 'Nguyễn Văn An' })).toBeVisible()
  })

  it('exposes toast status and dismiss action in Vietnamese', () => {
    const onDismiss = () => {}
    render(
      <Toast
        variant="success"
        title="Đã lưu"
        message="Thông tin đã được cập nhật."
        onDismiss={onDismiss}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('Thông tin đã được cập nhật.')
    expect(screen.getByRole('button', { name: 'Đóng thông báo' })).toBeVisible()
  })

  it('keeps skeleton decorative for assistive technology', () => {
    const { container } = render(<Skeleton className="h-4 w-20" />)
    expect(container.firstElementChild).toHaveAttribute('aria-hidden', 'true')
  })

  it('connects tooltip text to its keyboard-accessible trigger', () => {
    render(
      <Tooltip label="Xem thêm">
        <button type="button">Mở</button>
      </Tooltip>,
    )

    const trigger = screen.getByRole('button', { name: 'Mở' })
    expect(trigger).toHaveAttribute('aria-describedby')
    expect(screen.getByRole('tooltip', { name: 'Xem thêm' })).toBeInTheDocument()
  })

  it('provides consistent loading, empty and retry states', () => {
    const onRetry = () => {}
    const { getAllByRole, getByRole, getByText } = render(
      <>
        <LoadingState message="Đang tải báo cáo..." />
        <EmptyState title="Chưa có cảnh báo" description="Hệ thống chưa ghi nhận cảnh báo mới." />
        <ErrorState message="Không thể tải báo cáo." onRetry={onRetry} />
      </>,
    )

    const statusMessages = getAllByRole('status')
    expect(
      statusMessages.some((message) => message.textContent.includes('Đang tải báo cáo...')),
    ).toBe(true)
    expect(getByText('Chưa có cảnh báo')).toBeInTheDocument()
    const retryButton = getByRole('button', { name: 'Thử lại' })
    expect(getByRole('alert')).toHaveTextContent('Không thể tải báo cáo.')
    fireEvent.click(retryButton)
  })
})
