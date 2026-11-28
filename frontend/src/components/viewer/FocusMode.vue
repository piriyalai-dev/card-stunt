<script setup lang="ts">
/**
 * 🔦 Focus / Show mode — กล่องสีใหญ่ + รหัสยักษ์ สำหรับถือใช้งานกลางแสตน
 *
 * - ตามคิวสด (SSE) เสมอ — ผู้คุมคือแหล่งความจริง เมื่อ advance ผู้ชมตามทันที
 * - Screen Wake Lock เปิดอัตโนมัติ; ถ้าเบราว์เซอร์ไม่รองรับจะซ่อนสวิตช์
 * - ปัดซ้าย/ขวา หรือลูกศรคีย์บอร์ด = เปลี่ยนฉาก (โดนคิวสดดึงกลับเมื่อผู้คุม advance)
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import PlateGrid from './PlateGrid.vue'
import { colorIndex, cueView } from '@/lib/seatView'
import { useWakeLock } from '@/lib/wakeLock'
import type { PublicMeta, PublicSeat } from '@/types/public'

const props = defineProps<{
  meta: PublicMeta
  seat: PublicSeat
  startIndex: number
  liveStuntId: number | null
  liveActive: boolean
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const colors = computed(() => colorIndex(props.seat.palettes))

function clampIndex(value: number): number {
  const max = props.seat.stunts.length - 1
  if (max < 0) return 0
  return Math.min(Math.max(0, value), max)
}

const index = ref(clampIndex(props.startIndex))
const current = computed(() => props.seat.stunts[index.value] ?? null)
const cue = computed(() =>
  current.value ? cueView(current.value, colors.value, index.value) : null,
)
const next = computed(() => {
  const total = props.seat.stunts.length
  if (!total) return null
  return props.seat.stunts[(index.value + 1) % total]
})
const nextCue = computed(() =>
  next.value ? cueView(next.value, colors.value, (index.value + 1) % props.seat.stunts.length) : null,
)
const mixCount = computed(() => cue.value?.colors.length ?? 0)

const wake = useWakeLock()

function prev(): void {
  const total = props.seat.stunts.length
  if (!total) return
  index.value = (index.value - 1 + total) % total
}

function nextCueStep(): void {
  const total = props.seat.stunts.length
  if (!total) return
  index.value = (index.value + 1) % total
}

function jump(value: number): void {
  index.value = clampIndex(value)
}

function onSelectChange(event: Event): void {
  jump(Number((event.target as HTMLSelectElement).value))
}

// ── ตามคิวสด (บังคับ) ─────────────────────────────────────────────
// ผู้คุมคือแหล่งความจริง — advance แล้วดึง index ตามทันทีเสมอ ไม่มี opt-out
watch(
  () => props.liveStuntId,
  (stuntId) => {
    if (!props.liveActive || stuntId === null) return
    const found = props.seat.stunts.findIndex((s) => s.id === stuntId)
    if (found >= 0) index.value = found
  },
)

watch(
  () => props.liveActive,
  (active) => {
    if (!active) return
    if (props.liveStuntId !== null) {
      const found = props.seat.stunts.findIndex((s) => s.id === props.liveStuntId)
      if (found >= 0) index.value = found
    }
  },
)

// ── swipe + keyboard ──────────────────────────────────────────────
let startX = 0
let startY = 0
let tracking = false

function onTouchStart(event: TouchEvent): void {
  const touch = event.touches[0]
  if (!touch) return
  startX = touch.clientX
  startY = touch.clientY
  tracking = true
}

function onTouchEnd(event: TouchEvent): void {
  if (!tracking) return
  tracking = false
  const touch = event.changedTouches[0]
  if (!touch) return
  const dx = touch.clientX - startX
  const dy = touch.clientY - startY
  if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) {
    if (dx < 0) nextCueStep()
    else prev()
  }
}

function onKey(event: KeyboardEvent): void {
  if (event.key === 'ArrowRight') nextCueStep()
  else if (event.key === 'ArrowLeft') prev()
  else if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  void wake.enable()
  window.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="fixed inset-0 z-50 flex flex-col bg-canvas text-ink-1">
    <!-- top bar -->
    <header class="flex shrink-0 items-center gap-2 border-b border-line bg-surface px-3 py-2">
      <button
        type="button"
        class="grid h-10 w-10 place-items-center rounded-control text-ink-2 hover:bg-canvas"
        aria-label="ปิดโหมดโฟกัส"
        @click="emit('close')"
      >
        <i class="bi bi-x-lg" aria-hidden="true" />
      </button>
      <div class="min-w-0 flex-1">
        <div class="truncate text-caption font-semibold text-ink-2">
          {{ meta.name }} · แถว {{ seat.row_label }} ที่นั่ง {{ seat.seat_label }}
        </div>
        <div class="text-[11px] text-ink-3">v.{{ meta.published_version }}</div>
      </div>

      <span
        v-if="liveActive"
        class="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-semibold bg-brand-tint text-brand"
        title="กำลังตามคิวสด"
      >
        <i class="bi bi-broadcast" aria-hidden="true" />
        คิวสด
      </span>

      <button
        v-if="wake.supported"
        type="button"
        class="inline-flex h-10 items-center gap-1.5 rounded-control px-2 text-[12px] font-semibold"
        :class="wake.wanted.value ? 'bg-ok-soft text-ok-strong' : 'text-ink-3 hover:bg-canvas'"
        :aria-pressed="wake.wanted.value"
        @click="wake.toggle()"
      >
        <i :class="['bi', wake.wanted.value ? 'bi-lightbulb-fill' : 'bi-lightbulb']" aria-hidden="true" />
        จอติด
      </button>
    </header>

    <!-- current cue -->
    <main
      class="flex min-h-0 flex-1 flex-col items-center justify-center px-4 py-4"
      @touchstart="onTouchStart"
      @touchend="onTouchEnd"
    >
      <p v-if="current" class="mb-3 text-center text-caption font-semibold text-ink-2">
        ฉาก {{ index + 1 }}/{{ seat.stunts.length }} · {{ current.code }} {{ current.title }} · ด้าน {{ current.side }}
      </p>

      <div class="w-full max-w-[min(88vw,24rem)]">
        <PlateGrid v-if="cue" :plate="cue.plate" :colors="colors" :show-codes="true" :gap="4" code-class="text-xl sm:text-2xl" />
      </div>

      <div class="mt-4 text-center">
        <div data-testid="focus-code" class="font-display text-6xl font-extrabold leading-none text-ink-1">
          ด้าน {{ current?.side ?? '—' }}
        </div>
        <p v-if="mixCount > 1" class="mt-1 text-caption text-ink-2">
          ใช้ {{ mixCount }} สี —
          <span v-for="(color, i) in cue?.colors ?? []" :key="color.id">
            {{ color.code }} {{ color.name_th }}<span v-if="i < mixCount - 1"> · </span>
          </span>
        </p>
        <p v-if="current?.notes" class="mt-1 text-caption text-ink-2">{{ current.notes }}</p>
      </div>

    </main>

    <!-- next cue preview + controls -->
    <footer class="shrink-0 border-t border-line bg-surface px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2">
      <p data-testid="next-cue" class="mb-2 text-center text-caption text-ink-2">
        <template v-if="nextCue">
          โค้ดถัดไปเตรียมเปิด:
          <span class="font-bold text-ink-1">{{ nextCue.stunt.code }} ({{ nextCue.dominant.color?.name_th ?? 'ว่าง' }})</span>
        </template>
        <template v-else>ยังไม่มีฉากถัดไป</template>
      </p>

      <div class="mx-auto flex max-w-xl items-center gap-2">
        <button
          type="button"
          class="grid h-14 w-14 shrink-0 place-items-center rounded-control border border-line bg-surface text-2xl text-ink-1 active:bg-canvas"
          aria-label="ฉากก่อนหน้า"
          @click="prev"
        >
          <i class="bi bi-chevron-left" aria-hidden="true" />
        </button>

        <label class="min-w-0 flex-1">
          <span class="sr-only">เลือกฉาก</span>
          <select
            :value="index"
            class="h-12 w-full rounded-control border border-line bg-surface px-3 text-body font-semibold"
            @change="onSelectChange"
          >
            <option v-for="(stunt, i) in seat.stunts" :key="stunt.id" :value="i">
              {{ String(i + 1).padStart(2, '0') }} · {{ stunt.code }} {{ stunt.title }}
            </option>
          </select>
        </label>

        <button
          type="button"
          class="grid h-14 w-14 shrink-0 place-items-center rounded-control bg-brand text-2xl text-white active:bg-brand-strong"
          aria-label="ฉากถัดไป"
          @click="nextCueStep"
        >
          <i class="bi bi-chevron-right" aria-hidden="true" />
        </button>
      </div>
    </footer>
  </div>
</template>
