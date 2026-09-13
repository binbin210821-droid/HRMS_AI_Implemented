import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import {
  AiLoadingIndicator,
  AnimatedTableRows,
  CounterNumber,
  FadeIn,
  PageTransition,
  SlideIn,
  StaggerList,
} from './index.js'

describe('shared animations', () => {
  it('renders the shared wrappers and localized counter value', () => {
    render(
      <>
        <FadeIn>Thông báo</FadeIn>
        <SlideIn direction="left">Nội dung</SlideIn>
        <PageTransition>Trang</PageTransition>
        <StaggerList>
          <span>Danh sách một</span>
          <span>Danh sách hai</span>
        </StaggerList>
        <CounterNumber value={1234} />
        <AiLoadingIndicator label="AI đang phân tích dữ liệu…" />
      </>,
    )

    expect(screen.getByText('Thông báo')).toBeInTheDocument()
    expect(screen.getByText('Nội dung')).toBeInTheDocument()
    expect(screen.getByText('Trang')).toBeInTheDocument()
    expect(screen.getByText('Danh sách một')).toBeInTheDocument()
    expect(screen.getByText('Danh sách hai')).toBeInTheDocument()
    expect(screen.getByLabelText('1234')).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'AI đang phân tích dữ liệu…' })).toBeInTheDocument()
  })

  it('renders animated table rows without changing table semantics', () => {
    render(
      <table>
        <tbody>
          <AnimatedTableRows>
            <tr key="employee-1">
              <td>Nguyễn Văn A</td>
            </tr>
            <tr key="employee-2">
              <td>Trần Thị B</td>
            </tr>
          </AnimatedTableRows>
        </tbody>
      </table>,
    )

    expect(screen.getByRole('cell', { name: 'Nguyễn Văn A' })).toBeInTheDocument()
    expect(screen.getByRole('cell', { name: 'Trần Thị B' })).toBeInTheDocument()
  })
})
