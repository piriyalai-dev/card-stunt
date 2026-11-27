/**
 * 🧭 ตัวช่วยอ่านข้อมูล public seat สำหรับ viewer — pure functions (เทสต์ใน `__tests__/seatView.spec.ts`)
 *
 * กติกาพิกัด: API public รับ/คืน **1-based labels** (`row`/`col` = 1..N) แต่ `blocked_seats`
 * และ `row_index`/`col_index` เป็น **0-based** — ฟังก์ชันในไฟล์นี้ทำงาน 0-based ทั้งหมด
 */
import type {
  Plate,
  PublicColor,
  PublicPalette,
  PublicSeatStunt,
  PublicStand,
} from '@/types/public'

/** 0 → A, 25 → Z, 26 → AA (เหมือน `core/grid.py::_alpha`) */
export function alphaIndex(n: number): string {
  let value = n + 1
  let out = ''
  while (value > 0) {
    const rem = (value - 1) % 26
    out = String.fromCharCode(65 + rem) + out
    value = Math.floor((value - 1) / 26)
  }
  return out
}

export function labelFor(
  index0: number,
  style: 'numeric' | 'alpha',
  prefix = '',
): string {
  return prefix + (style === 'alpha' ? alphaIndex(index0) : String(index0 + 1))
}

export function rowLabel(stand: PublicStand, row0: number): string {
  return labelFor(row0, stand.row_label_style, stand.row_label_prefix)
}

export function seatLabel(stand: PublicStand, col0: number): string {
  return labelFor(col0, stand.col_label_style, stand.col_label_prefix)
}

/** แถวที่แสดงจากบนลงล่าง — `bottom_to_top` = แถว 0 อยู่ล่างสุด (ชิดสนาม) */
export function displayRows(stand: PublicStand): number[] {
  const rows = Array.from({ length: stand.rows }, (_, i) => i)
  return stand.row_direction === 'bottom_to_top' ? rows.reverse() : rows
}

/** คอลัมน์ที่แสดงจากซ้ายไปขวา */
export function displayCols(stand: PublicStand): number[] {
  const cols = Array.from({ length: stand.cols }, (_, i) => i)
  return stand.col_direction === 'left_to_right' ? cols : cols.reverse()
}

export function isBlocked(stand: PublicStand, row0: number, col0: number): boolean {
  return stand.blocked_seats.some((s) => s.row === row0 && s.col === col0)
}

export function colorIndex(palettes: PublicPalette[]): Map<number, PublicColor> {
  const out = new Map<number, PublicColor>()
  for (const palette of palettes) {
    for (const color of palette.colors) {
      out.set(color.id, color)
    }
  }
  return out
}

export interface DominantColor {
  color: PublicColor | null
  colorId: number | null
  count: number
  total: number
}

/** สีที่ปรากฏมากที่สุดในเพลท (null = ช่องว่าง) */
export function dominantColor(plate: Plate, colors: Map<number, PublicColor>): DominantColor {
  const counts = new Map<number, number>()
  let total = 0
  if (plate) {
    for (const row of plate) {
      for (const cell of row) {
        if (cell === null) continue
        total += 1
        counts.set(cell, (counts.get(cell) ?? 0) + 1)
      }
    }
  }
  let bestId: number | null = null
  let best = 0
  for (const [id, count] of counts) {
    if (count > best) {
      best = count
      bestId = id
    }
  }
  return {
    color: bestId === null ? null : colors.get(bestId) ?? null,
    colorId: bestId,
    count: best,
    total,
  }
}

export function distinctColors(plate: Plate, colors: Map<number, PublicColor>): PublicColor[] {
  if (!plate) return []
  const seen = new Set<number>()
  const out: PublicColor[] = []
  for (const row of plate) {
    for (const cell of row) {
      if (cell === null || seen.has(cell)) continue
      seen.add(cell)
      const color = colors.get(cell)
      if (color) out.push(color)
    }
  }
  return out
}

export function plateHasContent(plate: Plate): boolean {
  return !!plate && plate.some((row) => row.some((cell) => cell !== null))
}

export interface CueView {
  stunt: PublicSeatStunt
  plate: Plate
  dominant: DominantColor
  colors: PublicColor[]
  index: number
}

/** รวมข้อมูลของฉากหนึ่งด้าน (A/B) ให้ component วาดได้ตรงกัน */
export function cueView(
  stunt: PublicSeatStunt,
  side: 'A' | 'B',
  colors: Map<number, PublicColor>,
  index: number,
): CueView {
  const plate = side === 'A' ? stunt.side_a : stunt.side_b
  return {
    stunt,
    plate,
    dominant: dominantColor(plate, colors),
    colors: distinctColors(plate, colors),
    index,
  }
}

/** มีด้าน B ที่มีเนื้อหาอยู่ไหม (ใช้ตัดสินว่าจะโชว์สวิตช์ A/B) */
export function hasSideB(stunts: PublicSeatStunt[]): boolean {
  return stunts.some((s) => plateHasContent(s.side_b))
}
