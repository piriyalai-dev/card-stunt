import { describe, expect, it } from 'vitest'
import {
  alphaLabel,
  blockedKeys,
  cellToSeat,
  gridSize,
  normalizeBlocked,
  seatBase,
  seatLabels,
} from '@/lib/geometry'
import type { Geometry } from '@/lib/geometry'

const g: Geometry = {
  rows: 9,
  cols: 33,
  subRows: 5,
  subCols: 5,
  rowDirection: 'bottom_to_top',
  colDirection: 'left_to_right',
}

describe('gridSize', () => {
  it('คูณ sub-grid ตามที่นั่ง', () => {
    expect(gridSize(g)).toEqual({ width: 165, height: 45 })
  })

  it('รองรับกรณีใหญ่ 50×80 ที่นั่ง', () => {
    expect(gridSize({ ...g, rows: 50, cols: 80 })).toEqual({ width: 400, height: 250 })
  })
})

describe('seatBase / cellToSeat', () => {
  it('bottom_to_top + left_to_right: ที่นั่ง 1 อยู่ล่างซ้ายของกริด', () => {
    expect(seatBase(0, 0, g)).toEqual({ row: 40, col: 0 })
    expect(seatBase(8, 32, g)).toEqual({ row: 0, col: 160 })
  })

  it('top_to_bottom + right_to_left กลับทั้งสองแกน', () => {
    const flipped: Geometry = {
      ...g,
      rowDirection: 'top_to_bottom',
      colDirection: 'right_to_left',
    }
    expect(seatBase(0, 0, flipped)).toEqual({ row: 0, col: 160 })
    expect(seatBase(8, 32, flipped)).toEqual({ row: 40, col: 0 })
  })

  it('round-trip ทุก combination ของทิศทาง', () => {
    for (const rowDirection of ['bottom_to_top', 'top_to_bottom'] as const) {
      for (const colDirection of ['left_to_right', 'right_to_left'] as const) {
        const geo: Geometry = { ...g, rowDirection, colDirection }
        const base = seatBase(4, 20, geo)
        const ref = cellToSeat(base.row + 2, base.col + 3, geo)
        expect(ref).toEqual({ seatRow: 4, seatCol: 20, subRow: 2, subCol: 3 })
      }
    }
  })

  it('ปฏิเสธพิกัดนอกแสตน', () => {
    expect(() => seatBase(9, 0, g)).toThrow('พิกัดที่นั่งอยู่นอกแสตน')
    expect(() => cellToSeat(45, 0, g)).toThrow('พิกัด pixel อยู่นอกกริด')
  })
})

describe('labels', () => {
  it('alpha ต่อเนื่อง A..Z, AA', () => {
    expect(alphaLabel(0)).toBe('A')
    expect(alphaLabel(25)).toBe('Z')
    expect(alphaLabel(26)).toBe('AA')
  })

  it('numeric เป็น 1-based และเติม prefix', () => {
    expect(
      seatLabels(0, 0, {
        rowStyle: 'numeric',
        colStyle: 'numeric',
        rowPrefix: 'แถว ',
        colPrefix: 'ที่นั่ง ',
      }),
    ).toEqual({ row: 'แถว 1', col: 'ที่นั่ง 1' })
  })
})

describe('blocked seats', () => {
  it('normalize ตัดซ้ำและเรียง', () => {
    expect(
      normalizeBlocked([
        { row: 1, col: 2 },
        { row: 0, col: 5 },
        { row: 1, col: 2 },
      ]),
    ).toEqual([
      { row: 0, col: 5 },
      { row: 1, col: 2 },
    ])
  })

  it('สร้าง key set สำหรับตรวจเร็ว', () => {
    const keys = blockedKeys([
      { row: 0, col: 0 },
      { row: 8, col: 32 },
    ])
    expect(keys.has('0,0')).toBe(true)
    expect(keys.has('8,32')).toBe(true)
    expect(keys.size).toBe(2)
  })
})
