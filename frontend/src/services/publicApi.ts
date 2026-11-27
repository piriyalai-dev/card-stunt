/**
 * 🌐 Public API (ไม่ auth) — ใช้ `fetch` ตรง ๆ **ไม่ใช่ axios instance ของ admin**
 *
 * เหตุผล: `services/api.ts` มี interceptor 401 ที่พาไปหน้า Login + cache SWR ที่ผูกกับ token
 * ⇒ ถ้าผู้ชมมี token หมดอายุค้างใน localStorage แล้วยิง public endpoint ผ่าน instance นั้น
 *   จะถูกเด้งออกจากหน้าโฟกัสกลางสนามทั้งที่ endpoint นี้ไม่ต้องล็อกอินเลย
 */
import type {
  LiveState,
  PublicMeta,
  PublicSeat,
  PublicVersion,
} from '@/types/public'
import {
  cacheKeys,
  readCache,
  writeCache,
  type Cached,
} from './publicCache'

export class PublicApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'PublicApiError'
    this.status = status
  }
}

export function apiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '')
}

/** แปลง path จาก backend (เช่น signed media URL) เป็น absolute */
export function absoluteApiUrl(path: string | null | undefined): string | null {
  if (!path) return null
  if (/^https?:\/\//.test(path)) return path
  return `${apiBase()}${path.startsWith('/') ? '' : '/'}${path}`
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, {
      signal,
      headers: { Accept: 'application/json' },
    })
  } catch (error) {
    throw new PublicApiError(
      error instanceof Error && error.name === 'AbortError'
        ? 'ยกเลิกคำขอ'
        : 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้',
    )
  }

  if (!response.ok) {
    let detail = 'โหลดข้อมูลไม่สำเร็จ'
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* body ไม่ใช่ JSON */
    }
    throw new PublicApiError(detail, response.status)
  }
  return (await response.json()) as T
}

// ── fetch ───────────────────────────────────────────────────────────

export function fetchMeta(slug: string, signal?: AbortSignal): Promise<PublicMeta> {
  return getJson(`/api/v1/public/events/${encodeURIComponent(slug)}/meta`, signal)
}

export function fetchSeatByPosition(
  slug: string,
  standId: number,
  row: number,
  col: number,
  signal?: AbortSignal,
): Promise<PublicSeat> {
  const params = new URLSearchParams({ row: String(row), col: String(col), stand_id: String(standId) })
  return getJson(`/api/v1/public/events/${encodeURIComponent(slug)}/seat?${params}`, signal)
}

export function fetchSeatByCode(
  slug: string,
  studentCode: string,
  signal?: AbortSignal,
): Promise<PublicSeat> {
  const params = new URLSearchParams({ student_code: studentCode })
  return getJson(`/api/v1/public/events/${encodeURIComponent(slug)}/seat?${params}`, signal)
}

export function fetchVersion(slug: string, signal?: AbortSignal): Promise<PublicVersion> {
  return getJson(`/api/v1/public/events/${encodeURIComponent(slug)}/version`, signal)
}

// ── offline-first loaders ──────────────────────────────────────────

export interface LoadResult<T> {
  data: T
  offline: boolean
  saved_at: number
}

export function cacheMetaPayload(slug: string, data: PublicMeta): Cached<PublicMeta> {
  return writeCache(cacheKeys.meta(slug), data)
}

export function cacheSeatPayload(slug: string, seat: PublicSeat): Cached<PublicSeat> {
  const entry = writeCache(
    cacheKeys.seat(slug, seat.stand_id, seat.row_index, seat.col_index),
    seat,
  )
  if (seat.student?.student_code) {
    writeCache(cacheKeys.seatCode(slug, seat.student.student_code), seat)
  }
  return entry
}

export async function loadMeta(slug: string, signal?: AbortSignal): Promise<LoadResult<PublicMeta>> {
  const key = cacheKeys.meta(slug)
  try {
    const data = await fetchMeta(slug, signal)
    const entry = cacheMetaPayload(slug, data)
    return { data, offline: false, saved_at: entry.saved_at }
  } catch (error) {
    const cached = readCache<PublicMeta>(key)
    if (cached) return { data: cached.data, offline: true, saved_at: cached.saved_at }
    throw error
  }
}

export async function loadSeatByPosition(
  slug: string,
  standId: number,
  row: number,
  col: number,
  signal?: AbortSignal,
): Promise<LoadResult<PublicSeat>> {
  // ⚠️ `cacheSeatPayload` เก็บด้วย index **0-based** (จาก response) แต่ผู้เรียกส่ง label 1-based
  //    (API public รับ 1-based) ⇒ key ต้องลบ 1 ไม่งั้น offline restore จะ miss เสมอ
  const key = cacheKeys.seat(slug, standId, row - 1, col - 1)
  try {
    const data = await fetchSeatByPosition(slug, standId, row, col, signal)
    const entry = cacheSeatPayload(slug, data)
    return { data, offline: false, saved_at: entry.saved_at }
  } catch (error) {
    const cached = readCache<PublicSeat>(key)
    if (cached) return { data: cached.data, offline: true, saved_at: cached.saved_at }
    throw error
  }
}

export async function loadSeatByCode(
  slug: string,
  studentCode: string,
  signal?: AbortSignal,
): Promise<LoadResult<PublicSeat>> {
  const key = cacheKeys.seatCode(slug, studentCode)
  try {
    const data = await fetchSeatByCode(slug, studentCode, signal)
    const entry = cacheSeatPayload(slug, data)
    return { data, offline: false, saved_at: entry.saved_at }
  } catch (error) {
    const cached = readCache<PublicSeat>(key)
    if (cached) return { data: cached.data, offline: true, saved_at: cached.saved_at }
    throw error
  }
}

/** เช็คเวอร์ชันใหม่แบบเงียบ ๆ — คืน null ถ้าออฟไลน์ (ไม่ใช่ error ที่ต้องแสดง) */
export async function checkVersion(slug: string): Promise<number | null> {
  try {
    const v = await fetchVersion(slug)
    return v.published_version
  } catch {
    return null
  }
}

// ── live sync (SSE) ─────────────────────────────────────────────────

export interface LiveHandlers {
  onState: (state: LiveState) => void
  onOpen?: () => void
  onError?: () => void
}

/** เปิด SSE — คืนฟังก์ชันปิด · EventSource reconnect เองอัตโนมัติ */
export function subscribeLive(slug: string, handlers: LiveHandlers): () => void {
  if (typeof window === 'undefined' || typeof EventSource === 'undefined') return () => {}

  const source = new EventSource(
    `${apiBase()}/api/v1/public/events/${encodeURIComponent(slug)}/live`,
  )
  const onMessage = (event: MessageEvent) => {
    try {
      handlers.onState(JSON.parse(event.data) as LiveState)
    } catch {
      /* payload เพี้ยน — ข้าม */
    }
  }
  source.addEventListener('snapshot', onMessage as EventListener)
  source.addEventListener('live', onMessage as EventListener)
  source.onopen = () => handlers.onOpen?.()
  source.onerror = () => handlers.onError?.()

  return () => source.close()
}
