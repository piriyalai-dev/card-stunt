<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppChip from '@/components/ui/AppChip.vue'
import AppEmptyState from '@/components/ui/AppEmptyState.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { EVENT_STATUS } from '@/constants/status'
import { errorMessage, formatDate, formatNumber } from '@/lib/format'
import * as eventsService from '@/services/events'
import { useAuthStore } from '@/stores/auth'
import type { EventCreate, EventOut, EventStatus } from '@/types/domain'

const authStore = useAuthStore()
const router = useRouter()

const events = ref<EventOut[]>([])
const loading = ref(true)
const error = ref('')
const filter = ref<'all' | EventStatus>('all')

const canManage = computed(() => authStore.hasPermission('MANAGE_EVENTS'))

const statusOptions = (Object.keys(EVENT_STATUS) as EventStatus[]).map((key) => ({
  key,
  ...EVENT_STATUS[key],
}))

const filtered = computed(() =>
  filter.value === 'all' ? events.value : events.value.filter((e) => e.status === filter.value),
)

const counts = computed(() => ({
  total: events.value.length,
  active: events.value.filter((e) => e.status === 'active').length,
  published: events.value.filter((e) => e.published_version > 0).length,
}))

async function load() {
  loading.value = true
  error.value = ''
  try {
    events.value = await eventsService.listEvents()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)

// ── สร้างงานใหม่ ──────────────────────────────────────────────────
const showCreate = ref(false)
const saving = ref(false)
const formError = ref('')
const form = reactive<EventCreate>({ name: '', slug: '', description: '', event_date: '' })

function openCreate() {
  form.name = ''
  form.slug = ''
  form.description = ''
  form.event_date = ''
  formError.value = ''
  showCreate.value = true
}

async function submitCreate() {
  if (!form.name.trim()) {
    formError.value = 'ต้องใส่ชื่องาน'
    return
  }
  saving.value = true
  formError.value = ''
  try {
    const created = await eventsService.createEvent({
      name: form.name.trim(),
      slug: form.slug?.trim() || null,
      description: form.description?.trim() || null,
      event_date: form.event_date || null,
    })
    showCreate.value = false
    await router.push({ name: 'event-overview', params: { eventId: created.id } })
  } catch (e) {
    formError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

function openEvent(event: EventOut) {
  router.push({ name: 'event-overview', params: { eventId: event.id } })
}
</script>

<template>
  <div>
    <PageHeader
      title="แดชบอร์ด"
      :description="`สวัสดี ${authStore.displayName} — เลือกงานที่ต้องการจัดการ หรือสร้างงานใหม่`"
    >
      <template #actions>
        <AppButton v-if="canManage" size="sm" @click="openCreate">
          <template #icon><i class="bi bi-plus-lg" aria-hidden="true" /></template>
          สร้างงานใหม่
        </AppButton>
      </template>
    </PageHeader>

    <!-- สรุปเร็ว -->
    <div class="grid grid-cols-3 gap-3 mb-5">
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          {{ formatNumber(counts.total) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">งานทั้งหมด</div>
      </AppCard>
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums text-ok-strong">
          {{ formatNumber(counts.active) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">กำลังใช้งาน</div>
      </AppCard>
      <AppCard class="!p-4">
        <div class="font-display text-title-l font-extrabold tabular-nums">
          {{ formatNumber(counts.published) }}
        </div>
        <div class="mt-1 text-caption text-ink-2">เคยเผยแพร่</div>
      </AppCard>
    </div>

    <!-- ฟิลเตอร์สถานะ -->
    <div class="chip-row mb-4">
      <AppChip label="ทั้งหมด" :active="filter === 'all'" :count="events.length" @click="filter = 'all'" />
      <AppChip
        v-for="opt in statusOptions"
        :key="opt.key"
        :label="opt.label"
        :active="filter === opt.key"
        :count="events.filter((e) => e.status === opt.key).length"
        @click="filter = opt.key"
      />
    </div>

    <p v-if="error" class="mb-4 rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>

    <!-- ฟอร์มสร้างงาน -->
    <AppCard v-if="showCreate" class="mb-5" :padded="true">
      <h3 class="font-display text-title-m font-bold mb-3">สร้างงานใหม่</h3>
      <form class="grid gap-3 sm:grid-cols-2" @submit.prevent="submitCreate">
        <div class="sm:col-span-2">
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="event-name">ชื่องาน</label>
          <input id="event-name" v-model="form.name" class="field" placeholder="เช่น กีฬาสี 69" required />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="event-slug">slug (ไม่บังคับ)</label>
          <input id="event-slug" v-model="form.slug" class="field" placeholder="สร้างจากชื่องานถ้าเว้นว่าง" />
        </div>
        <div>
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="event-date">วันที่จัดงาน</label>
          <input id="event-date" v-model="form.event_date" type="date" class="field" />
        </div>
        <div class="sm:col-span-2">
          <label class="block text-caption font-semibold text-ink-2 mb-1" for="event-desc">รายละเอียด</label>
          <textarea id="event-desc" v-model="form.description" class="field" rows="2" />
        </div>
        <p v-if="formError" class="sm:col-span-2 text-caption text-danger">{{ formError }}</p>
        <div class="sm:col-span-2 flex gap-2">
          <AppButton type="submit" :loading="saving">สร้างงาน</AppButton>
          <AppButton variant="secondary" @click="showCreate = false">ยกเลิก</AppButton>
        </div>
      </form>
    </AppCard>

    <!-- รายการงาน -->
    <div v-if="loading" class="grid gap-3 sm:grid-cols-2">
      <div v-for="n in 2" :key="n" class="h-32 rounded-card border border-line bg-surface skeleton-shimmer" />
    </div>

    <AppEmptyState
      v-else-if="filtered.length === 0"
      icon="bi-calendar2-week"
      :title="events.length === 0 ? 'ยังไม่มีงาน' : 'ไม่มีงานในสถานะนี้'"
      :description="events.length === 0 ? 'สร้างงานแรก แล้วตั้งค่าแสตน/ชุดสี/ฉากได้เลย' : 'ลองเลือกฟิลเตอร์อื่น'"
    >
      <AppButton v-if="canManage && events.length === 0" size="sm" @click="openCreate">สร้างงานแรก</AppButton>
    </AppEmptyState>

    <div v-else class="grid gap-3 sm:grid-cols-2">
      <button
        v-for="event in filtered"
        :key="event.id"
        type="button"
        class="text-left rounded-card border border-line bg-surface p-4 transition-colors hover:border-brand/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        @click="openEvent(event)"
      >
        <div class="flex items-start gap-3">
          <div class="min-w-0 flex-1">
            <h3 class="font-display text-title-m font-bold truncate">{{ event.name }}</h3>
            <p class="mt-0.5 text-caption text-ink-3 truncate">
              /e/{{ event.slug }} · {{ formatDate(event.event_date) }}
            </p>
          </div>
          <span
            class="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-semibold"
            :class="EVENT_STATUS[event.status].className"
          >
            {{ EVENT_STATUS[event.status].label }}
          </span>
        </div>
        <div class="mt-3 flex items-center gap-4 text-caption text-ink-2">
          <span><b class="tabular-nums">{{ event.version }}</b> เวอร์ชัน</span>
          <span v-if="event.published_version > 0" class="text-ok-strong">
            เผยแพร่ v.{{ event.published_version }}
          </span>
          <span v-else>ยังไม่เผยแพร่</span>
        </div>
      </button>
    </div>
  </div>
</template>
