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

async function parseError(response: Response): Promise<PublicApiError> {
  let detail = 'โหลดข้อมูลไม่สำเร็จ'
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') detail = body.detail
  } catch {
    /* body ไม่ใช่ JSON */
  }
  return new PublicApiError(detail, response.status)
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

  if (!response.ok) throw await parseError(response)
  return (await response.json()) as T
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${apiBase()}${path}`, {
      method: 'POST',
      signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (error) {
    throw new PublicApiError(
      error instanceof Error && error.name === 'AbortError'
        ? 'ยกเลิกคำขอ'
        : 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้',
    )
  }

  if (!response.ok) throw await parseError(response)
  return (await response.json()) as T
}

// ── fetch ───────────────────────────────────────────────────────────

export function fetchMeta(slug: string, signal?: AbortSignal): Promise<PublicMeta> {
  return getJson(`/api/v1/public/events/${encodeURIComponent(slug)}/meta`, signal)
}

/** ล็อกอินด้วยรหัสสุ่มที่พิมพ์แจกนักเรียน — คืนโพยของที่นั่งนั้น */
export function claimSeat(slug: string, accessCode: string, signal?: AbortSignal): Promise<PublicSeat> {
  return postJson(
    `/api/v1/public/events/${encodeURIComponent(slug)}/claim`,
    { access_code: accessCode },
    signal,
  )
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

export function cacheClaimPayload(slug: string, code: string, seat: PublicSeat): Cached<PublicSeat> {
  return writeCache(cacheKeys.access(slug, code), seat)
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

export async function loadClaim(
  slug: string,
  accessCode: string,
  signal?: AbortSignal,
): Promise<LoadResult<PublicSeat>> {
  const key = cacheKeys.access(slug, accessCode)
  try {
    const data = await claimSeat(slug, accessCode, signal)
    const entry = cacheClaimPayload(slug, accessCode, data)
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
