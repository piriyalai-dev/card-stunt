/**
 * ✂️ คณิตศาสตร์ของ crop frame แบบ "cover" — ใช้ทั้งหน้า preview และตอนแปลงจริง
 *
 * Frame มีอัตราส่วนล็อกกับแสตน: `(gridW · seatAspect) : gridH` (design §8.7)
 * ผู้ใช้ซูม/เลื่อนรูป *ข้างหลัง* frame ⇒ ภาพที่เห็นใน frame คือภาพที่ถูกแปลงเป๊ะ ๆ
 * (คำนวณ source rect เดียวกันทั้งสองทาง)
 *
 * ⚠️ pure — เทสต์ใน vitest ได้โดยไม่ต้องมี canvas
 */

export interface CoverLayout {
  /** px ต่อ source px */
  scale: number
  drawW: number
  drawH: number
  /** ตำแหน่งซ้ายบนของรูปบน frame (CSS px) */
  x: number
  y: number
}

export interface SourceRect {
  sx: number
  sy: number
  sw: number
  sh: number
}

/** อัตราส่วน frame = (gridW · seatAspect) / gridH */
export function frameAspect(gridWidth: number, gridHeight: number, seatAspect: number): number {
  if (gridHeight <= 0) return 1
  const aspect = (gridWidth * Math.max(0.01, seatAspect)) / gridHeight
  return Number.isFinite(aspect) && aspect > 0 ? aspect : 1
}

/**
 * คำนวณ layout แบบ cover + clamp offset ไม่ให้มีช่องว่างใน frame
 *
 * @param zoom 1 = พอดี frame (cover) · >1 = ขยาย
 * @param offsetX/offsetY การเลื่อนจากกึ่งกลาง (px ของ frame)
 */
export function coverLayout(
  srcW: number,
  srcH: number,
  frameW: number,
  frameH: number,
  zoom: number,
  offsetX: number,
  offsetY: number,
): CoverLayout {
  const safeZoom = Math.max(1, Number.isFinite(zoom) ? zoom : 1)
  const baseScale = Math.max(frameW / Math.max(1, srcW), frameH / Math.max(1, srcH))
  const scale = baseScale * safeZoom
  const drawW = srcW * scale
  const drawH = srcH * scale
  const maxX = Math.max(0, (drawW - frameW) / 2)
  const maxY = Math.max(0, (drawH - frameH) / 2)
  const ox = Math.min(maxX, Math.max(-maxX, offsetX))
  const oy = Math.min(maxY, Math.max(-maxY, offsetY))
  return {
    scale,
    drawW,
    drawH,
    x: (frameW - drawW) / 2 + ox,
    y: (frameH - drawH) / 2 + oy,
  }
}

/** พื้นที่ของ source ที่โผล่ใน frame — ใช้ `drawImage(base, sx,sy,sw,sh, 0,0,gridW,gridH)` */
export function sourceRect(
  layout: CoverLayout,
  frameW: number,
  frameH: number,
  srcW: number,
  srcH: number,
): SourceRect {
  const sw = Math.min(srcW, frameW / layout.scale)
  const sh = Math.min(srcH, frameH / layout.scale)
  const sx = Math.min(Math.max(0, -layout.x / layout.scale), Math.max(0, srcW - sw))
  const sy = Math.min(Math.max(0, -layout.y / layout.scale), Math.max(0, srcH - sh))
  return { sx, sy, sw, sh }
}

/** หา frame ที่ใหญ่ที่สุดที่พอดีในกล่อง (คงอัตราส่วน) */
export function fitFrame(
  boxW: number,
  boxH: number,
  aspect: number,
): { width: number; height: number } {
  const safeAspect = aspect > 0 ? aspect : 1
  let width = boxW
  let height = width / safeAspect
  if (height > boxH) {
    height = boxH
    width = height * safeAspect
  }
  return { width: Math.max(1, Math.floor(width)), height: Math.max(1, Math.floor(height)) }
}
