<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { BRAND } from '@/constants/brand'
import type { CanvasCellEvent } from '@/components/studio/types'
import type { Grid, Region } from '@/lib/grid'
import { seatLabels, type Geometry, type LabelStyleSpec } from '@/lib/geometry'
import { createGridCanvas, drawBlockedSeats, drawGeometryOverlay, pointToCell } from '@/lib/renderer'

/**
 * 🖼 Canvas หลายชั้นของ Pixel Studio
 *
 * ชั้นล่าง → บน: พื้นตารางหมากรุก / ภาพอ้างอิง / พิกเซลสี / กริด+ที่นั่ง / ช่องบล็อก / preview / hover
 *
 * ⚡ ภาพพิกเซลสร้างเป็น `ImageData` 1 px ต่อช่อง **ครั้งเดียวต่อ revision** แล้ว `drawImage`
 *   ขยายด้วย nearest-neighbor — 100,000 ช่อง (250×400) ยังลื่น
 */
const props = defineProps<{
  grid: Grid
  revision: number
  width: number
  height: number
  lookup: ReadonlyMap<number, string>
  geometry: Geometry
  labels: LabelStyleSpec
  blocked: ReadonlySet<string>
  showGrid: boolean
  distanceMode: boolean
  reference: CanvasImageSource | null
  showReference: boolean
  referenceOpacity: number
  preview: number[] | null
  previewHex: string | null
  selection: Region | null
}>()

const emit = defineEmits<{
  'cell-down': [event: CanvasCellEvent]
  'cell-move': [event: CanvasCellEvent]
  'cell-up': [event: CanvasCellEvent]
  hover: [{ x: number; y: number; inside: boolean } | null]
}>()

const wrap = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

const cssW = ref(1)
const cssH = ref(1)
const cellSize = ref(8)
const panX = ref(0)
const panY = ref(0)
const viewInitialized = ref(false)
const userAdjusted = ref(false)
const spacePressed = ref(false)
const panning = ref(false)
/** กำลังลากเครื่องมือวาดอยู่ — parent จะ redraw เองผ่าน revision ⇒ ไม่ต้องวาดซ้ำที่ hover */
const painting = ref(false)

let lastPointer = { x: 0, y: 0 }
let resizeObserver: ResizeObserver | null = null
let gridCanvas: HTMLCanvasElement | null = null
let gridCanvasRev = -1
let gridCanvasLookup: ReadonlyMap<number, string> | null = null

const transform = computed(() => ({
  originX: (cssW.value - props.width * cellSize.value) / 2 + panX.value,
  originY: (cssH.value - props.height * cellSize.value) / 2 + panY.value,
  cellSize: cellSize.value,
}))

// ── พื้นหลังหมากรุกสำหรับช่องว่าง ───────────────────────────────
let checkerPattern: CanvasPattern | null = null
let checkerForCtx: CanvasRenderingContext2D | null = null

function getChecker(ctx: CanvasRenderingContext2D): CanvasPattern | null {
  if (checkerForCtx === ctx && checkerPattern) return checkerPattern
  const tile = document.createElement('canvas')
  tile.width = 16
  tile.height = 16
  const tctx = tile.getContext('2d')
  if (!tctx) return null
  tctx.fillStyle = '#FFFFFF'
  tctx.fillRect(0, 0, 16, 16)
  tctx.fillStyle = '#F1F2F4'
  tctx.fillRect(0, 0, 8, 8)
  tctx.fillRect(8, 8, 8, 8)
  checkerPattern = ctx.createPattern(tile, 'repeat')
  checkerForCtx = ctx
  return checkerPattern
}

function fit() {
  if (props.width <= 0 || props.height <= 0) return
  const scale = Math.min(
    (cssW.value * 0.88) / props.width,
    (cssH.value * 0.88) / props.height,
  )
  cellSize.value = Math.min(40, Math.max(1, scale))
  panX.value = 0
  panY.value = 0
  userAdjusted.value = false
  viewInitialized.value = true
  draw()
}

function resize() {
  const el = wrap.value
  const c = canvas.value
  if (!el || !c) return
  const rect = el.getBoundingClientRect()
  if (rect.width < 2 || rect.height < 2) return
  cssW.value = rect.width
  cssH.value = rect.height
  const dpr = window.devicePixelRatio || 1
  c.width = Math.round(rect.width * dpr)
  c.height = Math.round(rect.height * dpr)
  c.style.width = `${rect.width}px`
  c.style.height = `${rect.height}px`
  if (!viewInitialized.value) fit()
  else draw()
}

function draw() {
  const c = canvas.value
  if (!c) return
  const ctx = c.getContext('2d')
  if (!ctx) return
  const dpr = window.devicePixelRatio || 1
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssW.value, cssH.value)

  const t = transform.value
  const gx = t.originX
  const gy = t.originY
  const gw = props.width * t.cellSize
  const gh = props.height * t.cellSize

  // พื้นหลังพื้นที่กริด
  const checker = getChecker(ctx)
  if (checker) {
    ctx.fillStyle = checker
    ctx.fillRect(gx, gy, gw, gh)
  } else {
    ctx.fillStyle = '#FFFFFF'
    ctx.fillRect(gx, gy, gw, gh)
  }

  // ชั้นภาพอ้างอิง (ใต้พิกเซล)
  if (props.showReference && props.reference) {
    ctx.save()
    ctx.globalAlpha = props.referenceOpacity
    ctx.imageSmoothingEnabled = true
    ctx.imageSmoothingQuality = 'high'
    ctx.drawImage(props.reference, gx, gy, gw, gh)
    ctx.restore()
  }

  // ชั้นพิกเซล — cache ต่อ revision
  if (!gridCanvas || gridCanvasRev !== props.revision || gridCanvasLookup !== props.lookup) {
    gridCanvas = createGridCanvas(props.grid, props.width, props.height, props.lookup)
    gridCanvasRev = props.revision
    gridCanvasLookup = props.lookup
  }
  ctx.save()
  ctx.imageSmoothingEnabled = false
  if (props.distanceMode) {
    ctx.filter = `blur(${Math.max(0.6, t.cellSize * 0.18)}px)`
  }
  ctx.drawImage(gridCanvas, gx, gy, gw, gh)
  ctx.filter = 'none'
  ctx.restore()

  if (props.distanceMode) return

  // กริด/ขอบที่นั่ง
  if (props.showGrid) {
    drawGeometryOverlay(ctx, t, props.geometry, {
      showSubGrid: t.cellSize >= 6,
      showSeatGrid: t.cellSize * props.geometry.subCols >= 8,
    })
    drawLabels(ctx, t)
  }

  // ช่องที่บล็อก
  drawBlockedSeats(ctx, t, props.geometry, props.blocked)

  // preview (เส้น/สี่เหลี่ยม/วงรี ระหว่างลาก)
  if (props.preview && props.preview.length > 0 && props.previewHex) {
    ctx.save()
    ctx.globalAlpha = 0.55
    ctx.fillStyle = props.previewHex
    for (const index of props.preview) {
      const x = index % props.width
      const y = (index - x) / props.width
      ctx.fillRect(
        gx + x * t.cellSize,
        gy + y * t.cellSize,
        Math.ceil(t.cellSize),
        Math.ceil(t.cellSize),
      )
    }
    ctx.restore()
  }

  // selection (marquee)
  if (props.selection) {
    const s = props.selection
    const sx = gx + s.x * t.cellSize
    const sy = gy + s.y * t.cellSize
    const sw = Math.max(1, s.w * t.cellSize)
    const sh = Math.max(1, s.h * t.cellSize)
    ctx.save()
    ctx.fillStyle = 'rgba(185,28,28,.08)'
    ctx.fillRect(sx, sy, sw, sh)
    ctx.strokeStyle = BRAND
    ctx.lineWidth = 1.5
    ctx.setLineDash([4, 3])
    ctx.strokeRect(Math.round(sx) + 0.5, Math.round(sy) + 0.5, sw, sh)
    ctx.restore()
  }

  //  hover
  if (hoverCell.value.inside) {
    ctx.strokeStyle = BRAND
    ctx.lineWidth = 1.5
    ctx.strokeRect(
      Math.round(gx + hoverCell.value.x * t.cellSize) + 0.5,
      Math.round(gy + hoverCell.value.y * t.cellSize) + 0.5,
      Math.ceil(t.cellSize),
      Math.ceil(t.cellSize),
    )
  }

  // ขอบกริด
  ctx.strokeStyle = 'rgba(31,35,40,.55)'
  ctx.lineWidth = 1
  ctx.strokeRect(Math.round(gx) + 0.5, Math.round(gy) + 0.5, Math.round(gw), Math.round(gh))
}

function drawLabels(
  ctx: CanvasRenderingContext2D,
  t: { originX: number; originY: number; cellSize: number },
) {
  const g = props.geometry
  const seatW = g.subCols * t.cellSize
  const seatH = g.subRows * t.cellSize
  const gx = t.originX
  const gy = t.originY
  ctx.save()
  ctx.font = '11px "Noto Sans Thai", Tahoma, sans-serif'
  ctx.fillStyle = '#5F6368'
  ctx.textBaseline = 'middle'
  if (seatH >= 18) {
    ctx.textAlign = 'right'
    for (let v = 0; v < g.rows; v += 1) {
      const seatRow = g.rowDirection === 'bottom_to_top' ? g.rows - 1 - v : v
      const label = seatLabels(seatRow, 0, props.labels).row
      ctx.fillText(label, gx - 6, gy + v * seatH + seatH / 2)
    }
  }
  if (seatW >= 18) {
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    for (let v = 0; v < g.cols; v += 1) {
      const seatCol = g.colDirection === 'left_to_right' ? v : g.cols - 1 - v
      const label = seatLabels(0, seatCol, props.labels).col
      ctx.fillText(label, gx + v * seatW + seatW / 2, gy - 4)
    }
  }
  ctx.restore()
}

// ── pointer ─────────────────────────────────────────────────────
const hoverCell = ref({ x: -1, y: -1, inside: false })

function toCell(event: PointerEvent): CanvasCellEvent {
  const c = canvas.value
  if (!c) return { x: -1, y: -1, inside: false, altKey: event.altKey, shiftKey: event.shiftKey }
  const rect = c.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const cell = pointToCell(x, y, transform.value, props.width, props.height)
  return {
    x: cell.col,
    y: cell.row,
    inside: cell.inside,
    altKey: event.altKey,
    shiftKey: event.shiftKey,
  }
}

function updateHover(event: PointerEvent) {
  const cell = toCell(event)
  hoverCell.value = { x: cell.x, y: cell.y, inside: cell.inside }
  emit('hover', cell.inside ? { x: cell.x, y: cell.y, inside: true } : null)
  if (!panning.value && !painting.value) draw()
}

function onPointerDown(event: PointerEvent) {
  if (event.button === 1 || spacePressed.value) {
    panning.value = true
    lastPointer = { x: event.clientX, y: event.clientY }
    canvas.value?.setPointerCapture(event.pointerId)
    event.preventDefault()
    return
  }
  if (event.button !== 0) return
  painting.value = true
  canvas.value?.setPointerCapture(event.pointerId)
  emit('cell-down', toCell(event))
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  if (panning.value) {
    panX.value += event.clientX - lastPointer.x
    panY.value += event.clientY - lastPointer.y
    lastPointer = { x: event.clientX, y: event.clientY }
    userAdjusted.value = true
    draw()
    return
  }
  updateHover(event)
  if (event.buttons & 1) emit('cell-move', toCell(event))
}

function onPointerUp(event: PointerEvent) {
  if (panning.value) {
    panning.value = false
    return
  }
  painting.value = false
  emit('cell-up', toCell(event))
  draw()
}

function onPointerLeave(event: PointerEvent) {
  if (panning.value) return
  painting.value = false
  hoverCell.value = { x: -1, y: -1, inside: false }
  emit('hover', null)
  if (event.buttons & 1) emit('cell-up', toCell(event))
  draw()
}

function onWheel(event: WheelEvent) {
  if (!(event.ctrlKey || event.metaKey)) return
  event.preventDefault()
  const c = canvas.value
  if (!c) return
  const rect = c.getBoundingClientRect()
  const mx = event.clientX - rect.left
  const my = event.clientY - rect.top
  const t = transform.value
  const cx = (mx - t.originX) / t.cellSize
  const cy = (my - t.originY) / t.cellSize
  const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15
  const next = Math.min(48, Math.max(0.5, t.cellSize * factor))
  // รักษาจุดใต้ cursor ให้อยู่ที่เดิม
  const newOriginX = mx - cx * next
  const newOriginY = my - cy * next
  cellSize.value = next
  panX.value = newOriginX - (cssW.value - props.width * next) / 2
  panY.value = newOriginY - (cssH.value - props.height * next) / 2
  userAdjusted.value = true
  draw()
}

function zoomBy(factor: number) {
  const cx = cssW.value / 2
  const cy = cssH.value / 2
  const t = transform.value
  const gx = (cx - t.originX) / t.cellSize
  const gy = (cy - t.originY) / t.cellSize
  const next = Math.min(48, Math.max(0.5, t.cellSize * factor))
  cellSize.value = next
  panX.value = cx - gx * next - (cssW.value - props.width * next) / 2
  panY.value = cy - gy * next - (cssH.value - props.height * next) / 2
  userAdjusted.value = true
  draw()
}

defineExpose({ fit, zoomBy })

// ── space-to-pan ────────────────────────────────────────────────
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}

function onKeyDown(event: KeyboardEvent) {
  if (event.code === 'Space' && !isTypingTarget(event.target)) {
    spacePressed.value = true
    event.preventDefault()
  }
}

function onKeyUp(event: KeyboardEvent) {
  if (event.code === 'Space') spacePressed.value = false
}

watch(
  () => [
    props.revision,
    props.grid,
    props.lookup,
    props.width,
    props.height,
    props.showGrid,
    props.distanceMode,
    props.showReference,
    props.referenceOpacity,
    props.reference,
    props.preview,
    props.previewHex,
    props.blocked,
    props.selection,
  ],
  () => {
    draw()
  },
)

watch(
  () => [props.width, props.height],
  () => {
    if (!userAdjusted.value) fit()
    else draw()
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  resizeObserver = new ResizeObserver(resize)
  if (wrap.value) resizeObserver.observe(wrap.value)
  resize()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  resizeObserver?.disconnect()
})
</script>

<template>
  <div
    ref="wrap"
    class="relative h-full min-h-[320px] w-full overflow-hidden bg-canvas"
    :class="spacePressed ? 'cursor-grab' : 'cursor-crosshair'"
  >
    <canvas
      ref="canvas"
      class="block touch-none"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointerleave="onPointerLeave"
      @wheel="onWheel"
    />
    <div class="pointer-events-none absolute left-2 top-2 rounded bg-surface/90 px-2 py-1 text-[11px] text-ink-2">
      {{ Math.round(cellSize * 10) / 10 }} px/ช่อง
      <span v-if="spacePressed"> · ลากเพื่อเลื่อน</span>
    </div>
  </div>
</template>
