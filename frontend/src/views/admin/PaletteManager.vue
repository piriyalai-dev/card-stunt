<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppEmptyState from '@/components/ui/AppEmptyState.vue'
import { useEventContext } from '@/composables/eventContext'
import { autoTextColor, normalizeHex } from '@/lib/color'
import { errorMessage } from '@/lib/format'
import * as palettesService from '@/services/palettes'
import type { ColorCreate, ColorOut, PaletteOut } from '@/types/domain'

const ctx = useEventContext()
const event = ctx?.event

/** ชุดสีมาตรฐาน 12 สี — ใช้ได้ทั้งสร้างใหม่และเติมเข้าชุดเดิม */
const PRESET: Array<{ code: string; name_th: string; hex: string }> = [
  { code: '01', name_th: 'แดง', hex: '#B91C1C' },
  { code: '02', name_th: 'ขาว', hex: '#FFFFFF' },
  { code: '03', name_th: 'ดำ', hex: '#111111' },
  { code: '04', name_th: 'เหลือง', hex: '#FACC15' },
  { code: '05', name_th: 'ส้ม', hex: '#F97316' },
  { code: '06', name_th: 'เขียว', hex: '#15803D' },
  { code: '07', name_th: 'เขียวอ่อน', hex: '#86EFAC' },
  { code: '08', name_th: 'ฟ้า', hex: '#0EA5E9' },
  { code: '09', name_th: 'น้ำเงิน', hex: '#1D4ED8' },
  { code: '10', name_th: 'ม่วง', hex: '#7E22CE' },
  { code: '11', name_th: 'ชมพู', hex: '#EC4899' },
  { code: '12', name_th: 'เทา', hex: '#78716C' },
]

const palettes = ref<PaletteOut[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const selected = computed(() => palettes.value.find((p) => p.id === selectedId.value) ?? null)

const paletteForm = reactive({ name: '', description: '', is_default: false })
const createForm = reactive({ name: 'ชุดสีหลัก', description: '' })
const showCreate = ref(false)

function clearMessages() {
  error.value = ''
  message.value = ''
}

async function load() {
  if (!event?.value) return
  loading.value = true
  clearMessages()
  try {
    palettes.value = await palettesService.listPalettes(event.value.id)
    if (palettes.value.length > 0) {
      if (!palettes.value.some((p) => p.id === selectedId.value)) {
        selectedId.value = palettes.value[0]!.id
      }
    } else {
      selectedId.value = null
    }
    syncPaletteForm()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

watch(selectedId, () => {
  syncPaletteForm()
  editingId.value = null
  clearMessages()
})

function syncPaletteForm() {
  const p = selected.value
  if (!p) return
  paletteForm.name = p.name
  paletteForm.description = p.description ?? ''
  paletteForm.is_default = p.is_default
}

function replacePalette(updated: PaletteOut) {
  palettes.value = palettes.value.map((p) => (p.id === updated.id ? updated : p))
  syncPaletteForm()
}

async function refreshSelected() {
  if (!selected.value) return
  const fresh = await palettesService.getPalette(selected.value.id)
  replacePalette(fresh)
}

// ── สร้าง / นำเข้า ────────────────────────────────────────────────
async function createPalette(withPreset: boolean) {
  if (!event?.value) return
  if (!createForm.name.trim()) {
    error.value = 'ต้องใส่ชื่อชุดสี'
    return
  }
  saving.value = true
  clearMessages()
  try {
    const colors: ColorCreate[] = withPreset
      ? PRESET.map((c, i) => ({
          code: c.code,
          name_th: c.name_th,
          hex: c.hex,
          text_color: autoTextColor(c.hex),
          order_index: i,
        }))
      : []
    const created = await palettesService.createPalette(event.value.id, {
      name: createForm.name.trim(),
      description: createForm.description.trim() || null,
      colors,
    })
    palettes.value = [...palettes.value, created]
    selectedId.value = created.id
    showCreate.value = false
    createForm.name = 'ชุดสีหลัก'
    createForm.description = ''
    message.value = withPreset ? 'สร้างชุดสีจาก preset แล้ว' : 'สร้างชุดสีแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function savePalette() {
  if (!selected.value) return
  saving.value = true
  clearMessages()
  try {
    const updated = await palettesService.updatePalette(selected.value.id, {
      name: paletteForm.name.trim(),
      description: paletteForm.description.trim() || null,
      is_default: paletteForm.is_default,
    })
    replacePalette(updated)
    message.value = 'บันทึกชุดสีแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function removePalette() {
  const p = selected.value
  if (!p) return
  if (!window.confirm(`ลบชุดสี "${p.name}"? สีทั้งหมดในชุดจะหายไปด้วย`)) return
  saving.value = true
  clearMessages()
  try {
    await palettesService.deletePalette(p.id)
    palettes.value = palettes.value.filter((x) => x.id !== p.id)
    selectedId.value = palettes.value[0]?.id ?? null
    message.value = 'ลบชุดสีแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── เพิ่มสี ───────────────────────────────────────────────────────
const addForm = reactive<ColorCreate>({
  code: '',
  name_th: '',
  hex: '#B91C1C',
  text_color: autoTextColor('#B91C1C'),
})

function onAddHexInput() {
  const normalized = normalizeHex(addForm.hex)
  if (normalized) {
    addForm.hex = normalized
    addForm.text_color = autoTextColor(normalized)
  }
}

async function addColor() {
  if (!selected.value) return
  if (!addForm.code.trim() || !addForm.name_th.trim()) {
    error.value = 'ต้องใส่รหัสสีและชื่อสี'
    return
  }
  const hex = normalizeHex(addForm.hex)
  if (!hex) {
    error.value = 'สีต้องอยู่ในรูป #RRGGBB'
    return
  }
  saving.value = true
  clearMessages()
  try {
    await palettesService.addColor(selected.value.id, {
      code: addForm.code.trim(),
      name_th: addForm.name_th.trim(),
      hex,
      text_color: addForm.text_color,
      order_index: selected.value.colors.length,
    })
    await refreshSelected()
    addForm.code = ''
    addForm.name_th = ''
    message.value = 'เพิ่มสีแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function addPresetColors() {
  const p = selected.value
  if (!p) return
  saving.value = true
  clearMessages()
  try {
    const used = new Set(p.colors.map((c) => c.code))
    let added = 0
    let order = p.colors.length
    for (const preset of PRESET) {
      if (used.has(preset.code)) continue
      await palettesService.addColor(p.id, {
        ...preset,
        text_color: autoTextColor(preset.hex),
        order_index: order,
      })
      order += 1
      added += 1
    }
    await refreshSelected()
    message.value = added > 0 ? `เพิ่ม ${added} สีจาก preset` : 'มีสีครบ preset แล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── แก้ไขสี ───────────────────────────────────────────────────────
const editingId = ref<number | null>(null)
const edit = reactive<ColorOut>({
  id: 0,
  code: '',
  name_th: '',
  hex: '#FFFFFF',
  text_color: '#000000',
  order_index: 0,
})

function startEdit(color: ColorOut) {
  editingId.value = color.id
  Object.assign(edit, { ...color })
  clearMessages()
}

function onEditHexInput() {
  const normalized = normalizeHex(edit.hex)
  if (normalized) {
    edit.hex = normalized
    edit.text_color = autoTextColor(normalized)
  }
}

async function saveEdit() {
  if (!selected.value || editingId.value === null) return
  const hex = normalizeHex(edit.hex)
  if (!hex) {
    error.value = 'สีต้องอยู่ในรูป #RRGGBB'
    return
  }
  saving.value = true
  clearMessages()
  try {
    await palettesService.updateColor(selected.value.id, editingId.value, {
      code: edit.code.trim(),
      name_th: edit.name_th.trim(),
      hex,
      text_color: edit.text_color,
    })
    await refreshSelected()
    editingId.value = null
    message.value = 'บันทึกสีแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function moveColor(color: ColorOut, delta: -1 | 1) {
  const p = selected.value
  if (!p) return
  const index = p.colors.findIndex((c) => c.id === color.id)
  const other = p.colors[index + delta]
  if (!other) return
  saving.value = true
  clearMessages()
  try {
    await palettesService.updateColor(p.id, color.id, { order_index: other.order_index })
    await palettesService.updateColor(p.id, other.id, { order_index: color.order_index })
    await refreshSelected()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── ลบสี (ต้องเลือกสีแทนถ้าสีถูกใช้ในฉาก) ────────────────────────
const deletingId = ref<number | null>(null)
const replacementId = ref<number | null>(null)

const deleteTarget = computed(() =>
  selected.value?.colors.find((c) => c.id === deletingId.value) ?? null,
)
const replacementOptions = computed(() =>
  (selected.value?.colors ?? []).filter((c) => c.id !== deletingId.value),
)

function startDelete(color: ColorOut) {
  deletingId.value = color.id
  replacementId.value = replacementOptions.value[0]?.id ?? null
  clearMessages()
}

async function confirmDelete() {
  if (!selected.value || deletingId.value === null) return
  saving.value = true
  clearMessages()
  try {
    await palettesService.deleteColor(
      selected.value.id,
      deletingId.value,
      replacementId.value,
    )
    await refreshSelected()
    deletingId.value = null
    message.value = 'ลบสีแล้ว — ฉากที่ใช้สีนี้ถูกแทนสีให้แล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── JSON import / export ─────────────────────────────────────────
const fileInput = ref<HTMLInputElement | null>(null)

function exportJson() {
  const p = selected.value
  if (!p) return
  const payload = {
    name: p.name,
    description: p.description,
    colors: p.colors.map((c) => ({
      code: c.code,
      name_th: c.name_th,
      hex: c.hex,
      text_color: c.text_color,
    })),
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `palette-${p.id}.json`
  a.click()
  URL.revokeObjectURL(url)
}

async function onImportFile(domEvent: Event) {
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !event?.value) return
  saving.value = true
  clearMessages()
  try {
    const raw = JSON.parse(await file.text()) as {
      name?: unknown
      description?: unknown
      colors?: unknown
    }
    const name = typeof raw.name === 'string' && raw.name.trim() ? raw.name.trim() : 'ชุดสีนำเข้า'
    if (!Array.isArray(raw.colors)) throw new Error('ไฟล์ไม่มีรายการ colors')
    const colors: ColorCreate[] = raw.colors.map((item, index) => {
      const c = item as Record<string, unknown>
      const code = typeof c.code === 'string' ? c.code.trim() : ''
      const nameTh = typeof c.name_th === 'string' ? c.name_th.trim() : ''
      const hex = typeof c.hex === 'string' ? normalizeHex(c.hex) : null
      if (!code || !nameTh || !hex) {
        throw new Error(`สีรายการที่ ${index + 1} ไม่ครบ (code/name_th/hex)`)
      }
      const text = typeof c.text_color === 'string' ? normalizeHex(c.text_color) : null
      return {
        code,
        name_th: nameTh,
        hex,
        text_color: text ?? autoTextColor(hex),
        order_index: index,
      }
    })
    const created = await palettesService.createPalette(event.value.id, {
      name,
      description: typeof raw.description === 'string' ? raw.description : null,
      colors,
    })
    palettes.value = [...palettes.value, created]
    selectedId.value = created.id
    message.value = `นำเข้าชุดสี ${colors.length} สีแล้ว`
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

const textColorPreviewStyle = (hex: string, text: string) => ({
  backgroundColor: hex,
  color: text,
})
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
      <div class="flex flex-wrap items-center gap-2">
        <button
          v-for="palette in palettes"
          :key="palette.id"
          type="button"
          class="inline-flex h-10 items-center gap-1.5 rounded-full border px-3 text-[13px] font-semibold"
          :class="
            selectedId === palette.id
              ? 'border-brand/30 bg-brand-tint text-brand'
              : 'border-line bg-surface text-ink-2 hover:text-ink-1'
          "
          @click="selectedId = palette.id"
        >
          {{ palette.name }}
          <span class="text-[11px] text-ink-3">{{ palette.colors.length }} สี</span>
        </button>
        <AppButton variant="secondary" size="sm" @click="showCreate = !showCreate">
          <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
          ชุดสีใหม่
        </AppButton>
        <AppButton variant="secondary" size="sm" @click="fileInput?.click()">นำเข้า JSON</AppButton>
        <input ref="fileInput" type="file" accept="application/json,.json" class="hidden" @change="onImportFile" />
      </div>

      <AppCard v-if="showCreate" :padded="true">
        <h3 class="font-display text-title-m font-bold mb-3">สร้างชุดสีใหม่</h3>
        <div class="grid gap-3 sm:grid-cols-2">
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">ชื่อชุดสี</label>
            <input v-model="createForm.name" class="field" />
          </div>
          <div>
            <label class="block text-caption font-semibold text-ink-2 mb-1">คำอธิบาย</label>
            <input v-model="createForm.description" class="field" />
          </div>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <AppButton :loading="saving" @click="createPalette(true)">สร้างพร้อม preset 12 สี</AppButton>
          <AppButton variant="secondary" :loading="saving" @click="createPalette(false)">สร้างชุดเปล่า</AppButton>
        </div>
      </AppCard>

      <AppEmptyState
        v-if="!selected"
        icon="bi-palette"
        title="ยังไม่มีชุดสี"
        description="สร้างชุดสีใหม่ (เลือกใช้ preset 12 สีมาตรฐานได้) หรือนำเข้าไฟล์ JSON"
      >
        <AppButton size="sm" @click="showCreate = true">สร้างชุดสี</AppButton>
      </AppEmptyState>

      <template v-else>
        <AppCard :padded="true">
          <div class="flex flex-wrap items-end gap-3">
            <div class="min-w-[180px] flex-1">
              <label class="block text-caption font-semibold text-ink-2 mb-1">ชื่อชุดสี</label>
              <input v-model="paletteForm.name" class="field" />
            </div>
            <div class="min-w-[180px] flex-[2]">
              <label class="block text-caption font-semibold text-ink-2 mb-1">คำอธิบาย</label>
              <input v-model="paletteForm.description" class="field" />
            </div>
            <label class="flex h-11 items-center gap-2 text-sm">
              <input v-model="paletteForm.is_default" type="checkbox" class="h-4 w-4" />
              ใช้เป็นชุดหลัก
            </label>
            <div class="flex gap-2">
              <AppButton :loading="saving" @click="savePalette">บันทึก</AppButton>
              <AppButton variant="danger" @click="removePalette">ลบชุดสี</AppButton>
            </div>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <AppButton variant="secondary" size="sm" :loading="saving" @click="addPresetColors">
              เพิ่มสีจาก preset
            </AppButton>
            <AppButton variant="secondary" size="sm" @click="exportJson">ส่งออก JSON</AppButton>
          </div>
        </AppCard>

        <!-- ตารางสี -->
        <AppCard :padded="false">
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] text-sm">
              <thead class="border-b border-line bg-canvas text-left text-caption text-ink-2">
                <tr>
                  <th class="px-3 py-2 font-semibold">ลำดับ</th>
                  <th class="px-3 py-2 font-semibold">รหัส</th>
                  <th class="px-3 py-2 font-semibold">ชื่อสี</th>
                  <th class="px-3 py-2 font-semibold">สี</th>
                  <th class="px-3 py-2 font-semibold">สีตัวอักษร</th>
                  <th class="px-3 py-2 font-semibold">ตัวอย่าง</th>
                  <th class="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                <tr v-for="(color, index) in selected.colors" :key="color.id" class="border-b border-line last:border-0">
                  <td class="px-3 py-2">
                    <div class="flex items-center gap-1">
                      <span class="w-5 text-ink-3 tabular-nums">{{ index + 1 }}</span>
                      <button
                        type="button"
                        class="grid h-7 w-7 place-items-center rounded text-ink-3 hover:bg-canvas hover:text-ink-1 disabled:opacity-30"
                        :disabled="index === 0"
                        aria-label="เลื่อนขึ้น"
                        @click="moveColor(color, -1)"
                      >
                        <i class="bi bi-chevron-up" aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        class="grid h-7 w-7 place-items-center rounded text-ink-3 hover:bg-canvas hover:text-ink-1 disabled:opacity-30"
                        :disabled="index === selected.colors.length - 1"
                        aria-label="เลื่อนลง"
                        @click="moveColor(color, 1)"
                      >
                        <i class="bi bi-chevron-down" aria-hidden="true" />
                      </button>
                    </div>
                  </td>

                  <template v-if="editingId === color.id">
                    <td class="px-3 py-2"><input v-model="edit.code" class="field !py-1.5" /></td>
                    <td class="px-3 py-2"><input v-model="edit.name_th" class="field !py-1.5" /></td>
                    <td class="px-3 py-2">
                      <input v-model="edit.hex" class="field !py-1.5" @input="onEditHexInput" />
                    </td>
                    <td class="px-3 py-2">
                      <input v-model="edit.text_color" class="field !py-1.5" />
                    </td>
                    <td class="px-3 py-2">
                      <span
                        class="inline-block rounded px-3 py-1 text-sm font-bold"
                        :style="textColorPreviewStyle(edit.hex, edit.text_color)"
                      >
                        {{ edit.code }}
                      </span>
                    </td>
                    <td class="px-3 py-2">
                      <div class="flex gap-1">
                        <AppButton size="sm" :loading="saving" @click="saveEdit">บันทึก</AppButton>
                        <AppButton size="sm" variant="secondary" @click="editingId = null">ยกเลิก</AppButton>
                      </div>
                    </td>
                  </template>

                  <template v-else>
                    <td class="px-3 py-2 font-mono text-[13px]">{{ color.code }}</td>
                    <td class="px-3 py-2">{{ color.name_th }}</td>
                    <td class="px-3 py-2">
                      <span class="inline-flex items-center gap-1.5">
                        <span
                          class="inline-block h-5 w-8 rounded border border-line"
                          :style="{ backgroundColor: color.hex }"
                          aria-hidden="true"
                        />
                        <span class="font-mono text-[12px] text-ink-2">{{ color.hex }}</span>
                      </span>
                    </td>
                    <td class="px-3 py-2 font-mono text-[12px] text-ink-2">{{ color.text_color }}</td>
                    <td class="px-3 py-2">
                      <span
                        class="inline-block rounded px-3 py-1 text-sm font-bold"
                        :style="textColorPreviewStyle(color.hex, color.text_color)"
                      >
                        {{ color.code }}
                      </span>
                    </td>
                    <td class="px-3 py-2">
                      <div class="flex justify-end gap-1">
                        <AppButton size="sm" variant="secondary" @click="startEdit(color)">แก้ไข</AppButton>
                        <AppButton size="sm" variant="danger" @click="startDelete(color)">ลบ</AppButton>
                      </div>
                    </td>
                  </template>
                </tr>
                <tr v-if="selected.colors.length === 0">
                  <td colspan="7" class="px-3 py-6 text-center text-caption text-ink-2">
                    ยังไม่มีสีในชุดนี้ — เพิ่มสีด้านล่างหรือใช้ preset
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppCard>

        <!-- ลบสี -->
        <AppCard v-if="deleteTarget" :padded="true" class="border-danger/30">
          <h3 class="font-display text-title-m font-bold mb-1">
            ลบสี {{ deleteTarget.code }} · {{ deleteTarget.name_th }}
          </h3>
          <p class="text-caption text-ink-2 mb-3">
            ถ้าสีนี้ถูกใช้ในฉาก ระบบจะแทนด้วยสีที่เลือก — ฉากทั้งหมดจะถูกบันทึกใหม่ทันที
          </p>
          <label class="block text-caption font-semibold text-ink-2 mb-1">สีทดแทน</label>
          <select v-model.number="replacementId" class="field max-w-xs">
            <option :value="null">— ไม่มี (ลบได้เฉพาะเมื่อไม่มีฉากใช้) —</option>
            <option v-for="c in replacementOptions" :key="c.id" :value="c.id">
              {{ c.code }} · {{ c.name_th }}
            </option>
          </select>
          <div class="mt-3 flex gap-2">
            <AppButton variant="danger" :loading="saving" @click="confirmDelete">ยืนยันลบสี</AppButton>
            <AppButton variant="secondary" @click="deletingId = null">ยกเลิก</AppButton>
          </div>
        </AppCard>

        <!-- เพิ่มสี -->
        <AppCard :padded="true">
          <h3 class="font-display text-title-m font-bold mb-3">เพิ่มสี</h3>
          <form class="grid gap-3 sm:grid-cols-5" @submit.prevent="addColor">
            <div>
              <label class="block text-caption font-semibold text-ink-2 mb-1">รหัส</label>
              <input v-model="addForm.code" class="field" placeholder="01" required />
            </div>
            <div class="sm:col-span-2">
              <label class="block text-caption font-semibold text-ink-2 mb-1">ชื่อสี</label>
              <input v-model="addForm.name_th" class="field" placeholder="แดงสด" required />
            </div>
            <div>
              <label class="block text-caption font-semibold text-ink-2 mb-1">สี</label>
              <div class="flex gap-1">
                <input v-model="addForm.hex" class="field" @input="onAddHexInput" />
                <input
                  v-model="addForm.hex"
                  type="color"
                  class="h-11 w-11 shrink-0 cursor-pointer rounded-control border border-line bg-surface p-1"
                  aria-label="เลือกสี"
                />
              </div>
            </div>
            <div>
              <label class="block text-caption font-semibold text-ink-2 mb-1">สีตัวอักษร</label>
              <div class="flex gap-1">
                <input v-model="addForm.text_color" class="field" />
                <input
                  v-model="addForm.text_color"
                  type="color"
                  class="h-11 w-11 shrink-0 cursor-pointer rounded-control border border-line bg-surface p-1"
                  aria-label="เลือกสีตัวอักษร"
                />
              </div>
            </div>
            <div class="sm:col-span-5 flex items-center gap-3">
              <span
                class="inline-block rounded px-3 py-1 text-sm font-bold"
                :style="textColorPreviewStyle(addForm.hex || '#FFFFFF', addForm.text_color || '#000000')"
              >
                {{ addForm.code || 'A1' }}
              </span>
              <AppButton type="submit" :loading="saving">เพิ่มสี</AppButton>
            </div>
          </form>
        </AppCard>
      </template>
    </template>
  </div>
</template>
