// 🌐 ชนิดข้อมูลฝั่ง public viewer — ตรงกับ backend `services/public_service.py`
// (ไม่ใช้ `types/domain.ts` เพราะ endpoint public ส่งเฉพาะ subset ที่ปลอดภัย — ไม่มี id ภายในอื่น)

export interface PublicColor {
  /** id ของ palette_colors — `plate` ของเพลทเก็บค่านี้ ⇒ viewer ต้องใช้ resolve สี */
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
  event_date: string | null
  live: PublicLive
}

export type Plate = Array<Array<number | null>> | null

export interface PublicSeatStunt {
  id: number
  code: string
  title: string
  notes: string | null
  side: 'A' | 'B'
  plate: Plate
}

export interface PublicSeat {
  slug: string
  stand_id: number
  row_index: number
  col_index: number
  row_label: string
  seat_label: string
  student: { student_code: string | null; student_name: string } | null
  palettes: PublicPalette[]
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
