import { describe, expect, it } from 'vitest'
import { coverLayout, fitFrame, frameAspect, sourceRect } from '@/lib/crop'

describe('frameAspect', () => {
  it('คิดจาก grid × สัดส่วนเพลท', () => {
    // 165×45 grid, aspect 1 → 3.666…
    expect(frameAspect(165, 45, 1)).toBeCloseTo(165 / 45, 5)
    // aspect 1.5 ทำให้ frame กว้างขึ้น 1.5 เท่า
    expect(frameAspect(165, 45, 1.5)).toBeCloseTo((165 * 1.5) / 45, 5)
  })

  it('กันค่าผิดศูนย์', () => {
    expect(frameAspect(100, 0, 1)).toBe(1)
    expect(frameAspect(100, 50, 0)).toBeCloseTo(0.02, 5)
  })
})

describe('coverLayout', () => {
  it('zoom 1 ครอบ frame พอดีและจัดกึ่งกลาง', () => {
    // รูป 1000×500, frame 400×200 (aspect 2) → scale .4
    const layout = coverLayout(1000, 500, 400, 200, 1, 0, 0)
    expect(layout.scale).toBeCloseTo(0.4, 5)
    expect(layout.drawW).toBeCloseTo(400, 5)
    expect(layout.drawH).toBeCloseTo(200, 5)
    expect(layout.x).toBeCloseTo(0, 5)
    expect(layout.y).toBeCloseTo(0, 5)
  })

  it('รูปกว้างกว่าอัตราส่วน → เต็มสูงและล้นแนวนอน', () => {
    // รูป 1000×250 (aspect 4), frame 400×200 (aspect 2) → scale .8 → 800×200
    const layout = coverLayout(1000, 250, 400, 200, 1, 0, 0)
    expect(layout.drawH).toBeCloseTo(200, 5)
    expect(layout.drawW).toBeCloseTo(800, 5)
    expect(layout.x).toBeCloseTo(-200, 5)
  })

  it('clamp offset ไม่ให้มีช่องว่าง', () => {
    const layout = coverLayout(1000, 250, 400, 200, 1, 9999, -9999)
    expect(layout.x).toBeCloseTo(0, 5) // เลื่อนสุดขวา
    expect(layout.y).toBeCloseTo(0, 5) // ไม่มีที่ให้เลื่อนแนวตั้ง
  })

  it('zoom ขยายตามสัดส่วน', () => {
    const layout = coverLayout(1000, 500, 400, 200, 2, 0, 0)
    expect(layout.scale).toBeCloseTo(0.8, 5)
    expect(layout.drawW).toBeCloseTo(800, 5)
  })
})

describe('sourceRect', () => {
  it('zoom 1 เต็มภาพเมื่อ aspect ตรงกัน', () => {
    const layout = coverLayout(1000, 500, 400, 200, 1, 0, 0)
    expect(sourceRect(layout, 400, 200, 1000, 500)).toEqual({
      sx: 0,
      sy: 0,
      sw: 1000,
      sh: 500,
    })
  })

  it('ภาพกว้างเกิน → ครอปกลางแนวนอน', () => {
    const layout = coverLayout(1000, 250, 400, 200, 1, 0, 0)
    const rect = sourceRect(layout, 400, 200, 1000, 250)
    expect(rect.sx).toBeCloseTo(250, 5)
    expect(rect.sw).toBeCloseTo(500, 5)
    expect(rect.sy).toBeCloseTo(0, 5)
    expect(rect.sh).toBeCloseTo(250, 5)
  })

  it('เลื่อนขวาสุด → source เริ่มจาก 0 ภายในขอบ', () => {
    const layout = coverLayout(1000, 250, 400, 200, 1, 9999, 0)
    const rect = sourceRect(layout, 400, 200, 1000, 250)
    expect(rect.sx).toBeGreaterThanOrEqual(0)
    expect(rect.sx + rect.sw).toBeLessThanOrEqual(1000)
  })
})

describe('fitFrame', () => {
  it('พอดีกล่องเมื่อกล่องแคบ', () => {
    expect(fitFrame(400, 400, 2)).toEqual({ width: 400, height: 200 })
  })

  it('จำกัดด้วยความสูงเมื่อ frame สูง', () => {
    expect(fitFrame(400, 200, 1)).toEqual({ width: 200, height: 200 })
  })
})
