import api from './api'
import type { ExportFormat, ExportJob } from '@/types/domain'

const BASE = '/api/v1'

export async function listExports(eventId: number): Promise<ExportJob[]> {
  return (await api.get(`${BASE}/events/${eventId}/exports`)) as unknown as ExportJob[]
}

export async function createExport(
  eventId: number,
  body: { format: ExportFormat; stand_id?: number | null; scope?: string },
): Promise<ExportJob> {
  return (await api.post(`${BASE}/events/${eventId}/exports`, body)) as unknown as ExportJob
}

export async function getExport(jobId: number): Promise<ExportJob> {
  // สถานะต้องสด — ห้าม cache (poll ทุก 2 วิ)
  return (await api.get(`${BASE}/exports/${jobId}`, { noCache: true })) as unknown as ExportJob
}

export async function retryExport(jobId: number): Promise<ExportJob> {
  return (await api.post(`${BASE}/exports/${jobId}/retry`)) as unknown as ExportJob
}

export async function downloadExport(jobId: number): Promise<Blob> {
  return (await api.get(`${BASE}/exports/${jobId}/download`, {
    responseType: 'blob',
    noCache: true,
  })) as unknown as Blob
}

/** บันทึก Blob เป็นไฟล์ผ่าน <a download> — ใช้ร่วมกันทั้ง export */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
