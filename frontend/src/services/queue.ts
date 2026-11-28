import api from './api'
import type { LiveQueueItem } from '@/types/domain'

const BASE = '/api/v1/events'

export async function getQueue(eventId: number): Promise<LiveQueueItem[]> {
  return (await api.get(`${BASE}/${eventId}/queue`, { noCache: true })) as unknown as LiveQueueItem[]
}

export async function setQueue(eventId: number, order: number[]): Promise<LiveQueueItem[]> {
  return (await api.put(`${BASE}/${eventId}/queue`, { order })) as unknown as LiveQueueItem[]
}

export async function insertQueue(
  eventId: number,
  stuntId: number,
  position: number,
): Promise<LiveQueueItem[]> {
  return (await api.post(`${BASE}/${eventId}/queue/insert`, {
    stunt_id: stuntId,
    position,
  })) as unknown as LiveQueueItem[]
}

export async function removeQueue(eventId: number, stuntId: number): Promise<LiveQueueItem[]> {
  return (await api.delete(`${BASE}/${eventId}/queue/${stuntId}`)) as unknown as LiveQueueItem[]
}
