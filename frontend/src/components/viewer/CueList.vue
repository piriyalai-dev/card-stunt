<script setup lang="ts">
/**
 * 📋 My Cue List — ทุกฉากเรียงตามลำดับ พร้อมเพลท 5×5 ของที่นั่งเรา
 */
import { computed } from 'vue'
import PlateGrid from './PlateGrid.vue'
import { colorIndex, cueView } from '@/lib/seatView'
import type { PublicMeta, PublicSeat } from '@/types/public'

const props = withDefaults(
  defineProps<{
    meta: PublicMeta
    seat: PublicSeat
    offline: boolean
    savedAt: number | null
    liveConnected?: boolean
  }>(),
  { liveConnected: true },
)

const emit = defineEmits<{
  (e: 'focus', index: number): void
  (e: 'change-seat'): void
}>()

const colors = computed(() => colorIndex(props.seat.palettes))
const cues = computed(() =>
  props.seat.stunts.map((stunt, index) => cueView(stunt, colors.value, index)),
)

function savedAtText(ts: number | null): string {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="mx-auto w-full max-w-2xl px-4 pb-28 pt-5">
    <!-- หัว: ของฉัน -->
    <header class="rounded-card border border-line bg-surface p-4">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="text-caption font-semibold text-brand">{{ meta.name }}</p>
          <h1 class="mt-0.5 font-display text-title-l font-bold text-ink-1">
            แถว {{ seat.row_label }} · ที่นั่ง {{ seat.seat_label }}
          </h1>
          <p class="mt-1 truncate text-caption text-ink-2">
            <span v-if="seat.student?.student_name">{{ seat.student.student_name }}</span>
            <span v-else>ไม่ระบุชื่อ</span>
            <span v-if="seat.student?.student_code"> · {{ seat.student.student_code }}</span>
          </p>
        </div>
        <div class="shrink-0 text-right">
          <div class="text-caption font-semibold text-ink-2">v.{{ meta.published_version }}</div>
          <div v-if="offline" class="mt-0.5 text-[11px] font-semibold text-warn">
            ออฟไลน์{{ savedAt ? ` · ${savedAtText(savedAt)}` : '' }}
          </div>
          <div v-else-if="liveConnected" class="mt-0.5 text-[11px] text-ok-strong">ออนไลน์</div>
          <div v-else class="mt-0.5 text-[11px] font-semibold text-warn">ไม่ได้รับคิวสด</div>
        </div>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="h-9 rounded-control border border-line px-3 text-[13px] font-semibold text-ink-2 hover:text-brand"
          @click="emit('change-seat')"
        >
          เปลี่ยนรหัส
        </button>
      </div>
    </header>

    <p v-if="cues.length === 0" class="mt-6 rounded-card border border-line bg-surface p-6 text-center text-body text-ink-2">
      ยังไม่มีฉากที่เผยแพร่ — รอผู้ดูแลงานเผยแพร่ก่อน
    </p>

    <!-- รายการฉาก -->
    <ol class="mt-4 space-y-3">
      <li v-for="cue in cues" :key="cue.stunt.id">
        <button
          type="button"
          class="flex w-full items-start gap-3 rounded-card border border-line bg-surface p-3 text-left transition-colors hover:border-brand/50"
          @click="emit('focus', cue.index)"
        >
          <span class="grid h-10 w-10 shrink-0 place-items-center rounded-control bg-brand-tint font-display text-title-m font-bold text-brand">
            {{ String(cue.index + 1).padStart(2, '0') }}
          </span>

          <span class="min-w-0 flex-1">
            <span class="flex flex-wrap items-baseline gap-x-2">
              <span class="font-display text-title-m font-bold text-ink-1">{{ cue.stunt.code }}</span>
              <span class="text-body font-semibold text-ink-1">{{ cue.stunt.title }}</span>
              <span
                class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                :class="cue.stunt.side === 'A' ? 'bg-brand-tint text-brand' : 'bg-canvas text-ink-2'"
              >
                ด้าน {{ cue.stunt.side }}
              </span>
            </span>
            <span v-if="cue.stunt.notes" class="mt-0.5 block text-caption text-ink-2">
              {{ cue.stunt.notes }}
            </span>
            <span class="mt-2 flex flex-wrap gap-1.5">
              <span
                v-for="color in cue.colors"
                :key="color.id"
                class="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-[11px] font-semibold text-ink-2"
              >
                <span class="h-3 w-3 rounded-full border border-black/10" :style="{ backgroundColor: color.hex }" />
                {{ color.code }} {{ color.name_th }}
              </span>
              <span v-if="cue.colors.length === 0" class="text-[11px] text-ink-3">ว่าง</span>
            </span>
          </span>

          <span class="w-20 shrink-0 sm:w-24">
            <PlateGrid :plate="cue.plate" :colors="colors" />
          </span>
        </button>
      </li>
    </ol>

    <!-- แถบลอย: เปิดโหมดโฟกัส -->
    <div class="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur">
      <div class="mx-auto flex max-w-2xl items-center gap-3">
        <button
          type="button"
          class="h-12 flex-1 rounded-control bg-brand text-body font-bold text-white disabled:opacity-50"
          :disabled="cues.length === 0"
          @click="emit('focus', 0)"
        >
          เปิดโหมดโฟกัส
        </button>
      </div>
    </div>
  </div>
</template>
