import api from './api'
import type { AuditLogOptions, AuditLogPage } from '@/types/domain'

const BASE = '/api/v1/audit-logs'

export interface AuditQuery {
  action?: string
  entity_type?: string
  entity_id?: string
  status?: string
  service_name?: string
  q?: string
  limit?: number
  cursor?: string
}

export async function listAuditLogs(query: AuditQuery = {}): Promise<AuditLogPage> {
  // ห้าม cache — audit ต้องสดเสมอ (filters เปลี่ยนบ่อย + ไม่ควรเห็นของเก่า)
  return (await api.get(BASE, { params: query, noCache: true })) as unknown as AuditLogPage
}

export async function getAuditOptions(): Promise<AuditLogOptions> {
  return (await api.get(`${BASE}/options`, { noCache: true })) as unknown as AuditLogOptions
}
