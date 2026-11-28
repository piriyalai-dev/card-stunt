/**
 * 🧵 Quantize worker — ย้ายงาน CPU หนัก (ปรับแสง/quantize/despeckle) ออกจาก main thread
 * ⇒ ตอนแปลงรูปเป็นพิกเซล UI ไม่กระตุก (P6)
 *
 * รับ `Uint8ClampedArray` (ภาพที่ draw ลง canvas ขนาด grid แล้ว) + พารามิเตอร์
 * คืน `Grid` (Int32Array, transferable) — งานทั้งหมดเป็น pure function จาก lib
 */
import { applyAdjustments, quantizeImage, type QuantColor, type QuantizeOptions } from '../lib/quantize'
import { GridEditor, despeckle, type Grid } from '../lib/grid'

interface QuantizeRequest {
  data: Uint8ClampedArray
  gw: number
  gh: number
  adjust: { brightness: number; contrast: number; saturation: number; sharpness: number }
  colors: QuantColor[]
  options: QuantizeOptions
  despeckleOn: boolean
}

interface QuantizeResult {
  grid?: Grid
  error?: string
}

self.onmessage = (event: MessageEvent<QuantizeRequest>) => {
  const { data, gw, gh, adjust, colors, options, despeckleOn } = event.data
  try {
    applyAdjustments(data, gw, gh, adjust)

    const grid = quantizeImage(data, gw, gh, colors, options)

    if (despeckleOn) {
      const editor = new GridEditor(grid)
      despeckle(editor, gw, gh)
      editor.commit()
    }

    const result: QuantizeResult = { grid }
    ;(self as unknown as Worker).postMessage(result, { transfer: [grid.buffer] })
  } catch (err) {
    const result: QuantizeResult = { error: err instanceof Error ? err.message : String(err) }
    ;(self as unknown as Worker).postMessage(result)
  }
}

export {}
