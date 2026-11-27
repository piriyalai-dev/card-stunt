import { createRouter, createWebHistory } from 'vue-router'
import { REDIRECT_QUERY } from '@/router/redirect'
import { useAuthStore } from '@/stores/auth'
import MainLayout from '@/layouts/MainLayout.vue'

function getHomeRoute(): { name: string } {
  return { name: 'admin-home' }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/auth/LoginPage.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/admin',
      component: MainLayout,
      meta: { requiresAuth: true },
      redirect: () => getHomeRoute(),
      children: [
        {
          path: 'home',
          name: 'admin-home',
          component: () => import('@/views/admin/AdminHome.vue'),
          meta: { requiresAuth: true },
        },
        {
          // งาน (event) — แท็บย่อยทั้งหมดอยู่ใน EventWorkspace
          path: 'events/:eventId',
          component: () => import('@/views/admin/EventWorkspace.vue'),
          meta: { requiresAuth: true },
          children: [
            {
              path: '',
              name: 'event-overview',
              component: () => import('@/views/admin/EventOverview.vue'),
              meta: { requiresAuth: true },
            },
            {
              path: 'stands',
              name: 'event-stands',
              component: () => import('@/views/admin/StandConfigurator.vue'),
              meta: { requiresAuth: true, requiresPermission: 'MANAGE_STANDS' },
            },
            {
              path: 'palettes',
              name: 'event-palettes',
              component: () => import('@/views/admin/PaletteManager.vue'),
              meta: { requiresAuth: true, requiresPermission: 'MANAGE_PALETTES' },
            },
            {
              path: 'stunts',
              name: 'event-stunts',
              component: () => import('@/views/admin/StuntManager.vue'),
              meta: { requiresAuth: true, requiresPermission: 'MANAGE_STUNTS' },
            },
            {
              path: 'live',
              name: 'event-live',
              component: () => import('@/views/admin/LiveControl.vue'),
              meta: { requiresAuth: true, requiresPermission: 'CONTROL_LIVE' },
            },
            {
              path: 'exports',
              name: 'event-exports',
              component: () => import('@/views/admin/ExportCenter.vue'),
              meta: { requiresAuth: true, requiresPermission: 'EXPORT' },
            },
          ],
        },
        {
          path: 'stunts/:stuntId/studio',
          name: 'stunt-studio',
          component: () => import('@/views/admin/PixelStudio.vue'),
          meta: { requiresAuth: true, requiresPermission: 'MANAGE_STUNTS' },
        },
        {
          path: 'stunts/:stuntId/convert',
          name: 'stunt-convert',
          component: () => import('@/views/admin/ImageConverter.vue'),
          meta: { requiresAuth: true, requiresPermission: 'MANAGE_STUNTS' },
        },
        {
          path: 'password',
          name: 'admin-password',
          component: () => import('@/views/auth/ChangePassword.vue'),
          meta: { requiresAuth: true },
        },
      ],
    },
    {
      // โหมดนักเรียน (public) — slug เป็น optional เพื่อให้ PWA ที่ติดตั้งแล้วเปิด `/e`
      // แล้วกลับไปงานล่าสุดจาก localStorage ได้ (ดู StudentViewer)
      path: '/e/:slug?',
      name: 'viewer',
      component: () => import('@/views/viewer/StudentViewer.vue'),
      meta: { requiresAuth: false },
    },
    { path: '/', redirect: '/admin' },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      redirect: (to) => ({ name: 'login', query: { [REDIRECT_QUERY]: to.fullPath } }),
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const isAuthenticated = authStore.isAuthenticated

  if (to.meta.requiresAuth && !isAuthenticated) {
    return { name: 'login', query: { [REDIRECT_QUERY]: to.fullPath } }
  }

  if (isAuthenticated && !authStore.user) {
    try {
      await authStore.loadMe()
    } catch {
      /* ignore — user null → ตกไป route พื้นฐาน */
    }
  }

  if (to.path === '/login' && isAuthenticated) {
    return getHomeRoute()
  }

  if (isAuthenticated && authStore.mustChangePassword && to.name !== 'admin-password') {
    return { name: 'admin-password', query: { [REDIRECT_QUERY]: to.fullPath } }
  }

  const needPermission = to.meta.requiresPermission as string | undefined
  if (needPermission && isAuthenticated && !authStore.hasPermission(needPermission)) {
    return getHomeRoute()
  }

  return true
})

export default router
