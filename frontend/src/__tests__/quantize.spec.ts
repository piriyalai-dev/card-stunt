import { describe, expect, it } from 'vitest'
import {
  DEFAULT_ADJUST,
  applyAdjustments,
  nearestColor,
  quantizeImage,
  type QuantColor,
} from '@/lib/quantize'
import { EMPTY } from '@/lib/grid'

const RED: QuantColor = { id: 10, hex: '#FF0000' }
const BLUE: QuantColor = { id: 20, hex: '#0000FF' }
const BLACK: QuantColor = { id: 1, hex: '#000000' }
const WHITE: QuantColor = { id: 2, hex: '#FFFFFF' }

function pixels(values: Array<[number, number, number, number?]>): Uint8ClampedArray {
  const data = new Uint8ClampedArray(values.length * 4)
  values.forEach(([r, g, b, a = 255], i) => {
    data[i * 4] = r
    data[i * 4 + 1] = g
    data[i * 4 + 2] = b
    data[i * 4 + 3] = a
  })
  return data
}

describe('quantizeImage', () => {
  it('จับคู่สีที่ใกล้ที่สุดใน CIELAB', () => {
    const data = pixels([
      [255, 0, 0],
      [0, 0, 255],
    ])
    const grid = quantizeImage(data, 2, 1, [RED, BLUE])
    expect(Array.from(grid)).toEqual([RED.id, BLUE.id])
  })

  it('ช่องโปร่งใส → EMPTY', () => {
    const data = pixels([[255, 0, 0, 0]])
    const grid = quantizeImage(data, 1, 1, [RED], { alphaThreshold: 16 })
    expect(grid[0]).toBe(EMPTY)
  })

  it('สีพื้นหลังที่กำหนด → EMPTY', () => {
    const data = pixels([[250, 250, 250]])
    const grid = quantizeImage(data, 1, 1, [WHITE], {
      backgroundColor: '#FFFFFF',
      backgroundTolerance: 10,
    })
    expect(grid[0]).toBe(EMPTY)
  })

  it('allowedIds จำกัดสีที่ใช้ได้', () => {
    const data = pixels([[255, 0, 0]])
    const grid = quantizeImage(data, 1, 1, [RED, BLUE], { allowedIds: new Set([BLUE.id]) })
    expect(grid[0]).toBe(BLUE.id)
  })

  it('palette ว่าง → grid ว่างทั้งหมด', () => {
    const grid = quantizeImage(pixels([[1, 2, 3]]), 1, 1, [])
    expect(grid[0]).toBe(EMPTY)
  })

  it('Floyd–Steinberg กระจายเฉดเทาระหว่างดำ/ขาว', () => {
    const width = 8
    const height = 8
    const data = pixels(Array.from({ length: width * height }, () => [128, 128, 128] as [number, number, number]))
    const none = quantizeImage(data, width, height, [BLACK, WHITE], { dither: 'none' })
    const dithered = quantizeImage(data, width, height, [BLACK, WHITE], {
      dither: 'floyd',
      ditherStrength: 1,
    })
    const uniqueNone = new Set(Array.from(none))
    const uniqueDithered = new Set(Array.from(dithered))
    expect(uniqueNone.size).toBe(1)
    expect(uniqueDithered.size).toBe(2)
  })

  it('Bayer เป็น deterministic (ผลซ้ำได้)', () => {
    const width = 4
    const height = 4
    const data = pixels(Array.from({ length: 16 }, () => [100, 100, 100] as [number, number, number]))
    const a = quantizeImage(data, width, height, [BLACK, WHITE], { dither: 'bayer', ditherStrength: 1 })
    const b = quantizeImage(data, width, height, [BLACK, WHITE], { dither: 'bayer', ditherStrength: 1 })
    expect(Array.from(a)).toEqual(Array.from(b))
  })
})

describe('สเกลจริงของแสตน (Phase 4 gate)', () => {
  it('แปลง 250×400 = 100,000 ช่อง ด้วย 12 สีได้ภายในเวลาที่รับได้', () => {
    const width = 400
    const height = 250
    const palette: QuantColor[] = Array.from({ length: 12 }, (_, i) => ({
      id: i + 1,
      hex: `#${((i * 21) % 256).toString(16).padStart(2, '0')}${((i * 57) % 256)
        .toString(16)
        .padStart(2, '0')}${((i * 103) % 256).toString(16).padStart(2, '0')}`.toUpperCase(),
    }))
    const data = new Uint8ClampedArray(width * height * 4)
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const i = (y * width + x) * 4
        data[i] = (x * 255) / width
        data[i + 1] = (y * 255) / height
        data[i + 2] = ((x + y) * 255) / (width + height)
        data[i + 3] = 255
      }
    }
    const start = performance.now()
    const grid = quantizeImage(data, width, height, palette, { dither: 'floyd', ditherStrength: 0.5 })
    const elapsed = performance.now() - start

    expect(grid.length).toBe(100000)
    expect(Array.from(grid).every((v) => v !== EMPTY)).toBe(true)
    expect(elapsed).toBeLessThan(5000)
  })
})

describe('applyAdjustments', () => {
  it('brightness เพิ่มค่าทุกช่องสี', () => {
    const data = pixels([[100, 100, 100]])
    applyAdjustments(data, 1, 1, { ...DEFAULT_ADJUST, brightness: 20 })
    expect(data[0]!).toBeGreaterThan(100)
    expect(data[1]!).toBeGreaterThan(100)
  })

  it('contrast ดันค่าสว่างขึ้นและค่ามืดลง', () => {
    const data = pixels([
      [200, 200, 200],
      [50, 50, 50],
    ])
    applyAdjustments(data, 2, 1, { ...DEFAULT_ADJUST, contrast: 30 })
    expect(data[0]!).toBeGreaterThan(200)
    expect(data[4]!).toBeLessThan(50)
  })

  it('saturation -100 ทำให้เป็นเทา', () => {
    const data = pixels([[200, 50, 20]])
    applyAdjustments(data, 1, 1, { ...DEFAULT_ADJUST, saturation: -100 })
    expect(data[0]!).toBe(data[1]!)
    expect(data[1]!).toBe(data[2]!)
  })

  it('sharpness ไม่เปลี่ยนขนาดข้อมูลหรือ alpha', () => {
    const data = pixels([
      [10, 10, 10],
      [200, 200, 200],
      [10, 10, 10],
      [10, 10, 10],
      [200, 200, 200],
      [10, 10, 10],
    ])
    const before = data.length
    applyAdjustments(data, 3, 2, { ...DEFAULT_ADJUST, sharpness: 80 })
    expect(data.length).toBe(before)
    for (let i = 3; i < data.length; i += 4) expect(data[i]).toBe(255)
  })
})

describe('nearestColor', () => {
  it('เลือกสีใกล้สุด', () => {
    expect(nearestColor('#FE0101', [RED, BLUE])?.id).toBe(RED.id)
    expect(nearestColor('#F5F5F5', [BLACK, WHITE])?.id).toBe(WHITE.id)
  })
})
