<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import SeatMapEditor from '@/components/stand/SeatMapEditor.vue'
import { useEventContext } from '@/composables/eventContext'
import { gridSize, seatLabels } from '@/lib/geometry'
import { errorMessage, formatNumber } from '@/lib/format'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import type {
  ColDirection,
  LabelStyle,
  RowDirection,
  StandCreate,
  StandOut,
} from '@/types/domain'

const ctx = useEventContext()
const event = ctx?.event

const MAX_TOTAL_CELLS = 200000

const stands = ref<StandOut[]>([])
const selectedId = ref<number | null>(null)
const mode = ref<'view' | 'create'>('view')
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const stuntCount = ref(0)

const selected = computed(() => stands.value.find((s) => s.id === selectedId.value) ?? null)

interface FormShape {
  name: string
  rows: number
  cols: number
  subRows: number
  subCols: number
  aspect: number
  rowDirection: RowDirection
  colDirection: ColDirection
  rowLabelStyle: LabelStyle
  colLabelStyle: LabelStyle
  rowPrefix: string
  colPrefix: string
}

function emptyForm(): FormShape {
  return {
    name: 'โซนกลาง',
    rows: 9,
    cols: 33,
    subRows: 5,
    subCols: 5,
    aspect: 1,
    rowDirection: 'bottom_to_top',
    colDirection: 'left_to_right',
    rowLabelStyle: 'alpha',
    colLabelStyle: 'numeric',
    rowPrefix: '',
    colPrefix: '',
  }
}

const form = reactive<FormShape>(emptyForm())
const blockedDraft = ref<Array<{ row: number; col: number }>>([])

const geometry = computed(() => ({
  rows: form.rows,
  cols: form.cols,
  subRows: form.subRows,
  subCols: form.subCols,
}))

const size = computed(() => gridSize(geometry.value))
const totalCells = computed(() => size.value.width * size.value.height)
const tooBig = computed(() => totalCells.value > MAX_TOTAL_CELLS)

const sampleLabels = computed(() => {
  const spec = {
    rowStyle: form.rowLabelStyle,
    colStyle: form.colLabelStyle,
    rowPrefix: form.rowPrefix,
    colPrefix: form.colPrefix,
  }
  return {
    first: seatLabels(0, 0, spec),
    last: seatLabels(
      Math.max(0, form.rows - 1),
      Math.max(0, form.cols - 1),
      spec,
    ),
  }
})

const directionHint = computed(() => {
  const rowHint =
    form.rowDirection === 'bottom_to_top'
      ? 'แถวแรกอยู่ด้านล่าง (ชิดสนาม)'
      : 'แถวแรกอยู่ด้านบน'
  const colHint =
    form.colDirection === 'left_to_right'
      ? 'ที่นั่ง 1 อยู่ซ้ายสุด'
      : 'ที่นั่ง 1 อยู่ขวาสุด'
  return `${rowHint} · ${colHint}`
})

function fillFormFromStand(stand: StandOut) {
  form.name = stand.name
  form.rows = stand.rows
  form.cols = stand.cols
  form.subRows = stand.sub_rows
  form.subCols = stand.sub_cols
  form.aspect = stand.seat_aspect_ratio
  form.rowDirection = stand.row_direction
  form.colDirection = stand.col_direction
  form.rowLabelStyle = stand.row_label_style
  form.colLabelStyle = stand.col_label_style
  form.rowPrefix = stand.row_label_prefix
  form.colPrefix = stand.col_label_prefix
  blockedDraft.value = stand.blocked_seats.map((s) => ({ ...s }))
}

function clearMessages() {
  error.value = ''
  message.value = ''
}

async function load() {
  if (!event?.value) return
  loading.value = true
  clearMessages()
  try {
    const [list, stunts] = await Promise.all([
      standsService.listStands(event.value.id),
      stuntsService.listStunts(event.value.id),
    ])
    stands.value = list
    stuntCount.value = stunts.length
    if (list.length === 0) {
      mode.value = 'create'
      form.name = emptyForm().name
    } else if (selectedId.value === null || !list.some((s) => s.id === selectedId.value)) {
      selectedId.value = list[0]!.id
    }
    if (selectedId.value !== null) {
      const stand = list.find((s) => s.id === selectedId.value)
      if (stand) fillFormFromStand(stand)
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(selectedId, () => {
  const stand = selected.value
  if (stand) {
    mode.value = 'view'
    fillFormFromStand(stand)
    clearMessages()
  }
})

function startCreate() {
  mode.value = 'create'
  selectedId.value = null
  Object.assign(form, emptyForm())
  blockedDraft.value = []
  clearMessages()
}

function validateDimensions(): string | null {
  if (!Number.isInteger(form.rows) || form.rows <= 0) return 'จำนวนแถวต้องมากกว่า 0'
  if (!Number.isInteger(form.cols) || form.cols <= 0) return 'จำนวนที่นั่งต่อแถวต้องมากกว่า 0'
  if (form.subRows < 1 || form.subRows > 16) return 'ช่องย่อยต่อแถวต้องอยู่ระหว่าง 1–16'
  if (form.subCols < 1 || form.subCols > 16) return 'ช่องย่อยต่อที่นั่งต้องอยู่ระหว่าง 1–16'
  if (tooBig.value) return `กริดรวม ${formatNumber(totalCells.value)} ช่อง เกินเพดาน ${formatNumber(MAX_TOTAL_CELLS)}`
  return null
}

async function createStand() {
  if (!event?.value) return
  const problem = validateDimensions()
  if (problem) {
    error.value = problem
    return
  }
  saving.value = true
  clearMessages()
  try {
    const body: StandCreate = {
      name: form.name.trim() || 'แสตน',
      rows: form.rows,
      cols: form.cols,
      sub_rows: form.subRows,
      sub_cols: form.subCols,
      seat_aspect_ratio: form.aspect,
      row_direction: form.rowDirection,
      col_direction: form.colDirection,
      row_label_style: form.rowLabelStyle,
      col_label_style: form.colLabelStyle,
      row_label_prefix: form.rowPrefix,
      col_label_prefix: form.colPrefix,
      blocked_seats: blockedDraft.value,
    }
    const created = await standsService.createStand(event.value.id, body)
    stands.value = [...stands.value, created]
    selectedId.value = created.id
    mode.value = 'view'
    message.value = 'สร้างแสตนแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function saveMetadata() {
  if (!event?.value || !selected.value) return
  saving.value = true
  clearMessages()
  try {
    const updated = await standsService.updateStand(event.value.id, selected.value.id, {
      name: form.name.trim(),
      seat_aspect_ratio: form.aspect,
      row_direction: form.rowDirection,
      col_direction: form.colDirection,
      row_label_style: form.rowLabelStyle,
      col_label_style: form.colLabelStyle,
      row_label_prefix: form.rowPrefix,
      col_label_prefix: form.colPrefix,
    })
    replaceStand(updated)
    message.value = 'บันทึกการตั้งค่าแสตนแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

function replaceStand(updated: StandOut) {
  stands.value = stands.value.map((s) => (s.id === updated.id ? updated : s))
  fillFormFromStand(updated)
}

async function saveBlocked() {
  if (!selected.value) return
  saving.value = true
  clearMessages()
  try {
    const updated = await standsService.setBlockedSeats(
      selected.value.id,
      blockedDraft.value,
    )
    replaceStand(updated)
    message.value = 'บันทึกช่องที่บล็อกแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── resize ────────────────────────────────────────────────────────
const resize = reactive({
  rows: 0,
  cols: 0,
  subRows: 5,
  subCols: 5,
  allowCrop: false,
})
const showResize = ref(false)

function openResize() {
  if (!selected.value) return
  resize.rows = selected.value.rows
  resize.cols = selected.value.cols
  resize.subRows = selected.value.sub_rows
  resize.subCols = selected.value.sub_cols
  resize.allowCrop = false
  showResize.value = true
  clearMessages()
}

const resizeSize = computed(() =>
  gridSize({
    rows: resize.rows,
    cols: resize.cols,
    subRows: resize.subRows,
    subCols: resize.subCols,
  }),
)
const resizeTooBig = computed(
  () => resizeSize.value.width * resizeSize.value.height > MAX_TOTAL_CELLS,
)

async function applyResize() {
  if (!selected.value) return
  if (resizeTooBig.value) {
    error.value = 'ขนาดใหม่เกินเพดานกริด'
    return
  }
  if (
    stuntCount.value > 0 &&
    !window.confirm(
      `แสตนนี้มี ${stuntCount.value} ฉากที่อาจมีพิกเซลอยู่แล้ว\n` +
        'การเปลี่ยนขนาดจะครอป/เติมพิกเซลแบบยึดมุมบนซ้าย และเก็บ revision ไว้ให้ย้อนได้\nดำเนินการต่อ?',
    )
  ) {
    return
  }
  saving.value = true
  clearMessages()
  try {
    const updated = await standsService.resizeStand(selected.value.id, {
      rows: resize.rows,
      cols: resize.cols,
      sub_rows: resize.subRows,
      sub_cols: resize.subCols,
      allow_crop: stuntCount.value > 0 ? true : resize.allowCrop,
    })
    replaceStand(updated)
    // blocked ที่หลุดขอบใหม่ — ลองบันทึกเฉพาะที่ยังอยู่ในขอบ
    const filtered = updated.blocked_seats.filter(
      (s) => s.row < updated.rows && s.col < updated.cols,
    )
    if (filtered.length !== updated.blocked_seats.length) {
      const fixed = await standsService.setBlockedSeats(updated.id, filtered)
      replaceStand(fixed)
    }
    showResize.value = false
    message.value = 'ปรับขนาดแสตนแล้ว — ตรวจผังและแก้ช่องที่บล็อกอีกครั้ง'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

function clearBlocked() {
  blockedDraft.value = []
}

const rowDirectionOptions: Array<{ value: RowDirection; label: string }> = [
  { value: 'bottom_to_top', label: 'ล่าง → บน (แถว 1 อยู่ล่าง)' },
  { value: 'top_to_bottom', label: 'บน → ล่าง (แถว 1 อยู่บน)' },
]
const colDirectionOptions: Array<{ value: ColDirection; label: string }> = [
  { value: 'left_to_right', label: 'ซ้าย → ขวา' },
  { value: 'right_to_left', label: 'ขวา → ซ้าย' },
]
const labelStyleOptions: Array<{ value: LabelStyle; label: string }> = [
  { value: 'numeric', label: 'ตัวเลข 1, 2, 3…' },
  { value: 'alpha', label: 'ตัวอักษร A, B, C…' },
]

const seatsCount = computed(() => form.rows * form.cols - blockedDraft.value.length)

/** กัน canvas ผังใหญ่เกินเป็นร้อยล้านพิกเซล — ผังจริงงานโรงเรียนอยู่ราว 4,000 ที่นั่ง */
const seatMapTooLarge = computed(() => form.rows * form.cols > 20000)
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong">
      {{ message }}
    </p>

    <div v-if="loading" class="h-40 rounded-card border border-line bg-surface skeleton-shimmer" />

    <template v-else>
      <!-- เลือก/สร้างแสตน -->
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="stand in stands"
          :key="stand.id"
          type="button"
          class="inline-flex h-10 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold"
          :class="
            selectedId === stand.id && mode === 'view'
              ? 'border-brand/30 bg-brand-tint text-brand'
              : 'border-line bg-surface text-ink-2 hover:text-ink-1'
          "
          @click="selectedId = stand.id"
        >
          {{ stand.name }}
          <span class="text-[11px] text-ink-3">{{ stand.rows }}×{{ stand.cols }}</span>
        </button>
        <AppButton variant="secondary" size="sm" @click="startCreate">
          <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
          สร้างแสตนใหม่
        </AppButton>
      </div>

      <!-- ฟอร์ม (สร้าง/แก้ไข ใช้ร่วมกัน) -->
      <AppCard :padded="true">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 class="font-display text-title-m font-bold">
            {{ mode === 'create' ? 'สร้างแสตนใหม่' : `ตั้งค่า: ${selected?.name ?? ''}` }}
          </h3>
          <span class="text-caption text-ink-2">
            กริด {{ size.width }} × {{ size.height }} = {{ formatNumber(totalCells) }} ช่อง
          </span>
        </div>

        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div class="sm:col-span-2">
            <label class="block text-caption font-semibold text-ink-2 mb-1">ชื่อแสตน</label>
            <input v-model="form.name" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">จำนวนแถว</label>
            <input v-model.number="form.rows" type="number" min="1" class="field" :disabled="mode === 'view'" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ที่นั่งต่อแถว</label>
            <input v-model.number="form.cols" type="number" min="1" class="field" :disabled="mode === 'view'" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ช่องย่อย/แถว</label>
            <input v-model.number="form.subRows" type="number" min="1" max="16" class="field" :disabled="mode === 'view'" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ช่องย่อย/ที่นั่ง</label>
            <input v-model.number="form.subCols" type="number" min="1" max="16" class="field" :disabled="mode === 'view'" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">สัดส่วนเพลท</label>
            <input v-model.number="form.aspect" type="number" step="0.1" min="0.4" max="2.5" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ทิศทางแถว</label>
            <select v-model="form.rowDirection" class="field">
              <option v-for="opt in rowDirectionOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ทิศทางที่นั่ง</label>
            <select v-model="form.colDirection" class="field">
              <option v-for="opt in colDirectionOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ป้ายแถว</label>
            <select v-model="form.rowLabelStyle" class="field">
              <option v-for="opt in labelStyleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ป้ายที่นั่ง</label>
            <select v-model="form.colLabelStyle" class="field">
              <option v-for="opt in labelStyleOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">คำนำหน้าแถว</label>
            <input v-model="form.rowPrefix" class="field" placeholder="เช่น แถว " />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">คำนำหน้าที่นั่ง</label>
            <input v-model="form.colPrefix" class="field" placeholder="เช่น ที่นั่ง " />
          </div>
        </div>

        <p class="mt-3 text-caption text-ink-2">
          {{ directionHint }} · ตัวอย่างป้าย: <b>{{ sampleLabels.first.row }} / {{ sampleLabels.first.col }}</b>
          … <b>{{ sampleLabels.last.row }} / {{ sampleLabels.last.col }}</b>
          · {{ formatNumber(seatsCount) }} ที่นั่งใช้งาน
        </p>
        <p v-if="tooBig" class="mt-1 text-caption text-danger">
          กริดรวมเกินเพดาน {{ formatNumber(MAX_TOTAL_CELLS) }} ช่อง — ลดจำนวนที่นั่งหรือช่องย่อย
        </p>

        <div class="mt-3 flex flex-wrap gap-2">
          <AppButton v-if="mode === 'create'" :loading="saving" @click="createStand">สร้างแสตน</AppButton>
          <template v-else>
            <AppButton :loading="saving" @click="saveMetadata">บันทึกการตั้งค่า</AppButton>
            <AppButton variant="secondary" @click="openResize">ปรับขนาดแสตน</AppButton>
          </template>
        </div>
      </AppCard>

      <!-- ปรับขนาด (แยกจาก metadata เพราะมีผลกับ grid ของทุกฉาก) -->
      <AppCard v-if="showResize && selected" :padded="true">
        <h3 class="font-display text-title-m font-bold mb-1">ปรับขนาดแสตน</h3>
        <p class="text-caption text-ink-2 mb-3">
          มีผลกับกริดของทุกฉากในแสตนนี้ ({{ stuntCount }} ฉาก) — ระบบจะครอป/เติมพิกเซลแบบยึดมุมบนซ้าย
          และเก็บ revision ให้ย้อนกลับได้
        </p>
        <div class="grid gap-3 sm:grid-cols-4">
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">แถว</label>
            <input v-model.number="resize.rows" type="number" min="1" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ที่นั่งต่อแถว</label>
            <input v-model.number="resize.cols" type="number" min="1" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ช่องย่อย/แถว</label>
            <input v-model.number="resize.subRows" type="number" min="1" max="16" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ช่องย่อย/ที่นั่ง</label>
            <input v-model.number="resize.subCols" type="number" min="1" max="16" class="field" />
          </div>
        </div>
        <p class="mt-2 text-caption" :class="resizeTooBig ? 'text-danger' : 'text-ink-2'">
          กริดใหม่ {{ resizeSize.width }} × {{ resizeSize.height }} =
          {{ formatNumber(resizeSize.width * resizeSize.height) }} ช่อง
        </p>
        <div class="mt-3 flex gap-2">
          <AppButton :loading="saving" :disabled="resizeTooBig" @click="applyResize">ปรับขนาด</AppButton>
          <AppButton variant="secondary" @click="showResize = false">ยกเลิก</AppButton>
        </div>
      </AppCard>

      <!-- ผังแสตน -->
      <AppCard :padded="true">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 class="font-display text-title-m font-bold">ผังที่นั่ง</h3>
          <div class="flex gap-2">
            <AppButton variant="secondary" size="sm" @click="clearBlocked">ล้างช่องทั้งหมด</AppButton>
            <AppButton v-if="mode === 'view'" size="sm" :loading="saving" @click="saveBlocked">
              บันทึกช่องที่บล็อก
            </AppButton>
          </div>
        </div>
        <p
          v-if="seatMapTooLarge"
          class="rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-caption text-warn"
        >
          ผังนี้มี {{ formatNumber(form.rows * form.cols) }} ที่นั่ง — ใหญ่เกินกว่าจะวาดบนจอได้ลื่น
          (เพดานแสดงผล 20,000 ที่นั่ง) · ลดจำนวนแถว/ที่นั่ง หรือยอมรับว่าจะมาร์กช่องด้วยผังไม่ได้
        </p>
        <SeatMapEditor
          v-else
          v-model:blocked="blockedDraft"
          :rows="form.rows"
          :cols="form.cols"
          :row-direction="form.rowDirection"
          :col-direction="form.colDirection"
          :row-label-style="form.rowLabelStyle"
          :col-label-style="form.colLabelStyle"
          :row-prefix="form.rowPrefix"
          :col-prefix="form.colPrefix"
        />
        <p v-if="mode === 'create'" class="mt-2 text-caption text-ink-3">
          ช่องที่มาร์กจะถูกบันทึกพร้อมการสร้างแสตน
        </p>
      </AppCard>
    </template>
  </div>
</template>
