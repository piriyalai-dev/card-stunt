import api from './api'
import type { AuthUser } from '@/types/auth'

export async function login(
  username: string,
  password: string,
): Promise<{ access_token: string; user: AuthUser }> {
  return (await api.post('/api/auth/login', { username, password })) as {
    access_token: string
    user: AuthUser
  }
}

export async function fetchMe(): Promise<AuthUser> {
  // ห้าม cache — เป็นตัวตนผู้ใช้; Pinia ถือ state ล่าสุดไว้อยู่แล้ว
  return (await api.get('/api/auth/me', { noCache: true })) as AuthUser
}

export async function changePassword(
  old_password: string,
  new_password: string,
): Promise<{ status: string }> {
  return (await api.post('/api/auth/change-password', { old_password, new_password })) as {
    status: string
  }
}
