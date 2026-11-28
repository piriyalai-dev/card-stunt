import api from './api'
import type { UserCreate, UserOut, UserUpdate } from '@/types/domain'

const BASE = '/api/v1/users'

export async function listUsers(): Promise<UserOut[]> {
  return (await api.get(BASE)) as unknown as UserOut[]
}

export async function createUser(body: UserCreate): Promise<UserOut> {
  return (await api.post(BASE, body)) as unknown as UserOut
}

export async function updateUser(id: number, body: UserUpdate): Promise<UserOut> {
  return (await api.patch(`${BASE}/${id}`, body)) as unknown as UserOut
}

export async function deleteUser(id: number): Promise<void> {
  await api.delete(`${BASE}/${id}`)
}
