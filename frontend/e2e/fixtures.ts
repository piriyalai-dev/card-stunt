/** ข้อมูล mock ของ E2E — ตรงกับ shape ของ backend public/admin API */
import type { Page, Route } from '@playwright/test'

const now = '2026-11-27T10:00:00Z'

const plate = (colorId: number) => Array.from({ length: 5 }, () => Array.from({ length: 5 }, () => colorId))

export const standPublic = {
  id: 11,
  name: 'โซนกลาง',
  rows: 2,
  cols: 3,
  sub_rows: 5,
  sub_cols: 5,
  row_direction: 'bottom_to_top',
  col_direction: 'left_to_right',
  row_label_style: 'alpha',
  col_label_style: 'numeric',
  row_label_prefix: '',
  col_label_prefix: '',
  blocked_seats: [{ row: 0, col: 2 }],
}

export const meta = {
  slug: 'sport69',
  name: 'กีฬาสี 69 — โซนกลาง',
  published_version: 3,
  roster_lookup_enabled: true,
  event_date: '2026-11-27',
  stands: [standPublic],
  palettes: [
    {
      id: 5,
      name: 'ชุดหลัก',
      colors: [
        { id: 1, code: '01', name_th: 'แดงสด', hex: '#B91C1C', text_color: '#FFFFFF' },
        { id: 2, code: '02', name_th: 'ขาว', hex: '#FFFFFF', text_color: '#1F2328' },
      ],
    },
  ],
  stunts: [
    { id: 101, code: '01', title: 'เปิดตัว', order_index: 1, status: 'published' },
    { id: 102, code: '02', title: 'โลโก้โรงเรียน', order_index: 2, status: 'published' },
  ],
  live: { stunt_id: 101, stunt_index: 0, total: 2, is_active: false, published_version: 3 },
}

export const seat = {
  slug: 'sport69',
  stand_id: 11,
  row_index: 0,
  col_index: 0,
  row_label: 'A',
  seat_label: '1',
  student: { student_code: '10001', student_name: 'นาย ตัวอย่าง' },
  stunts: [
    { id: 101, code: '01', title: 'เปิดตัว', notes: 'ยกค้าง 8 จังหวะ', side_a: plate(1), side_b: null },
    { id: 102, code: '02', title: 'โลโก้โรงเรียน', notes: null, side_a: plate(2), side_b: null },
  ],
}

export const authUser = {
  id: 1,
  username: 'admin',
  display_name: 'Admin E2E',
  role: 'admin',
  is_admin: true,
  permissions: [
    'MANAGE_USERS', 'MANAGE_EVENTS', 'MANAGE_STANDS', 'MANAGE_PALETTES', 'MANAGE_STUNTS',
    'MANAGE_REVISIONS', 'PUBLISH_STUNTS', 'CONTROL_LIVE', 'MANAGE_ROSTERS', 'EXPORT', 'VIEW_AUDIT_LOG',
  ],
  must_change_password: false,
}

export const eventAdmin = {
  id: 1,
  slug: 'sport69',
  name: 'กีฬาสี 69 — โซนกลาง',
  description: null,
  event_date: '2026-11-27',
  status: 'active',
  version: 4,
  published_version: 3,
  public_access_enabled: true,
  roster_lookup_enabled: true,
  live_stunt_id: 101,
  live_is_active: false,
  created_at: now,
  updated_at: now,
}

export const standAdmin = {
  id: 11,
  event_id: 1,
  name: 'โซนกลาง',
  rows: 2,
  cols: 3,
  sub_rows: 5,
  sub_cols: 5,
  seat_aspect_ratio: 1,
  row_direction: 'bottom_to_top',
  col_direction: 'left_to_right',
  row_label_style: 'alpha',
  col_label_style: 'numeric',
  row_label_prefix: '',
  col_label_prefix: '',
  blocked_seats: [{ row: 0, col: 2 }],
  grid_width: 15,
  grid_height: 10,
  created_at: now,
  updated_at: now,
}

export const roster = {
  id: 7,
  event_id: 1,
  stand_id: 11,
  row_index: 0,
  col_index: 0,
  row_label: 'A',
  seat_label: '1',
  student_code: '10001',
  student_name: 'นาย ตัวอย่าง',
  note: null,
  created_at: now,
  updated_at: now,
}

export const exportJob = (id: number, status: string) => ({
  id,
  event_id: 1,
  stand_id: null,
  format: 'pdf',
  scope: 'event',
  status,
  file_path: status === 'done' ? `exports/${id}/export.pdf` : null,
  error: null,
  requested_by: 1,
  created_at: now,
  completed_at: status === 'done' ? now : null,
})

export const stuntsAdmin = [
  {
    id: 101, event_id: 1, stand_id: 11, palette_a_id: 5, palette_b_id: null,
    code: '01', title: 'เปิดตัว', section: null, notes: null, order_index: 1,
    status: 'published', grid_width: 15, grid_height: 10,
    reference_image_path: null, reference_transform: null, thumbnail_path: null,
    created_at: now, updated_at: now,
  },
  {
    id: 102, event_id: 1, stand_id: 11, palette_a_id: 5, palette_b_id: null,
    code: '02', title: 'โลโก้โรงเรียน', section: null, notes: null, order_index: 2,
    status: 'published', grid_width: 15, grid_height: 10,
    reference_image_path: null, reference_transform: null, thumbnail_path: null,
    created_at: now, updated_at: now,
  },
]

export const liveState = (currentId: number | null) => ({
  event_id: 1,
  slug: 'sport69',
  current_stunt_id: currentId,
  current_index: currentId === 101 ? 0 : currentId === 102 ? 1 : null,
  total: 2,
  published_version: 3,
  is_active: currentId !== null,
  stunt_ids: [101, 102],
})

// ── route installers ────────────────────────────────────────────────

type Handler = (route: Route) => Promise<void>

async function fulfillJson(route: Route, data: unknown, status = 200): Promise<void> {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) })
}

/** viewer: meta / seat / version — `/live` ถูก abort (ไม่ต้องเปิด SSE จริง) */
export async function mockPublicApi(page: Page): Promise<void> {
  await page.route('**/api/v1/public/events/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/meta')) return fulfillJson(route, meta)
    if (url.pathname.endsWith('/version')) {
      return fulfillJson(route, { published_version: 3, updated_at: now })
    }
    if (url.pathname.endsWith('/seat')) return fulfillJson(route, seat)
    if (url.pathname.endsWith('/live')) return route.abort()
    return fulfillJson(route, { detail: 'not mocked' }, 404)
  })
}

export interface AdminMock {
  /** เปลี่ยนผล GET /exports/2 ระหว่างเทสต์ (polling) */
  setNewJobStatus: (status: 'queued' | 'running' | 'done' | 'failed') => void
}

export async function mockAdminApi(page: Page): Promise<AdminMock> {
  let newJobStatus: 'queued' | 'running' | 'done' | 'failed' = 'queued'
  let liveCurrent: number | null = 101

  const handlers: Record<string, Handler> = {
    'GET /api/v1/auth/me': (route) => fulfillJson(route, authUser),
    'GET /api/v1/events/1': (route) => fulfillJson(route, eventAdmin),
    'GET /api/v1/events/1/stands': (route) => fulfillJson(route, [standAdmin]),
    'GET /api/v1/events/1/rosters': (route) => fulfillJson(route, [roster]),
    'GET /api/v1/events/1/exports': (route) => fulfillJson(route, [exportJob(1, 'done')]),
    'POST /api/v1/events/1/exports': (route) => fulfillJson(route, exportJob(2, 'queued')),
    'GET /api/v1/events/1/live': (route) => fulfillJson(route, liveState(liveCurrent)),
    'GET /api/v1/events/1/stunts': (route) => fulfillJson(route, stuntsAdmin),
    'POST /api/v1/events/1/live/advance': async (route) => {
      const body = route.request().postDataJSON() as { action: string; stunt_id?: number }
      if (body.action === 'next') liveCurrent = 102
      else if (body.action === 'prev') liveCurrent = 101
      else if (body.action === 'goto' && body.stunt_id) liveCurrent = body.stunt_id
      await fulfillJson(route, liveState(liveCurrent))
    },
  }

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const key = `${request.method()} ${url.pathname}`

    if (key === 'GET /api/v1/exports/2') {
      // poll แรก ๆ ยัง queued (ถ้าเทสต์ยังไม่สั่งเปลี่ยน) — เปลี่ยนได้ผ่าน AdminMock
      return fulfillJson(route, exportJob(2, newJobStatus))
    }
    if (key === 'GET /api/v1/exports/2/download') {
      return route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4 mock' })
    }
    if (key === 'POST /api/v1/events/1/rosters/import') {
      return fulfillJson(route, { inserted: 1, errors: [], total: 1 })
    }

    const handler = handlers[key]
    if (handler) return handler(route)
    return fulfillJson(route, { detail: `not mocked: ${key}` }, 404)
  })

  return {
    setNewJobStatus(status) {
      newJobStatus = status
    },
  }
}
