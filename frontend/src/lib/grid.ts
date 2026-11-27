/**
 * 🔲 แกนข้อมูลพิกเซลของ Pixel Studio
 *
 * - เก็บเป็น `Int32Array` แบบ row-major ⇒ แก้/วาด/นับเร็วกว่า array ของ object มาก
 *   (design report §8.8 บังคับ: "ห้าม v-for div พิกเซลหลายพันตัว")
 * - `EMPTY = -1` แทน `null` ของ backend — แปลงที่ขอบ API เท่านั้น
 * - Undo/redo เก็บเป็น **diff** (index + ค่าเดิม/ใหม่) ไม่ใช่ snapshot เต็ม
 *   ⇒ สโตรกยาว 200 ช่องใช้ ~1.6KB ไม่ใช่ 400KB และเก็บได้ 60 ขั้นโดยไม่กินแรม
 *
 * ⚠️ ไฟล์นี้ pure (ไม่มี DOM) ⇒ เทสต์ได้ใน vitest
 */

export const EMPTY = -1

export type Grid = Int32Array

export function createGrid(width: number, height: number, fill = EMPTY): Grid {
  const grid = new Int32Array(width * height)
  if (fill !== 0) grid.fill(fill)
  return grid
}

/** backend → local (null → EMPTY, ยาวไม่ตรง → เติม/ตัดให้พอดี) */
export function fromApiGrid(
  data: ReadonlyArray<number | null> | null | undefined,
  width: number,
  height: number,
): Grid {
  const size = width * height
  const grid = createGrid(width, height)
  if (!data) return grid
  const n = Math.min(size, data.length)
  for (let i = 0; i < n; i += 1) {
    const v = data[i]
    grid[i] = v === null || v === undefined ? EMPTY : v
  }
  return grid
}

/** local → backend (EMPTY → null) */
export function toApiGrid(grid: Grid): Array<number | null> {
  const out = Array.from({ length: grid.length }, () => null as number | null)
  for (let i = 0; i < grid.length; i += 1) {
    const v = grid[i]!
    out[i] = v === EMPTY ? null : v
  }
  return out
}

export function gridEquals(a: Grid, b: Grid): boolean {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) if (a[i] !== b[i]) return false
  return true
}

// ── RLE สำหรับ draft ใน localStorage ──────────────────────────────

/**
 * เข้ารหัสแบบ run-length: `"-1:1000,5:3"` — grid 100,000 ช่องที่มีพื้นที่ว่างส่วนใหญ่
 * เหลือไม่กี่ไบต์ · รูปแบบเสียหายเมื่อไหร่ `decodeRle` คืน `null` (ไม่ throw)
 */
export function encodeRle(grid: Grid): string {
  if (grid.length === 0) return ''
  const parts: string[] = []
  let value = grid[0]!
  let count = 1
  for (let i = 1; i < grid.length; i += 1) {
    const v = grid[i]!
    if (v === value) {
      count += 1
    } else {
      parts.push(`${value}:${count}`)
      value = v
      count = 1
    }
  }
  parts.push(`${value}:${count}`)
  return parts.join(',')
}

export function decodeRle(text: string, expectedLength: number): Grid | null {
  if (text === '') return expectedLength === 0 ? new Int32Array(0) : null
  const grid = createGrid(1, expectedLength)
  let offset = 0
  for (const part of text.split(',')) {
    const idx = part.indexOf(':')
    if (idx <= 0) return null
    const value = Number(part.slice(0, idx))
    const count = Number(part.slice(idx + 1))
    if (!Number.isInteger(value) || !Number.isInteger(count) || count < 0) return null
    if (offset + count > expectedLength) return null
    grid.fill(value, offset, offset + count)
    offset += count
  }
  return offset === expectedLength ? grid : null
}

// ── transaction + history ──────────────────────────────────────────

export interface GridChange {
  indices: Int32Array
  before: Int32Array
  after: Int32Array
}

/**
 * ตัวแก้ grid ที่จำค่าเดิมของทุกช่องที่ถูกแตะ
 *
 * ⚠️ **ต้องสร้างใหม่ต่อสโตรก** (pointerdown → pointerup) แล้ว `commit()` ครั้งเดียว
 *   ไม่ใช่สร้างใหม่ทุกครั้งที่ขยับเมาส์ (ไม่งั้น undo จะย้อนทีละพิกเซล)
 */
export class GridEditor {
  private readonly touched = new Map<number, number>()

  constructor(readonly grid: Grid) {}

  get size(): number {
    return this.touched.size
  }

  set(index: number, value: number): void {
    if (index < 0 || index >= this.grid.length) return
    const old = this.grid[index]!
    if (old === value) return
    if (!this.touched.has(index)) this.touched.set(index, old)
    this.grid[index] = value
  }

  setXY(x: number, y: number, width: number, height: number, value: number): void {
    if (x < 0 || y < 0 || x >= width || y >= height) return
    this.set(y * width + x, value)
  }

  commit(): GridChange | null {
    if (this.touched.size === 0) return null
    const n = this.touched.size
    const indices = new Int32Array(n)
    const before = new Int32Array(n)
    const after = new Int32Array(n)
    let i = 0
    for (const [index, oldValue] of this.touched) {
      indices[i] = index
      before[i] = oldValue
      after[i] = this.grid[index]!
      i += 1
    }
    this.touched.clear()
    return { indices, before, after }
  }
}

export function applyChange(grid: Grid, change: GridChange, direction: 'undo' | 'redo'): void {
  const values = direction === 'undo' ? change.before : change.after
  for (let i = 0; i < change.indices.length; i += 1) {
    grid[change.indices[i]!] = values[i]!
  }
}

export class GridHistory {
  /** 60 ขั้น — เกินกว่าที่ design §8.8 ขั้นต่ำ 50 · diff ทำให้ราคาถูก */
  static readonly LIMIT = 60

  private undoStack: GridChange[] = []
  private redoStack: GridChange[] = []

  get canUndo(): boolean {
    return this.undoStack.length > 0
  }

  get canRedo(): boolean {
    return this.redoStack.length > 0
  }

  get undoDepth(): number {
    return this.undoStack.length
  }

  push(change: GridChange | null): void {
    if (!change) return
    this.undoStack.push(change)
    if (this.undoStack.length > GridHistory.LIMIT) this.undoStack.shift()
    this.redoStack = []
  }

  undo(grid: Grid): GridChange | null {
    const change = this.undoStack.pop()
    if (!change) return null
    applyChange(grid, change, 'undo')
    this.redoStack.push(change)
    return change
  }

  redo(grid: Grid): GridChange | null {
    const change = this.redoStack.pop()
    if (!change) return null
    applyChange(grid, change, 'redo')
    this.undoStack.push(change)
    return change
  }

  clear(): void {
    this.undoStack = []
    this.redoStack = []
  }
}

// ── raster ops ─────────────────────────────────────────────────────

/** Bresenham — คืนทุกช่องบนเส้น (ใช้กับ brush/line ให้ไม่มีจุดขาด) */
export function bresenham(
  x0: number,
  y0: number,
  x1: number,
  y1: number,
): Array<[number, number]> {
  const points: Array<[number, number]> = []
  let x = x0
  let y = y0
  const dx = Math.abs(x1 - x0)
  const dy = -Math.abs(y1 - y0)
  const sx = x0 < x1 ? 1 : -1
  const sy = y0 < y1 ? 1 : -1
  let err = dx + dy
  // กันลูป runaway จากพิกัดมหาศาล (ไม่ควรเกิด แต่ปลอดภัยกว่า)
  let guard = Math.abs(x1 - x0) + Math.abs(y1 - y0) + 2
  while (guard-- > 0) {
    points.push([x, y])
    if (x === x1 && y === y1) break
    const e2 = 2 * err
    if (e2 >= dy) {
      err += dy
      x += sx
    }
    if (e2 <= dx) {
      err += dx
      y += sy
    }
  }
  return points
}

export function stampCircle(
  editor: GridEditor,
  width: number,
  height: number,
  cx: number,
  cy: number,
  radius: number,
  value: number,
): void {
  if (radius <= 0) {
    editor.setXY(cx, cy, width, height, value)
    return
  }
  const r2 = radius * radius
  for (let dy = -radius; dy <= radius; dy += 1) {
    for (let dx = -radius; dx <= radius; dx += 1) {
      if (dx * dx + dy * dy <= r2) editor.setXY(cx + dx, cy + dy, width, height, value)
    }
  }
}

/** วาดเส้นหนา (brush) — ใช้ Bresenham แล้ว stamp วงกลมที่ทุกจุด ⇒ ไม่มีรอยขาด */
export function paintLine(
  editor: GridEditor,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  value: number,
  size = 1,
): void {
  const radius = Math.max(0, Math.floor((size - 1) / 2))
  for (const [x, y] of bresenham(x0, y0, x1, y1)) {
    stampCircle(editor, width, height, x, y, radius, value)
  }
}

export function drawRect(
  editor: GridEditor,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  value: number,
  filled: boolean,
): void {
  const left = Math.max(0, Math.min(x0, x1))
  const right = Math.min(width - 1, Math.max(x0, x1))
  const top = Math.max(0, Math.min(y0, y1))
  const bottom = Math.min(height - 1, Math.max(y0, y1))
  for (let y = top; y <= bottom; y += 1) {
    for (let x = left; x <= right; x += 1) {
      const edge = x === left || x === right || y === top || y === bottom
      if (filled || edge) editor.setXY(x, y, width, height, value)
    }
  }
}

/**
 * รายการ index ของช่องที่รูปทรงจะกิน — ใช้ **preview ระหว่างลาก** (ก่อน commit)
 * ตัวเดียวกันกับที่ `drawRect`/`drawEllipse`/`paintLine` วาดจริง ⇒ preview ไม่โกหก
 */
export function shapeCells(
  tool: 'line' | 'rect' | 'ellipse',
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  filled = false,
): number[] {
  const out = new Set<number>()
  const add = (x: number, y: number): void => {
    if (x < 0 || y < 0 || x >= width || y >= height) return
    out.add(y * width + x)
  }
  if (tool === 'line') {
    for (const [x, y] of bresenham(x0, y0, x1, y1)) add(x, y)
    return Array.from(out)
  }

  const left = Math.max(0, Math.min(x0, x1))
  const right = Math.min(width - 1, Math.max(x0, x1))
  const top = Math.max(0, Math.min(y0, y1))
  const bottom = Math.min(height - 1, Math.max(y0, y1))

  if (tool === 'rect') {
    for (let y = top; y <= bottom; y += 1) {
      for (let x = left; x <= right; x += 1) {
        if (filled || x === left || x === right || y === top || y === bottom) add(x, y)
      }
    }
    return Array.from(out)
  }

  const cx = (left + right) / 2
  const cy = (top + bottom) / 2
  const rx = Math.max(0.5, (right - left) / 2)
  const ry = Math.max(0.5, (bottom - top) / 2)
  for (let y = top; y <= bottom; y += 1) {
    const dy = (y - cy) / ry
    if (Math.abs(dy) > 1) continue
    const dx = rx * Math.sqrt(Math.max(0, 1 - dy * dy))
    const lo = Math.round(cx - dx)
    const hi = Math.round(cx + dx)
    if (filled) {
      for (let x = lo; x <= hi; x += 1) add(x, y)
    } else {
      add(lo, y)
      add(hi, y)
    }
  }
  return Array.from(out)
}

export function drawEllipse(
  editor: GridEditor,
  width: number,
  height: number,
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  value: number,
  filled: boolean,
): void {
  const left = Math.min(x0, x1)
  const right = Math.max(x0, x1)
  const top = Math.min(y0, y1)
  const bottom = Math.max(y0, y1)
  const cx = (left + right) / 2
  const cy = (top + bottom) / 2
  const rx = Math.max(0.5, (right - left) / 2)
  const ry = Math.max(0.5, (bottom - top) / 2)
  for (let y = Math.max(0, top); y <= Math.min(height - 1, bottom); y += 1) {
    const dy = (y - cy) / ry
    if (Math.abs(dy) > 1) continue
    const dx = rx * Math.sqrt(Math.max(0, 1 - dy * dy))
    const lo = Math.round(cx - dx)
    const hi = Math.round(cx + dx)
    if (filled) {
      for (let x = Math.max(0, lo); x <= Math.min(width - 1, hi); x += 1) {
        editor.setXY(x, y, width, height, value)
      }
    } else {
      editor.setXY(lo, y, width, height, value)
      editor.setXY(hi, y, width, height, value)
    }
  }
  if (!filled) {
    // ปิดช่องว่างหัว/ท้ายที่การไล่ตามแถวอาจทิ้งไว้
    for (let x = Math.max(0, left); x <= Math.min(width - 1, right); x += 1) {
      const dx = (x - cx) / rx
      if (Math.abs(dx) > 1) continue
      const dy = ry * Math.sqrt(Math.max(0, 1 - dx * dx))
      editor.setXY(x, Math.round(cy - dy), width, height, value)
      editor.setXY(x, Math.round(cy + dy), width, height, value)
    }
  }
}

/** Flood fill 4 ทิศ — คืน transaction ที่ commit แล้ว (null = ไม่มีอะไรเปลี่ยน) */
export function floodFill(
  editor: GridEditor,
  width: number,
  height: number,
  startX: number,
  startY: number,
  value: number,
): GridChange | null {
  if (startX < 0 || startY < 0 || startX >= width || startY >= height) return null
  const grid = editor.grid
  const target = grid[startY * width + startX]!
  if (target === value) return null

  const stack: number[] = [startY * width + startX]
  const seen = new Uint8Array(grid.length)
  seen[stack[0]!] = 1
  while (stack.length > 0) {
    const index = stack.pop()!
    const x = index % width
    const y = (index - x) / width
    if (grid[index] !== target) continue
    editor.set(index, value)
    if (x > 0 && !seen[index - 1]) {
      seen[index - 1] = 1
      stack.push(index - 1)
    }
    if (x < width - 1 && !seen[index + 1]) {
      seen[index + 1] = 1
      stack.push(index + 1)
    }
    if (y > 0 && !seen[index - width]) {
      seen[index - width] = 1
      stack.push(index - width)
    }
    if (y < height - 1 && !seen[index + width]) {
      seen[index + width] = 1
      stack.push(index + width)
    }
  }
  return editor.commit()
}

/** ลบจุดเดี่ยวที่ไม่มีเพื่อนบ้านสีเดียวกันเลย (despeckle §8.7) */
export function despeckle(
  editor: GridEditor,
  width: number,
  height: number,
): GridChange | null {
  const src = editor.grid.slice()
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x
      const value = src[index]!
      if (value === EMPTY) continue
      let same = 0
      for (let dy = -1; dy <= 1 && same === 0; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
          if (dx === 0 && dy === 0) continue
          const nx = x + dx
          const ny = y + dy
          if (nx < 0 || ny < 0 || nx >= width || ny >= height) continue
          if (src[ny * width + nx] === value) {
            same += 1
            break
          }
        }
      }
      if (same === 0) editor.set(index, EMPTY)
    }
  }
  return editor.commit()
}

/** เลื่อนทั้งแผ่น (nudge) — คืน array ใหม่ ช่องที่หลุดขอบกลายเป็น EMPTY */
export function nudge(
  grid: Grid,
  width: number,
  height: number,
  dx: number,
  dy: number,
): Grid {
  const out = createGrid(width, height)
  for (let y = 0; y < height; y += 1) {
    const ny = y + dy
    if (ny < 0 || ny >= height) continue
    for (let x = 0; x < width; x += 1) {
      const nx = x + dx
      if (nx < 0 || nx >= width) continue
      out[ny * width + nx] = grid[y * width + x]!
    }
  }
  return out
}

/** ปรับขนาดแบบ top-left anchor (ตรงกับ `crop_or_pad_grid` ฝั่ง backend) */
export function cropOrPad(
  grid: Grid,
  oldWidth: number,
  oldHeight: number,
  newWidth: number,
  newHeight: number,
): Grid {
  const out = createGrid(newWidth, newHeight)
  const w = Math.min(oldWidth, newWidth)
  const h = Math.min(oldHeight, newHeight)
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      out[y * newWidth + x] = grid[y * oldWidth + x]!
    }
  }
  return out
}

// ── region / clipboard ────────────────────────────────────────────

export interface Region {
  x: number
  y: number
  w: number
  h: number
}

/** สร้าง region จากจุดสองจุด (คลิก/ลาก) — คืน null ถ้าอยู่นอกกริดทั้งหมด */
export function normalizeRegion(
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  width: number,
  height: number,
): Region | null {
  const left = Math.max(0, Math.min(x0, x1))
  const right = Math.min(width - 1, Math.max(x0, x1))
  const top = Math.max(0, Math.min(y0, y1))
  const bottom = Math.min(height - 1, Math.max(y0, y1))
  if (left > right || top > bottom) return null
  return { x: left, y: top, w: right - left + 1, h: bottom - top + 1 }
}

export function regionIndices(region: Region, width: number): number[] {
  const out: number[] = []
  for (let y = region.y; y < region.y + region.h; y += 1) {
    for (let x = region.x; x < region.x + region.w; x += 1) out.push(y * width + x)
  }
  return out
}

export function extractRegion(grid: Grid, width: number, region: Region): Int32Array {
  const values = new Int32Array(region.w * region.h)
  let i = 0
  for (let y = region.y; y < region.y + region.h; y += 1) {
    for (let x = region.x; x < region.x + region.w; x += 1) {
      values[i] = grid[y * width + x]!
      i += 1
    }
  }
  return values
}

/** วางค่าลง editor ที่ตำแหน่ง (originX, originY) — ช่องที่หลุดขอบถูกข้าม */
export function paintRegion(
  editor: GridEditor,
  width: number,
  height: number,
  originX: number,
  originY: number,
  source: Region,
  values: Int32Array,
): void {
  let i = 0
  for (let sy = 0; sy < source.h; sy += 1) {
    for (let sx = 0; sx < source.w; sx += 1) {
      editor.setXY(originX + sx, originY + sy, width, height, values[i]!)
      i += 1
    }
  }
}

/** เทียบ grid สองชุด → transaction (ใช้กับ move/import ที่แก้แบบไม่ผ่าน editor) */
export function diffGrids(before: Grid, after: Grid): GridChange | null {
  if (before.length !== after.length) return null
  const indices: number[] = []
  const beforeValues: number[] = []
  const afterValues: number[] = []
  for (let i = 0; i < before.length; i += 1) {
    if (before[i] !== after[i]) {
      indices.push(i)
      beforeValues.push(before[i]!)
      afterValues.push(after[i]!)
    }
  }
  if (indices.length === 0) return null
  return {
    indices: Int32Array.from(indices),
    before: Int32Array.from(beforeValues),
    after: Int32Array.from(afterValues),
  }
}

/** นับช่องต่อสี (ไม่รวม EMPTY) */
export function colorCounts(grid: Grid): Map<number, number> {
  const counts = new Map<number, number>()
  for (let i = 0; i < grid.length; i += 1) {
    const v = grid[i]!
    if (v === EMPTY) continue
    counts.set(v, (counts.get(v) ?? 0) + 1)
  }
  return counts
}

export function filledCount(grid: Grid): number {
  let n = 0
  for (let i = 0; i < grid.length; i += 1) if (grid[i] !== EMPTY) n += 1
  return n
}
