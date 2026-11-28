/**
 * 🧭 ตัวช่วยอ่านข้อมูล public seat สำหรับ viewer — pure functions (เทสต์ใน `__tests__/seatView.spec.ts`)
 */
import type { Plate, PublicColor, PublicPalette, PublicSeatStunt } from '@/types/public'

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

/** รวมข้อมูลของฉากหนึ่งให้ component วาดได้ตรงกัน */
export function cueView(
  stunt: PublicSeatStunt,
  colors: Map<number, PublicColor>,
  index: number,
): CueView {
  const plate = stunt.plate
  return {
    stunt,
    plate,
    dominant: dominantColor(plate, colors),
    colors: distinctColors(plate, colors),
    index,
  }
}
