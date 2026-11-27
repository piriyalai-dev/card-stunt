import api from './api'
import type { LiveAdminState } from '@/types/domain'

const BASE = '/api/v1'

export async function getLive(eventId: number): Promise<LiveAdminState> {
  return (await api.get(`${BASE}/events/${eventId}/live`, { noCache: true })) as unknown as LiveAdminState
}

export async function advanceLive(
  eventId: number,
  action: 'next' | 'prev' | 'goto',
  stuntId?: number,
): Promise<LiveAdminState> {
  return (await api.post(`${BASE}/events/${eventId}/live/advance`, {
    action,
    ...(stuntId !== undefined ? { stunt_id: stuntId } : {}),
  })) as unknown as LiveAdminState
}
