<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import QrCode from '@/components/QrCode.vue'
import { useEventContext } from '@/composables/eventContext'
import { EVENT_STATUS } from '@/constants/status'
import { errorMessage, formatDateTime, formatNumber, toDateInputValue } from '@/lib/format'
import * as eventsService from '@/services/events'
import * as palettesService from '@/services/palettes'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import { useAuthStore } from '@/stores/auth'
import type { EventStatus, PaletteOut, StandOut, StuntOut } from '@/types/domain'

const authStore = useAuthStore()
const router = useRouter()
const ctx = useEventContext()
const event = ctx?.event

const loading = ref(true)
const error = ref('')
const actionError = ref('')
const actionMessage = ref('')

const stands = ref<StandOut[]>([])
const palettes = ref<PaletteOut[]>([])
const stunts = ref<StuntOut[]>([])

const canManageEvent = computed(() => authStore.hasPermission('MANAGE_EVENTS'))

// ── ลิงก์ผู้ชม + QR ────────────────────────────────────────────────
const viewerUrl = computed(() => {
  const ev = event?.value
  return ev ? `${window.location.origin}/e/${ev.slug}` : ''
})
const copied = ref(false)

async function copyViewerUrl(): Promise<void> {
  try {
    await navigator.clipboard.writeText(viewerUrl.value)
    copied.value = true
    window.setTimeout(() => (copied.value = false), 2000)
  } catch {
    /* clipboard ต้องการ secure context — ปล่อยให้ copy เองจาก code block */
  }
}

function openViewer(): void {
  if (viewerUrl.value) window.open(viewerUrl.value, '_blank')
}
const canPublish = computed(() => authStore.hasPermission('PUBLISH_STUNTS'))
const canStands = computed(() => authStore.hasPermission('MANAGE_STANDS'))
const canPalettes = computed(() => authStore.hasPermission('MANAGE_PALETTES'))
const canStunts = computed(() => authStore.hasPermission('MANAGE_STUNTS'))

const stats = computed(() => {
  const seats = stands.value.reduce((sum, s) => sum + s.rows * s.cols - s.blocked_seats.length, 0)
  const colors = palettes.value.reduce((sum, p) => sum + p.colors.length, 0)
  return {
    seats,
    colors,
    stands: stands.value.length,
    stunts: stunts.value.length,
    colorSets: palettes.value.length,
    publishedStunts: stunts.value.filter((s) => s.status === 'published').length,
  }
})

async function load() {
  if (!event?.value) return
  loading.value = true
  error.value = ''
  const id = event.value.id
  try {
    const [s, p, st] = await Promise.all([
      standsService.listStands(id),
      palettesService.listPalettes(id),
      stuntsService.listStunts(id),
    ])
    stands.value = s
    palettes.value = p
    stunts.value = st
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── ตั้งค่างาน ────────────────────────────────────────────────────
const settings = reactive({
  name: '',
  description: '',
  event_date: '',
  status: 'draft' as EventStatus,
  public_access_enabled: false,
  palette_a_id: null as number | null,
  palette_b_id: null as number | null,
})
const saving = ref(false)
const settingsError = ref('')

function syncSettings() {
  if (!event?.value) return
  settings.name = event.value.name
  settings.description = event.value.description ?? ''
  settings.event_date = toDateInputValue(event.value.event_date)
  settings.status = event.value.status
  settings.public_access_enabled = event.value.public_access_enabled
  settings.palette_a_id = event.value.palette_a_id
  settings.palette_b_id = event.value.palette_b_id
}

onMounted(syncSettings)

async function saveSettings() {
  if (!event?.value) return
  saving.value = true
  settingsError.value = ''
  try {
    await eventsService.updateEvent(event.value.id, {
      name: settings.name.trim(),
      description: settings.description.trim() || undefined,
      event_date: settings.event_date || undefined,
      status: settings.status,
      public_access_enabled: settings.public_access_enabled,
      palette_a_id: settings.palette_a_id,
      palette_b_id: settings.palette_b_id,
    })
    await ctx?.reload()
    syncSettings()
    actionMessage.value = 'บันทึกการตั้งค่าแล้ว'
  } catch (e) {
    settingsError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── เผยแพร่ ───────────────────────────────────────────────────────
const publishing = ref(false)

async function publish() {
  if (!event?.value) return
  const ok = window.confirm(
    `เผยแพร่ทุกฉาก (${stats.value.stunts} ฉาก) ให้ผู้ชมเห็น และเริ่ม live ที่ฉากแรก?\n` +
      'ผู้ชมจะเห็นเวอร์ชันนี้ทันที',
  )
  if (!ok) return
  publishing.value = true
  actionError.value = ''
  actionMessage.value = ''
  try {
    await eventsService.publishEvent(event.value.id)
    await ctx?.reload()
    await load()
    actionMessage.value = 'เผยแพร่แล้ว — ลิงก์ผู้ชมพร้อมใช้งาน'
  } catch (e) {
    actionError.value = errorMessage(e)
  } finally {
    publishing.value = false
  }
}

const statusOptions = (Object.keys(EVENT_STATUS) as EventStatus[]).map((key) => ({
  key,
  ...EVENT_STATUS[key],
}))

function go(name: string) {
  if (!event?.value) return
  router.push({ name, params: { eventId: event.value.id } })
}
</script>

<template>
  <div v-if="event" class="space-y-5">
    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p
      v-if="actionError"
      class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger"
    >
      {{ actionError }}
    </p>
    <p
      v-if="actionMessage"
      class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong"
    >
      {{ actionMessage }}
    </p>

    <!-- สถิติ -->
    <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          {{ formatNumber(stats.stunts) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">ฉาก · เผยแพร่ {{ stats.publishedStunts }}</div>
      </AppCard>
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          {{ formatNumber(stats.colorSets) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">ชุดสี · {{ stats.colors }} สีรวม</div>
      </AppCard>
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          {{ formatNumber(stats.seats) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">ที่นั่ง · {{ stats.stands }} แสตน</div>
      </AppCard>
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          v.{{ event.published_version || 0 }}
        </div>
        <div class="mt-1 text-caption text-ink-2">
          อัปเดตล่าสุด {{ formatDateTime(event.updated_at) }}
        </div>
      </AppCard>
    </div>

    <!-- ทางลัด -->
    <AppCard :padded="true">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-display text-title-m font-bold">ขั้นตอนทำงาน</h3>
        <AppButton
          v-if="canPublish"
          size="sm"
          :loading="publishing"
          :disabled="stats.stunts === 0"
          @click="publish"
        >
          <template #icon><i class="bi bi-send" aria-hidden="true" /></template>
          เผยแพร่ทุกฉาก
        </AppButton>
      </div>
      <div class="grid gap-2 sm:grid-cols-3">
        <button
          v-if="canStands"
          type="button"
          class="rounded-control border border-line p-3 text-left hover:border-brand/40"
          @click="go('event-stands')"
        >
          <div class="flex items-center gap-2 font-semibold text-sm">
            <i class="bi bi-grid-3x3-gap text-brand" aria-hidden="true" /> ตั้งค่าแสตน
            <span v-if="stats.stands === 0" class="text-[11px] font-bold text-warn">ยังไม่มี</span>
          </div>
          <p class="mt-1 text-caption text-ink-2">แถว/ที่นั่ง · ทิศทาง · ช่องบันได</p>
        </button>
        <button
          v-if="canPalettes"
          type="button"
          class="rounded-control border border-line p-3 text-left hover:border-brand/40"
          @click="go('event-palettes')"
        >
          <div class="flex items-center gap-2 font-semibold text-sm">
            <i class="bi bi-palette text-brand" aria-hidden="true" /> ชุดสี
            <span v-if="stats.colors === 0" class="text-[11px] font-bold text-warn">ยังไม่มี</span>
          </div>
          <p class="mt-1 text-caption text-ink-2">รหัสสี · สีตัวอักษร · นำเข้า preset</p>
        </button>
        <button
          v-if="canStunts"
          type="button"
          class="rounded-control border border-line p-3 text-left hover:border-brand/40"
          @click="go('event-stunts')"
        >
          <div class="flex items-center gap-2 font-semibold text-sm">
            <i class="bi bi-easel2 text-brand" aria-hidden="true" /> ฉาก
            <span v-if="stats.stunts === 0" class="text-[11px] font-bold text-warn">ยังไม่มี</span>
          </div>
          <p class="mt-1 text-caption text-ink-2">สร้าง/เรียงฉาก · แปลงรูป · วาดพิกเซล</p>
        </button>
      </div>
      <p v-if="!canStands && !canPalettes && !canStunts" class="text-caption text-ink-2">
        บทบาทของคุณยังไม่มีสิทธิ์แก้ไขงานนี้ — ติดต่อแอดมิน
      </p>
    </AppCard>

    <!-- ลิงก์ผู้ชม -->
    <AppCard v-if="event.public_access_enabled && event.published_version > 0" :padded="true">
      <h3 class="font-display text-title-m font-bold mb-1">ลิงก์แจกผู้ชม</h3>
      <p class="text-caption text-ink-2 mb-3">นักเรียนเปิดลิงก์นี้บนมือถือเพื่อดูโพยของตัวเอง</p>
      <div class="flex flex-wrap items-center gap-4">
        <QrCode :value="viewerUrl" :size="160" />
        <div class="min-w-0 flex-1">
          <code class="block truncate rounded-control bg-canvas px-3 py-2 text-sm">{{ viewerUrl }}</code>
          <div class="mt-2 flex gap-2">
            <AppButton size="sm" variant="secondary" @click="copyViewerUrl">
              <template #icon><i class="bi bi-clipboard" aria-hidden="true" /></template>
              คัดลอกลิงก์
            </AppButton>
            <AppButton size="sm" variant="text" @click="openViewer">
              <template #icon><i class="bi bi-box-arrow-up-right" aria-hidden="true" /></template>
              เปิด
            </AppButton>
          </div>
          <p v-if="copied" class="mt-2 text-caption text-ok-strong">คัดลอกแล้ว</p>
        </div>
      </div>
    </AppCard>

    <!-- ตั้งค่างาน (admin) -->
    <AppCard v-if="canManageEvent" :padded="true">
      <h3 class="font-display text-title-m font-bold mb-3">ตั้งค่างาน</h3>
      <form class="grid gap-3 sm:grid-cols-2" @submit.prevent="saveSettings">
        <div class="sm:col-span-2">
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-name">ชื่องาน</label>
          <input id="set-name" v-model="settings.name" class="field" required />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-date">วันที่จัดงาน</label>
          <input id="set-date" v-model="settings.event_date" type="date" class="field" />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-status">สถานะ</label>
          <select id="set-status" v-model="settings.status" class="field">
            <option v-for="opt in statusOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
        </div>
        <div class="sm:col-span-2">
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-desc">รายละเอียด</label>
          <textarea id="set-desc" v-model="settings.description" class="field" rows="2" />
        </div>
        <label class="flex items-center gap-2 text-sm">
          <input v-model="settings.public_access_enabled" type="checkbox" class="h-4 w-4" />
          เปิดให้ผู้ชมเข้าดู
        </label>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-palette-a">ชุดสี ด้าน A</label>
          <select id="set-palette-a" v-model.number="settings.palette_a_id" class="field">
            <option :value="null">— ไม่ระบุ —</option>
            <option v-for="palette in palettes" :key="palette.id" :value="palette.id">
              {{ palette.name }} ({{ palette.colors.length }} สี)
            </option>
          </select>
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="set-palette-b">ชุดสี ด้าน B</label>
          <select id="set-palette-b" v-model.number="settings.palette_b_id" class="field">
            <option :value="null">— ไม่ระบุ —</option>
            <option v-for="palette in palettes" :key="palette.id" :value="palette.id">
              {{ palette.name }} ({{ palette.colors.length }} สี)
            </option>
          </select>
        </div>
        <p v-if="settingsError" class="sm:col-span-2 text-caption text-danger">{{ settingsError }}</p>
        <div class="sm:col-span-2">
          <AppButton type="submit" :loading="saving">บันทึก</AppButton>
        </div>
      </form>
    </AppCard>

    <p v-if="loading" class="text-caption text-ink-3">กำลังโหลดข้อมูลงาน…</p>
  </div>
</template>
