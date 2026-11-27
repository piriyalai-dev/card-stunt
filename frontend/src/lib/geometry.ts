/**
 * 🧭 Coordinate Convention ฝั่ง frontend — **ต้องตรงกับ `backend/core/grid.py` ทุกบรรทัด**
 *
 * แสตนจริง = `cols` ที่นั่ง × `rows` แถว · แต่ละคนถือเพลท `sub_rows × sub_cols`
 * ⇒ กริดรวม = `(cols·sub_cols) × (rows·sub_rows)`
 *
 * `grid_data` เป็น **row-major flat array** ใน Audience View:
 * - `r = 0` = แถวบนสุดเมื่อมองจากสนาม
 * - `c = 0` = คอลัมน์ซ้ายสุด
 * - ทิศทาง (`row_direction`/`col_direction`) เป็นตัวแมป "แถว/ที่นั่งจริง" ลงไปในกริด
 *
 * ⚠️ พิกัดในไฟล์นี้ **0-based หมด** · ป้ายที่ผู้ใช้เห็นเป็น 1-based
 *   (backend ใช้กฎเดียวกัน — ถ้าแก้ที่นี่ให้แก้ `core/grid.py` ด้วย)
 */
import type { ColDirection, LabelStyle, RowDirection, StandOut } from '@/types/domain'

export interface Geometry {
  rows: number
  cols: number
  subRows: number
  subCols: number
  rowDirection: RowDirection
  colDirection: ColDirection
}

export interface LabelStyleSpec {
  rowStyle: LabelStyle
  colStyle: LabelStyle
  rowPrefix: string
  colPrefix: string
}

export interface SeatRef {
  seatRow: number
  seatCol: number
  subRow: number
  subCol: number
}

/** แปลง `StandOut` → geometry ที่ฟังก์ชันในไฟล์นี้กินได้ */
export function geometryOf(stand: StandOut): Geometry {
  return {
    rows: stand.rows,
    cols: stand.cols,
    subRows: stand.sub_rows,
    subCols: stand.sub_cols,
    rowDirection: stand.row_direction,
    colDirection: stand.col_direction,
  }
}

export function labelStyleOf(stand: StandOut): LabelStyleSpec {
  return {
    rowStyle: stand.row_label_style,
    colStyle: stand.col_label_style,
    rowPrefix: stand.row_label_prefix,
    colPrefix: stand.col_label_prefix,
  }
}

/** ขนาดกริดรวม (จำนวนช่องพิกเซล) */
export function gridSize(g: Pick<Geometry, 'rows' | 'cols' | 'subRows' | 'subCols'>): {
  width: number
  height: number
} {
  return { width: g.cols * g.subCols, height: g.rows * g.subRows }
}

/** มุมบนซ้าย `(gridRow, gridCol)` ของเพลทที่นั่งนั้น — 0-based */
export function seatBase(
  seatRow: number,
  seatCol: number,
  g: Geometry,
): { row: number; col: number } {
  if (seatRow < 0 || seatRow >= g.rows || seatCol < 0 || seatCol >= g.cols) {
    throw new RangeError('พิกัดที่นั่งอยู่นอกแสตน')
  }
  const row =
    g.rowDirection === 'bottom_to_top'
      ? (g.rows - 1 - seatRow) * g.subRows
      : seatRow * g.subRows
  const col =
    g.colDirection === 'left_to_right'
      ? seatCol * g.subCols
      : (g.cols - 1 - seatCol) * g.subCols
  return { row, col }
}

/** แปลงพิกัด pixel กลับเป็นที่นั่ง + ช่องย่อยภายในเพลท */
export function cellToSeat(gridRow: number, gridCol: number, g: Geometry): SeatRef {
  const width = g.cols * g.subCols
  const height = g.rows * g.subRows
  if (gridRow < 0 || gridRow >= height || gridCol < 0 || gridCol >= width) {
    throw new RangeError('พิกัด pixel อยู่นอกกริด')
  }
  const seatRow =
    g.rowDirection === 'bottom_to_top'
      ? g.rows - 1 - Math.floor(gridRow / g.subRows)
      : Math.floor(gridRow / g.subRows)
  const seatCol =
    g.colDirection === 'left_to_right'
      ? Math.floor(gridCol / g.subCols)
      : g.cols - 1 - Math.floor(gridCol / g.subCols)
  return {
    seatRow,
    seatCol,
    subRow: gridRow % g.subRows,
    subCol: gridCol % g.subCols,
  }
}

/** 0 → A, 25 → Z, 26 → AA … (เหมือน `_alpha` ฝั่ง backend) */
export function alphaLabel(index: number): string {
  let n = index + 1
  let out = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    out = String.fromCharCode(65 + rem) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}

/** ป้ายแถว/ที่นั่ง (1-based) ตามสไตล์ที่ตั้งไว้ */
export function seatLabels(
  seatRow: number,
  seatCol: number,
  style: LabelStyleSpec,
): { row: string; col: string } {
  const row =
    style.rowStyle === 'alpha'
      ? style.rowPrefix + alphaLabel(seatRow)
      : style.rowPrefix + String(seatRow + 1)
  const col =
    style.colStyle === 'alpha'
      ? style.colPrefix + alphaLabel(seatCol)
      : style.colPrefix + String(seatCol + 1)
  return { row, col }
}

/** ทำให้ blocked seats อยู่ในรูป `{row, col}` 0-based ไม่ซ้ำ และเรียงแล้ว */
export function normalizeBlocked(
  items: ReadonlyArray<{ row: number; col: number }>,
): Array<{ row: number; col: number }> {
  const seen = new Set<string>()
  const out: Array<{ row: number; col: number }> = []
  for (const item of items) {
    const key = `${item.row},${item.col}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ row: item.row, col: item.col })
  }
  return out.sort((a, b) => a.row - b.row || a.col - b.col)
}

export function blockedKeys(items: ReadonlyArray<{ row: number; col: number }>): Set<string> {
  return new Set(items.map((s) => `${s.row},${s.col}`))
}

export function isBlockedKey(row: number, col: number, keys: ReadonlySet<string>): boolean {
  return keys.has(`${row},${col}`)
}

/** เช็คว่าที่นั่งนี้ควรถูกล็อก (เพลททับช่องที่ถูกมาร์ก) */
export function isSeatBlocked(
  seatRow: number,
  seatCol: number,
  blocked: ReadonlySet<string>,
): boolean {
  return blocked.has(`${seatRow},${seatCol}`)
}
