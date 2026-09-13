import { describe, expect, it } from 'vitest'

import { buildCoordinationDirectiveSla, buildLifecycleDirectiveSla } from './managerDirectiveSla.js'

const today = new Date('2026-09-12T00:00:00Z')

describe('manager directive SLA builders', () => {
  it('groups lifecycle directives and calculates open, timing, revision, and overdue metrics', () => {
    const rows = buildLifecycleDirectiveSla(
      [
        {
          target_manager_id: 'manager-1',
          target_manager_name: 'Nguyễn An',
          status: 'acknowledged',
          issued_at: '2026-09-08T08:00:00Z',
          acknowledged_at: '2026-09-08T10:00:00Z',
          commitment_date: '2026-09-10',
        },
        {
          target_manager_id: 'manager-1',
          target_manager_name: 'Nguyễn An',
          status: 'needs_revision',
          issued_at: '2026-09-07T08:00:00Z',
          acknowledged_at: '2026-09-07T09:00:00Z',
          submitted_at: '2026-09-07T13:00:00Z',
          revision_requested_at: '2026-09-07T15:00:00Z',
          commitment_date: '2026-09-09',
        },
        {
          target_manager_id: 'manager-1',
          target_manager_name: 'Nguyễn An',
          status: 'accepted',
          issued_at: '2026-09-06T08:00:00Z',
          acknowledged_at: '2026-09-06T09:00:00Z',
          submitted_at: '2026-09-06T13:00:00Z',
          commitment_date: '2026-09-06',
        },
        {
          target_manager_id: 'manager-2',
          target_manager_name: 'Trần Bình',
          status: 'pending',
          issued_at: '2026-09-11T08:00:00Z',
          commitment_date: '2026-09-13',
        },
      ],
      today,
    )

    expect(rows).toEqual([
      {
        manager_id: 'manager-1',
        manager_name: 'Nguyễn An',
        total_count: 3,
        open_count: 2,
        average_acknowledgement_hours: 4 / 3,
        average_processing_hours: 4,
        revision_rate: 50,
        overdue_commitment_count: 1,
      },
      {
        manager_id: 'manager-2',
        manager_name: 'Trần Bình',
        total_count: 1,
        open_count: 1,
        average_acknowledgement_hours: null,
        average_processing_hours: null,
        revision_rate: null,
        overdue_commitment_count: 0,
      },
    ])
  })

  it('keeps pending coordination separate and groups fulfilled work by manager', () => {
    expect(
      buildCoordinationDirectiveSla([
        { status: 'pending', issued_at: '2026-09-10T08:00:00Z' },
        {
          status: 'fulfilled',
          fulfilled_by: 'manager-1',
          fulfilled_by_name: 'Nguyễn An',
          issued_at: '2026-09-10T08:00:00Z',
          fulfilled_at: '2026-09-10T12:00:00Z',
        },
        {
          status: 'fulfilled',
          fulfilled_by: 'manager-1',
          fulfilled_by_name: 'Nguyễn An',
          issued_at: '2026-09-11T08:00:00Z',
          fulfilled_at: '2026-09-11T10:00:00Z',
        },
      ]),
    ).toEqual({
      pending_count: 1,
      rows: [
        {
          manager_id: 'manager-1',
          manager_name: 'Nguyễn An',
          fulfilled_count: 2,
          average_fulfillment_hours: 3,
        },
      ],
    })
  })
})
