import api from './api'
import type {
  RevisionOut,
  StuntCreate,
  StuntGrid,
  StuntOut,
  StuntStats,
  StuntUpdate,
} from '@/types/domain'

export async function listStunts(eventId: number): Promise<StuntOut[]> {
  return (await api.get(`/api/v1/events/${eventId}/stunts`)) as unknown as StuntOut[]
}

export async function getStunt(stuntId: number): Promise<StuntOut> {
  return (await api.get(`/api/v1/stunts/${stuntId}`)) as unknown as StuntOut
}

export async function createStunt(eventId: number, body: StuntCreate): Promise<StuntOut> {
  return (await api.post(`/api/v1/events/${eventId}/stunts`, body)) as unknown as StuntOut
}

export async function updateStunt(stuntId: number, body: StuntUpdate): Promise<StuntOut> {
  return (await api.patch(`/api/v1/stunts/${stuntId}`, body)) as unknown as StuntOut
}

export async function deleteStunt(stuntId: number): Promise<void> {
  await api.delete(`/api/v1/stunts/${stuntId}`)
}

export async function reorderStunts(eventId: number, order: number[]): Promise<void> {
  await api.patch(`/api/v1/events/${eventId}/stunts/reorder`, { order })
}

/** grid เต็ม (payload ใหญ่) — ใช้เฉพาะใน Pixel Studio ไม่ใช่ใน list */
export async function getGrid(stuntId: number): Promise<StuntGrid> {
  return (await api.get(`/api/v1/stunts/${stuntId}/grid`, {
    noCache: true,
  })) as unknown as StuntGrid
}

export async function saveGrid(
  stuntId: number,
  body: { grid_data?: Array<number | null>; note?: string },
): Promise<StuntOut> {
  return (await api.put(`/api/v1/stunts/${stuntId}/grid`, body)) as unknown as StuntOut
}

export async function listRevisions(stuntId: number): Promise<RevisionOut[]> {
  return (await api.get(
    `/api/v1/stunts/${stuntId}/revisions`,
  )) as unknown as RevisionOut[]
}

export async function restoreRevision(stuntId: number, revisionId: number): Promise<StuntOut> {
  return (await api.post(
    `/api/v1/stunts/${stuntId}/revisions/${revisionId}/restore`,
  )) as unknown as StuntOut
}

export async function uploadReference(stuntId: number, file: File): Promise<StuntOut> {
  const form = new FormData()
  form.append('file', file)
  return (await api.post(`/api/v1/stunts/${stuntId}/reference-image`, form, {
    // ⚠️ axios instance ตั้ง default Content-Type: application/json ไว้
    //    ⇒ transformRequest จะ JSON.stringify(FormData) และ FastAPI ตอบ 422
    //    การตั้ง multipart ที่นี่ทำให้ axios ข้าม JSON transform แล้วปล่อยให้
    //    browser ใส่ boundary เอง (resolveConfig จะลบ header นี้ออกในเบราว์เซอร์)
    headers: { 'Content-Type': 'multipart/form-data' },
  })) as unknown as StuntOut
}

export async function getStats(stuntId: number): Promise<StuntStats> {
  return (await api.get(`/api/v1/stunts/${stuntId}/stats`)) as unknown as StuntStats
}

export interface StuntMediaUrls {
  reference_url: string | null
  thumbnail_url: string | null
}

/** Signed URL ของภาพอ้างอิง (หมดอายุ ~15 นาที) — ใช้กับ `<img>`/overlay ได้โดยไม่ต้องแนบ token */
export async function getMediaUrls(stuntId: number): Promise<StuntMediaUrls> {
  return (await api.get(`/api/v1/stunts/${stuntId}/media-urls`)) as unknown as StuntMediaUrls
}
