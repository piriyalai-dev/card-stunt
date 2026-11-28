<script setup lang="ts">
/**
 * 🖼️ อัปโหลดรูป → พรีวิวทั้ง 2 ชุดสี (ด้าน A / ด้าน B) → เลือกด้านแล้วสร้างฉากใหม่ทันที
 *
 * ต่างจาก ImageConverter (แปลงรูปของฉากที่มีอยู่แล้ว): นี่คือจุดเริ่มต้นสร้างฉากจากรูป
 * โดยไม่ต้องกรอกฟอร์มก่อน — quantize 2 รอบด้วย palette A/B แล้วให้เลือกว่าจะไปอยู่ด้านไหน
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppEmptyState from '@/components/ui/AppEmptyState.vue'
import { coverLayout, fitFrame, frameAspect, sourceRect } from '@/lib/crop'
import { colorCounts, filledCount, toApiGrid, type Grid } from '@/lib/grid'
import { errorMessage, formatNumber } from '@/lib/format'
import type { DitherMode } from '@/lib/quantize'
import { createGridCanvas, lookupFromColors } from '@/lib/renderer'
import * as eventsService from '@/services/events'
import * as palettesService from '@/services/palettes'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import type { ColorOut, EventOut, PaletteOut, StandOut } from '@/types/domain'

const route = useRoute()
const router = useRouter()
const eventId = computed(() => Number(route.params.eventId))

const event = ref<EventOut | null>(null)
const stands = ref<StandOut[]>([])
const palettes = ref<PaletteOut[]>([])
const standId = ref<number | null>(null)
const loading = ref(true)
const error = ref('')
const message = ref('')

const stand = computed(() => stands.value.find((s) => s.id === standId.value) ?? null)
const paletteA = computed(() => palettes.value.find((p) => p.id === event.value?.palette_a_id) ?? null)
const paletteB = computed(() => palettes.value.find((p) => p.id === event.value?.palette_b_id) ?? null)

const gridWidth = computed(() => stand.value?.grid_width ?? 0)
const gridHeight = computed(() => stand.value?.grid_height ?? 0)
const seatAspect = computed(() => stand.value?.seat_aspect_ratio ?? 1)
const aspect = computed(() => frameAspect(gridWidth.value, gridHeight.value, seatAspect.value))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [ev, st, pl] = await Promise.all([
      eventsService.getEvent(eventId.value),
      standsService.listStands(eventId.value),
      palettesService.listPalettes(eventId.value),
    ])
    event.value = ev
    stands.value = st
    palettes.value = pl
    standId.value = st[0]?.id ?? null
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── frame / crop ─────────────────────────────────────────────────
const frameBox = ref<HTMLElement | null>(null)
const boxW = ref(480)
let resizeObserver: ResizeObserver | null = null

const frame = computed(() => fitFrame(Math.min(boxW.value, 560), 420, aspect.value))
const frameW = computed(() => frame.value.width)
const frameH = computed(() => frame.value.height)

const base = ref<HTMLCanvasElement | null>(null)
const imageName = ref('')
const cropCanvas = ref<HTMLCanvasElement | null>(null)
const zoom = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

const layout = computed(() => {
  const src = base.value
  if (!src) return null
  return coverLayout(src.width, src.height, frameW.value, frameH.value, zoom.value, offsetX.value, offsetY.value)
})

function clampOffsets() {
  const src = base.value
  if (!src) return
  const scale = Math.max(frameW.value / src.width, frameH.value / src.height) * zoom.value
  const maxX = Math.max(0, (src.width * scale - frameW.value) / 2)
  const maxY = Math.max(0, (src.height * scale - frameH.value) / 2)
  offsetX.value = Math.min(maxX, Math.max(-maxX, offsetX.value))
  offsetY.value = Math.min(maxY, Math.max(-maxY, offsetY.value))
}

function drawCrop() {
  const canvas = cropCanvas.value
  const src = base.value
  const l = layout.value
  if (!canvas || !src || !l) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.round(frameW.value * dpr)
  canvas.height = Math.round(frameH.value * dpr)
  canvas.style.width = `${frameW.value}px`
  canvas.style.height = `${frameH.value}px`
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.fillStyle = '#1F2328'
  ctx.fillRect(0, 0, frameW.value, frameH.value)
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(src, l.x, l.y, l.drawW, l.drawH)
  ctx.strokeStyle = 'rgba(255,255,255,.35)'
  ctx.lineWidth = 1
  ctx.beginPath()
  for (let i = 1; i <= 2; i += 1) {
    ctx.moveTo((frameW.value * i) / 3, 0)
    ctx.lineTo((frameW.value * i) / 3, frameH.value)
    ctx.moveTo(0, (frameH.value * i) / 3)
    ctx.lineTo(frameW.value, (frameH.value * i) / 3)
  }
  ctx.stroke()
  ctx.strokeStyle = 'rgba(255,255,255,.85)'
  ctx.strokeRect(0.5, 0.5, frameW.value - 1, frameH.value - 1)
}

let panning = false
let lastPanX = 0
let lastPanY = 0

function onPointerDown(event: PointerEvent) {
  if (!base.value) return
  panning = true
  lastPanX = event.clientX
  lastPanY = event.clientY
  cropCanvas.value?.setPointerCapture(event.pointerId)
  event.preventDefault()
}

function onPointerMove(event: PointerEvent) {
  if (!panning || !cropCanvas.value) return
  const rect = cropCanvas.value.getBoundingClientRect()
  const factor = frameW.value / Math.max(1, rect.width)
  offsetX.value += (event.clientX - lastPanX) * factor
  offsetY.value += (event.clientY - lastPanY) * factor
  lastPanX = event.clientX
  lastPanY = event.clientY
  clampOffsets()
  drawCrop()
  scheduleCompute()
}

function onPointerUp() {
  panning = false
}

function onWheel(event: WheelEvent) {
  if (!base.value) return
  const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12
  setZoom(zoom.value * factor)
}

function setZoom(value: number) {
  zoom.value = Math.min(4, Math.max(1, value))
  clampOffsets()
  drawCrop()
  scheduleCompute()
}

function setBase(canvas: HTMLCanvasElement, resetOffsets = true) {
  base.value = canvas
  if (resetOffsets) {
    zoom.value = 1
    offsetX.value = 0
    offsetY.value = 0
  }
  clampOffsets()
  void nextTick(() => {
    drawCrop()
    scheduleCompute()
  })
}

function rebuildWith(quarterTurn: boolean, transform: (ctx: CanvasRenderingContext2D) => void) {
  const src = base.value
  if (!src) return
  const c = document.createElement('canvas')
  c.width = quarterTurn ? src.height : src.width
  c.height = quarterTurn ? src.width : src.height
  const ctx = c.getContext('2d')
  if (!ctx) return
  transform(ctx)
  setBase(c, false)
}

function rotate90() {
  rebuildWith(true, (ctx) => {
    const src = base.value!
    ctx.translate(src.height / 2, src.width / 2)
    ctx.rotate(Math.PI / 2)
    ctx.drawImage(src, -src.width / 2, -src.height / 2)
  })
}

function flipH() {
  rebuildWith(false, (ctx) => {
    const src = base.value!
    ctx.translate(src.width, 0)
    ctx.scale(-1, 1)
    ctx.drawImage(src, 0, 0)
  })
}

function flipV() {
  rebuildWith(false, (ctx) => {
    const src = base.value!
    ctx.translate(0, src.height)
    ctx.scale(1, -1)
    ctx.drawImage(src, 0, 0)
  })
}

async function onFile(domEvent: Event) {
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  error.value = ''
  message.value = ''
  if (!file.type.startsWith('image/')) {
    error.value = 'ไฟล์ต้องเป็นรูปภาพ (PNG/JPG/WEBP)'
    return
  }
  if (file.size > 10 * 1024 * 1024) {
    error.value = 'ไฟล์ใหญ่เกิน 10 MB'
    return
  }
  imageName.value = file.name
  const url = URL.createObjectURL(file)
  const img = new Image()
  img.onload = () => {
    const c = document.createElement('canvas')
    c.width = img.naturalWidth
    c.height = img.naturalHeight
    c.getContext('2d')?.drawImage(img, 0, 0)
    setBase(c)
    URL.revokeObjectURL(url)
  }
  img.onerror = () => {
    error.value = 'เปิดรูปไม่ได้ — ลองไฟล์อื่น'
    URL.revokeObjectURL(url)
  }
  img.src = url
  input.value = ''
}

// ── ปรับแต่ง + quantize (2 palettes) ─────────────────────────────
const adjust = reactive({ brightness: 0, contrast: 0, saturation: 0, sharpness: 0 })
const dither = ref<DitherMode>('none')
const ditherStrength = ref(0.6)
const despeckleOn = ref(false)

const resultA = ref<Grid | null>(null)
const resultB = ref<Grid | null>(null)
const canvasA = ref<HTMLCanvasElement | null>(null)
const canvasB = ref<HTMLCanvasElement | null>(null)
const computing = ref(false)
let computeTimer: number | undefined

function scheduleCompute() {
  if (computeTimer) window.clearTimeout(computeTimer)
  computing.value = true
  computeTimer = window.setTimeout(() => void compute(), 120)
}

let quantizeWorker: Worker | null = null

function getQuantizeWorker(): Worker {
  if (!quantizeWorker) {
    quantizeWorker = new Worker(new URL('../../workers/quantize.worker.ts', import.meta.url), {
      type: 'module',
    })
  }
  return quantizeWorker
}

function runQuantizeFor(data: Uint8ClampedArray, gw: number, gh: number, colors: ColorOut[]): Promise<Grid> {
  return new Promise((resolve, reject) => {
    const worker = getQuantizeWorker()
    const onMessage = (event: MessageEvent<{ grid?: Grid; error?: string }>) => {
      worker.removeEventListener('message', onMessage)
      if (event.data?.error) reject(new Error(event.data.error))
      else if (event.data?.grid) resolve(event.data.grid)
      else reject(new Error('quantize worker ตอบกลับไม่สมบูรณ์'))
    }
    worker.addEventListener('message', onMessage)
    worker.postMessage(
      {
        data,
        gw,
        gh,
        adjust: {
          brightness: adjust.brightness,
          contrast: adjust.contrast,
          saturation: adjust.saturation,
          sharpness: adjust.sharpness,
        },
        colors: colors.map((c) => ({ id: c.id, hex: c.hex })),
        options: {
          dither: dither.value,
          ditherStrength: ditherStrength.value,
          allowedIds: new Set(colors.map((c) => c.id)),
          alphaThreshold: 16,
          backgroundColor: null,
          backgroundTolerance: 0,
        },
        despeckleOn: despeckleOn.value,
      },
      { transfer: [data.buffer] },
    )
  })
}

async function compute() {
  const src = base.value
  const pa = paletteA.value
  const pb = paletteB.value
  if (!src || !pa || gridWidth.value === 0) {
    resultA.value = null
    resultB.value = null
    computing.value = false
    return
  }
  await nextTick()
  computing.value = true
  try {
    const gw = gridWidth.value
    const gh = gridHeight.value
    const l = coverLayout(src.width, src.height, frameW.value, frameH.value, zoom.value, offsetX.value, offsetY.value)
    const rect = sourceRect(l, frameW.value, frameH.value, src.width, src.height)

    const out = document.createElement('canvas')
    out.width = gw
    out.height = gh
    const octx = out.getContext('2d')
    if (!octx) return
    octx.imageSmoothingEnabled = true
    octx.imageSmoothingQuality = 'high'
    octx.drawImage(src, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, gw, gh)
    const image = octx.getImageData(0, 0, gw, gh)

    // ⚠️ transfer detach buffer ⇒ ต้อง copy ข้อมูลคนละชุดต่อ palette
    const dataA = new Uint8ClampedArray(image.data)
    const dataB = new Uint8ClampedArray(image.data)
    const [a, b] = await Promise.all([
      runQuantizeFor(dataA, gw, gh, pa.colors),
      pb ? runQuantizeFor(dataB, gw, gh, pb.colors) : Promise.resolve(null),
    ])
    resultA.value = a
    resultB.value = b
    await nextTick()
    drawResult(canvasA.value, resultA.value, pa.colors)
    drawResult(canvasB.value, resultB.value, pb?.colors ?? [])
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    computing.value = false
  }
}

function drawResult(canvas: HTMLCanvasElement | null, grid: Grid | null, colors: ColorOut[]): void {
  if (!canvas || !grid) return
  const gw = gridWidth.value
  const gh = gridHeight.value
  const lookup = lookupFromColors(colors)
  const off = createGridCanvas(grid, gw, gh, lookup)
  canvas.width = gw
  canvas.height = gh
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(off, 0, 0)
}

const countsA = computed(() => (resultA.value ? colorCounts(resultA.value) : new Map<number, number>()))
const countsB = computed(() => (resultB.value ? colorCounts(resultB.value) : new Map<number, number>()))
const filledA = computed(() => (resultA.value ? filledCount(resultA.value) : 0))
const filledB = computed(() => (resultB.value ? filledCount(resultB.value) : 0))
const total = computed(() => gridWidth.value * gridHeight.value)

const usageA = computed(() => (paletteA.value?.colors ?? []).map((c) => ({ color: c, count: countsA.value.get(c.id) ?? 0 })))
const usageB = computed(() => (paletteB.value?.colors ?? []).map((c) => ({ color: c, count: countsB.value.get(c.id) ?? 0 })))

const resultDisplay = computed(() => {
  const ratio = gridHeight.value > 0 ? gridWidth.value / gridHeight.value : 1
  let width = 320
  let height = width / ratio
  if (height > 240) {
    height = 240
    width = height * ratio
  }
  return { width: `${Math.round(width)}px`, height: `${Math.round(height)}px` }
})

// ── create ───────────────────────────────────────────────────────
const code = ref('')
const title = ref('')
const section = ref('')
const creating = ref(false)

async function createStunt(side: 'A' | 'B') {
  if (!event.value || !stand.value) return
  if (!code.value.trim() || !title.value.trim()) {
    error.value = 'ต้องใส่รหัสและชื่อฉากก่อน'
    return
  }
  const grid = side === 'A' ? resultA.value : resultB.value
  if (!grid) {
    error.value = 'ยังไม่มีผลลัพธ์ — เลือกรูปก่อน'
    return
  }
  creating.value = true
  error.value = ''
  message.value = ''
  try {
    const created = await stuntsService.createStunt(event.value.id, {
      code: code.value.trim(),
      title: title.value.trim(),
      section: section.value.trim() || null,
      stand_id: stand.value.id,
      side,
    })
    await stuntsService.saveGrid(created.id, { grid_data: toApiGrid(grid) })
    message.value = `สร้างฉาก ${created.code} (ด้าน ${side}) แล้ว`
    void router.push({ name: 'stunt-studio', params: { stuntId: created.id } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    creating.value = false
  }
}

function backToStunts() {
  void router.push({ name: 'event-stunts', params: { eventId: eventId.value } })
}

// ── wiring ───────────────────────────────────────────────────────
watch([zoom, offsetX, offsetY, frameW, frameH], () => {
  drawCrop()
  scheduleCompute()
})
watch(cropCanvas, (el) => {
  if (el) drawCrop()
})
watch(adjust, scheduleCompute, { deep: true })
watch([dither, ditherStrength, despeckleOn], scheduleCompute)
watch(standId, () => {
  // แสตนเปลี่ยน → ขนาดกริดเปลี่ยน → reset ผลลัพธ์
  resultA.value = null
  resultB.value = null
  drawCrop()
  scheduleCompute()
})
watch(frameBox, (el) => {
  resizeObserver?.disconnect()
  resizeObserver = null
  if (!el) return
  resizeObserver = new ResizeObserver((entries) => {
    const width = entries[0]?.contentRect.width
    if (width) boxW.value = width
  })
  resizeObserver.observe(el)
})

onMounted(() => {
  window.addEventListener('pointerup', onPointerUp)
  drawCrop()
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerup', onPointerUp)
  resizeObserver?.disconnect()
  if (computeTimer) window.clearTimeout(computeTimer)
  quantizeWorker?.terminate()
  quantizeWorker = null
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-2">
      <AppButton variant="secondary" size="sm" @click="backToStunts">
        <template #icon><i class="bi bi-arrow-left" aria-hidden="true" /></template>
        กลับไปฉาก
      </AppButton>
      <div class="min-w-0">
        <h2 class="font-display text-title-m font-bold truncate">
          อัปโหลดรูปสร้างฉาก
          <span v-if="event" class="text-ink-2">· {{ event.name }}</span>
        </h2>
        <p class="text-caption text-ink-2">เลือกรูป → พรีวิว 2 ชุดสี → เลือกด้าน A/B → สร้างฉาก</p>
      </div>
    </div>

    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">{{ error }}</p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong">{{ message }}</p>

    <div v-if="loading" class="h-64 rounded-card border border-line bg-surface skeleton-shimmer" />

    <AppEmptyState
      v-else-if="stands.length === 0"
      icon="bi-grid-3x3-gap"
      title="ยังไม่มีแสตน"
      description="ต้องสร้างแสตนก่อนจึงจะอัปโหลดรูปสร้างฉากได้"
    >
      <AppButton size="sm" @click="backToStunts">กลับไปตั้งค่าแสตน</AppButton>
    </AppEmptyState>

    <div v-else-if="!paletteA && !paletteB" class="rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-caption text-warn">
      ยังไม่ได้กำหนดชุดสี ด้าน A/B — ไปที่หน้า ภาพรวม → ตั้งค่างาน เพื่อกำหนดชุดสีก่อน
    </div>

    <template v-else>
      <div class="grid items-start gap-4 lg:grid-cols-2">
        <!-- ฝั่งซ้าย: เลือกรูป + ครอป -->
        <AppCard :padded="true">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h3 class="font-display text-title-m font-bold">1) เลือกรูป + ครอป</h3>
            <div class="flex items-center gap-2">
              <label class="block text-caption text-ink-2">แสตน</label>
              <select v-model.number="standId" class="field !w-auto !py-1.5">
                <option v-for="s in stands" :key="s.id" :value="s.id">{{ s.name }} ({{ s.grid_width }}×{{ s.grid_height }})</option>
              </select>
            </div>
          </div>

          <div ref="frameBox" class="w-full">
            <div v-if="!base" class="grid place-items-center rounded-control border border-line bg-canvas px-4 py-16 text-center">
              <div>
                <i class="bi bi-image text-3xl text-ink-3" aria-hidden="true" />
                <p class="mt-2 text-sm font-semibold">เลือกรูปเพื่อเริ่ม</p>
                <p class="mt-1 text-caption text-ink-2">PNG · JPG · WEBP ไม่เกิน 10 MB</p>
                <label class="mt-4 inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-control bg-brand px-3 text-[13px] font-semibold text-white hover:bg-brand-strong">
                  <i class="bi bi-upload" aria-hidden="true" />
                  เลือกรูป
                  <input type="file" accept="image/*" class="hidden" @change="onFile" />
                </label>
              </div>
            </div>
            <div v-else class="flex justify-center">
              <canvas
                ref="cropCanvas"
                class="block cursor-grab touch-none rounded-control active:cursor-grabbing"
                @pointerdown="onPointerDown"
                @pointermove="onPointerMove"
                @wheel.prevent="onWheel"
              />
            </div>
          </div>

          <div v-if="base" class="mt-3 space-y-2">
            <div class="flex flex-wrap gap-1.5">
              <AppButton size="sm" variant="secondary" @click="rotate90">หมุน 90°</AppButton>
              <AppButton size="sm" variant="secondary" @click="flipH">พลิกซ้าย–ขวา</AppButton>
              <AppButton size="sm" variant="secondary" @click="flipV">พลิกบน–ล่าง</AppButton>
              <label class="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-[13px] font-semibold hover:bg-canvas">
                <i class="bi bi-upload" aria-hidden="true" />
                เปลี่ยนรูป
                <input type="file" accept="image/*" class="hidden" @change="onFile" />
              </label>
            </div>
            <label class="flex items-center gap-2 text-sm">
              <span class="w-16 text-caption text-ink-2">ซูม</span>
              <input
                :value="zoom"
                type="range"
                min="1"
                max="4"
                step="0.05"
                class="w-full accent-brand"
                @input="setZoom(Number(($event.target as HTMLInputElement).value))"
              />
              <span class="w-10 text-right text-caption tabular-nums">{{ zoom.toFixed(1) }}×</span>
            </label>
            <p class="text-caption text-ink-3">
              ลากบนภาพเพื่อเลื่อน · ภาพถูกล็อกอัตราส่วนเดียวกับแสตน
              <span v-if="imageName">· {{ imageName }}</span>
            </p>
          </div>
        </AppCard>

        <!-- ฝั่งขวา: ปรับแต่ง -->
        <AppCard :padded="true">
          <h3 class="font-display text-title-m font-bold mb-3">2) ปรับแต่ง</h3>
          <div class="space-y-2.5">
            <label class="flex items-center gap-3 text-sm">
              <span class="w-24 text-caption text-ink-2">ความสว่าง</span>
              <input v-model.number="adjust.brightness" type="range" min="-100" max="100" class="w-full accent-brand" />
              <span class="w-10 text-right text-caption tabular-nums">{{ adjust.brightness }}</span>
            </label>
            <label class="flex items-center gap-3 text-sm">
              <span class="w-24 text-caption text-ink-2">คอนทราสต์</span>
              <input v-model.number="adjust.contrast" type="range" min="-100" max="100" class="w-full accent-brand" />
              <span class="w-10 text-right text-caption tabular-nums">{{ adjust.contrast }}</span>
            </label>
            <label class="flex items-center gap-3 text-sm">
              <span class="w-24 text-caption text-ink-2">ความอิ่มสี</span>
              <input v-model.number="adjust.saturation" type="range" min="-100" max="100" class="w-full accent-brand" />
              <span class="w-10 text-right text-caption tabular-nums">{{ adjust.saturation }}</span>
            </label>
            <label class="flex items-center gap-3 text-sm">
              <span class="w-24 text-caption text-ink-2">ความคม</span>
              <input v-model.number="adjust.sharpness" type="range" min="0" max="100" class="w-full accent-brand" />
              <span class="w-10 text-right text-caption tabular-nums">{{ adjust.sharpness }}</span>
            </label>

            <div class="grid gap-2 sm:grid-cols-2">
              <label class="block text-sm">
                <span class="mb-1 block text-caption text-ink-2">Dither</span>
                <select v-model="dither" class="field">
                  <option value="none">ไม่มี (โลโก้/ตัวหนังสือ)</option>
                  <option value="floyd">Floyd–Steinberg (ภาพถ่าย)</option>
                  <option value="bayer">Ordered Bayer 4×4</option>
                </select>
              </label>
              <label class="flex items-end gap-2 text-sm">
                <span class="flex-1">
                  <span class="mb-1 block text-caption text-ink-2">ความแรง dither</span>
                  <input v-model.number="ditherStrength" type="range" min="0" max="1" step="0.05" class="w-full accent-brand" />
                </span>
                <span class="w-10 pb-3 text-right text-caption tabular-nums">{{ ditherStrength.toFixed(2) }}</span>
              </label>
            </div>

            <label class="flex items-center gap-2 text-sm">
              <input v-model="despeckleOn" type="checkbox" class="h-4 w-4" />
              ลบจุดเดี่ยว (despeckle)
            </label>
          </div>
        </AppCard>
      </div>

      <!-- ผลลัพธ์: 2 ชุดสี -->
      <AppCard :padded="true">
        <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 class="font-display text-title-m font-bold">3) เลือกด้าน</h3>
          <span class="text-caption" :class="computing ? 'text-warn' : 'text-ink-2'">
            {{ computing ? 'กำลังประมวลผล…' : `${formatNumber(total)} ช่องต่อด้าน` }}
          </span>
        </div>

        <div class="grid gap-4 md:grid-cols-2">
          <div class="rounded-control border border-line p-3">
            <div class="mb-2 flex items-center justify-between">
              <span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold uppercase bg-brand-tint text-brand">ด้าน A</span>
              <span class="text-caption text-ink-2">{{ paletteA?.name ?? '— ไม่มีชุดสี —' }}</span>
            </div>
            <div v-if="resultA" class="max-w-full overflow-auto rounded-control border border-line bg-canvas p-2">
              <canvas ref="canvasA" class="block" style="image-rendering: pixelated" :style="resultDisplay" />
            </div>
            <div v-else class="grid aspect-[4/3] place-items-center rounded-control border border-dashed border-line text-caption text-ink-3">
              {{ computing ? 'กำลังแปลง…' : 'ยังไม่มีผลลัพธ์' }}
            </div>
            <p class="mt-1 text-caption text-ink-3">{{ filledA }} / {{ formatNumber(total) }} ช่องมีสี</p>
            <div class="mt-2 flex flex-wrap gap-1">
              <span
                v-for="row in usageA"
                :key="row.color.id"
                class="inline-flex items-center gap-1 rounded-full border border-line px-1.5 py-0.5 text-[10px] text-ink-2"
                :title="row.color.name_th"
              >
                <span class="h-3 w-3 rounded-full border border-line" :style="{ backgroundColor: row.color.hex }" aria-hidden="true" />
                {{ row.color.code }} {{ row.count }}
              </span>
            </div>
          </div>

          <div class="rounded-control border border-line p-3">
            <div class="mb-2 flex items-center justify-between">
              <span class="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold uppercase bg-canvas text-ink-2">ด้าน B</span>
              <span class="text-caption text-ink-2">{{ paletteB?.name ?? '— ไม่มีชุดสี —' }}</span>
            </div>
            <div v-if="resultB" class="max-w-full overflow-auto rounded-control border border-line bg-canvas p-2">
              <canvas ref="canvasB" class="block" style="image-rendering: pixelated" :style="resultDisplay" />
            </div>
            <div v-else class="grid aspect-[4/3] place-items-center rounded-control border border-dashed border-line text-caption text-ink-3">
              {{ computing ? 'กำลังแปลง…' : 'ยังไม่มีผลลัพธ์' }}
            </div>
            <p class="mt-1 text-caption text-ink-3">{{ filledB }} / {{ formatNumber(total) }} ช่องมีสี</p>
            <div class="mt-2 flex flex-wrap gap-1">
              <span
                v-for="row in usageB"
                :key="row.color.id"
                class="inline-flex items-center gap-1 rounded-full border border-line px-1.5 py-0.5 text-[10px] text-ink-2"
                :title="row.color.name_th"
              >
                <span class="h-3 w-3 rounded-full border border-line" :style="{ backgroundColor: row.color.hex }" aria-hidden="true" />
                {{ row.color.code }} {{ row.count }}
              </span>
            </div>
          </div>
        </div>

        <!-- ฟอร์มสร้าง -->
        <div class="mt-4 border-t border-line pt-4">
          <h4 class="mb-2 text-caption font-bold text-ink-2">ตั้งชื่อฉาก แล้วเลือกด้านที่จะสร้าง</h4>
          <div class="grid gap-2 sm:grid-cols-3">
            <input v-model="code" class="field" placeholder="รหัสฉาก เช่น 01" />
            <input v-model="title" class="field" placeholder="ชื่อฉาก เช่น เปิดตัว" />
            <input v-model="section" class="field" placeholder="กลุ่ม/ช่วง (ไม่บังคับ)" />
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <AppButton :disabled="!resultA || creating || !code.trim() || !title.trim()" :loading="creating" @click="createStunt('A')">
              <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
              สร้างเป็นด้าน A
            </AppButton>
            <AppButton variant="secondary" :disabled="!resultB || creating || !code.trim() || !title.trim()" :loading="creating" @click="createStunt('B')">
              <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
              สร้างเป็นด้าน B
            </AppButton>
          </div>
          <p class="mt-2 text-caption text-ink-3">สร้างแล้วจะเปิด Pixel Studio ให้แก้ไขต่อได้ทันที</p>
        </div>
      </AppCard>
    </template>
  </div>
</template>
