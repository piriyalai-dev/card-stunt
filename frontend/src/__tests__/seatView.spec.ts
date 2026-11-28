import { describe, expect, it } from 'vitest'
import { colorIndex, cueView, distinctColors, dominantColor, plateHasContent } from '@/lib/seatView'
import type { PublicColor, PublicPalette, PublicSeatStunt } from '@/types/public'

const colors: PublicColor[] = [
  { id: 11, code: '01', name_th: 'แดงสด', hex: '#B91C1C', text_color: '#FFFFFF' },
  { id: 12, code: '02', name_th: 'ขาว', hex: '#FFFFFF', text_color: '#1F2328' },
  { id: 13, code: '03', name_th: 'เหลือง', hex: '#EAB308', text_color: '#1F2328' },
]

const palettes: PublicPalette[] = [{ id: 1, name: 'หลัก', colors }]

const stunt = (overrides: Partial<PublicSeatStunt> = {}): PublicSeatStunt => ({
  id: 5,
  code: 'S1',
  title: 'เปิดตัว',
  notes: null,
  side: 'A',
  plate: [
    [11, 11],
    [12, 11],
  ],
  ...overrides,
})

describe('plate colors', () => {
  const map = colorIndex(palettes)

  it('colorIndex สร้าง map จาก id', () => {
    expect(map.get(11)?.name_th).toBe('แดงสด')
    expect(map.size).toBe(3)
  })

  it('dominantColor นับสีที่มากที่สุดและไม่นับช่องว่าง', () => {
    const d = dominantColor(stunt().plate, map)
    expect(d.colorId).toBe(11)
    expect(d.count).toBe(3)
    expect(d.total).toBe(4)
    expect(d.color?.code).toBe('01')
  })

  it('dominantColor ของเพลทว่างคือ null', () => {
    const d = dominantColor([[null, null], [null, null]], map)
    expect(d.color).toBeNull()
    expect(d.total).toBe(0)
  })

  it('distinctColors เรียงตามที่พบครั้งแรกและข้าม null', () => {
    expect(distinctColors(stunt().plate, map).map((c) => c.id)).toEqual([11, 12])
  })

  it('plateHasContent', () => {
    expect(plateHasContent(stunt().plate)).toBe(true)
    expect(plateHasContent(null)).toBe(false)
  })

  it('cueView พก plate + side + index', () => {
    const s = stunt({ plate: [[13, 13], [13, 13]] })
    const cue = cueView(s, map, 1)
    expect(cue.dominant.colorId).toBe(13)
    expect(cue.stunt.side).toBe('A')
    expect(cue.index).toBe(1)
  })
})
