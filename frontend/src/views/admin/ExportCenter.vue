<script setup lang="ts">
/**
 * 📦 รายชื่อ & Export Center (staff)
 *
 * - import รายชื่อ CSV/XLSX เข้าที่นั่ง
 * - สั่ง export PDF (โพยรายที่นั่ง) / CSV (ตารางรวม) / ZIP (ภาพกริดทุกฉาก)
 * - ติดตามสถานะแบบ poll จนเสร็จ แล้วดาวน์โหลด
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { useEventContext } from '@/composables/eventContext'
import { errorMessage, formatDateTime, formatNumber } from '@/lib/format'
import * as exportsService from '@/services/exports'
import * as rostersService from '@/services/rosters'
import * as standsService from '@/services/stands'
import type {
  ExportFormat,
  ExportJob,
  ExportStatus,
  RosterOut,
  StandOut,
} from '@/types/domain'

const ctx = useEventContext()
const event = ctx?.event

const stands = ref<StandOut[]>([])
const rosters = ref<RosterOut[]>([])
const jobs = ref<ExportJob[]>([])
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const message = ref('')

// ── import ────────────────────────────────────────────────────────
const importStandId = ref<number | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const importResult = ref<{ inserted: number; errors: string[]; total: number } | null>(null)

// ── export ────────────────────────────────────────────────────────
const exportStandId = ref<number | null>(null) // null = ทั้งงาน
const creating = ref<ExportFormat | null>(null)

// ── roster filter ─────────────────────────────────────────────────
const rosterQuery = ref('')
const rosterStandFilter = ref<number | null>(null)

const STATUS_META: Record<ExportStatus, { label: string; className: string }> = {
  queued: { label: 'รอคิว', className: 'bg-canvas text-ink-2 border-line' },
  running: { label: 'กำลังสร้าง', className: 'bg-warn-soft text-warn border-warn/30' },
  done: { label: 'เสร็จ', className: 'bg-ok-soft text-ok-strong border-ok-line' },
  failed: { label: 'ล้มเหลว', className: 'bg-danger-soft text-danger border-danger/30' },
}

const FORMAT_LABEL: Record<ExportFormat, string> = {
  pdf: 'PDF โพยรายที่นั่ง',
  csv: 'CSV ตารางรวม',
  zip: 'ZIP ภาพกริดทุกฉาก',
}

const standName = computed(() => {
  const map = new Map(stands.value.map((s) => [s.id, s.name]))
  return (id: number | null) => (id === null ? 'ทั้งงาน' : map.get(id) ?? `stand #${id}`)
})

const rosterCounts = computed(() => {
  const map = new Map<number, number>()
  for (const r of rosters.value) map.set(r.stand_id, (map.get(r.stand_id) ?? 0) + 1)
  return map
})

const filteredRosters = computed(() => {
  const q = rosterQuery.value.trim().toLowerCase()
  return rosters.value
    .filter((r) => !rosterStandFilter.value || r.stand_id === rosterStandFilter.value)
    .filter((r) => {
      if (!q) return true
      return [r.student_code, r.student_name, r.row_label, r.seat_label, r.note]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q))
    })
    .slice(0, 200)
})

const hasActiveJobs = computed(() =>
  jobs.value.some((j) => j.status === 'queued' || j.status === 'running'),
)

let pollTimer: number | null = null

async function load(): Promise<void> {
  if (!event?.value) return
  loading.value = true
  error.value = ''
  try {
    const eventId = event.value.id
    const [standList, rosterList, jobList] = await Promise.all([
      standsService.listStands(eventId),
      rostersService.listRosters(eventId),
      exportsService.listExports(eventId),
    ])
    stands.value = standList
    rosters.value = rosterList
    jobs.value = jobList
    if (!importStandId.value) importStandId.value = standList[0]?.id ?? null
    if (hasActiveJobs.value) startPolling()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function startPolling(): void {
  if (pollTimer) return
  pollTimer = window.setInterval(() => void pollJobs(), 2500)
}

function stopPolling(): void {
  if (!pollTimer) return
  window.clearInterval(pollTimer)
  pollTimer = null
}

async function pollJobs(): Promise<void> {
  const active = jobs.value.filter((j) => j.status === 'queued' || j.status === 'running')
  if (active.length === 0) {
    stopPolling()
    return
  }
  try {
    const updated = await Promise.all(active.map((j) => exportsService.getExport(j.id)))
    const byId = new Map(updated.map((j) => [j.id, j]))
    jobs.value = jobs.value.map((j) => byId.get(j.id) ?? j)
    if (!hasActiveJobs.value) stopPolling()
  } catch {
    // poll ล้มชั่วคราว (เน็ตหลุด) — รอบหน้าลองใหม่ ไม่ต้องรบกวนผู้ใช้
  }
}

async function onFileChange(domEvent: Event): Promise<void> {
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0] ?? null
  importResult.value = null
  actionError.value = ''
  if (!file || !importStandId.value || !event?.value) return
  importing.value = true
  try {
    importResult.value = await rostersService.importRoster(event.value.id, importStandId.value, file)
    message.value = `นำเข้ารายชื่อแล้ว ${importResult.value.inserted}/${importResult.value.total} แถว`
    const refreshed = await rostersService.listRosters(event.value.id)
    rosters.value = refreshed
  } catch (e) {
    actionError.value = errorMessage(e)
  } finally {
    importing.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function removeRoster(roster: RosterOut): Promise<void> {
  if (!event?.value) return
  if (!window.confirm(`ลบ ${roster.student_name} (${roster.row_label}·${roster.seat_label})?`)) return
  actionError.value = ''
  try {
    await rostersService.deleteRoster(roster.id)
    rosters.value = rosters.value.filter((r) => r.id !== roster.id)
  } catch (e) {
    actionError.value = errorMessage(e)
  }
}

async function createExport(format: ExportFormat): Promise<void> {
  if (!event?.value) return
  creating.value = format
  actionError.value = ''
  message.value = ''
  try {
    const job = await exportsService.createExport(event.value.id, {
      format,
      stand_id: exportStandId.value,
      scope: exportStandId.value ? 'stand' : 'event',
    })
    jobs.value = [job, ...jobs.value]
    message.value = `สั่งสร้าง ${FORMAT_LABEL[format]} แล้ว — รอ Worker สร้างไฟล์`
    startPolling()
  } catch (e) {
    actionError.value = errorMessage(e)
  } finally {
    creating.value = null
  }
}

async function retry(job: ExportJob): Promise<void> {
  actionError.value = ''
  try {
    const updated = await exportsService.retryExport(job.id)
    jobs.value = jobs.value.map((j) => (j.id === job.id ? updated : j))
    startPolling()
  } catch (e) {
    actionError.value = errorMessage(e)
  }
}

async function download(job: ExportJob): Promise<void> {
  if (!event?.value) return
  actionError.value = ''
  try {
    const blob = await exportsService.downloadExport(job.id)
    const ext = job.format
    exportsService.saveBlob(blob, `${event.value.slug}-${job.format}-${job.id}.${ext}`)
  } catch (e) {
    actionError.value = errorMessage(e)
  }
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<template>
  <div v-if="event" class="space-y-5">
    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="actionError" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ actionError }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption font-semibold text-ok-strong">
      {{ message }}
    </p>

    <div class="grid gap-3 sm:grid-cols-3">
      <AppCard muted>
        <div class="text-caption text-ink-2">ที่นั่งทั้งหมด</div>
        <div class="mt-1 font-display text-title-l font-bold">
          {{ formatNumber(stands.reduce((n, s) => n + s.rows * s.cols - s.blocked_seats.length, 0)) }}
        </div>
      </AppCard>
      <AppCard muted>
        <div class="text-caption text-ink-2">รายชื่อที่ผูกแล้ว</div>
        <div class="mt-1 font-display text-title-l font-bold">{{ formatNumber(rosters.length) }}</div>
      </AppCard>
      <AppCard muted>
        <div class="text-caption text-ink-2">งาน export ล่าสุด</div>
        <div class="mt-1 font-display text-title-l font-bold">{{ jobs[0] ? FORMAT_LABEL[jobs[0].format] : '—' }}</div>
      </AppCard>
    </div>

    <!-- 1) import รายชื่อ -->
    <AppCard>
      <h3 class="font-display text-title-m font-bold">อัปโหลดรายชื่อ</h3>
      <p class="mt-1 text-caption text-ink-2">
        ไฟล์ CSV/XLSX ต้องมีคอลัมน์ <code class="font-mono">row</code>, <code class="font-mono">col</code>,
        <code class="font-mono">student_code</code>, <code class="font-mono">student_name</code>
        (row/col เป็นเลข 1-based ตามป้ายแสตน)
      </p>
      <div class="mt-3 flex flex-wrap items-end gap-2">
        <label class="min-w-[10rem] flex-1">
          <span class="mb-1 block text-caption font-semibold text-ink-2">แสตน</span>
          <select v-model.number="importStandId" class="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm">
            <option v-for="s in stands" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
        <label class="min-w-[12rem] flex-[2]">
          <span class="mb-1 block text-caption font-semibold text-ink-2">ไฟล์รายชื่อ</span>
          <input
            ref="fileInput"
            type="file"
            accept=".csv,.xlsx,text/csv"
            class="block w-full rounded-control border border-line bg-surface px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand-tint file:px-3 file:py-1.5 file:text-brand"
            :disabled="importing"
            @change="onFileChange"
          />
        </label>
      </div>
      <p v-if="importing" class="mt-2 text-caption text-ink-2">กำลังนำเข้า…</p>
      <div v-if="importResult" class="mt-2 rounded-control bg-canvas p-3 text-caption">
        นำเข้า {{ importResult.inserted }}/{{ importResult.total }} แถว
        <ul v-if="importResult.errors.length" class="mt-1 list-inside list-disc text-danger">
          <li v-for="(err, i) in importResult.errors.slice(0, 5)" :key="i">{{ err }}</li>
          <li v-if="importResult.errors.length > 5">… และอีก {{ importResult.errors.length - 5 }} แถว</li>
        </ul>
      </div>
      <p v-if="stands.length === 0" class="mt-2 text-caption text-warn">ยังไม่มีแสตน — สร้างที่แท็บ “ตั้งค่าแสตน” ก่อน</p>
    </AppCard>

    <!-- 2) ตารางรายชื่อ -->
    <AppCard>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="font-display text-title-m font-bold">รายชื่อในงาน</h3>
        <div class="flex flex-wrap gap-2">
          <select v-model.number="rosterStandFilter" class="h-9 rounded-control border border-line bg-surface px-2 text-[13px]">
            <option :value="null">ทุกแสตน</option>
            <option v-for="s in stands" :key="s.id" :value="s.id">{{ s.name }} ({{ rosterCounts.get(s.id) ?? 0 }})</option>
          </select>
          <input
            v-model="rosterQuery"
            placeholder="ค้นหาชื่อ/เลข/ที่นั่ง"
            class="h-9 w-44 rounded-control border border-line bg-surface px-3 text-[13px]"
          />
        </div>
      </div>
      <div v-if="loading" class="mt-3 h-24 rounded-control bg-canvas skeleton-shimmer" />
      <p v-else-if="filteredRosters.length === 0" class="mt-3 text-caption text-ink-2">
        ยังไม่มีรายชื่อที่ตรงเงื่อนไข — อัปโหลดไฟล์ด้านบน
      </p>
      <div v-else class="mt-3 overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-caption text-ink-2">
            <tr class="border-b border-line">
              <th class="py-2 pr-3 font-semibold">ที่นั่ง</th>
              <th class="py-2 pr-3 font-semibold">รหัส</th>
              <th class="py-2 pr-3 font-semibold">รหัสล็อกอิน</th>
              <th class="py-2 pr-3 font-semibold">ชื่อ</th>
              <th class="py-2 pr-3 font-semibold">แสตน</th>
              <th class="py-2 font-semibold" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in filteredRosters" :key="r.id" class="border-b border-line/70">
              <td class="py-1.5 pr-3 font-semibold">{{ r.row_label }} · {{ r.seat_label }}</td>
              <td class="py-1.5 pr-3 font-mono text-[12px]">{{ r.student_code || '—' }}</td>
              <td class="py-1.5 pr-3 font-mono text-[12px] font-semibold text-brand">{{ r.access_code || '—' }}</td>
              <td class="py-1.5 pr-3">{{ r.student_name }}</td>
              <td class="py-1.5 pr-3 text-ink-2">{{ standName(r.stand_id) }}</td>
              <td class="py-1.5 text-right">
                <button class="text-caption text-danger hover:underline" @click="removeRoster(r)">ลบ</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="rosters.length > 200" class="mt-2 text-caption text-ink-3">แสดง 200 แถวแรก — ใช้ตัวกรองเพื่อค้นหา</p>
      </div>
    </AppCard>

    <!-- 3) export -->
    <AppCard>
      <h3 class="font-display text-title-m font-bold">สร้างไฟล์ส่งออก</h3>
      <p class="mt-1 text-caption text-ink-2">
        PDF = การ์ดโพยรายที่นั่ง (4 ใบ/หน้า A4) · CSV = ตารางทุกที่นั่ง×ฉาก · ZIP = ภาพกริดเต็มทุกฉาก + seats.csv
      </p>
      <div class="mt-3 flex flex-wrap items-end gap-2">
        <label class="min-w-[12rem] flex-1">
          <span class="mb-1 block text-caption font-semibold text-ink-2">ขอบเขต</span>
          <select v-model.number="exportStandId" class="h-10 w-full rounded-control border border-line bg-surface px-3 text-sm">
            <option :value="null">ทั้งงาน (ทุกแสตน)</option>
            <option v-for="s in stands" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
        </label>
      </div>
      <div class="mt-3 flex flex-wrap gap-2">
        <AppButton
          v-for="format in (['pdf', 'csv', 'zip'] as ExportFormat[])"
          :key="format"
          variant="secondary"
          :loading="creating === format"
          :disabled="!!creating"
          @click="createExport(format)"
        >
          <i class="bi bi-file-earmark-arrow-down" aria-hidden="true" />
          {{ FORMAT_LABEL[format] }}
        </AppButton>
      </div>
    </AppCard>

    <AppCard>
      <h3 class="font-display text-title-m font-bold">ประวัติการ export</h3>
      <p v-if="jobs.length === 0" class="mt-2 text-caption text-ink-2">ยังไม่มีงาน export</p>
      <div v-else class="mt-3 overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="text-left text-caption text-ink-2">
            <tr class="border-b border-line">
              <th class="py-2 pr-3 font-semibold">#</th>
              <th class="py-2 pr-3 font-semibold">รูปแบบ</th>
              <th class="py-2 pr-3 font-semibold">ขอบเขต</th>
              <th class="py-2 pr-3 font-semibold">สถานะ</th>
              <th class="py-2 pr-3 font-semibold">เวลา</th>
              <th class="py-2 font-semibold" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.id" class="border-b border-line/70 align-top">
              <td class="py-2 pr-3 font-mono text-[12px]">{{ job.id }}</td>
              <td class="py-2 pr-3">{{ job.format.toUpperCase() }}</td>
              <td class="py-2 pr-3 text-ink-2">{{ standName(job.stand_id) }}</td>
              <td class="py-2 pr-3">
                <span class="inline-block rounded-full border px-2 py-0.5 text-[11px] font-semibold" :class="STATUS_META[job.status].className">
                  {{ STATUS_META[job.status].label }}
                </span>
                <p v-if="job.error" class="mt-1 max-w-xs text-[11px] text-danger">{{ job.error }}</p>
              </td>
              <td class="py-2 pr-3 text-[12px] text-ink-3">{{ formatDateTime(job.created_at) }}</td>
              <td class="py-2 text-right">
                <button
                  v-if="job.status === 'done'"
                  class="text-caption font-semibold text-brand hover:underline"
                  @click="download(job)"
                >
                  ดาวน์โหลด
                </button>
                <button
                  v-else-if="job.status === 'failed'"
                  class="text-caption font-semibold text-brand hover:underline"
                  @click="retry(job)"
                >
                  ลองใหม่
                </button>
                <span v-else class="text-caption text-ink-3">…</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </AppCard>
  </div>
</template>
