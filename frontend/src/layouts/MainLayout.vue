<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { NAV_GROUPS, routeTitles } from '@/constants/nav'
import { roleLabel } from '@/constants/roles'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const title = computed(() => {
  const name = route.name ? String(route.name) : ''
  return route.meta.headerTitle || routeTitles[name] || 'Pixel Stand'
})

const groups = computed(() =>
  NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((item) => !item.permission || authStore.hasPermission(item.permission)),
  })).filter((g) => g.items.length > 0),
)

const displayName = computed(() => authStore.displayName || '—')
const roleText = computed(() => roleLabel(authStore.role))

function handleLogout() {
  authStore.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="flex h-[100dvh] overflow-hidden bg-canvas font-sans text-ink-1">
    <!-- sidebar (desktop) -->
    <aside class="hidden lg:flex lg:w-64 shrink-0 flex-col border-r border-line bg-surface">
      <div class="flex items-center gap-2.5 h-16 px-5 border-b border-line">
        <div class="grid place-items-center w-8 h-8 rounded-lg bg-brand text-white font-display font-extrabold">P</div>
        <span class="font-display font-bold">Pixel Stand</span>
      </div>

      <nav class="flex-1 overflow-y-auto py-4 px-3">
        <div v-for="g in groups" :key="g.key" class="mb-5">
          <div class="px-2 mb-1 text-caption font-semibold text-ink-3">{{ g.label }}</div>
          <RouterLink
            v-for="item in g.items"
            :key="item.key"
            :to="item.to"
            class="flex items-center gap-2.5 px-2 py-2.5 rounded-control text-sm"
            :class="route.name === item.to.name ? 'text-brand bg-brand-tint' : 'text-ink-2 hover:bg-brand-tint hover:text-brand'"
          >
            <i :class="`bi ${item.icon}`" aria-hidden="true"></i>
            {{ item.label }}
          </RouterLink>
        </div>
      </nav>

      <div class="border-t border-line px-5 py-4">
        <div class="font-semibold text-sm">{{ displayName }}</div>
        <div class="text-caption text-ink-2">{{ roleText }}</div>
        <button class="mt-2 text-sm text-ink-2 hover:text-brand" @click="handleLogout">ออกจากระบบ</button>
      </div>
    </aside>

    <!-- main column -->
    <div class="flex-1 min-w-0 flex flex-col overflow-hidden">
      <header class="shrink-0 flex items-center gap-3 h-16 px-5 border-b border-line bg-surface lg:hidden">
        <div class="grid place-items-center w-8 h-8 rounded-lg bg-brand text-white font-display font-extrabold">P</div>
        <h1 class="font-display font-bold text-title-m truncate">{{ title }}</h1>
        <button class="ml-auto text-sm text-ink-2 hover:text-brand" @click="handleLogout">ออกจากระบบ</button>
      </header>

      <main class="flex-1 overflow-y-auto">
        <div class="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
