import type { RouteLocationRaw } from 'vue-router'

export interface AppRouteMeta {
  requiresAuth?: boolean
  requiresPermission?: string
  headerBack?: RouteLocationRaw | false
  headerTitle?: string
}

declare module 'vue-router' {
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface RouteMeta extends AppRouteMeta {}
}
