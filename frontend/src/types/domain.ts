// 📦 ชนิดข้อมูลโดเมน — ตรงกับ backend `models/*_schemas.py`
//
// ⚠️ ตัวเลข `grid_*` มาจาก backend เป็น **จำนวนช่องจริง** (cols × sub_cols) ไม่ใช่จำนวนที่นั่ง
//    ⇒ อย่าเอาไปใช้แทน rows/cols ของ stand โดยตรง

export type EventStatus = 'draft' | 'active' | 'archived'
export type StuntStatus = 'draft' | 'ready' | 'published'
export type Side = 'A' | 'B'

export interface EventOut {
  id: number
  slug: string
  name: string
  description: string | null
  event_date: string | null
  status: EventStatus
  version: number
  published_version: number
  public_access_enabled: boolean
  palette_a_id: number | null
  palette_b_id: number | null
  live_stunt_id: number | null
  live_is_active: boolean
  created_at: string
  updated_at: string
}

export interface EventCreate {
  name: string
  slug?: string | null
  description?: string | null
  event_date?: string | null
}

export interface EventUpdate {
  name?: string
  slug?: string
  description?: string | null
  event_date?: string | null
  status?: EventStatus
  public_access_enabled?: boolean
  palette_a_id?: number | null
  palette_b_id?: number | null
}

export type RowDirection = 'bottom_to_top' | 'top_to_bottom'
export type ColDirection = 'left_to_right' | 'right_to_left'
export type LabelStyle = 'numeric' | 'alpha'

export interface StandOut {
  id: number
  event_id: number
  name: string
  rows: number
  cols: number
  sub_rows: number
  sub_cols: number
  seat_aspect_ratio: number
  row_direction: RowDirection
  col_direction: ColDirection
  row_label_style: LabelStyle
  col_label_style: LabelStyle
  row_label_prefix: string
  col_label_prefix: string
  blocked_seats: Array<{ row: number; col: number }>
  grid_width: number
  grid_height: number
  created_at: string
  updated_at: string
}

export interface StandCreate {
  name: string
  rows: number
  cols: number
  sub_rows?: number
  sub_cols?: number
  seat_aspect_ratio?: number
  row_direction?: RowDirection
  col_direction?: ColDirection
  row_label_style?: LabelStyle
  col_label_style?: LabelStyle
  row_label_prefix?: string
  col_label_prefix?: string
  blocked_seats?: Array<{ row: number; col: number }>
}

export type StandUpdate = Partial<
  Pick<
    StandCreate,
    | 'name'
    | 'seat_aspect_ratio'
    | 'row_direction'
    | 'col_direction'
    | 'row_label_style'
    | 'col_label_style'
    | 'row_label_prefix'
    | 'col_label_prefix'
  >
>

export interface StandResize {
  rows: number
  cols: number
  sub_rows?: number
  sub_cols?: number
  allow_crop?: boolean
}

export interface ColorOut {
  id: number
  code: string
  name_th: string
  hex: string
  text_color: string
  order_index: number
}

export interface ColorCreate {
  code: string
  name_th: string
  hex: string
  text_color?: string
  order_index?: number
}

export interface ColorUpdate {
  code?: string
  name_th?: string
  hex?: string
  text_color?: string
  order_index?: number
}

export interface PaletteOut {
  id: number
  event_id: number | null
  name: string
  description: string | null
  is_default: boolean
  colors: ColorOut[]
  created_at: string
  updated_at: string
}

export interface PaletteCreate {
  name: string
  description?: string | null
  is_default?: boolean
  colors?: ColorCreate[]
}

export interface StuntOut {
  id: number
  event_id: number
  stand_id: number
  side: Side
  code: string
  title: string
  section: string | null
  notes: string | null
  order_index: number
  status: StuntStatus
  grid_width: number
  grid_height: number
  reference_image_path: string | null
  reference_transform: Record<string, unknown> | null
  thumbnail_path: string | null
  created_at: string
  updated_at: string
}

export interface StuntCreate {
  code: string
  title: string
  section?: string | null
  notes?: string | null
  order_index?: number
  stand_id?: number | null
  side?: Side
}

export interface StuntUpdate {
  code?: string
  title?: string
  section?: string | null
  notes?: string | null
  order_index?: number
  status?: StuntStatus
  side?: Side
  reference_transform?: Record<string, unknown> | null
}

export interface StuntGrid {
  grid_width: number
  grid_height: number
  grid_data: Array<number | null>
}

export interface RevisionOut {
  id: number
  revision_no: number
  grid_width: number
  grid_height: number
  note: string | null
  created_by: number | null
  created_at: string
}

export interface StuntStats {
  total_cells: number
  filled: number
  color_counts: Record<string, number>
}

// ── Roster / Export (Phase 5 — staff) ─────────────────────────────

export interface RosterOut {
  id: number
  event_id: number
  stand_id: number
  row_index: number
  col_index: number
  row_label: string | null
  seat_label: string | null
  student_code: string | null
  access_code: string | null
  student_name: string
  note: string | null
  created_at: string
  updated_at: string
}

export type ExportFormat = 'pdf' | 'csv' | 'zip'
export type ExportStatus = 'queued' | 'running' | 'done' | 'failed'

export interface ExportJob {
  id: number
  event_id: number
  stand_id: number | null
  format: ExportFormat
  scope: 'event' | 'stand'
  status: ExportStatus
  file_path: string | null
  error: string | null
  requested_by: number | null
  created_at: string
  completed_at: string | null
}

export interface LiveAdminState {
  event_id: number
  slug: string
  current_stunt_id: number | null
  current_index: number | null
  total: number
  published_version: number
  is_active: boolean
  stunt_ids: number[]
}

export interface LiveQueueItem {
  stunt_id: number
  position: number
  code: string
  title: string
  side: Side
  status: StuntStatus
}

// ── User management (admin — MANAGE_USERS) ────────────────────────

export type UserRole = 'admin' | 'designer' | 'staff'

export interface UserOut {
  id: number
  username: string
  display_name: string | null
  role: UserRole
  is_admin: boolean
  permissions: string[]
  must_change_password: boolean
}

export interface UserCreate {
  username: string
  password: string
  display_name?: string | null
  role?: UserRole
}

export interface UserUpdate {
  display_name?: string | null
  role?: UserRole
  password?: string
}

// ── Audit log (admin — VIEW_AUDIT_LOG) ────────────────────────────

export interface AuditLogOut {
  id: number
  trace_id: string | null
  user_id: number | null
  actor_identifier: string
  client_source: string
  service_name: string
  action: string
  entity_type: string | null
  entity_id: string | null
  status: string
  error_detail: string | null
  old_values: unknown
  new_values: unknown
  endpoint_or_command: string | null
  ip_address: string | null
  user_agent: string | null
  execution_time_ms: number | null
  created_at: string
}

export interface AuditLogPage {
  items: AuditLogOut[]
  next_cursor: string | null
  has_more: boolean
}

export interface AuditLogOptions {
  actions: string[]
  statuses: string[]
  entity_types: string[]
  service_names: string[]
}
