<script setup lang="ts">
/**
 * 🪑 Seat picker (public) — เลือกที่นั่ง 2 ทาง: dropdown/แตะผัง หรือค้นหาเลขประจำตัว
 */
import { computed, ref, watch } from 'vue'
import { formatDate } from '@/lib/format'
import { displayCols, displayRows, isBlocked, rowLabel, seatLabel } from '@/lib/seatView'
import type { PublicMeta } from '@/types/public'

const props = defineProps<{
  meta: PublicMeta
  busy?: boolean
  error?: string
}>()

const emit = defineEmits<{
  (e: 'select', payload: { standId: number; row: number; col: number }): void
  (e: 'search-code', code: string): void
}>()

const standId = ref(props.meta.stands[0]?.id ?? 0)
const selected = ref<{ row: number; col: number } | null>(null)
const rowChoice = ref(1)
const colChoice = ref(1)
const code = ref('')
const codeError = ref('')

const stand = computed(() => props.meta.stands.find((s) => s.id === standId.value) ?? null)
const rows = computed(() => (stand.value ? displayRows(stand.value) : []))
const cols = computed(() => (stand.value ? displayCols(stand.value) : []))
const selectedLabel = computed(() => {
  if (!stand.value || !selected.value) return ''
  return `${rowLabel(stand.value, selected.value.row - 1)} · ${seatLabel(stand.value, selected.value.col - 1)}`
})

watch(
  () => props.meta.stands,
  (stands) => {
    if (!stands.some((s) => s.id === standId.value)) standId.value = stands[0]?.id ?? 0
  },
)

watch(standId, () => {
  selected.value = null
  rowChoice.value = 1
  colChoice.value = 1
})

watch(selected, (value) => {
  if (!value) return
  rowChoice.value = value.row
  colChoice.value = value.col
})

/** dropdown เปลี่ยน → sync กับผัง (ถ้าช่องปิด ล้าง selection) */
watch([rowChoice, colChoice], ([row, col]) => {
  if (blocked(row - 1, col - 1)) {
    selected.value = null
    return
  }
  selected.value = { row, col }
})

function blocked(row0: number, col0: number): boolean {
  return !!stand.value && isBlocked(stand.value, row0, col0)
}

function pick(row0: number, col0: number): void {
  if (blocked(row0, col0)) return
  selected.value = { row: row0 + 1, col: col0 + 1 }
}

function submit(): void {
  if (!stand.value || !selected.value) return
  emit('select', {
    standId: stand.value.id,
    row: selected.value.row,
    col: selected.value.col,
  })
}

function search(): void {
  codeError.value = ''
  const value = code.value.trim()
  if (!value) {
    codeError.value = 'กรอกเลขประจำตัวก่อนค้นหา'
    return
  }
  emit('search-code', value)
}
</script>

<template>
  <div class="mx-auto w-full max-w-2xl px-4 py-8">
    <header class="mb-6 text-center">
      <p class="text-caption font-semibold text-brand">Pixel Stand</p>
      <h1 class="mt-1 font-display text-title-l font-bold text-ink-1">{{ meta.name }}</h1>
      <p v-if="meta.event_date" class="mt-1 text-caption text-ink-2">
        {{ formatDate(meta.event_date) }}
        <span aria-hidden="true">·</span> เวอร์ชัน v.{{ meta.published_version }}
      </p>
    </header>

    <p
      v-if="error"
      class="mb-4 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger"
      role="alert"
    >
      {{ error }}
    </p>

    <section class="rounded-card border border-line bg-surface p-4">
      <h2 class="mb-3 font-display text-title-m font-bold text-ink-1">เลือกที่นั่งของคุณ</h2>

      <label v-if="meta.stands.length > 1" class="mb-3 block">
        <span class="mb-1 block text-caption font-semibold text-ink-2">แสตน</span>
        <select
          v-model.number="standId"
          class="h-11 w-full rounded-control border border-line bg-surface px-3 text-body text-ink-1"
        >
          <option v-for="s in meta.stands" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>

      <div v-if="stand" class="flex flex-wrap items-end gap-3">
        <label class="min-w-[6rem] flex-1">
          <span class="mb-1 block text-caption font-semibold text-ink-2">แถว</span>
          <select
            v-model.number="rowChoice"
            class="h-11 w-full rounded-control border border-line bg-surface px-3 text-body"
          >
            <option v-for="row0 in rows" :key="row0" :value="row0 + 1">
              {{ rowLabel(stand, row0) }}
            </option>
          </select>
        </label>
        <label class="min-w-[6rem] flex-1">
          <span class="mb-1 block text-caption font-semibold text-ink-2">ที่นั่ง</span>
          <select
            v-model.number="colChoice"
            class="h-11 w-full rounded-control border border-line bg-surface px-3 text-body"
          >
            <option v-for="col0 in cols" :key="col0" :value="col0 + 1">
              {{ seatLabel(stand, col0) }}
            </option>
          </select>
        </label>
        <div class="min-w-[8rem] flex-1 text-right">
          <span class="text-caption text-ink-3">ที่เลือก:</span>
          <div class="font-display text-title-m font-bold text-ink-1">
            {{ selectedLabel || 'ยังไม่ได้เลือก' }}
          </div>
        </div>
      </div>

      <!-- ผังแสตน -->
      <div v-if="stand" class="mt-4 overflow-x-auto pb-1">
        <div :style="{ minWidth: `${stand.cols * 24 + 34}px` }">
          <div
            v-for="row0 in rows"
            :key="row0"
            class="mb-1 flex items-center gap-1"
          >
            <span class="w-6 shrink-0 text-right text-[11px] font-semibold text-ink-3">
              {{ rowLabel(stand, row0) }}
            </span>
            <div
              class="grid flex-1 gap-1"
              :style="{ gridTemplateColumns: `repeat(${stand.cols}, minmax(0, 1fr))` }"
            >
              <button
                v-for="col0 in cols"
                :key="col0"
                type="button"
                class="grid aspect-square min-w-0 place-items-center rounded-[4px] border text-[9px] font-semibold transition-colors"
                :class="[
                  blocked(row0, col0)
                    ? 'cursor-not-allowed border-line bg-stone-200 text-stone-400'
                    : selected && selected.row === row0 + 1 && selected.col === col0 + 1
                      ? 'border-brand bg-brand text-white'
                      : 'border-line bg-surface text-ink-2 hover:border-brand/50 hover:text-brand',
                ]"
                :disabled="blocked(row0, col0)"
                :aria-label="`แถว ${rowLabel(stand, row0)} ที่นั่ง ${seatLabel(stand, col0)}${blocked(row0, col0) ? ' (ช่องปิด)' : ''}`"
                @click="pick(row0, col0)"
              >
                {{ stand.cols <= 24 ? seatLabel(stand, col0) : '' }}
              </button>
            </div>
          </div>
          <p class="mt-2 text-[11px] text-ink-3">ช่องเทา = ช่องปิด/ทางเดิน · แถวล่างคือแถวชิดสนาม</p>
        </div>
      </div>

      <button
        type="button"
        class="mt-4 h-12 w-full rounded-control bg-brand text-body font-bold text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
        :disabled="busy || !selected"
        @click="submit"
      >
        {{ busy ? 'กำลังโหลดโพย…' : selected ? `เข้าดูโพย — ${selectedLabel}` : 'แตะที่นั่งบนผังเพื่อเลือก' }}
      </button>
    </section>

    <section
      v-if="meta.roster_lookup_enabled"
      class="mt-4 rounded-card border border-line bg-surface p-4"
    >
      <h2 class="font-display text-title-m font-bold text-ink-1">หรือค้นหาด้วยเลขประจำตัว</h2>
      <form class="mt-2 flex gap-2" @submit.prevent="search">
        <input
          v-model="code"
          inputmode="numeric"
          autocomplete="off"
          placeholder="เลขประจำตัวนักเรียน"
          class="h-11 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body"
          :disabled="busy"
        />
        <button
          type="submit"
          class="h-11 shrink-0 rounded-control bg-surface px-4 text-sm font-semibold text-brand ring-1 ring-brand/30 hover:bg-brand-tint disabled:opacity-50"
          :disabled="busy"
        >
          ค้นหา
        </button>
      </form>
      <p v-if="codeError" class="mt-1 text-caption text-danger">{{ codeError }}</p>
      <p v-if="error" class="mt-1 text-caption text-danger">{{ error }}</p>
    </section>

    <p v-if="meta.stands.length === 0" class="mt-4 text-center text-body text-ink-2">
      งานนี้ยังไม่มีแสตน — ติดต่อผู้ดูแลงาน
    </p>
    <p v-if="!meta.roster_lookup_enabled" class="mt-4 text-center text-caption text-ink-3">
      งานนี้ปิดการค้นหาด้วยเลขประจำตัว — เลือกจากผังแสตนเท่านั้น
    </p>
  </div>
</template>
