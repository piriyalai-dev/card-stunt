<script setup lang="ts">
/**
 * 📡 คุมคิวสด (staff) — กด next/prev/goto แล้วผู้ชมที่เปิด SSE เลื่อนตาม
 *
 * ⚠️ การกด advance **ไม่แทนที่** การทำงานฝั่งผู้ชม: ผู้ชมยังเลื่อนเองได้และจะกลับมา
 *    ตามคิวสดเมื่อกดเปิด "ตามคิวสด" อีกครั้ง ⇒ หน้า admin ต้องบอกเรื่องนี้ให้ชัด
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import { useEventContext } from '@/composables/eventContext'
import { errorMessage } from '@/lib/format'
import * as liveService from '@/services/live'
import * as stuntsService from '@/services/stunts'
import type { LiveAdminState, StuntOut } from '@/types/domain'

const ctx = useEventContext()
const event = ctx?.event

const live = ref<LiveAdminState | null>(null)
const stunts = ref<StuntOut[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const message = ref('')

let pollTimer: number | null = null

const published = computed(() => stunts.value.filter((s) => s.status === 'published'))
const current = computed(() => published.value.find((s) => s.id === live.value?.current_stunt_id) ?? null)
const currentPos = computed(() => {
  if (!live.value || live.value.current_index === null) return null
  return live.value.current_index + 1
})

const viewerPath = computed(() => (event?.value ? `/e/${event.value.slug}` : null))

async function load(): Promise<void> {
  if (!event?.value) return
  loading.value = true
  error.value = ''
  try {
    const [state, list] = await Promise.all([
      liveService.getLive(event.value.id),
      stuntsService.listStunts(event.value.id),
    ])
    live.value = state
    stunts.value = list
    if (selectedId.value === null && state.current_stunt_id !== null) {
      selectedId.value = state.current_stunt_id
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function refreshState(): Promise<void> {
  if (!event?.value || busy.value) return
  try {
    live.value = await liveService.getLive(event.value.id)
  } catch {
    // poll เงียบ ๆ — หลุดแล้วรอบหน้าลองใหม่
  }
}

async function advance(action: 'next' | 'prev' | 'goto', stuntId?: number): Promise<void> {
  if (!event?.value) return
  busy.value = true
  error.value = ''
  message.value = ''
  try {
    live.value = await liveService.advanceLive(event.value.id, action, stuntId)
    selectedId.value = live.value.current_stunt_id
    message.value = live.value.current_stunt_id
      ? 'เลื่อนคิวแล้ว — ผู้ชมที่เปิดอยู่จะตามภายในไม่กี่วินาที'
      : 'อัปเดตคิวแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function gotoSelected(): void {
  if (selectedId.value === null) return
  void advance('goto', selectedId.value)
}

onMounted(async () => {
  await load()
  pollTimer = window.setInterval(() => void refreshState(), 8000)
})

onUnmounted(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})
</script>

<template>
  <div v-if="event" class="space-y-5">
    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption font-semibold text-ok-strong">
      {{ message }}
    </p>

    <AppCard>
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <h3 class="font-display text-title-m font-bold">คิวสดวันแข่ง</h3>
            <span
              class="rounded-full px-2 py-0.5 text-[11px] font-semibold"
              :class="live?.is_active ? 'bg-brand-tint text-brand' : 'bg-canvas text-ink-3'"
            >
              {{ live?.is_active ? 'กำลังออกอากาศ' : 'ยังไม่เริ่ม' }}
            </span>
          </div>
          <p class="mt-1 text-caption text-ink-2">
            ฉากปัจจุบัน:
            <span class="font-semibold text-ink-1">
              {{ current ? `${current.code} ${current.title}` : '— ยังไม่เลือก —' }}
            </span>
            <span v-if="currentPos"> · {{ currentPos }}/{{ live?.total ?? published.length }}</span>
          </p>
        </div>
        <a
          v-if="viewerPath"
          :href="viewerPath"
          target="_blank"
          rel="noopener"
          class="inline-flex h-9 items-center gap-1.5 rounded-control border border-line bg-surface px-3 text-[13px] font-semibold text-ink-2 hover:text-brand"
        >
          <i class="bi bi-box-arrow-up-right" aria-hidden="true" />
          เปิดหน้าผู้ชม
        </a>
      </div>

      <div v-if="loading" class="mt-4 h-24 rounded-control bg-canvas skeleton-shimmer" />

      <template v-else>
        <p v-if="published.length === 0" class="mt-4 rounded-control bg-warn-soft p-3 text-caption text-warn">
          ยังไม่มีฉากที่เผยแพร่ — ต้อง publish งานก่อนจึงจะคุมคิวสดได้
        </p>

        <div v-else class="mt-4 flex items-center gap-2">
          <button
            type="button"
            class="grid h-14 w-14 shrink-0 place-items-center rounded-control border border-line bg-surface text-2xl text-ink-1 hover:bg-canvas disabled:opacity-50"
            :disabled="busy"
            aria-label="ฉากก่อนหน้า"
            @click="advance('prev')"
          >
            <i class="bi bi-chevron-left" aria-hidden="true" />
          </button>

          <select v-model.number="selectedId" class="h-12 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body">
            <option v-for="(stunt, i) in published" :key="stunt.id" :value="stunt.id">
              {{ String(i + 1).padStart(2, '0') }} · {{ stunt.code }} {{ stunt.title }}
            </option>
          </select>

          <AppButton :disabled="busy || selectedId === null" @click="gotoSelected">ไปฉากนี้</AppButton>

          <button
            type="button"
            class="grid h-14 w-14 shrink-0 place-items-center rounded-control bg-brand text-2xl text-white hover:bg-brand-strong disabled:opacity-50"
            :disabled="busy"
            aria-label="ฉากถัดไป"
            @click="advance('next')"
          >
            <i class="bi bi-chevron-right" aria-hidden="true" />
          </button>
        </div>

        <p class="mt-2 text-[11px] text-ink-3">
          ผู้ชมที่เปิดหน้าโฟกัสจะเลื่อนตามอัตโนมัติ (SSE) · ถ้าผู้ชมปิด “ตามคิวสด” ไว้ เขาจะยังเลื่อนเองได้
        </p>

        <ol class="mt-4 grid gap-2 sm:grid-cols-2">
          <li v-for="(stunt, i) in published" :key="stunt.id">
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-control border px-3 py-2 text-left text-sm transition-colors"
              :class="
                stunt.id === live?.current_stunt_id
                  ? 'border-brand bg-brand-tint text-brand'
                  : 'border-line bg-surface text-ink-1 hover:border-brand/40'
              "
              :disabled="busy"
              @click="advance('goto', stunt.id)"
            >
              <span class="w-6 shrink-0 font-mono text-[11px] text-ink-3">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="min-w-0 flex-1 truncate">
                <span class="font-semibold">{{ stunt.code }}</span> {{ stunt.title }}
              </span>
              <span v-if="stunt.id === live?.current_stunt_id" class="text-[11px] font-bold">● LIVE</span>
            </button>
          </li>
        </ol>
      </template>
    </AppCard>
  </div>
</template>
