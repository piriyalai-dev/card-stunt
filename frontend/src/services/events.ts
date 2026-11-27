import api from './api'
import type { EventCreate, EventOut, EventUpdate } from '@/types/domain'

const BASE = '/api/v1/events'

export async function listEvents(): Promise<EventOut[]> {
  return (await api.get(BASE)) as unknown as EventOut[]
}

export async function getEvent(eventId: number): Promise<EventOut> {
  return (await api.get(`${BASE}/${eventId}`)) as unknown as EventOut
}

export async function createEvent(body: EventCreate): Promise<EventOut> {
  return (await api.post(BASE, body)) as unknown as EventOut
}

export async function updateEvent(eventId: number, body: EventUpdate): Promise<EventOut> {
  return (await api.patch(`${BASE}/${eventId}`, body)) as unknown as EventOut
}

export async function deleteEvent(eventId: number): Promise<void> {
  await api.delete(`${BASE}/${eventId}`)
}

export async function publishEvent(eventId: number): Promise<EventOut> {
  return (await api.post(`${BASE}/${eventId}/publish`)) as unknown as EventOut
}

export async function duplicateEvent(
  eventId: number,
  body: { name: string; slug?: string | null },
): Promise<EventOut> {
  return (await api.post(`${BASE}/${eventId}/duplicate`, body)) as unknown as EventOut
}
