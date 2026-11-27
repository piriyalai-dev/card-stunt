<script setup lang="ts">
/**
 * 🎓 Student Viewer (public PWA) — /e/:slug?
 *
 * 3 สถานะ: picker (เลือกที่นั่ง) → list (โพยทุกฉาก) → focus (โฟกัสกลางแสตน)
 *
 * - ข้อมูล meta/seat ถูก cache ลง localStorage ⇒ เปิดออฟไลน์กลางสนามได้หลังเคยเปิดออนไลน์
 * - SSE live sync เป็น "ของแถม": หลุดได้โดยผู้ใช้ยังเลื่อนเองได้ (ห้าม block UI)
 * - เวอร์ชันใหม่ของงาน: เช็คทุก 60 วิ + ตอนกลับมา online แล้วโหลดใหม่ให้อัตโนมัติ
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import CueList from '@/components/viewer/CueList.vue'
import FocusMode from '@/components/viewer/FocusMode.vue'
import SeatPicker from '@/components/viewer/SeatPicker.vue'
import { errorMessage } from '@/lib/format'
import {
  cacheKeys,
  getLastSlug,
  readCache,
  removeCache,
  setLastSlug,
  writeCache,
} from '@/services/publicCache'
import {
  checkVersion,
  loadMeta,
  loadSeatByCode,
  loadSeatByPosition,
  subscribeLive,
} from '@/services/publicApi'
import type { PublicMeta, PublicSeat } from '@/types/public'

interface SavedSelection {
  stand_id: number
  row: number
  col: number
  row_label: string
  seat_label: string
}

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
const view = ref<'picker' | 'list' | 'focus'>('picker')
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

function persistSelection(data: PublicSeat): void {
  const saved: SavedSelection = {
    stand_id: data.stand_id,
    row: data.row_index + 1,
    col: data.col_index + 1,
    row_label: data.row_label,
    seat_label: data.seat_label,
  }
  writeCache(cacheKeys.selection(slug.value), saved)
}

async function applySeatLoader(loader: () => Promise<{ data: PublicSeat; offline: boolean; saved_at: number }>): Promise<void> {
  busy.value = true
  seatError.value = ''
  try {
    const result = await loader()
    seat.value = result.data
    // ใช้ค่าของคำขอล่าสุด (ถ้ากลับมาออนไลน์แล้ว ไม่ควรค้างป้ายออฟไลน์จากรอบก่อน)
    offline.value = result.offline
    savedAt.value = result.saved_at
    persistSelection(result.data)
    view.value = 'list'
    window.scrollTo({ top: 0 })
  } catch (e) {
    seatError.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

function selectSeat(payload: { standId: number; row: number; col: number }): void {
  void applySeatLoader(() =>
    loadSeatByPosition(slug.value, payload.standId, payload.row, payload.col),
  )
}

function searchCode(code: string): void {
  void applySeatLoader(() => loadSeatByCode(slug.value, code))
}

function changeSeat(): void {
  removeCache(cacheKeys.selection(slug.value))
  seat.value = null
  seatError.value = ''
  view.value = 'picker'
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
      const current = seat.value
      const seatResult = await loadSeatByPosition(
        slug.value, current.stand_id, current.row_index + 1, current.col_index + 1,
      )
      seat.value = seatResult.data
      offline.value = offline.value || seatResult.offline
      savedAt.value = seatResult.saved_at
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

    const saved = readCache<SavedSelection>(cacheKeys.selection(slug.value))
    if (saved) {
      try {
        const seatResult = await loadSeatByPosition(
          slug.value, saved.data.stand_id, saved.data.row, saved.data.col,
        )
        seat.value = seatResult.data
        offline.value = offline.value || seatResult.offline
        savedAt.value = seatResult.saved_at
        view.value = 'list'
      } catch {
        // ที่นั่งเดิมใช้ไม่ได้แล้ว (ถูกแก้ผัง/ปิดช่อง) — กลับไปเลือกใหม่ ไม่ใช่ค้าง error
        removeCache(cacheKeys.selection(slug.value))
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
  view.value = 'picker'
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
        เปิดลิงก์/QR ของงานจากผู้ดูแล เพื่อดูโพยของที่นั่งคุณ
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

      <SeatPicker
        v-if="view === 'picker'"
        :meta="meta"
        :busy="busy"
        :error="seatError"
        @select="selectSeat"
        @search-code="searchCode"
      />

      <CueList
        v-else-if="view === 'list' && seat"
        :meta="meta"
        :seat="seat"
        :offline="offline"
        :saved-at="savedAt"
        :live-connected="liveConnected"
        @focus="openFocus"
        @change-seat="changeSeat"
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
