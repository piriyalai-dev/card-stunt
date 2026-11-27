import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authService from '@/services/auth'
import { clearQueryCache } from '@/services/queryCache'
import type { AuthUser } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<AuthUser | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)

  const displayName = computed(() => user.value?.display_name || user.value?.username || '')
  const role = computed(() => user.value?.role ?? null)
  const isAdmin = computed(() => user.value?.is_admin ?? false)
  const permissions = computed(() => user.value?.permissions || [])
  const mustChangePassword = computed(() => user.value?.must_change_password ?? false)

  function setToken(token: string) {
    accessToken.value = token
    localStorage.setItem('access_token', token)
  }

  function setUser(u: AuthUser) {
    user.value = u
    localStorage.setItem('user_id_str', String(u.id))
  }

  async function login(username: string, password: string): Promise<AuthUser> {
    const res = await authService.login(username, password)
    clearQueryCache()
    setToken(res.access_token)
    setUser(res.user)
    return res.user
  }

  async function loadMe() {
    if (!accessToken.value) return null
    const me = await authService.fetchMe()
    setUser(me)
    return me
  }

  function markPasswordChanged() {
    if (user.value) user.value.must_change_password = false
  }

  function hasPermission(perm: string): boolean {
    if (isAdmin.value) return true
    return permissions.value.includes(perm)
  }

  function logout() {
    clearQueryCache()
    accessToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_id_str')
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
    loadMe,
    markPasswordChanged,
    hasPermission,
    logout,
  }
})
