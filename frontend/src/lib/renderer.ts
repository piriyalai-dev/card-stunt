/**
 * 🖌 Canvas renderer — แปลง grid (Int32Array) เป็นภาพ 1 พิกเซลต่อ 1 ช่อง
 *
 * 🔴 **หัวใจของ performance:** 100,000 ช่อง (250×400) วาดเป็น `ImageData` ครั้งเดียว
 *    แล้ว `drawImage` ขยายด้วย `imageSmoothingEnabled = false` — ไม่ใช่ `fillRect` 100k ครั้ง
 *    ต่อเฟรม (design §8.8 "ห้าม v-for div พิกเซลหลายพันตัว" ใช้หลักเดียวกันกับ canvas)
 *
 * ⚠️ ไฟล์นี้แตะ DOM (HTMLCanvasElement/ImageData) — ไม่อยู่ในชุดเทสต์ pure
 */
import { EMPTY, type Grid } from './grid'
import { hexToRgb } from './color'
import { gridSize, type Geometry } from './geometry'

export type ColorLookup = ReadonlyMap<number, string>

export function lookupFromColors(
  colors: ReadonlyArray<{ id: number; hex: string }>,
): Map<number, string> {
  return new Map(colors.map((c) => [c.id, c.hex]))
}

/** RGB ของทุกสีใน palette (cache ต่อ lookup) */
const rgbCache = new WeakMap<ColorLookup, Map<number, [number, number, number]>>()

function rgbFor(lookup: ColorLookup, id: number): [number, number, number] | null {
  let cache = rgbCache.get(lookup)
  if (!cache) {
    cache = new Map()
    rgbCache.set(lookup, cache)
  }
  const hit = cache.get(id)
  if (hit) return hit
  const hex = lookup.get(id)
  if (!hex) return null
  const { r, g, b } = hexToRgb(hex)
  const rgb: [number, number, number] = [r, g, b]
  cache.set(id, rgb)
  return rgb
}

/**
 * สร้าง canvas ขนาด `width × height` (1 px = 1 ช่อง) — ช่องว่างโปร่งใส
 * ผู้เรียกเอา canvas นี้ไป `drawImage` ขยายต่อ (ด้วย smoothing ปิด)
 */
export function createGridCanvas(
  grid: Grid,
  width: number,
  height: number,
  lookup: ColorLookup,
): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return canvas

  const image = ctx.createImageData(width, height)
  const data = image.data
  for (let i = 0; i < grid.length; i += 1) {
    const value = grid[i]!
    if (value === EMPTY) continue
    const rgb = rgbFor(lookup, value)
    if (!rgb) continue
    const p = i * 4
    data[p] = rgb[0]
    data[p + 1] = rgb[1]
    data[p + 2] = rgb[2]
    data[p + 3] = 255
  }
  ctx.putImageData(image, 0, 0)
  return canvas
}

export interface ViewTransform {
  /** จุดซ้ายบนของกริดบน canvas (CSS px) */
  originX: number
  originY: number
  /** ขนาด 1 ช่อง (CSS px) */
  cellSize: number
}

/** แปลงพิกัดเมาส์ (CSS px ใน canvas) → ช่อง grid (อาจอยู่นอกกริด) */
export function pointToCell(
  x: number,
  y: number,
  transform: ViewTransform,
  width: number,
  height: number,
): { col: number; row: number; inside: boolean } {
  const col = Math.floor((x - transform.originX) / transform.cellSize)
  const row = Math.floor((y - transform.originY) / transform.cellSize)
  return { col, row, inside: col >= 0 && row >= 0 && col < width && row < height }
}

/** วาดเส้นกริดย่อย + เส้นขอบที่นั่ง — เรียกจาก StudioCanvas หลัง drawImage ภาพ */
export function drawGeometryOverlay(
  ctx: CanvasRenderingContext2D,
  transform: ViewTransform,
  geometry: Geometry,
  options: { showSubGrid: boolean; showSeatGrid: boolean },
): void {
  const { originX, originY, cellSize } = transform
  const { width, height } = gridSize(geometry)
  const right = originX + width * cellSize
  const bottom = originY + height * cellSize

  if (options.showSubGrid && cellSize >= 6) {
    ctx.strokeStyle = 'rgba(31,35,40,.10)'
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let c = 1; c < width; c += 1) {
      const x = Math.round(originX + c * cellSize) + 0.5
      ctx.moveTo(x, originY)
      ctx.lineTo(x, bottom)
    }
    for (let r = 1; r < height; r += 1) {
      const y = Math.round(originY + r * cellSize) + 0.5
      ctx.moveTo(originX, y)
      ctx.lineTo(right, y)
    }
    ctx.stroke()
  }

  if (options.showSeatGrid) {
    ctx.strokeStyle = 'rgba(31,35,40,.45)'
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let c = 0; c <= geometry.cols; c += 1) {
      const x = Math.round(originX + c * geometry.subCols * cellSize) + 0.5
      ctx.moveTo(x, originY)
      ctx.lineTo(x, bottom)
    }
    for (let r = 0; r <= geometry.rows; r += 1) {
      const y = Math.round(originY + r * geometry.subRows * cellSize) + 0.5
      ctx.moveTo(originX, y)
      ctx.lineTo(right, y)
    }
    ctx.stroke()
  }
}

/** ลายทแยงบนที่นั่งที่ถูกบล็อก (บันได/ทางเดิน) */
export function drawBlockedSeats(
  ctx: CanvasRenderingContext2D,
  transform: ViewTransform,
  geometry: Geometry,
  blocked: ReadonlySet<string>,
): void {
  if (blocked.size === 0) return
  const { originX, originY, cellSize } = transform
  const w = geometry.subCols * cellSize
  const h = geometry.subRows * cellSize
  ctx.save()
  ctx.fillStyle = 'rgba(31,35,40,.42)'
  for (const key of blocked) {
    const [rowText, colText] = key.split(',')
    const row = Number(rowText)
    const col = Number(colText)
    if (!Number.isInteger(row) || !Number.isInteger(col)) continue
    if (row < 0 || col < 0 || row >= geometry.rows || col >= geometry.cols) continue
    // ตำแหน่งใน grid — ใช้ seatBase logic แบบ inline (เลี่ยง throw ต่อช่อง)
    const gr =
      geometry.rowDirection === 'bottom_to_top'
        ? (geometry.rows - 1 - row) * geometry.subRows
        : row * geometry.subRows
    const gc =
      geometry.colDirection === 'left_to_right'
        ? col * geometry.subCols
        : (geometry.cols - 1 - col) * geometry.subCols
    const x = originX + gc * cellSize
    const y = originY + gr * cellSize
    ctx.fillRect(x, y, w, h)
  }
  ctx.restore()
}
