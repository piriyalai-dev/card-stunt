/**
 * 💾 Offline cache ของฝั่งผู้ชม (localStorage)
 *
 * ⛔ **ห้ามย้ายไป service worker** — SW cache เป็น per-origin ไม่ใช่ per-user และกฎของ
 *    โปรเจกต์ห้าม cache `/api` ใน `sw.js` เด็ดขาด (ดู `public/sw.js`)
 * ✅ ข้อมูล public ไม่มีข้อมูลส่วนตัวนอกจากชื่อ/เลขนักศึกษา *ของที่นั่งที่ผู้ใช้ใส่รหัสล็อกอิน*
 *    ⇒ เก็บใน localStorage ของเครื่องนั้นเป็นเรื่องที่ผู้ใช้คาดหมาย (เปิดออฟไลน์กลางสนาม)
 */

const PREFIX = 'pixelstand:v1'

export interface Cached<T> {
  data: T
  saved_at: number
}

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string): boolean {
  try {
    localStorage.setItem(key, value)
    return true
  } catch {
    // โหมดส่วนตัว/พื้นที่เต็ม — ใช้งานออนไลน์ต่อไปได้ ไม่ใช่ error ที่ต้องรบกวนผู้ใช้
    return false
  }
}

function safeRemove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

export const cacheKeys = {
  meta: (slug: string) => `${PREFIX}:event:${slug}:meta`,
  access: (slug: string, code: string) =>
    `${PREFIX}:event:${slug}:access:${code.trim().toUpperCase()}`,
  lastAccess: (slug: string) => `${PREFIX}:event:${slug}:last-access`,
  lastSlug: () => `${PREFIX}:last-slug`,
  followLive: () => `${PREFIX}:follow-live`,
}

export function readCache<T>(key: string): Cached<T> | null {
  const raw = safeGet(key)
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Cached<T>
    if (!parsed || typeof parsed.saved_at !== 'number' || !parsed.data) return null
    return parsed
  } catch {
    return null
  }
}

export function writeCache<T>(key: string, data: T): Cached<T> {
  const entry: Cached<T> = { data, saved_at: Date.now() }
  safeSet(key, JSON.stringify(entry))
  return entry
}

export function removeCache(key: string): void {
  safeRemove(key)
}

export function setLastSlug(slug: string): void {
  safeSet(cacheKeys.lastSlug(), slug)
}

export function getLastSlug(): string | null {
  return safeGet(cacheKeys.lastSlug())
}

export function setLastAccess(slug: string, code: string): void {
  safeSet(cacheKeys.lastAccess(slug), code.trim().toUpperCase())
}

export function getLastAccess(slug: string): string | null {
  return safeGet(cacheKeys.lastAccess(slug))
}
