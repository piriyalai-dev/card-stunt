<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppEmptyState from '@/components/ui/AppEmptyState.vue'
import { useEventContext } from '@/composables/eventContext'
import { STUNT_STATUS } from '@/constants/status'
import { errorMessage, formatDateTime } from '@/lib/format'
import * as eventsService from '@/services/events'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import { useAuthStore } from '@/stores/auth'
import type { Side, StandOut, StuntCreate, StuntOut, StuntStatus } from '@/types/domain'

const authStore = useAuthStore()
const router = useRouter()
const ctx = useEventContext()
const event = ctx?.event

const canPublish = computed(() => authStore.hasPermission('PUBLISH_STUNTS'))

const stunts = ref<StuntOut[]>([])
const stands = ref<StandOut[]>([])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const message = ref('')

const flatMode = ref(false)
const sideFilter = ref<'ALL' | Side>('ALL')

async function load() {
  if (!event?.value) return
  loading.value = true
  error.value = ''
  const id = event.value.id
  try {
    const [st, sd] = await Promise.all([
      stuntsService.listStunts(id),
      standsService.listStands(id),
    ])
    stunts.value = [...st].sort((a, b) => a.order_index - b.order_index || a.id - b.id)
    stands.value = sd
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

function standName(id: number): string {
  return stands.value.find((s) => s.id === id)?.name ?? `#${id}`
}

const visibleStunts = computed(() =>
  sideFilter.value === 'ALL' ? stunts.value : stunts.value.filter((s) => s.side === sideFilter.value),
)

const groups = computed(() => {
  const map = new Map<string, StuntOut[]>()
  for (const stunt of visibleStunts.value) {
    const key = stunt.section?.trim() || 'ไม่มีกลุ่ม'
    const list = map.get(key) ?? []
    list.push(stunt)
    map.set(key, list)
  }
  return Array.from(map, ([label, items]) => ({ label, items }))
})

// ── editor (create + edit) ───────────────────────────────────────
interface Draft {
  id: number | null
  code: string
  title: string
  section: string
  notes: string
  status: StuntStatus
  stand_id: number | null
  side: Side
}

const editorOpen = ref(false)
const draft = reactive<Draft>({
  id: null,
  code: '',
  title: '',
  section: '',
  notes: '',
  status: 'draft',
  stand_id: null,
  side: 'A',
})
const formError = ref('')

function openCreate() {
  if (stands.value.length === 0) {
    error.value = 'ต้องสร้างแสตนก่อนจึงจะสร้างฉากได้'
    return
  }
  Object.assign(draft, {
    id: null,
    code: '',
    title: '',
    section: '',
    notes: '',
    status: 'draft',
    stand_id: stands.value[0]!.id,
    side: 'A' as Side,
  })
  formError.value = ''
  editorOpen.value = true
}

function openEdit(stunt: StuntOut) {
  Object.assign(draft, {
    id: stunt.id,
    code: stunt.code,
    title: stunt.title,
    section: stunt.section ?? '',
    notes: stunt.notes ?? '',
    status: stunt.status,
    stand_id: stunt.stand_id,
    side: stunt.side,
  })
  formError.value = ''
  editorOpen.value = true
}

async function saveDraft() {
  if (!event?.value) return
  if (!draft.code.trim() || !draft.title.trim()) {
    formError.value = 'ต้องใส่รหัสและชื่อฉาก'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    if (draft.id === null) {
      const body: StuntCreate = {
        code: draft.code.trim(),
        title: draft.title.trim(),
        section: draft.section.trim() || null,
        notes: draft.notes.trim() || null,
        order_index: stunts.value.length,
        stand_id: draft.stand_id,
        side: draft.side,
      }
      await stuntsService.createStunt(event.value.id, body)
      message.value = 'สร้างฉากแล้ว'
    } else {
      await stuntsService.updateStunt(draft.id, {
        code: draft.code.trim(),
        title: draft.title.trim(),
        section: draft.section.trim(),
        notes: draft.notes.trim(),
        status: draft.status,
        side: draft.side,
      })
      message.value = 'บันทึกฉากแล้ว'
    }
    editorOpen.value = false
    await load()
  } catch (e) {
    formError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function duplicateStunt(stunt: StuntOut) {
  if (!event?.value) return
  const code = window.prompt('รหัสของฉากสำเนา', `${stunt.code}-copy`)
  if (!code?.trim()) return
  saving.value = true
  error.value = ''
  message.value = ''
  let createdId: number | null = null
  try {
    const created = await stuntsService.createStunt(event.value.id, {
      code: code.trim(),
      title: `${stunt.title} (สำเนา)`,
      section: stunt.section,
      notes: stunt.notes,
      // order_index เดียวกับต้นฉบับ + id ใหม่ที่มากกว่า ⇒ อยู่ถัดจากต้นฉบับทันที
      order_index: stunt.order_index,
      stand_id: stunt.stand_id,
      side: stunt.side,
    })
    createdId = created.id
    const size = stunt.grid_width * stunt.grid_height
    const grid = await stuntsService.getGrid(stunt.id)
    if (grid.grid_data.length === size) {
      await stuntsService.saveGrid(created.id, {
        grid_data: grid.grid_data,
        note: `สำเนาจากฉาก ${stunt.code}`,
      })
    }
    await load()
    message.value = `ทำสำเนาฉาก ${stunt.code} แล้ว`
  } catch (e) {
    if (createdId !== null) {
      try {
        await stuntsService.deleteStunt(createdId)
      } catch {
        /* ลบไม่ได้ก็ปล่อยเป็นฉากร่าง — ผู้ใช้ลบเองได้ */
      }
    }
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function removeStunt(stunt: StuntOut) {
  if (!window.confirm(`ลบฉาก ${stunt.code} · ${stunt.title}? ประวัติ revision จะถูกลบตาม`)) return
  saving.value = true
  error.value = ''
  try {
    await stuntsService.deleteStunt(stunt.id)
    stunts.value = stunts.value.filter((s) => s.id !== stunt.id)
    message.value = 'ลบฉากแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── reorder ───────────────────────────────────────────────────────
async function persistOrder(ids: number[]) {
  if (!event?.value) return
  const byId = new Map(stunts.value.map((s) => [s.id, s]))
  stunts.value = ids.map((id) => byId.get(id)!).filter(Boolean)
  saving.value = true
  try {
    await stuntsService.reorderStunts(event.value.id, ids)
  } catch (e) {
    error.value = errorMessage(e)
    await load()
  } finally {
    saving.value = false
  }
}

async function move(stunt: StuntOut, delta: -1 | 1) {
  const ids = stunts.value.map((s) => s.id)
  const index = ids.indexOf(stunt.id)
  const target = index + delta
  if (index < 0 || target < 0 || target >= ids.length) return
  const [moved] = ids.splice(index, 1)
  ids.splice(target, 0, moved!)
  await persistOrder(ids)
}

const draggingId = ref<number | null>(null)

function onDragStart(stunt: StuntOut) {
  draggingId.value = stunt.id
}

function onDrop(target: StuntOut) {
  const from = draggingId.value
  draggingId.value = null
  if (from === null || from === target.id) return
  const ids = stunts.value.map((s) => s.id)
  const fromIndex = ids.indexOf(from)
  const toIndex = ids.indexOf(target.id)
  if (fromIndex < 0 || toIndex < 0) return
  const [moved] = ids.splice(fromIndex, 1)
  ids.splice(toIndex, 0, moved!)
  void persistOrder(ids)
}

// ── publish ───────────────────────────────────────────────────────
const publishing = ref(false)

async function publish() {
  if (!event?.value) return
  const unpublished = stunts.value.filter((s) => s.status !== 'published').length
  const ok = window.confirm(
    `เผยแพร่ทุกฉาก (${stunts.value.length} ฉาก · ยังไม่เผยแพร่ ${unpublished})?\n` +
      'ผู้ชมจะเห็นเวอร์ชันใหม่ทันที',
  )
  if (!ok) return
  publishing.value = true
  error.value = ''
  try {
    await eventsService.publishEvent(event.value.id)
    await ctx?.reload()
    await load()
    message.value = 'เผยแพร่ทุกฉากแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    publishing.value = false
  }
}

function openStudio(stunt: StuntOut) {
  router.push({ name: 'stunt-studio', params: { stuntId: stunt.id } })
}

function openConvert(stunt: StuntOut) {
  router.push({ name: 'stunt-convert', params: { stuntId: stunt.id } })
}

function openUpload() {
  if (!event?.value) return
  router.push({ name: 'stunt-upload', params: { eventId: event.value.id } })
}

const statusOptions = (Object.keys(STUNT_STATUS) as StuntStatus[]).map((key) => ({
  key,
  ...STUNT_STATUS[key],
}))
</script>

<template>
  <div class="space-y-4">
    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong">
      {{ message }}
    </p>

    <div class="flex flex-wrap items-center gap-2">
      <AppButton size="sm" :disabled="stands.length === 0" @click="openCreate">
        <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
        สร้างฉาก
      </AppButton>
      <AppButton size="sm" variant="secondary" :disabled="stands.length === 0" @click="openUpload">
        <template #icon><i class="bi bi-image" aria-hidden="true" /></template>
        อัปโหลดรูป
      </AppButton>
      <AppButton variant="secondary" size="sm" @click="flatMode = !flatMode">
        <template #icon><i class="bi bi-arrows-move" aria-hidden="true" /></template>
        {{ flatMode ? 'มุมมองกลุ่ม' : 'โหมดเรียงลำดับ' }}
      </AppButton>
      <div class="inline-flex rounded-control border border-line p-0.5">
        <button
          v-for="opt in (['ALL', 'A', 'B'] as const)"
          :key="opt"
          type="button"
          class="h-8 rounded-[10px] px-3 text-[13px] font-semibold"
          :class="sideFilter === opt ? 'bg-brand text-white' : 'text-ink-2'"
          @click="sideFilter = opt"
        >
          {{ opt === 'ALL' ? 'ทั้งหมด' : `ด้าน ${opt}` }}
        </button>
      </div>
      <AppButton
        v-if="canPublish"
        size="sm"
        class="ml-auto"
        :loading="publishing"
        :disabled="stunts.length === 0"
        @click="publish"
      >
        <template #icon><i class="bi bi-send" aria-hidden="true" /></template>
        เผยแพร่ทุกฉาก
      </AppButton>
    </div>

    <p v-if="stands.length === 0" class="rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-caption text-warn">
      ยังไม่มีแสตน — ไปที่แท็บ "ตั้งค่าแสตน" เพื่อสร้างก่อน แล้วจึงสร้างฉากได้
    </p>

    <div v-if="loading" class="grid gap-3 sm:grid-cols-2">
      <div v-for="n in 4" :key="n" class="h-32 rounded-card border border-line bg-surface skeleton-shimmer" />
    </div>

    <AppEmptyState
      v-else-if="stunts.length === 0"
      icon="bi-easel2"
      title="ยังไม่มีฉาก"
      description="สร้างฉากแรก แล้ววาดพิกเซลด้วยมือหรือแปลงจากรูป"
    >
      <AppButton size="sm" :disabled="stands.length === 0" @click="openCreate">สร้างฉากแรก</AppButton>
    </AppEmptyState>

    <!-- ฟอร์มสร้าง/แก้ไข -->
    <AppCard v-if="editorOpen" :padded="true">
      <h3 class="font-display text-title-m font-bold mb-3">
        {{ draft.id === null ? 'สร้างฉากใหม่' : `แก้ไขฉาก ${draft.code}` }}
      </h3>
      <form class="grid gap-3 sm:grid-cols-2" @submit.prevent="saveDraft">
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1">รหัสฉาก</label>
          <input v-model="draft.code" class="field" placeholder="01" required />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1">ชื่อฉาก</label>
          <input v-model="draft.title" class="field" placeholder="เปิดตัว" required />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1">กลุ่ม/ช่วง</label>
          <input v-model="draft.section" class="field" placeholder="เช่น เพลงเชียร์ 1" />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1">แสตน</label>
          <select
            v-model.number="draft.stand_id"
            class="field"
            :disabled="draft.id !== null"
          >
            <option v-for="stand in stands" :key="stand.id" :value="stand.id">
              {{ stand.name }} ({{ stand.rows }}×{{ stand.cols }})
            </option>
          </select>
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1">ด้าน</label>
          <select v-model="draft.side" class="field">
            <option value="A">ด้าน A</option>
            <option value="B">ด้าน B</option>
          </select>
        </div>
        <div v-if="draft.id !== null">
          <label class="block text-caption font-semibold text-ink-2 mb-1">สถานะ</label>
          <select v-model="draft.status" class="field">
            <option v-for="opt in statusOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
        </div>
        <div class="sm:col-span-2">
          <label class="block text-caption font-semibold text-ink-2 mb-1">หมายเหตุ</label>
          <textarea v-model="draft.notes" class="field" rows="2" placeholder="คำใบ้ให้เด็ก เช่น ยกค้าง 8 จังหวะ" />
        </div>
        <p v-if="formError" class="sm:col-span-2 text-caption text-danger">{{ formError }}</p>
        <div class="sm:col-span-2 flex gap-2">
          <AppButton type="submit" :loading="saving">บันทึก</AppButton>
          <AppButton variant="secondary" @click="editorOpen = false">ยกเลิก</AppButton>
        </div>
      </form>
    </AppCard>

    <!-- โหมดเรียงลำดับ (ลากได้) -->
    <AppCard v-if="flatMode && stunts.length > 0" :padded="true">
      <h3 class="font-display text-title-m font-bold mb-1">เรียงลำดับฉาก</h3>
      <p class="text-caption text-ink-2 mb-3">ลากการ์ดเพื่อจัดลำดับ หรือใช้ปุ่มขึ้น/ลง (ใช้งานได้บนมือถือ)</p>
      <ul class="space-y-2">
        <li
          v-for="(stunt, index) in stunts"
          :key="stunt.id"
          draggable="true"
          class="flex items-center gap-3 rounded-control border border-line bg-surface px-3 py-2"
          :class="draggingId === stunt.id ? 'opacity-50' : ''"
          @dragstart="onDragStart(stunt)"
          @dragover.prevent
          @drop="onDrop(stunt)"
        >
          <span class="w-6 text-center text-caption font-bold text-ink-3 tabular-nums">{{ index + 1 }}</span>
          <i class="bi bi-grip-vertical text-ink-3" aria-hidden="true" />
          <span class="font-mono text-[13px] text-ink-2">{{ stunt.code }}</span>
          <span class="min-w-0 flex-1 truncate">{{ stunt.title }}</span>
          <span class="text-caption text-ink-3">{{ stunt.section || 'ไม่มีกลุ่ม' }}</span>
          <AppButton size="sm" variant="secondary" :disabled="index === 0" @click="move(stunt, -1)">ขึ้น</AppButton>
          <AppButton
            size="sm"
            variant="secondary"
            :disabled="index === stunts.length - 1"
            @click="move(stunt, 1)"
          >
            ลง
          </AppButton>
        </li>
      </ul>
    </AppCard>

    <!-- มุมมองกลุ่ม -->
    <template v-else-if="!loading && stunts.length > 0">
      <section v-for="group in groups" :key="group.label" class="space-y-2">
        <h3 class="text-caption font-bold text-ink-2">{{ group.label }}</h3>
        <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <AppCard v-for="stunt in group.items" :key="stunt.id" :padded="true" class="flex flex-col">
            <div class="flex items-start gap-2">
              <div class="grid h-10 w-10 shrink-0 place-items-center rounded-control bg-canvas font-mono text-sm font-bold text-ink-1">
                {{ stunt.code }}
              </div>
              <div class="min-w-0 flex-1">
                <h4 class="truncate font-semibold">{{ stunt.title }}</h4>
                <p class="text-caption text-ink-2">
                  {{ standName(stunt.stand_id) }} · {{ stunt.grid_width }}×{{ stunt.grid_height }}
                </p>
              </div>
              <span
                class="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold"
                :class="STUNT_STATUS[stunt.status].className"
              >
                {{ STUNT_STATUS[stunt.status].label }}
              </span>
            </div>

            <p class="mt-2 text-caption text-ink-2">
              <span
                class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                :class="stunt.side === 'A' ? 'bg-brand-tint text-brand' : 'bg-canvas text-ink-2'"
              >
                ด้าน {{ stunt.side }}
              </span>
            </p>
            <p v-if="stunt.notes" class="mt-1 line-clamp-2 text-caption text-ink-3">{{ stunt.notes }}</p>
            <p class="mt-1 text-[11px] text-ink-3">แก้ล่าสุด {{ formatDateTime(stunt.updated_at) }}</p>

            <div class="mt-3 flex flex-wrap gap-1.5">
              <AppButton size="sm" @click="openStudio(stunt)">เปิด Studio</AppButton>
              <AppButton size="sm" variant="secondary" @click="openConvert(stunt)">แปลงรูป</AppButton>
              <AppButton size="sm" variant="secondary" @click="openEdit(stunt)">แก้ไข</AppButton>
              <AppButton size="sm" variant="secondary" :loading="saving" @click="duplicateStunt(stunt)">
                ทำสำเนา
              </AppButton>
              <AppButton size="sm" variant="danger" class="ml-auto" @click="removeStunt(stunt)">ลบ</AppButton>
            </div>
          </AppCard>
        </div>
      </section>
    </template>

    <p class="text-caption text-ink-3">
      <RouterLink :to="{ name: 'event-palettes', params: { eventId: event?.id } }" class="hover:text-brand">
        จัดการชุดสี
      </RouterLink>
      ·
      <RouterLink :to="{ name: 'event-stands', params: { eventId: event?.id } }" class="hover:text-brand">
        ตั้งค่าแสตน
      </RouterLink>
    </p>
  </div>
</template>
