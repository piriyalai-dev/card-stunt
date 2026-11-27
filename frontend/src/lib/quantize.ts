/**
 * 🖼 Image-to-Pixel engine — ปรับภาพ → จับคู่ palette (CIELAB/ΔE2000) → dither
 *
 * ทุกอย่างทำงานบน **เบราว์เซอร์** (design §8.7: "ไม่ส่งรูปไป backend ทุกครั้ง")
 * ตัว component แค่ย่อรูปให้ได้ขนาด grid → `getImageData` → เรียกฟังก์ชันในไฟล์นี้
 *
 * ⚠️ pure ทั้งไฟล์ (รับ `Uint8ClampedArray` ธรรมดา ไม่ผูกกับ `<canvas>`)
 *   ⇒ เทสต์ได้ด้วยข้อมูลสังเคราะห์ใน vitest
 */
import { deltaE2000, hexToRgb, rgbToLab, type Lab, type Rgb } from './color'
import { EMPTY, createGrid, type Grid } from './grid'

export interface QuantColor {
  id: number
  hex: string
}

export interface QuantEntry {
  id: number
  rgb: Rgb
  lab: Lab
}

export type DitherMode = 'none' | 'floyd' | 'bayer'

export interface AdjustOptions {
  /** -100 … 100 */
  brightness: number
  /** -100 … 100 */
  contrast: number
  /** -100 … 100 */
  saturation: number
  /** 0 … 100 — unsharp mask */
  sharpness: number
}

export interface QuantizeOptions {
  dither?: DitherMode
  /** 0 … 1 — ความแรงของ dither */
  ditherStrength?: number
  /** จำกัดสีที่ใช้ได้ (ผู้ใช้ปิดบางสีชั่วคราว) */
  allowedIds?: ReadonlySet<number> | null
  /** พิกเซลที่โปร่งใสกว่า threshold → ช่องว่าง */
  alphaThreshold?: number
  /** สีพื้นหลังที่ถือว่า "ว่าง" เช่น ขาว — null = ไม่ใช้ */
  backgroundColor?: string | null
  /** ΔE2000 ที่ยอมรับว่าตรงกับสีพื้นหลัง */
  backgroundTolerance?: number
}

export const DEFAULT_ADJUST: AdjustOptions = {
  brightness: 0,
  contrast: 0,
  saturation: 0,
  sharpness: 0,
}

export function buildQuantEntries(colors: ReadonlyArray<QuantColor>): QuantEntry[] {
  return colors.map((c) => {
    const rgb = hexToRgb(c.hex)
    return { id: c.id, rgb, lab: rgbToLab(rgb) }
  })
}

/**
 * ตัวหา "สีที่ใกล้ที่สุด" พร้อม cache 3D quantized RGB (5 บิต/ช่อง = 32³ ช่อง)
 *
 * ⚠️ cache ทำให้การลากสไลเดอร์ซ้ำ ๆ เร็วขึ้นมาก — รูปเดียวกัน/พาเลตเดียวกัน
 *   จะไม่ต้องคำนวณ ΔE2000 ใหม่ 100,000 ครั้งทุกเฟรม
 */
export class NearestFinder {
  private readonly cache = new Int16Array(32 * 32 * 32).fill(-1)

  constructor(private readonly entries: ReadonlyArray<QuantEntry>) {}

  get isEmpty(): boolean {
    return this.entries.length === 0
  }

  find(r: number, g: number, b: number): QuantEntry | null {
    if (this.entries.length === 0) return null
    if (this.entries.length === 1) return this.entries[0]!

    const key = ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3)
    const cached = this.cache[key]!
    if (cached >= 0) return this.entries[cached]!

    const lab = rgbToLab({ r, g, b })
    let best = 0
    let bestDistance = Number.POSITIVE_INFINITY
    for (let i = 0; i < this.entries.length; i += 1) {
      const d = deltaE2000(lab, this.entries[i]!.lab)
      if (d < bestDistance) {
        bestDistance = d
        best = i
      }
    }
    this.cache[key] = best
    return this.entries[best]!
  }
}

const BAYER_4 = [
  [0, 8, 2, 10],
  [12, 4, 14, 6],
  [3, 11, 1, 9],
  [15, 7, 13, 5],
] as const

const clamp255 = (v: number): number => (v < 0 ? 0 : v > 255 ? 255 : v)

/**
 * ปรับภาพในที่ (in-place) — เรียกก่อน quantize
 * ลำดับ: brightness → contrast → saturation → sharpness
 */
export function applyAdjustments(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  options: AdjustOptions,
): void {
  const { brightness, contrast, saturation, sharpness } = options
  const needsColor = brightness !== 0 || contrast !== 0 || saturation !== 0
  if (needsColor) {
    const shift = brightness * 2.55
    const c = contrast * 2.55
    const factor = (259 * (c + 255)) / (255 * (259 - c))
    const sat = 1 + saturation / 100
    for (let i = 0; i < data.length; i += 4) {
      if (data[i + 3]! < 128) continue
      let r = data[i]! + shift
      let g = data[i + 1]! + shift
      let b = data[i + 2]! + shift
      r = factor * (r - 128) + 128
      g = factor * (g - 128) + 128
      b = factor * (b - 128) + 128
      if (saturation !== 0) {
        const gray = 0.299 * r + 0.587 * g + 0.114 * b
        r = gray + (r - gray) * sat
        g = gray + (g - gray) * sat
        b = gray + (b - gray) * sat
      }
      data[i] = clamp255(Math.round(r))
      data[i + 1] = clamp255(Math.round(g))
      data[i + 2] = clamp255(Math.round(b))
    }
  }

  if (sharpness > 0 && width > 2 && height > 2) {
    const amount = sharpness / 50 // 0 … 2
    const src = data.slice()
    for (let y = 1; y < height - 1; y += 1) {
      for (let x = 1; x < width - 1; x += 1) {
        const i = (y * width + x) * 4
        if (src[i + 3]! < 128) continue
        for (let ch = 0; ch < 3; ch += 1) {
          let sum = 0
          for (let dy = -1; dy <= 1; dy += 1) {
            for (let dx = -1; dx <= 1; dx += 1) {
              if (dx === 0 && dy === 0) continue
              sum += src[((y + dy) * width + (x + dx)) * 4 + ch]!
            }
          }
          const avg = sum / 8
          const p = src[i + ch]!
          data[i + ch] = clamp255(Math.round(p + amount * (p - avg)))
        }
      }
    }
  }
}

export function quantizeImage(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  colors: ReadonlyArray<QuantColor>,
  options: QuantizeOptions = {},
): Grid {
  const allowed = options.allowedIds
  const usable = allowed ? colors.filter((c) => allowed.has(c.id)) : colors
  const finder = new NearestFinder(buildQuantEntries(usable))
  const grid = createGrid(width, height)
  if (finder.isEmpty) return grid

  const dither = options.dither ?? 'none'
  const strength = Math.min(1, Math.max(0, options.ditherStrength ?? 0.6))
  const alphaThreshold = options.alphaThreshold ?? 16
  const bgLab = options.backgroundColor ? rgbToLab(hexToRgb(options.backgroundColor)) : null
  const bgTolerance = options.backgroundTolerance ?? 10

  const isBackground = (r: number, g: number, b: number): boolean => {
    if (!bgLab) return false
    return deltaE2000(rgbToLab({ r, g, b }), bgLab) <= bgTolerance
  }

  if (dither === 'floyd') {
    const size = width * height
    const errR = new Float32Array(size)
    const errG = new Float32Array(size)
    const errB = new Float32Array(size)
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const p = y * width + x
        const i = p * 4
        if (data[i + 3]! < alphaThreshold) {
          grid[p] = EMPTY
          continue
        }
        const r = clamp255(data[i]! + errR[p]!)
        const g = clamp255(data[i + 1]! + errG[p]!)
        const b = clamp255(data[i + 2]! + errB[p]!)
        if (isBackground(r, g, b)) {
          grid[p] = EMPTY
          continue
        }
        const hit = finder.find(Math.round(r), Math.round(g), Math.round(b))
        if (!hit) {
          grid[p] = EMPTY
          continue
        }
        grid[p] = hit.id
        const eR = (r - hit.rgb.r) * strength
        const eG = (g - hit.rgb.g) * strength
        const eB = (b - hit.rgb.b) * strength
        diffuse(errR, errG, errB, width, height, x, y, eR, eG, eB)
      }
    }
    return grid
  }

  const offset = 40 * strength
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const p = y * width + x
      const i = p * 4
      if (data[i + 3]! < alphaThreshold) {
        grid[p] = EMPTY
        continue
      }
      let r = data[i]!
      let g = data[i + 1]!
      let b = data[i + 2]!
      if (dither === 'bayer') {
        const t = ((BAYER_4[y & 3]![x & 3]! + 0.5) / 16 - 0.5) * offset
        r = clamp255(r + t)
        g = clamp255(g + t)
        b = clamp255(b + t)
      }
      if (isBackground(r, g, b)) {
        grid[p] = EMPTY
        continue
      }
      const hit = finder.find(Math.round(r), Math.round(g), Math.round(b))
      grid[p] = hit ? hit.id : EMPTY
    }
  }
  return grid
}

function diffuse(
  errR: Float32Array,
  errG: Float32Array,
  errB: Float32Array,
  width: number,
  height: number,
  x: number,
  y: number,
  eR: number,
  eG: number,
  eB: number,
): void {
  const add = (nx: number, ny: number, f: number): void => {
    if (nx < 0 || ny < 0 || nx >= width || ny >= height) return
    const p = ny * width + nx
    errR[p] = errR[p]! + eR * f
    errG[p] = errG[p]! + eG * f
    errB[p] = errB[p]! + eB * f
  }
  add(x + 1, y, 7 / 16)
  add(x - 1, y + 1, 3 / 16)
  add(x, y + 1, 5 / 16)
  add(x + 1, y + 1, 1 / 16)
}

/** สีที่ใกล้ที่สุดใน palette สำหรับสีเดียว (ใช้กับ eyedropper/ตัวอย่างสี) */
export function nearestColor(
  hex: string,
  colors: ReadonlyArray<QuantColor>,
): QuantColor | null {
  if (colors.length === 0) return null
  const lab = rgbToLab(hexToRgb(hex))
  let best = colors[0]!
  let bestDistance = Number.POSITIVE_INFINITY
  for (const color of colors) {
    const d = deltaE2000(lab, rgbToLab(hexToRgb(color.hex)))
    if (d < bestDistance) {
      bestDistance = d
      best = color
    }
  }
  return best
}
