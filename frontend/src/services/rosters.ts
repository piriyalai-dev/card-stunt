import api from './api'
import type { RosterOut } from '@/types/domain'

const BASE = '/api/v1'

export async function listRosters(eventId: number, standId?: number): Promise<RosterOut[]> {
  return (await api.get(`${BASE}/events/${eventId}/rosters`, {
    params: standId ? { stand_id: standId } : undefined,
  })) as unknown as RosterOut[]
}

export async function createRoster(
  eventId: number,
  body: {
    stand_id: number
    row_index: number
    col_index: number
    student_code?: string | null
    student_name: string
    note?: string | null
  },
): Promise<RosterOut> {
  return (await api.post(`${BASE}/events/${eventId}/rosters`, body)) as unknown as RosterOut
}

export async function importRoster(
  eventId: number,
  standId: number,
  file: File,
): Promise<{ inserted: number; errors: string[]; total: number }> {
  const form = new FormData()
  form.append('stand_id', String(standId))
  form.append('file', file)
  return (await api.post(`${BASE}/events/${eventId}/rosters/import`, form, {
    // axios default เป็น application/json ⇒ ต้องบอก multipart ไม่งั้น FormData ถูก JSON.stringify
    headers: { 'Content-Type': 'multipart/form-data' },
  })) as unknown as { inserted: number; errors: string[]; total: number }
}

export async function deleteRoster(rosterId: number): Promise<void> {
  await api.delete(`${BASE}/rosters/${rosterId}`)
}
