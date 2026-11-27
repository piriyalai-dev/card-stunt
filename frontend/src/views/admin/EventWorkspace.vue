<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import { provideEventContext } from '@/composables/eventContext'
import { EVENT_STATUS } from '@/constants/status'
import { errorMessage, formatDate } from '@/lib/format'
import * as eventsService from '@/services/events'
import { useAuthStore } from '@/stores/auth'
import type { EventOut } from '@/types/domain'

const route = useRoute()
const authStore = useAuthStore()

const event = ref<EventOut | null>(null)
const loading = ref(true)
const error = ref('')

const eventId = computed(() => Number(route.params.eventId))

const TABS = [
  { name: 'event-overview', label: 'ภาพรวม', icon: 'bi-info-circle', permission: null },
  { name: 'event-stands', label: 'ตั้งค่าแสตน', icon: 'bi-grid-3x3-gap', permission: 'MANAGE_STANDS' },
  { name: 'event-palettes', label: 'ชุดสี', icon: 'bi-palette', permission: 'MANAGE_PALETTES' },
  { name: 'event-stunts', label: 'ฉาก', icon: 'bi-easel2', permission: 'MANAGE_STUNTS' },
] as const

const tabs = computed(() =>
  TABS.filter((t) => !t.permission || authStore.hasPermission(t.permission)),
)

const statusMeta = computed(() => (event.value ? EVENT_STATUS[event.value.status] : null))
const publicPath = computed(() =>
  event.value && event.value.public_access_enabled && event.value.published_version > 0
    ? `/e/${event.value.slug}`
    : null,
)

async function reload() {
  if (!Number.isFinite(eventId.value)) {
    error.value = 'รหัสงานไม่ถูกต้อง'
    loading.value = false
    return
  }
  loading.value = true
  error.value = ''
  try {
    event.value = await eventsService.getEvent(eventId.value)
  } catch (e) {
    event.value = null
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(reload)
watch(eventId, reload)

provideEventContext({ event, reload })
</script>

<template>
  <div>
    <div v-if="loading && !event" class="space-y-3">
      <div class="h-8 w-56 rounded-control bg-canvas skeleton-shimmer" />
      <div class="h-40 rounded-card border border-line bg-surface skeleton-shimmer" />
    </div>

    <div
      v-else-if="error"
      class="rounded-card border border-danger/30 bg-danger-soft p-4 text-caption text-danger"
    >
      {{ error }}
      <AppButton variant="secondary" size="sm" class="ml-2" @click="reload">ลองใหม่</AppButton>
    </div>

    <template v-else-if="event">
      <div class="mb-1 flex items-center gap-1.5 text-caption text-ink-3">
        <RouterLink :to="{ name: 'admin-home' }" class="hover:text-brand">แดชบอร์ด</RouterLink>
        <span aria-hidden="true">/</span>
        <span class="truncate">{{ event.name }}</span>
      </div>

      <div class="mb-4 flex flex-wrap items-start gap-3">
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="font-display text-title-l font-bold truncate">{{ event.name }}</h2>
            <span
              v-if="statusMeta"
              class="rounded-full border px-2 py-0.5 text-[11px] font-semibold"
              :class="statusMeta.className"
            >
              {{ statusMeta.label }}
            </span>
          </div>
          <p class="mt-0.5 text-caption text-ink-2">
            {{ formatDate(event.event_date) }} ·
            {{ event.published_version > 0 ? `เผยแพร่ v.${event.published_version}` : 'ยังไม่เผยแพร่' }}
          </p>
        </div>
        <a
          v-if="publicPath"
          :href="publicPath"
          target="_blank"
          rel="noopener"
          class="inline-flex h-9 items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-[13px] font-semibold text-ink-2 hover:text-brand"
        >
          <i class="bi bi-box-arrow-up-right" aria-hidden="true" />
          เปิดหน้าผู้ชม
        </a>
      </div>

      <nav class="mb-5 flex gap-1 overflow-x-auto border-b border-line" aria-label="เมนูงาน">
        <RouterLink
          v-for="tab in tabs"
          :key="tab.name"
          :to="{ name: tab.name, params: { eventId: event.id } }"
          class="-mb-px inline-flex h-11 shrink-0 items-center gap-1.5 border-b-2 px-3 text-sm font-semibold whitespace-nowrap transition-colors"
          :class="
            route.name === tab.name
              ? 'border-brand text-brand'
              : 'border-transparent text-ink-2 hover:text-ink-1'
          "
        >
          <i :class="['bi', tab.icon]" aria-hidden="true" />
          {{ tab.label }}
        </RouterLink>
      </nav>

      <RouterView />
    </template>
  </div>
</template>
