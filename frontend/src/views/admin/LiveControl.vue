<script setup lang="ts">
/**
 * 📡 คุมคิวสด (staff) — จัดคิวล่วงหน้า (เรียง/แทรก/ลบ) + กด next/prev/goto แล้วผู้ชมตาม
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
import * as queueService from '@/services/queue'
import * as stuntsService from '@/services/stunts'
import type { LiveAdminState, LiveQueueItem, StuntOut } from '@/types/domain'

const ctx = useEventContext()
const event = ctx?.event

const live = ref<LiveAdminState | null>(null)
const stunts = ref<StuntOut[]>([])
const queue = ref<LiveQueueItem[]>([])
const selectedId = ref<number | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const message = ref('')

let pollTimer: number | null = null

const current = computed(() => queue.value.find((q) => q.stunt_id === live.value?.current_stunt_id) ?? null)
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
    const [state, list, q] = await Promise.all([
      liveService.getLive(event.value.id),
      stuntsService.listStunts(event.value.id),
      queueService.getQueue(event.value.id),
    ])
    live.value = state
    stunts.value = list
    queue.value = q
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

// ── จัดคิว (เรียง/แทรก/ลบ) ────────────────────────────────────────
const insertId = ref<number | null>(null)
const insertCandidates = computed(() => {
  const inQueue = new Set(queue.value.map((q) => q.stunt_id))
  return stunts.value.filter((s) => !inQueue.has(s.id))
})

function sideBadge(side: string): string {
  return `ด้าน ${side}`
}

async function reorderQueue(newOrder: number[]): Promise<void> {
  if (!event?.value) return
  busy.value = true
  error.value = ''
  try {
    queue.value = await queueService.setQueue(event.value.id, newOrder)
    message.value = 'บันทึกคิวแล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function moveQueue(item: LiveQueueItem, delta: -1 | 1): void {
  const ids = queue.value.map((q) => q.stunt_id)
  const index = ids.indexOf(item.stunt_id)
  const target = index + delta
  if (index < 0 || target < 0 || target >= ids.length) return
  const [moved] = ids.splice(index, 1)
  ids.splice(target, 0, moved!)
  void reorderQueue(ids)
}

function removeQueueItem(item: LiveQueueItem): void {
  if (!event?.value) return
  busy.value = true
  error.value = ''
  queueService
    .removeQueue(event.value.id, item.stunt_id)
    .then((q) => {
      queue.value = q
      message.value = 'นำออกจากคิวแล้ว'
    })
    .catch((e) => {
      error.value = errorMessage(e)
    })
    .finally(() => {
      busy.value = false
    })
}

function insert(): void {
  if (!event?.value || insertId.value === null) return
  busy.value = true
  error.value = ''
  queueService
    .insertQueue(event.value.id, insertId.value, queue.value.length)
    .then((q) => {
      queue.value = q
      insertId.value = null
      message.value = 'เพิ่มเข้าท้ายคิวแล้ว'
    })
    .catch((e) => {
      error.value = errorMessage(e)
    })
    .finally(() => {
      busy.value = false
    })
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
            <span v-if="currentPos"> · {{ currentPos }}/{{ queue.length }}</span>
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
        <p v-if="queue.length === 0" class="mt-4 rounded-control bg-warn-soft p-3 text-caption text-warn">
          คิวยังว่าง — เพิ่มฉากลงคิวด้านล่าง แล้วเผยแพร่งานก่อนคุมคิวสด
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
            <option v-for="(item, i) in queue" :key="item.stunt_id" :value="item.stunt_id">
              {{ String(i + 1).padStart(2, '0') }} · {{ item.code }} {{ item.title }} · ด้าน {{ item.side }}
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
      </template>
    </AppCard>

    <!-- จัดคิว -->
    <AppCard :padded="true">
      <h3 class="font-display text-title-m font-bold mb-1">จัดคิวแสดง</h3>
      <p class="text-caption text-ink-2 mb-3">
        เรียงลำดับที่จะแสดงล่วงหน้า — สลับ ด้าน A / ด้าน B ตามที่วางแผนไว้ (กด ▲▼ เลื่อน หรือแทรก/ลบได้)
      </p>

      <ol v-if="queue.length > 0" class="space-y-2">
        <li
          v-for="(item, i) in queue"
          :key="item.stunt_id"
          class="flex items-center gap-2 rounded-control border px-3 py-2"
          :class="item.stunt_id === live?.current_stunt_id ? 'border-brand bg-brand-tint' : 'border-line bg-surface'"
        >
          <span class="w-6 shrink-0 text-center font-mono text-[11px] text-ink-3">{{ String(i + 1).padStart(2, '0') }}</span>
          <span
            class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
            :class="item.side === 'A' ? 'bg-brand-tint text-brand' : 'bg-canvas text-ink-2'"
          >
            {{ sideBadge(item.side) }}
          </span>
          <span class="min-w-0 flex-1 truncate text-sm">
            <span class="font-semibold">{{ item.code }}</span> {{ item.title }}
          </span>
          <span v-if="item.stunt_id === live?.current_stunt_id" class="text-[11px] font-bold text-brand">● LIVE</span>
          <AppButton size="sm" variant="secondary" :disabled="busy || i === 0" @click="moveQueue(item, -1)">▲</AppButton>
          <AppButton size="sm" variant="secondary" :disabled="busy || i === queue.length - 1" @click="moveQueue(item, 1)">▼</AppButton>
          <AppButton size="sm" variant="danger" :disabled="busy" @click="removeQueueItem(item)">ลบ</AppButton>
        </li>
      </ol>
      <p v-else class="rounded-control bg-canvas p-4 text-center text-caption text-ink-3">
        คิวยังว่าง — เพิ่มฉากจากรายการด้านล่าง
      </p>

      <div class="mt-4 flex flex-wrap items-end gap-2">
        <div class="min-w-0 flex-1">
          <label class="block text-caption font-semibold text-ink-2 mb-1">เพิ่มฉากเข้าคิว</label>
          <select v-model.number="insertId" class="field">
            <option :value="null">— เลือกฉาก —</option>
            <option v-for="s in insertCandidates" :key="s.id" :value="s.id">
              {{ s.code }} {{ s.title }} · ด้าน {{ s.side }}
            </option>
          </select>
        </div>
        <AppButton :disabled="busy || insertId === null" @click="insert">เพิ่มเข้าท้ายคิว</AppButton>
      </div>
    </AppCard>
  </div>
</template>
