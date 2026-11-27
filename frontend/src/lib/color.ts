/**
 * 🎨 สีสำหรับ Image-to-Pixel — conversion + WCAG contrast + CIELAB / CIEDE2000
 *
 * ทำไมต้อง CIELAB ไม่ใช่ระยะ RGB ตรง ๆ: RGB distance ไม่ตรงกับที่ตาคนเห็น
 * (เขียวสว่างกับเหลืองหม่นอาจใกล้กันใน RGB แต่คนละสีชัดเจน) ⇒ พิกเซลจะถูกจับคู่สีผิด
 * ทั้งที่ palette มีสีที่ถูกต้องอยู่แล้ว — ดู design report §8.7
 *
 * ⚠️ ไฟล์นี้เป็น **pure** ทั้งหมด (ไม่มี DOM) ⇒ เทสต์ได้ใน vitest/jsdom
 */

export interface Rgb {
  r: number
  g: number
  b: number
}

export type Lab = [number, number, number]

const clamp255 = (v: number): number => (v < 0 ? 0 : v > 255 ? 255 : Math.round(v))
const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v)

export function hexToRgb(hex: string): Rgb {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim())
  if (!m) return { r: 0, g: 0, b: 0 }
  const n = parseInt(m[1]!, 16)
  return { r: (n >> 16) & 0xff, g: (n >> 8) & 0xff, b: n & 0xff }
}

export function rgbToHex({ r, g, b }: Rgb): string {
  const hex = ((clamp255(r) << 16) | (clamp255(g) << 8) | clamp255(b)).toString(16)
  return `#${hex.padStart(6, '0').toUpperCase()}`
}

export function isValidHex(hex: string): boolean {
  return /^#?[0-9a-f]{6}$/i.test(hex.trim())
}

/** คืน `#RRGGBB` ตัวพิมพ์ใหญ่ — คืน null ถ้าไม่ใช่ hex 6 หลัก */
export function normalizeHex(hex: string): string | null {
  if (!isValidHex(hex)) return null
  return rgbToHex(hexToRgb(hex))
}

/** SRGB (0–255) → linear (0–1) ตาม WCAG 2.x */
export function srgbToLinear(channel: number): number {
  const c = channel / 255
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
}

/** relative luminance ตาม WCAG — ใช้คิด contrast ratio */
export function relativeLuminance({ r, g, b }: Rgb): number {
  return 0.2126 * srgbToLinear(r) + 0.7152 * srgbToLinear(g) + 0.0722 * srgbToLinear(b)
}

export function contrastRatio(a: Rgb, b: Rgb): number {
  const la = relativeLuminance(a)
  const lb = relativeLuminance(b)
  const hi = Math.max(la, lb)
  const lo = Math.min(la, lb)
  return (hi + 0.05) / (lo + 0.05)
}

/**
 * สีตัวอักษรที่อ่านง่ายที่สุดบนพื้น `hex` — ขาวหรือดำ
 * (ใช้กับ `palette_colors.text_color` ตอนผู้ใช้ยังไม่แก้เอง)
 */
export function autoTextColor(hex: string): string {
  const bg = hexToRgb(hex)
  const white = contrastRatio(bg, { r: 255, g: 255, b: 255 })
  const black = contrastRatio(bg, { r: 0, g: 0, b: 0 })
  return white >= black ? '#FFFFFF' : '#000000'
}

/** RGB → CIE XYZ (D65) */
export function rgbToXyz({ r, g, b }: Rgb): [number, number, number] {
  const rl = srgbToLinear(r)
  const gl = srgbToLinear(g)
  const bl = srgbToLinear(b)
  return [
    (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) * 100,
    (rl * 0.2126729 + gl * 0.7151522 + bl * 0.072175) * 100,
    (rl * 0.0193339 + gl * 0.119192 + bl * 0.9503041) * 100,
  ]
}

const WHITE_D65: [number, number, number] = [95.047, 100.0, 108.883]

function labF(t: number): number {
  return t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116
}

/** RGB → CIELAB (D65) */
export function rgbToLab(rgb: Rgb): Lab {
  const [x, y, z] = rgbToXyz(rgb)
  const fx = labF(x / WHITE_D65[0])
  const fy = labF(y / WHITE_D65[1])
  const fz = labF(z / WHITE_D65[2])
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)]
}

/** CIE76 — เร็ว แต่ไม่ค่อยตรงกับสายตามนุษย์ในทุกช่วงสี */
export function deltaE76(a: Lab, b: Lab): number {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])
}

const RAD = Math.PI / 180

/** CIEDE2000 — ใช้เป็นค่าเริ่มต้น (design §8.7) */
export function deltaE2000(a: Lab, b: Lab): number {
  const [L1, a1, b1] = a
  const [L2, a2, b2] = b

  const C1 = Math.hypot(a1, b1)
  const C2 = Math.hypot(a2, b2)
  const Cbar = (C1 + C2) / 2
  const Cbar7 = Cbar ** 7
  const G = 0.5 * (1 - Math.sqrt(Cbar7 / (Cbar7 + 25 ** 7)))

  const a1p = (1 + G) * a1
  const a2p = (1 + G) * a2
  const C1p = Math.hypot(a1p, b1)
  const C2p = Math.hypot(a2p, b2)

  const h1p = hueDegrees(b1, a1p)
  const h2p = hueDegrees(b2, a2p)

  const dLp = L2 - L1
  const dCp = C2p - C1p
  const dhpRaw = h2p - h1p
  let dhp = 0
  if (C1p * C2p === 0) dhp = 0
  else if (Math.abs(dhpRaw) <= 180) dhp = dhpRaw
  else if (dhpRaw > 180) dhp = dhpRaw - 360
  else dhp = dhpRaw + 360
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dhp * RAD) / 2)

  const Lbarp = (L1 + L2) / 2
  const Cbarp = (C1p + C2p) / 2
  const hbarp = meanHue(h1p, h2p, C1p, C2p)

  const T =
    1 -
    0.17 * Math.cos((hbarp - 30) * RAD) +
    0.24 * Math.cos(2 * hbarp * RAD) +
    0.32 * Math.cos((3 * hbarp + 6) * RAD) -
    0.2 * Math.cos((4 * hbarp - 63) * RAD)

  const Sl = 1 + (0.015 * (Lbarp - 50) ** 2) / Math.sqrt(20 + (Lbarp - 50) ** 2)
  const Sc = 1 + 0.045 * Cbarp
  const Sh = 1 + 0.015 * Cbarp * T

  const dTheta = 30 * Math.exp(-(((hbarp - 275) / 25) ** 2))
  const Cbarp7 = Cbarp ** 7
  const Rc = 2 * Math.sqrt(Cbarp7 / (Cbarp7 + 25 ** 7))
  const Rt = -Math.sin(2 * dTheta * RAD) * Rc

  const tL = dLp / Sl
  const tC = dCp / Sc
  const tH = dHp / Sh
  return Math.sqrt(tL * tL + tC * tC + tH * tH + Rt * tC * tH)
}

function hueDegrees(b: number, ap: number): number {
  if (b === 0 && ap === 0) return 0
  const deg = Math.atan2(b, ap) / RAD
  return deg < 0 ? deg + 360 : deg
}

function meanHue(h1: number, h2: number, c1: number, c2: number): number {
  if (c1 * c2 === 0) return h1 + h2
  if (Math.abs(h1 - h2) <= 180) return (h1 + h2) / 2
  if (h1 + h2 < 360) return (h1 + h2 + 360) / 2
  return (h1 + h2 - 360) / 2
}

/** ผสมสีตามสัดส่วน (0–1) */
export function mixRgb(a: Rgb, b: Rgb, t: number): Rgb {
  const k = clamp01(t)
  return {
    r: clamp255(a.r + (b.r - a.r) * k),
    g: clamp255(a.g + (b.g - a.g) * k),
    b: clamp255(a.b + (b.b - a.b) * k),
  }
}
