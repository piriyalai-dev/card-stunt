import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authService from '@/services/auth'
import { accessToken } from '@/services/token'
import { clearQueryCache } from '@/services/queryCache'
import type { AuthUser } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  const displayName = computed(() => user.value?.display_name || user.value?.username || '')
  const role = computed(() => user.value?.role ?? null)
  const isAdmin = computed(() => user.value?.is_admin ?? false)
  const permissions = computed(() => user.value?.permissions || [])
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  function setToken(token: string | null) {
    accessToken.value = token
  }

  function setUser(u: AuthUser | null) {
    user.value = u
  }

  async function login(username: string, password: string): Promise<AuthUser> {
    const res = await authService.login(username, password)
    clearQueryCache()
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }

  // เปิดหน้าใหม่ (F5) — ไม่มี access token ใน memory → ขอใหม่จาก refresh cookie (httpOnly)
  async function bootstrap(): Promise<void> {
    if (accessToken.value) {
      if (!user.value) await loadMe()
      return
    }
    const res = await authService.refresh()
    setToken(res.access_token)
    setUser(res.user)
  }

  async function loadMe() {
    if (!accessToken.value) return null
    const me = await authService.fetchMe()
    setUser(me)
    return me
  }

  function hasPermission(perm: string): boolean {
    if (isAdmin.value) return true
    return permissions.value.includes(perm)
  }

  async function logout() {
    try {
      await authService.logout()
    } catch {
      /* ignore — ล้างฝั่ง client ต่อให้ล้ม */
    } finally {
      clearQueryCache()
      setToken(null)
      setUser(null)
    }
  }

  return {
    accessToken,
    user,
    isAuthenticated,
    displayName,
    role,
    isAdmin,
    permissions,
    mustChangePassword,
    setToken,
    setUser,
    login,
    bootstrap,
    loadMe,
    hasPermission,
    logout,
  }
})
