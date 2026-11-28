<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { coverLayout, fitFrame, frameAspect, sourceRect } from '@/lib/crop'
import { colorCounts, encodeRle, filledCount, type Grid } from '@/lib/grid'
import { errorMessage, formatNumber } from '@/lib/format'
import type { DitherMode } from '@/lib/quantize'
import { createGridCanvas } from '@/lib/renderer'
import * as eventsService from '@/services/events'
import * as palettesService from '@/services/palettes'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import type { PaletteOut, StandOut, StuntOut } from '@/types/domain'

const route = useRoute()
const router = useRouter()
const stuntId = computed(() => Number(route.params.stuntId))

const stunt = ref<StuntOut | null>(null)
const stand = ref<StandOut | null>(null)
const palettes = ref<PaletteOut[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')

const side = ref<'A' | 'B'>('A')
const eventPaletteA = ref<number | null>(null)
const eventPaletteB = ref<number | null>(null)

const gridWidth = computed(() => stunt.value?.grid_width ?? 0)
const gridHeight = computed(() => stunt.value?.grid_height ?? 0)

const paletteId = computed(() =>
  side.value === 'A' ? eventPaletteA.value : eventPaletteB.value,
)
const palette = computed(
  () => palettes.value.find((p) => p.id === paletteId.value) ?? null,
)
const colors = computed(() => palette.value?.colors ?? [])

const aspect = computed(() =>
  stand.value
    ? frameAspect(gridWidth.value, gridHeight.value, stand.value.seat_aspect_ratio)
    : 1,
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const st = await stuntsService.getStunt(stuntId.value)
    stunt.value = st
    stand.value = await standsService.getStand(st.stand_id)
    palettes.value = await palettesService.listPalettes(st.event_id)
    const ev = await eventsService.getEvent(st.event_id)
    eventPaletteA.value = ev.palette_a_id
    eventPaletteB.value = ev.palette_b_id
    side.value = st.side
    resetAllowed()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function resetAllowed() {
  allowed.value = new Set(colors.value.map((c) => c.id))
}

watch(paletteId, () => {
  resetAllowed()
  scheduleCompute()
})

const canUseSideB = computed(() => !!eventPaletteB.value)

function setSide(next: 'A' | 'B') {
  if (next === 'B' && !canUseSideB.value) return
  side.value = next
}

// ── frame / crop ─────────────────────────────────────────────────
const frameBox = ref<HTMLElement | null>(null)
const boxW = ref(480)
let resizeObserver: ResizeObserver | null = null

const frame = computed(() => fitFrame(Math.min(boxW.value, 560), 420, aspect.value))
const frameW = computed(() => frame.value.width)
const frameH = computed(() => frame.value.height)

const base = ref<HTMLCanvasElement | null>(null)
const originalFile = ref<File | null>(null)
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
  // เส้นแบ่งสามส่วน (ช่วยจัดองค์ประกอบ)
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
  // ⚠️ canvas ในเทมเพลตถูก mount *หลัง* base เปลี่ยน (v-if)
  // ⇒ drawCrop() ทันทีจะเจอ ref = null และภาพ preview จะว่างถาวร
  void nextTick(() => {
    drawCrop()
    scheduleCompute()
  })
}

function rebuildWith(
  quarterTurn: boolean,
  transform: (ctx: CanvasRenderingContext2D) => void,
) {
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
  originalFile.value = file
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

// ── settings ─────────────────────────────────────────────────────
const adjust = reactive({ brightness: 0, contrast: 0, saturation: 0, sharpness: 0 })
const dither = ref<DitherMode>('none')
const ditherStrength = ref(0.6)
const allowed = ref<Set<number>>(new Set())
const useBackground = ref(false)
const backgroundHex = ref('#FFFFFF')
const backgroundTolerance = ref(10)
const despeckleOn = ref(false)

const resultGrid = ref<Grid | null>(null)
const resultCanvas = ref<HTMLCanvasElement | null>(null)
const computing = ref(false)
let computeTimer: number | undefined

function scheduleCompute() {
  if (computeTimer) window.clearTimeout(computeTimer)
  computing.value = true
  computeTimer = window.setTimeout(() => void compute(), 120)
}

function toggleColor(id: number) {
  const next = new Set(allowed.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  allowed.value = next
  scheduleCompute()
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

/** ส่งภาพ (Uint8ClampedArray) ไป worker ทำ adjust + quantize + despeckle → คืน Grid */
function runQuantize(data: Uint8ClampedArray, gw: number, gh: number): Promise<Grid> {
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
        colors: colors.value.map((c) => ({ id: c.id, hex: c.hex })),
        options: {
          dither: dither.value,
          ditherStrength: ditherStrength.value,
          allowedIds: allowed.value,
          alphaThreshold: 16,
          backgroundColor: useBackground.value ? backgroundHex.value : null,
          backgroundTolerance: backgroundTolerance.value,
        },
        despeckleOn: despeckleOn.value,
      },
      { transfer: [data.buffer] },
    )
  })
}

async function compute() {
  const src = base.value
  const p = palette.value
  if (!src || !p || colors.value.length === 0 || gridWidth.value === 0) {
    resultGrid.value = null
    computing.value = false
    return
  }
  await nextTick()
  computing.value = true
  try {
    const gw = gridWidth.value
    const gh = gridHeight.value
    const l = coverLayout(
      src.width,
      src.height,
      frameW.value,
      frameH.value,
      zoom.value,
      offsetX.value,
      offsetY.value,
    )
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

    // CPU หนัก (adjust + quantize + despeckle) ย้ายไป worker — ไม่ block main thread
    const grid = await runQuantize(image.data, gw, gh)

    resultGrid.value = grid
    await nextTick()
    drawResult()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    computing.value = false
  }
}

function drawResult() {
  const canvas = resultCanvas.value
  const grid = resultGrid.value
  if (!canvas || !grid) return
  const gw = gridWidth.value
  const gh = gridHeight.value
  const lookup = new Map(colors.value.map((c) => [c.id, c.hex]))
  const off = createGridCanvas(grid, gw, gh, lookup)
  canvas.width = gw
  canvas.height = gh
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(off, 0, 0)
}

const counts = computed(() => (resultGrid.value ? colorCounts(resultGrid.value) : new Map()))
const filled = computed(() => (resultGrid.value ? filledCount(resultGrid.value) : 0))
const total = computed(() => gridWidth.value * gridHeight.value)

const colorUsage = computed(() =>
  colors.value.map((c) => ({ color: c, count: counts.value.get(c.id) ?? 0 })),
)

/** ขนาดแสดงผลของ canvas ผลลัพธ์ — ใหญ่พอเห็นชัด แต่ไม่ล้นจอ (wrapper เลื่อนได้) */
const resultDisplay = computed(() => {
  const ratio = gridHeight.value > 0 ? gridWidth.value / gridHeight.value : 1
  let width = 560
  let height = width / ratio
  if (height > 320) {
    height = 320
    width = height * ratio
  }
  return { width: `${Math.round(width)}px`, height: `${Math.round(height)}px` }
})

// ── apply ────────────────────────────────────────────────────────
const pendingKey = (id: number) => `pixelstand:pending-import:${id}`

function applyToStudio() {
  if (!resultGrid.value || !stunt.value) return
  sessionStorage.setItem(
    pendingKey(stunt.value.id),
    JSON.stringify({
      width: gridWidth.value,
      height: gridHeight.value,
      rle: encodeRle(resultGrid.value),
      at: Date.now(),
    }),
  )
  void router.push({ name: 'stunt-studio', params: { stuntId: stunt.value.id } })
}

const uploadingRef = ref(false)

async function uploadReference() {
  if (!stunt.value || !originalFile.value) return
  uploadingRef.value = true
  error.value = ''
  try {
    await stuntsService.uploadReference(stunt.value.id, originalFile.value)
    message.value = 'อัปโหลดภาพอ้างอิงแล้ว (การแสดงภาพอ้างอิงใน Studio จะมา Phase 5)'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    uploadingRef.value = false
  }
}

function backToStunts() {
  if (!stunt.value) return
  router.push({ name: 'event-stunts', params: { eventId: stunt.value.event_id } })
}

// ── wiring ───────────────────────────────────────────────────────
watch([zoom, offsetX, offsetY, frameW, frameH], () => {
  drawCrop()
  scheduleCompute()
})

// canvas อาจถูก mount ทีหลัง (v-if) — วาดเมื่อ ref พร้อม
watch(cropCanvas, (el) => {
  if (el) drawCrop()
})
watch(adjust, scheduleCompute, { deep: true })
watch(
  [
    dither,
    ditherStrength,
    useBackground,
    backgroundHex,
    backgroundTolerance,
    despeckleOn,
  ],
  scheduleCompute,
)

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
          แปลงรูปเป็นพิกเซล
          <span v-if="stunt" class="text-ink-2">· {{ stunt.code }} {{ stunt.title }}</span>
        </h2>
        <p class="text-caption text-ink-2">
          กริด {{ gridWidth }} × {{ gridHeight }} · {{ formatNumber(total) }} ช่อง
        </p>
      </div>
      <div class="ml-auto inline-flex rounded-control border border-line bg-surface p-0.5">
        <button
          type="button"
          class="h-9 rounded-lg px-3 text-[13px] font-semibold"
          :class="side === 'A' ? 'bg-brand-tint text-brand' : 'text-ink-2'"
          @click="setSide('A')"
        >
          ด้าน A
        </button>
        <button
          type="button"
          class="h-9 rounded-lg px-3 text-[13px] font-semibold disabled:opacity-40"
          :class="side === 'B' ? 'bg-brand-tint text-brand' : 'text-ink-2'"
          :disabled="!canUseSideB"
          @click="setSide('B')"
        >
          ด้าน B
        </button>
      </div>
    </div>

    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong">
      {{ message }}
    </p>

    <div v-if="loading" class="h-64 rounded-card border border-line bg-surface skeleton-shimmer" />

    <AppCard v-else-if="!palette" :padded="true">
      <p class="text-caption text-ink-2">
        ฉากนี้ยังไม่มีชุดสีสำหรับด้าน {{ side }} — ไปที่หน้า ภาพรวม → ตั้งค่างาน เพื่อกำหนดชุดสีก่อน
      </p>
    </AppCard>

    <div v-else class="grid items-start gap-4 lg:grid-cols-2">
      <!-- ฝั่งซ้าย: crop -->
      <AppCard :padded="true">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 class="font-display text-title-m font-bold">ครอปภาพ</h3>
          <label class="inline-flex h-9 cursor-pointer items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-[13px] font-semibold hover:bg-canvas">
            <i class="bi bi-upload" aria-hidden="true" />
            เลือกรูป
            <input type="file" accept="image/*" class="hidden" @change="onFile" />
          </label>
        </div>

        <div ref="frameBox" class="w-full">
          <div v-if="!base" class="grid place-items-center rounded-control border border-line bg-canvas px-4 py-16 text-center">
            <div>
              <i class="bi bi-image text-3xl text-ink-3" aria-hidden="true" />
              <p class="mt-2 text-sm font-semibold">ลากวางหรือเลือกรูป</p>
              <p class="mt-1 text-caption text-ink-2">PNG · JPG · WEBP ไม่เกิน 10 MB</p>
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
            <AppButton
              size="sm"
              variant="secondary"
              :loading="uploadingRef"
              :disabled="!originalFile"
              @click="uploadReference"
            >
              อัปโหลดเป็นภาพอ้างอิง
            </AppButton>
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
        <h3 class="font-display text-title-m font-bold mb-3">ปรับแต่ง</h3>

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

          <div class="rounded-control border border-line p-3">
            <label class="flex items-center gap-2 text-sm">
              <input v-model="useBackground" type="checkbox" class="h-4 w-4" />
              ทำสีพื้นหลังให้เป็นช่องว่าง
            </label>
            <div v-if="useBackground" class="mt-2 flex flex-wrap items-center gap-2">
              <input v-model="backgroundHex" type="color" class="h-9 w-12 cursor-pointer rounded border border-line bg-surface p-1" aria-label="สีพื้นหลัง" />
              <input v-model="backgroundHex" class="field max-w-[130px] !py-1.5" />
              <label class="flex flex-1 items-center gap-2 text-caption text-ink-2">
                ความคลาดได้
                <input v-model.number="backgroundTolerance" type="range" min="0" max="30" class="w-full accent-brand" />
                {{ backgroundTolerance }}
              </label>
            </div>
          </div>
        </div>

        <div class="mt-4">
          <div class="mb-1 flex items-center justify-between">
            <span class="text-caption font-semibold text-ink-2">สีที่ใช้ ({{ allowed.size }}/{{ colors.length }})</span>
            <button type="button" class="text-caption text-brand" @click="resetAllowed">ใช้ทุกสี</button>
          </div>
          <div class="flex flex-wrap gap-1.5">
            <button
              v-for="color in colors"
              :key="color.id"
              type="button"
              class="inline-flex h-8 items-center gap-1 rounded-full border px-2 text-[12px] font-semibold"
              :class="allowed.has(color.id) ? 'border-brand/30 bg-brand-tint text-brand' : 'border-line bg-surface text-ink-3 line-through'"
              :aria-pressed="allowed.has(color.id)"
              @click="toggleColor(color.id)"
            >
              <span class="h-3.5 w-3.5 rounded-full border border-line" :style="{ backgroundColor: color.hex }" aria-hidden="true" />
              {{ color.code }}
            </button>
          </div>
        </div>
      </AppCard>
    </div>

    <!-- ผลลัพธ์ -->
    <AppCard v-if="resultGrid" :padded="true">
      <div class="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-display text-title-m font-bold">ผลลัพธ์</h3>
        <span class="text-caption" :class="computing ? 'text-warn' : 'text-ink-2'">
          {{ computing ? 'กำลังประมวลผล…' : `${formatNumber(filled)} / ${formatNumber(total)} ช่องมีสี` }}
        </span>
      </div>
      <div class="grid gap-4 sm:grid-cols-[minmax(0,1fr)_260px]">
        <div class="max-w-full overflow-auto rounded-control border border-line bg-canvas p-2">
          <canvas
            ref="resultCanvas"
            class="block"
            style="image-rendering: pixelated"
            :style="resultDisplay"
          />
        </div>
        <div class="space-y-1.5">
          <div
            v-for="row in colorUsage"
            :key="row.color.id"
            class="flex items-center gap-2 text-caption"
          >
            <span class="h-4 w-4 rounded border border-line" :style="{ backgroundColor: row.color.hex }" aria-hidden="true" />
            <span class="font-mono">{{ row.color.code }}</span>
            <span class="min-w-0 flex-1 truncate text-ink-2">{{ row.color.name_th }}</span>
            <span class="tabular-nums text-ink-2">{{ formatNumber(row.count) }}</span>
          </div>
        </div>
      </div>
      <div class="mt-4 flex flex-wrap items-center gap-2">
        <AppButton :disabled="!resultGrid || filled === 0" @click="applyToStudio">
          <template #icon><i class="bi bi-brush" aria-hidden="true" /></template>
          ส่งไปที่ Studio
        </AppButton>
        <p class="text-caption text-ink-3">ผลลัพธ์จะกลายเป็น 1 ขั้น undo ใน Studio — กด Undo ได้ถ้าไม่ชอบ</p>
      </div>
    </AppCard>
  </div>
</template>
