import { describe, expect, it } from 'vitest'
import {
  alphaIndex,
  colorIndex,
  cueView,
  displayCols,
  displayRows,
  distinctColors,
  dominantColor,
  hasSideB,
  isBlocked,
  labelFor,
  plateHasContent,
  rowLabel,
  seatLabel,
} from '@/lib/seatView'
import type { PublicColor, PublicPalette, PublicSeatStunt, PublicStand } from '@/types/public'

const stand = (overrides: Partial<PublicStand> = {}): PublicStand => ({
  id: 1,
  name: 'โซนกลาง',
  rows: 3,
  cols: 4,
  sub_rows: 2,
  sub_cols: 2,
  row_direction: 'bottom_to_top',
  col_direction: 'left_to_right',
  row_label_style: 'alpha',
  col_label_style: 'numeric',
  row_label_prefix: '',
  col_label_prefix: '',
  blocked_seats: [{ row: 0, col: 1 }],
  ...overrides,
})

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
  side_a: [
    [11, 11],
    [12, 11],
  ],
  side_b: null,
  ...overrides,
})

describe('labels', () => {
  it('alphaIndex ต่อเนื่องแบบ spreadsheet', () => {
    expect(alphaIndex(0)).toBe('A')
    expect(alphaIndex(25)).toBe('Z')
    expect(alphaIndex(26)).toBe('AA')
    expect(alphaIndex(27)).toBe('AB')
  })

  it('labelFor รองรับ numeric/alpha และ prefix', () => {
    expect(labelFor(0, 'numeric')).toBe('1')
    expect(labelFor(2, 'alpha', 'R')).toBe('RC')
  })

  it('rowLabel/seatLabel ใช้สไตล์ของ stand', () => {
    const s = stand({ row_label_prefix: 'แถว ' , col_label_style: 'alpha' })
    expect(rowLabel(s, 0)).toBe('แถว A')
    expect(seatLabel(s, 1)).toBe('B')
  })
})

describe('orientation', () => {
  it('bottom_to_top แสดงแถว 0 ล่างสุด', () => {
    expect(displayRows(stand({ row_direction: 'bottom_to_top' }))).toEqual([2, 1, 0])
  })

  it('top_to_bottom แสดงแถว 0 บนสุด', () => {
    expect(displayRows(stand({ row_direction: 'top_to_bottom' }))).toEqual([0, 1, 2])
  })

  it('right_to_left กลับคอลัมน์', () => {
    expect(displayCols(stand({ col_direction: 'right_to_left' }))).toEqual([3, 2, 1, 0])
    expect(displayCols(stand())).toEqual([0, 1, 2, 3])
  })

  it('isBlocked ใช้พิกัด 0-based', () => {
    const s = stand()
    expect(isBlocked(s, 0, 1)).toBe(true)
    expect(isBlocked(s, 0, 2)).toBe(false)
  })
})

describe('plate colors', () => {
  const map = colorIndex(palettes)

  it('colorIndex สร้าง map จาก id', () => {
    expect(map.get(11)?.name_th).toBe('แดงสด')
    expect(map.size).toBe(3)
  })

  it('dominantColor นับสีที่มากที่สุดและไม่นับช่องว่าง', () => {
    const d = dominantColor(stunt().side_a, map)
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
    expect(distinctColors(stunt().side_a, map).map((c) => c.id)).toEqual([11, 12])
  })

  it('plateHasContent/hasSideB', () => {
    expect(plateHasContent(stunt().side_a)).toBe(true)
    expect(plateHasContent(null)).toBe(false)
    expect(hasSideB([stunt()])).toBe(false)
    expect(hasSideB([stunt({ side_b: [[13, null], [null, null]] })])).toBe(true)
  })

  it('cueView เลือกด้านถูกและพก index', () => {
    const s = stunt({ side_b: [[13, 13], [13, 13]] })
    const a = cueView(s, 'A', map, 0)
    const b = cueView(s, 'B', map, 1)
    expect(a.dominant.colorId).toBe(11)
    expect(b.dominant.colorId).toBe(13)
    expect(b.index).toBe(1)
  })
})
