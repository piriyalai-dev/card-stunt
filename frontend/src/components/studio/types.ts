/** เหตุการณ์ pointer จาก `StudioCanvas` — พิกัดเป็นช่อง grid (0-based, อาจอยู่นอกกริด) */
export interface CanvasCellEvent {
  x: number
  y: number
  inside: boolean
  altKey: boolean
  shiftKey: boolean
}
