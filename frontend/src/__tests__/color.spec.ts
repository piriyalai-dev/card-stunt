import { describe, expect, it } from 'vitest'
import {
  autoTextColor,
  contrastRatio,
  deltaE2000,
  deltaE76,
  hexToRgb,
  isValidHex,
  rgbToHex,
  rgbToLab,
  type Lab,
} from '@/lib/color'

describe('hex ↔ rgb', () => {
  it('ไปกลับได้', () => {
    expect(rgbToHex(hexToRgb('#B91C1C'))).toBe('#B91C1C')
    expect(rgbToHex(hexToRgb('15803d'))).toBe('#15803D')
  })

  it('hex เสีย → ดำ (ไม่ throw)', () => {
    expect(hexToRgb('nope')).toEqual({ r: 0, g: 0, b: 0 })
    expect(isValidHex('#12345')).toBe(false)
    expect(isValidHex('#123456')).toBe(true)
  })
})

describe('WCAG contrast', () => {
  it('ดำ–ขาว = 21:1', () => {
    expect(contrastRatio({ r: 0, g: 0, b: 0 }, { r: 255, g: 255, b: 255 })).toBeCloseTo(21, 0)
  })

  it('autoTextColor เลือกฝั่งที่ตัดกันมากกว่า', () => {
    expect(autoTextColor('#FFFFFF')).toBe('#000000')
    expect(autoTextColor('#000000')).toBe('#FFFFFF')
    expect(autoTextColor('#B91C1C')).toBe('#FFFFFF')
    expect(autoTextColor('#FFE08A')).toBe('#000000')
  })
})

describe('CIELAB / Delta-E', () => {
  it('ขาวได้ L≈100 และ chroma≈0', () => {
    const [l, a, b] = rgbToLab({ r: 255, g: 255, b: 255 })
    expect(l).toBeCloseTo(100, 1)
    expect(a).toBeCloseTo(0, 1)
    expect(b).toBeCloseTo(0, 1)
  })

  it('สีเดียวกัน = 0', () => {
    const lab = rgbToLab({ r: 185, g: 28, b: 28 })
    expect(deltaE76(lab, lab)).toBe(0)
    expect(deltaE2000(lab, lab)).toBe(0)
  })

  it('ดำกับขาว ≈ 100', () => {
    const black = rgbToLab({ r: 0, g: 0, b: 0 })
    const white = rgbToLab({ r: 255, g: 255, b: 255 })
    expect(deltaE2000(black, white)).toBeCloseTo(100, 0)
  })

  it('แดงกับเขียวห่างกันมากกว่าแดงกับแดงเข้ม', () => {
    const red = rgbToLab({ r: 255, g: 0, b: 0 })
    const darkRed = rgbToLab({ r: 150, g: 0, b: 0 })
    const green = rgbToLab({ r: 0, g: 255, b: 0 })
    expect(deltaE2000(red, green)).toBeGreaterThan(deltaE2000(red, darkRed))
  })

  // ชุดอ้างอิง Sharma–Melgosa–Dalal (CIEDE2000) — คู่ที่ 1,2,3,4,7,9,13,16,21,23,25,26
  it.each([
    [[50, 2.6772, -79.7751], [50, 0, -82.7485], 2.0425],
    [[50, 3.1571, -77.2803], [50, 0, -82.7485], 2.8615],
    [[50, 2.8361, -74.02], [50, 0, -82.7485], 3.4412],
    [[50, -1.3802, -84.2814], [50, 0, -82.7485], 1.0],
    [[50, 0, 0], [50, -1, 2], 2.3669],
    [[50, 2.49, -0.001], [50, -2.49, 0.0009], 7.1792],
    [[50, -0.001, 2.49], [50, 0.0009, -2.49], 4.8045],
    [[50, 2.5, 0], [50, 0, -2.5], 4.3065],
    [[50, 2.5, 0], [50, 3.1736, 0.5854], 1.0],
    [[50, 2.5, 0], [50, 3.2592, 0.335], 1.0],
    [[60.2574, -34.0099, 36.2677], [60.4626, -34.1751, 39.4387], 1.2644],
    [[63.0109, -31.0961, -5.8663], [62.8187, -29.7946, -4.0864], 1.263],
  ] as Array<[Lab, Lab, number]>)('Sharma reference ΔE00', (a, b, expected) => {
    expect(deltaE2000(a, b)).toBeCloseTo(expected, 3)
  })
})
