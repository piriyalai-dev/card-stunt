<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { seatLabels } from '@/lib/geometry'
import type { ColDirection, LabelStyle, RowDirection } from '@/types/domain'

/**
 * 🪑 แผนผังแสตนแบบคลิก/ลากมาร์กช่องบันได
 *
 * วาดด้วย `<canvas>` ไม่ใช่ `v-for` ปุ่มทีละที่นั่ง — แสตน 50×80 = 4,000 ที่นั่ง
 * ถ้าทำเป็น DOM node จะเลื่อนวนและกินแรมบนแท็บเล็ตที่ใช้หน้างาน
 *
 * 🧭 **แสดงใน Audience View:** แถว/คอลัมน์ถูกพลิกตาม `row_direction`/`col_direction`
 *   ⇒ เปลี่ยนทิศทางแล้วเห็นป้ายสลับที่ทันที (design §8.4 "กันภาพกลับด้านตั้งแต่ตั้งค่า")
 *   แต่ `blocked` ที่ emit ออกไปเป็นพิกัด **logical** (ตรงกับ backend) เสมอ
 */
const props = withDefaults(
  defineProps<{
    rows: number
    cols: number
    rowDirection: RowDirection
    colDirection: ColDirection
    rowLabelStyle: LabelStyle
    colLabelStyle: LabelStyle
    rowPrefix: string
    colPrefix: string
    blocked: Array<{ row: number; col: number }>
    disabled?: boolean
  }>(),
  { disabled: false },
)

const emit = defineEmits<{
  'update:blocked': [value: Array<{ row: number; col: number }>]
}>()

const CELL = 16
const GUTTER_L = 46
const GUTTER_T = 26
const PAD = 6
const FONT = '10px "Noto Sans Thai", Tahoma, sans-serif'

const canvas = ref<HTMLCanvasElement | null>(null)
const hover = ref<{ seatRow: number; seatCol: number } | null>(null)
let painting: 'add' | 'remove' | null = null
let blockedSet = new Set<string>()

const cssWidth = computed(() => GUTTER_L + props.cols * CELL + PAD * 2)
const cssHeight = computed(() => GUTTER_T + props.rows * CELL + PAD * 2)

const labelSpec = computed(() => ({
  rowStyle: props.rowLabelStyle,
  colStyle: props.colLabelStyle,
  rowPrefix: props.rowPrefix,
  colPrefix: props.colPrefix,
}))

function visualToSeat(vRow: number, vCol: number): { seatRow: number; seatCol: number } {
  const seatRow = props.rowDirection === 'bottom_to_top' ? props.rows - 1 - vRow : vRow
  const seatCol = props.colDirection === 'left_to_right' ? vCol : props.cols - 1 - vCol
  return { seatRow, seatCol }
}

watch(
  () => props.blocked,
  (value) => {
    blockedSet = new Set(value.map((s) => `${s.row},${s.col}`))
    draw()
  },
  { deep: true, immediate: true },
)

watch(
  () => [
    props.rows,
    props.cols,
    props.rowDirection,
    props.colDirection,
    props.rowLabelStyle,
    props.colLabelStyle,
    props.rowPrefix,
    props.colPrefix,
    hover.value,
  ],
  draw,
)

function draw() {
  const el = canvas.value
  if (!el) return
  const dpr = window.devicePixelRatio || 1
  el.width = Math.round(cssWidth.value * dpr)
  el.height = Math.round(cssHeight.value * dpr)
  el.style.width = `${cssWidth.value}px`
  el.style.height = `${cssHeight.value}px`

  const ctx = el.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, cssWidth.value, cssHeight.value)

  // หัวคอลัมน์
  ctx.font = FONT
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = '#5F6368'
  for (let v = 0; v < props.cols; v += 1) {
    const { seatCol } = visualToSeat(0, v)
    const label = seatLabels(0, seatCol, labelSpec.value).col
    ctx.fillText(label, GUTTER_L + v * CELL + CELL / 2, GUTTER_T - 12)
  }
  // หัวแถว
  ctx.textAlign = 'right'
  for (let v = 0; v < props.rows; v += 1) {
    const { seatRow } = visualToSeat(v, 0)
    const label = seatLabels(seatRow, 0, labelSpec.value).row
    ctx.fillText(label, GUTTER_L - 6, GUTTER_T + v * CELL + CELL / 2)
  }

  for (let vRow = 0; vRow < props.rows; vRow += 1) {
    for (let vCol = 0; vCol < props.cols; vCol += 1) {
      const { seatRow, seatCol } = visualToSeat(vRow, vCol)
      const x = GUTTER_L + vCol * CELL
      const y = GUTTER_T + vRow * CELL
      const isBlocked = blockedSet.has(`${seatRow},${seatCol}`)
      const isHover =
        hover.value?.seatRow === seatRow && hover.value?.seatCol === seatCol

      if (isBlocked) {
        ctx.fillStyle = '#6B6F76'
        ctx.fillRect(x + 1, y + 1, CELL - 2, CELL - 2)
        ctx.strokeStyle = 'rgba(255,255,255,.7)'
        ctx.lineWidth = 1
        ctx.beginPath()
        ctx.moveTo(x + 2, y + CELL - 2)
        ctx.lineTo(x + CELL - 2, y + 2)
        ctx.stroke()
      } else {
        ctx.fillStyle = '#FFFFFF'
        ctx.fillRect(x + 1, y + 1, CELL - 2, CELL - 2)
      }

      ctx.strokeStyle = isHover ? '#B91C1C' : '#E7E7EA'
      ctx.lineWidth = isHover ? 2 : 1
      ctx.strokeRect(x + 1.5, y + 1.5, CELL - 3, CELL - 3)
    }
  }
}

function cellAt(event: PointerEvent): { seatRow: number; seatCol: number } | null {
  const el = canvas.value
  if (!el) return null
  const rect = el.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  const vCol = Math.floor((x - GUTTER_L) / CELL)
  const vRow = Math.floor((y - GUTTER_T) / CELL)
  if (vRow < 0 || vCol < 0 || vRow >= props.rows || vCol >= props.cols) return null
  return visualToSeat(vRow, vCol)
}

function applyAt(seat: { seatRow: number; seatCol: number }) {
  if (!painting) return
  const key = `${seat.seatRow},${seat.seatCol}`
  const isBlocked = blockedSet.has(key)
  if (painting === 'add' && !isBlocked) {
    blockedSet.add(key)
    emitBlocked()
  } else if (painting === 'remove' && isBlocked) {
    blockedSet.delete(key)
    emitBlocked()
  }
}

function emitBlocked() {
  const list = Array.from(blockedSet).map((key) => {
    const [row, col] = key.split(',').map(Number)
    return { row: row!, col: col! }
  })
  emit('update:blocked', list)
  draw()
}

function onPointerDown(event: PointerEvent) {
  if (props.disabled) return
  const seat = cellAt(event)
  if (!seat) return
  const isBlocked = blockedSet.has(`${seat.seatRow},${seat.seatCol}`)
  painting = isBlocked ? 'remove' : 'add'
  canvas.value?.setPointerCapture(event.pointerId)
  hover.value = seat
  applyAt(seat)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  const seat = cellAt(event)
  if (!seat) {
    hover.value = null
    return
  }
  hover.value = seat
  if (painting) applyAt(seat)
}

function onPointerUp() {
  painting = null
}

function onPointerLeave() {
  if (!painting) hover.value = null
}

onMounted(() => {
  window.addEventListener('pointerup', onPointerUp)
  draw()
})
onBeforeUnmount(() => window.removeEventListener('pointerup', onPointerUp))

const hoverLabel = computed(() =>
  hover.value ? seatLabels(hover.value.seatRow, hover.value.seatCol, labelSpec.value) : null,
)
const hoverBlocked = computed(() =>
  hover.value
    ? blockedSet.has(`${hover.value.seatRow},${hover.value.seatCol}`)
    : false,
)
</script>

<template>
  <div>
    <div class="mb-2 flex flex-wrap items-center gap-3 text-caption text-ink-2">
      <span v-if="hoverLabel">
        ชี้ที่: <b class="text-ink-1">{{ hoverLabel.row }} · {{ hoverLabel.col }}</b>
        <span :class="hoverBlocked ? 'text-danger' : 'text-ok-strong'">
          · {{ hoverBlocked ? 'ช่องถูกบล็อก' : 'ว่าง' }}
        </span>
      </span>
      <span v-else>คลิก/ลากบนผังเพื่อมาร์กช่องบันไดหรือทางเดิน</span>
      <span class="ml-auto text-ink-3">ช่องที่บล็อก {{ blocked.length }}</span>
    </div>

    <div class="max-w-full overflow-auto rounded-control border border-line bg-surface p-1">
      <canvas
        ref="canvas"
        class="block touch-none select-none"
        :class="disabled ? 'cursor-not-allowed opacity-60' : 'cursor-crosshair'"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerleave="onPointerLeave"
      />
    </div>
  </div>
</template>
