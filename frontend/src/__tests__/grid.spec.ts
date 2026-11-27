import { describe, expect, it } from 'vitest'
import {
  EMPTY,
  GridEditor,
  GridHistory,
  bresenham,
  colorCounts,
  createGrid,
  cropOrPad,
  decodeRle,
  despeckle,
  diffGrids,
  encodeRle,
  extractRegion,
  floodFill,
  fromApiGrid,
  normalizeRegion,
  nudge,
  paintRegion,
  regionIndices,
  shapeCells,
  toApiGrid,
} from '@/lib/grid'

describe('grid ↔ API', () => {
  it('null → EMPTY และกลับ', () => {
    const grid = fromApiGrid([1, null, 3], 3, 1)
    expect(Array.from(grid)).toEqual([1, EMPTY, 3])
    expect(toApiGrid(grid)).toEqual([1, null, 3])
  })

  it('ข้อมูลสั้นกว่า/ยาวกว่า → เติม/ตัด', () => {
    const grid = fromApiGrid([5], 3, 1)
    expect(Array.from(grid)).toEqual([5, EMPTY, EMPTY])
    const longer = fromApiGrid([1, 2, 3, 4], 2, 1)
    expect(Array.from(longer)).toEqual([1, 2])
  })
})

describe('RLE draft encoding', () => {
  it('ไปกลับได้แม่นยำ', () => {
    const grid = createGrid(6, 2)
    grid[0] = 7
    grid[1] = 7
    grid[5] = 2
    const text = encodeRle(grid)
    expect(text).toBe('7:2,-1:3,2:1,-1:6')
    expect(Array.from(decodeRle(text, grid.length)!)).toEqual(Array.from(grid))
  })

  it('250×400 (100k ช่อง) ว่างเกือบทั้งหมด → RLE สั้นและถอดคืนได้', () => {
    const grid = createGrid(400, 250)
    grid[12345] = 9
    const text = encodeRle(grid)
    expect(text.length).toBeLessThan(40)
    expect(Array.from(decodeRle(text, grid.length)!).every((v, i) => v === grid[i])).toBe(true)
  })

  it('ข้อมูลเสีย → null (ไม่ throw)', () => {
    expect(decodeRle('x:2', 2)).toBeNull()
    expect(decodeRle('1:5', 3)).toBeNull()
    expect(decodeRle('1:1', 2)).toBeNull()
  })
})

describe('GridEditor + history', () => {
  it('commit เก็บเฉพาะช่องที่เปลี่ยน', () => {
    const grid = createGrid(4, 1)
    const editor = new GridEditor(grid)
    editor.setXY(1, 0, 4, 1, 9)
    editor.setXY(1, 0, 4, 1, 9)
    expect(editor.size).toBe(1)
    const change = editor.commit()!
    expect(Array.from(change.indices)).toEqual([1])
    expect(Array.from(change.before)).toEqual([EMPTY])
    expect(Array.from(change.after)).toEqual([9])
  })

  it('undo/redo คืนค่าเดิมและค่าใหม่', () => {
    const grid = createGrid(4, 1)
    const history = new GridHistory()
    const editor = new GridEditor(grid)
    editor.setXY(2, 0, 4, 1, 5)
    history.push(editor.commit())
    expect(grid[2]).toBe(5)

    history.undo(grid)
    expect(grid[2]).toBe(EMPTY)
    expect(history.canRedo).toBe(true)

    history.redo(grid)
    expect(grid[2]).toBe(5)
  })

  it('push ใหม่ล้าง redo และจำกัด 60 ขั้น', () => {
    const grid = createGrid(100, 1)
    const history = new GridHistory()
    for (let i = 0; i < 70; i += 1) {
      const editor = new GridEditor(grid)
      editor.setXY(i, 0, 100, 1, 1)
      history.push(editor.commit())
    }
    expect(history.undoDepth).toBe(60)
    for (let i = 0; i < 60; i += 1) history.undo(grid)
    expect(history.canUndo).toBe(false)
  })
})

describe('raster ops', () => {
  it('bresenham เริ่ม/จบตรงและไม่มีจุดขาด', () => {
    const points = bresenham(0, 0, 4, 3)
    expect(points[0]).toEqual([0, 0])
    expect(points[points.length - 1]).toEqual([4, 3])
    for (let i = 1; i < points.length; i += 1) {
      const [x0, y0] = points[i - 1]!
      const [x1, y1] = points[i]!
      expect(Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0))).toBe(1)
    }
  })

  it('flood fill จำกัดอยู่ที่บริเวณที่ต่อเนื่อง', () => {
    const w = 5
    const h = 3
    const grid = createGrid(w, h)
    // กำแพงแนวตั้งที่คอลัมน์ 2
    for (let y = 0; y < h; y += 1) grid[y * w + 2] = 9
    const editor = new GridEditor(grid)
    floodFill(editor, w, h, 0, 0, 4)
    expect(grid[0]).toBe(4)
    expect(grid[1]).toBe(4)
    expect(grid[2]).toBe(9)
    expect(grid[3]).toBe(EMPTY)
  })

  it('despeckle ลบจุดเดี่ยวแต่ไม่แตะกลุ่ม', () => {
    const w = 5
    const h = 1
    const grid = createGrid(w, h)
    grid[0] = 1 // เดี่ยว
    grid[2] = 2 // กลุ่มสองช่อง
    grid[3] = 2
    const editor = new GridEditor(grid)
    despeckle(editor, w, h)
    expect(grid[0]).toBe(EMPTY)
    expect(grid[2]).toBe(2)
    expect(grid[3]).toBe(2)
  })

  it('nudge เลื่อนทั้งแผ่นและตัดขอบ', () => {
    const grid = createGrid(3, 2)
    grid[0] = 7 // (0,0)
    const moved = nudge(grid, 3, 2, 1, 1)
    expect(moved[1 * 3 + 1]).toBe(7)
    expect(moved[0]).toBe(EMPTY)
  })

  it('cropOrPad ใช้ top-left anchor', () => {
    const grid = fromApiGrid([1, 2, 3, 4], 2, 2)
    const big = cropOrPad(grid, 2, 2, 3, 3)
    expect(big[0]).toBe(1)
    expect(big[1]).toBe(2)
    expect(big[3]).toBe(3)
    expect(big[5]).toBe(EMPTY)
  })

  it('shapeCells: เส้นตรงมีปลายทางครบและไม่ออกนอกกริด', () => {
    const cells = shapeCells('line', 5, 5, 0, 0, 9, 9)
    expect(cells).toContain(0)
    expect(cells).toContain(4 * 5 + 4)
    for (const i of cells) {
      expect(i).toBeGreaterThanOrEqual(0)
      expect(i).toBeLessThan(25)
    }
  })

  it('shapeCells: สี่เหลี่ยมโปร่งมีแต่ขอบ', () => {
    const cells = new Set(shapeCells('rect', 5, 5, 1, 1, 3, 3))
    expect(cells.has(1 * 5 + 1)).toBe(true) // มุม
    expect(cells.has(2 * 5 + 2)).toBe(false) // กลาง
    expect(cells.size).toBe(8)
  })

  it('shapeCells: วงรีอยู่ในกรอบ bbox', () => {
    const cells = shapeCells('ellipse', 10, 10, 2, 3, 7, 8)
    expect(cells.length).toBeGreaterThan(0)
    for (const i of cells) {
      const x = i % 10
      const y = Math.floor(i / 10)
      expect(x).toBeGreaterThanOrEqual(2)
      expect(x).toBeLessThanOrEqual(7)
      expect(y).toBeGreaterThanOrEqual(3)
      expect(y).toBeLessThanOrEqual(8)
    }
  })

  it('region: normalize กลับทิศได้และ clip ขอบ', () => {
    expect(normalizeRegion(5, 4, 2, 1, 10, 10)).toEqual({ x: 2, y: 1, w: 4, h: 4 })
    expect(normalizeRegion(-3, -3, 1, 1, 10, 10)).toEqual({ x: 0, y: 0, w: 2, h: 2 })
    expect(normalizeRegion(20, 20, 30, 30, 10, 10)).toBeNull()
    expect(regionIndices({ x: 1, y: 1, w: 2, h: 2 }, 5)).toEqual([6, 7, 11, 12])
  })

  it('extract + paint region ไปกลับได้', () => {
    const grid = fromApiGrid([1, 2, 3, 4, 5, 6, 7, 8, 9], 3, 3)
    const region = { x: 1, y: 0, w: 2, h: 2 }
    const values = extractRegion(grid, 3, region)
    expect(Array.from(values)).toEqual([2, 3, 5, 6])
    const target = createGrid(3, 3)
    const editor = new GridEditor(target)
    paintRegion(editor, 3, 3, 0, 1, region, values)
    expect(Array.from(target)).toEqual([EMPTY, EMPTY, EMPTY, 2, 3, EMPTY, 5, 6, EMPTY])
  })

  it('diffGrids สร้าง transaction ที่ undo ได้', () => {
    const before = fromApiGrid([1, 2, 3], 3, 1)
    const after = fromApiGrid([1, 8, 3], 3, 1)
    const change = diffGrids(before, after)!
    expect(Array.from(change.indices)).toEqual([1])
    const history = new GridHistory()
    history.push(change)
    history.undo(after)
    expect(Array.from(after)).toEqual([1, 2, 3])
  })

  it('colorCounts ไม่นับช่องว่าง', () => {
    const grid = fromApiGrid([1, 1, null, 2], 4, 1)
    const counts = colorCounts(grid)
    expect(counts.get(1)).toBe(2)
    expect(counts.get(2)).toBe(1)
    expect(counts.has(EMPTY)).toBe(false)
  })
})
