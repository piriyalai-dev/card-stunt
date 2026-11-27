// 🌐 ชนิดข้อมูลฝั่ง public viewer — ตรงกับ backend `services/public_service.py`
// (ไม่ใช้ `types/domain.ts` เพราะ endpoint public ส่งเฉพาะ subset ที่ปลอดภัย — ไม่มี id ภายในอื่น)

export interface PublicColor {
  /** id ของ palette_colors — `grid_data` ของเพลทเก็บค่านี้ ⇒ viewer ต้องใช้ resolve สี */
  id: number
  code: string
  name_th: string
  hex: string
  text_color: string
}

export interface PublicPalette {
  id: number
  name: string
  colors: PublicColor[]
}

export interface PublicStand {
  id: number
  name: string
  rows: number
  cols: number
  sub_rows: number
  sub_cols: number
  row_direction: 'bottom_to_top' | 'top_to_bottom'
  col_direction: 'left_to_right' | 'right_to_left'
  row_label_style: 'numeric' | 'alpha'
  col_label_style: 'numeric' | 'alpha'
  row_label_prefix: string
  col_label_prefix: string
  blocked_seats: Array<{ row: number; col: number }>
}

export interface PublicStunt {
  id: number
  code: string
  title: string
  order_index: number
  status: string
}

export interface PublicLive {
  stunt_id: number | null
  stunt_index: number | null
  total: number
  is_active: boolean
  published_version: number
}

export interface PublicMeta {
  slug: string
  name: string
  published_version: number
  roster_lookup_enabled: boolean
  event_date: string | null
  stands: PublicStand[]
  palettes: PublicPalette[]
  stunts: PublicStunt[]
  live: PublicLive
}

export type Plate = Array<Array<number | null>> | null

export interface PublicSeatStunt {
  id: number
  code: string
  title: string
  notes: string | null
  side_a: Plate
  side_b: Plate
}

export interface PublicSeat {
  slug: string
  stand_id: number
  row_index: number
  col_index: number
  row_label: string
  seat_label: string
  student: { student_code: string | null; student_name: string } | null
  stunts: PublicSeatStunt[]
}

export interface PublicVersion {
  published_version: number
  updated_at: string
}

export interface LiveState {
  event_id: number
  slug: string
  current_stunt_id: number | null
  current_index: number | null
  total: number
  published_version: number
  is_active: boolean
  stunt_ids: number[]
}
