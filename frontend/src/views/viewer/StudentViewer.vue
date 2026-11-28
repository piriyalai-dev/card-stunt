<script setup lang="ts">
/**
 * 🎓 Student Viewer (public PWA) — /e/:slug?
 *
 * 3 สถานะ: code (ใส่รหัสล็อกอิน) → list (โพยทุกฉาก) → focus (โฟกัสกลางแสตน)
 *
 * - ล็อกอินด้วยรหัสสุ่มที่พิมพ์แจกนักเรียน (ไม่เลือกที่นั่ง/ค้นหาเลข ปชช. — กันลิงค์หลุดต่อภาพ)
 * - ข้อมูล meta/seat ถูก cache ลง localStorage ⇒ เปิดออฟไลน์กลางสนามได้หลังเคยเปิดออนไลน์
 * - SSE live sync เป็น "ของแถม": หลุดได้โดยผู้ใช้ยังเลื่อนเองได้ (ห้าม block UI)
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CodeEntry from '@/components/viewer/CodeEntry.vue'
import CueList from '@/components/viewer/CueList.vue'
import FocusMode from '@/components/viewer/FocusMode.vue'
import { errorMessage } from '@/lib/format'
import {
  cacheKeys,
  getLastAccess,
  getLastSlug,
  removeCache,
  setLastAccess,
  setLastSlug,
} from '@/services/publicCache'
import {
  checkVersion,
  loadClaim,
  loadMeta,
  subscribeLive,
} from '@/services/publicApi'
import type { PublicMeta, PublicSeat } from '@/types/public'

const route = useRoute()

const slug = ref(String(route.params.slug ?? '').trim() || getLastSlug() || '')
const slugInput = ref(slug.value)
const meta = ref<PublicMeta | null>(null)
const seat = ref<PublicSeat | null>(null)
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const seatError = ref('')
const offline = ref(false)
const savedAt = ref<number | null>(null)
const view = ref<'code' | 'list' | 'focus'>('code')
const focusIndex = ref(0)
const liveStuntId = ref<number | null>(null)
const liveActive = ref(false)
const liveConnected = ref(false)
const notice = ref('')

let closeLive: (() => void) | null = null
let versionTimer: number | null = null
let noticeTimer: number | null = null
let onlineHandler: (() => void) | null = null

const hasEvent = computed(() => !!slug.value)
const showOfflineBanner = computed(() => offline.value && !!meta.value)

function showNotice(text: string): void {
  notice.value = text
  if (noticeTimer) window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => (notice.value = ''), 6000)
}

function savedAtText(ts: number | null): string {
  if (!ts) return ''
  const date = new Date(ts)
  return date.toLocaleString('th-TH', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function claim(code: string): Promise<void> {
  busy.value = true
  seatError.value = ''
  try {
    const result = await loadClaim(slug.value, code)
    seat.value = result.data
    offline.value = result.offline
    savedAt.value = result.saved_at
    setLastAccess(slug.value, code)
    view.value = 'list'
    window.scrollTo({ top: 0 })
  } catch (e) {
    seatError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function changeCode(): void {
  const code = getLastAccess(slug.value)
  if (code) removeCache(cacheKeys.access(slug.value, code))
  removeCache(cacheKeys.lastAccess(slug.value))
  seat.value = null
  seatError.value = ''
  view.value = 'code'
  window.scrollTo({ top: 0 })
}

function openFocus(index: number): void {
  focusIndex.value = index
  view.value = 'focus'
}

function closeFocus(): void {
  view.value = 'list'
}

function stopLive(): void {
  closeLive?.()
  closeLive = null
  liveConnected.value = false
}

function startLive(): void {
  stopLive()
  if (!slug.value) return
  closeLive = subscribeLive(slug.value, {
    onState(state) {
      liveConnected.value = true
      liveStuntId.value = state.current_stunt_id
      liveActive.value = state.is_active
    },
    onOpen() {
      liveConnected.value = true
    },
    onError() {
      // EventSource จะ reconnect เอง — แค่บอกว่าตอนนี้ไม่ได้รับสัญญาณ
      liveConnected.value = false
    },
  })
}

// ผู้คุม advance แล้วต้องตามทันที แม้ผู้ชมอยู่หน้าโพย (list) — ดึงเข้าโฟกัสที่ฉากล่าสุด
watch(
  () => liveStuntId.value,
  (stuntId) => {
    if (!liveActive.value || stuntId === null || !seat.value) return
    if (view.value === 'focus') return
    const found = seat.value.stunts.findIndex((s) => s.id === stuntId)
    if (found >= 0) {
      focusIndex.value = found
      view.value = 'focus'
    }
  },
)

async function refreshData(reason?: string): Promise<void> {
  if (!slug.value) return
  try {
    const metaResult = await loadMeta(slug.value)
    const previousVersion = meta.value?.published_version ?? 0
    meta.value = metaResult.data
    offline.value = metaResult.offline
    savedAt.value = metaResult.saved_at
    liveStuntId.value = metaResult.data.live.stunt_id
    liveActive.value = metaResult.data.live.is_active

    if (seat.value) {
      const code = getLastAccess(slug.value)
      if (code) {
        const seatResult = await loadClaim(slug.value, code)
        seat.value = seatResult.data
        offline.value = offline.value || seatResult.offline
        savedAt.value = seatResult.saved_at
      }
    }

    if (reason) showNotice(reason)
    else if (metaResult.data.published_version > previousVersion && previousVersion > 0) {
      showNotice(`มีอัปเดตใหม่ v.${metaResult.data.published_version}`)
    }
  } catch (e) {
    if (!meta.value) error.value = errorMessage(e)
  }
}

async function init(): Promise<void> {
  if (!slug.value) {
    loading.value = false
    return
  }
  setLastSlug(slug.value)
  loading.value = true
  error.value = ''
  try {
    const metaResult = await loadMeta(slug.value)
    meta.value = metaResult.data
    offline.value = metaResult.offline
    savedAt.value = metaResult.saved_at
    liveStuntId.value = metaResult.data.live.stunt_id
    liveActive.value = metaResult.data.live.is_active

    startLive()

    const savedCode = getLastAccess(slug.value)
    if (savedCode) {
      try {
        const seatResult = await loadClaim(slug.value, savedCode)
        seat.value = seatResult.data
        offline.value = offline.value || seatResult.offline
        savedAt.value = seatResult.saved_at
        view.value = 'list'
      } catch {
        // รหัสเดิมใช้ไม่ได้แล้ว (โดนลบ/งานเปลี่ยน) — กลับไปใส่ใหม่ ไม่ใช่ค้าง error
        removeCache(cacheKeys.access(slug.value, savedCode))
        removeCache(cacheKeys.lastAccess(slug.value))
      }
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function tickVersion(): Promise<void> {
  if (!slug.value || !meta.value) return
  const version = await checkVersion(slug.value)
  if (version !== null && version > meta.value.published_version) {
    await refreshData()
  }
}

function openSlug(): void {
  const value = slugInput.value.trim().toLowerCase()
  if (!value) return
  slug.value = value
}

watch(slug, () => {
  seat.value = null
  meta.value = null
  view.value = 'code'
  void init()
})

onMounted(() => {
  void init()
  versionTimer = window.setInterval(() => void tickVersion(), 60_000)
  onlineHandler = () => void refreshData('กลับมาออนไลน์แล้ว — อัปเดตข้อมูลล่าสุด')
  window.addEventListener('online', onlineHandler)
})

onUnmounted(() => {
  stopLive()
  if (versionTimer) window.clearInterval(versionTimer)
  if (noticeTimer) window.clearTimeout(noticeTimer)
  if (onlineHandler) window.removeEventListener('online', onlineHandler)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="min-h-[100dvh] bg-canvas">
    <!-- ไม่มี slug: เปิดจาก home screen หลังติดตั้ง หรือลิงก์ไม่มีรหัสงาน -->
    <div v-if="!hasEvent" class="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center justify-center px-5 text-center">
      <div class="grid h-16 w-16 place-items-center rounded-2xl bg-brand font-display text-3xl font-extrabold text-white">P</div>
      <h1 class="mt-4 font-display text-title-l font-bold text-ink-1">Pixel Stand</h1>
      <p class="mt-2 text-body text-ink-2">
        เปิดลิงก์/QR ของงานจากผู้ดูแล แล้วใส่รหัสล็อกอินของที่นั่งคุณ
      </p>
      <form class="mt-5 flex w-full gap-2" @submit.prevent="openSlug">
        <input
          v-model="slugInput"
          placeholder="รหัสงาน เช่น sport69"
          class="h-11 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body"
        />
        <button class="h-11 shrink-0 rounded-control bg-brand px-4 text-sm font-semibold text-white" type="submit">
          เปิด
        </button>
      </form>
    </div>

    <!-- กำลังโหลด -->
    <div v-else-if="loading" class="mx-auto max-w-2xl px-4 py-10">
      <div class="h-8 w-48 rounded-control bg-surface skeleton-shimmer" />
      <div class="mt-4 h-64 rounded-card border border-line bg-surface skeleton-shimmer" />
      <p class="mt-3 text-center text-caption text-ink-3">กำลังโหลดโพย…</p>
    </div>

    <!-- error ระดับงาน -->
    <div v-else-if="error && !meta" class="mx-auto flex min-h-[100dvh] max-w-md flex-col items-center justify-center px-5 text-center">
      <i class="bi bi-wifi-off text-4xl text-ink-3" aria-hidden="true" />
      <h1 class="mt-3 font-display text-title-m font-bold text-ink-1">เปิดงานไม่ได้</h1>
      <p class="mt-1 text-body text-ink-2">{{ error }}</p>
      <button class="mt-4 h-11 rounded-control bg-brand px-5 text-sm font-bold text-white" @click="refreshData('ลองโหลดใหม่แล้ว')">
        ลองใหม่
      </button>
      <button class="mt-2 text-sm text-ink-2 hover:text-brand" @click="slug = ''">เปลี่ยนรหัสงาน</button>
    </div>

    <template v-else-if="meta">
      <!-- แบนเนอร์สถานะ -->
      <div v-if="showOfflineBanner" class="sticky top-0 z-30 bg-warn-soft px-4 py-2 text-center text-caption font-semibold text-warn">
        กำลังใช้ข้อมูลออฟไลน์{{ savedAt ? ` (บันทึก ${savedAtText(savedAt)})` : '' }} —
        ข้อมูลอาจไม่ใช่เวอร์ชันล่าสุด
      </div>
      <div v-if="notice" class="sticky top-0 z-30 bg-ok-soft px-4 py-2 text-center text-caption font-semibold text-ok-strong">
        {{ notice }}
      </div>

      <CodeEntry
        v-if="view === 'code'"
        :meta="meta"
        :busy="busy"
        :error="seatError"
        @claim="claim"
      />

      <CueList
        v-else-if="view === 'list' && seat"
        :meta="meta"
        :seat="seat"
        :offline="offline"
        :saved-at="savedAt"
        :live-connected="liveConnected"
        @focus="openFocus"
        @change-seat="changeCode"
      />

      <FocusMode
        v-if="view === 'focus' && seat"
        :meta="meta"
        :seat="seat"
        :start-index="focusIndex"
        :live-stunt-id="liveStuntId"
        :live-active="liveActive"
        @close="closeFocus"
      />
    </template>
  </div>
</template>
