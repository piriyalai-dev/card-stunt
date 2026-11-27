import api from './api'
import type { StandCreate, StandOut, StandResize, StandUpdate } from '@/types/domain'

export async function listStands(eventId: number): Promise<StandOut[]> {
  return (await api.get(`/api/v1/events/${eventId}/stands`)) as unknown as StandOut[]
}

export async function getStand(standId: number): Promise<StandOut> {
  return (await api.get(`/api/v1/stands/${standId}`)) as unknown as StandOut
}

export async function createStand(eventId: number, body: StandCreate): Promise<StandOut> {
  return (await api.post(`/api/v1/events/${eventId}/stands`, body)) as unknown as StandOut
}

export async function updateStand(
  eventId: number,
  standId: number,
  body: StandUpdate,
): Promise<StandOut> {
  return (await api.patch(
    `/api/v1/events/${eventId}/stands/${standId}`,
    body,
  )) as unknown as StandOut
}

export async function resizeStand(standId: number, body: StandResize): Promise<StandOut> {
  return (await api.post(`/api/v1/stands/${standId}/resize`, body)) as unknown as StandOut
}

export async function setBlockedSeats(
  standId: number,
  blockedSeats: Array<{ row: number; col: number }>,
): Promise<StandOut> {
  return (await api.patch(`/api/v1/stands/${standId}/blocked-seats`, {
    blocked_seats: blockedSeats,
  })) as unknown as StandOut
}
