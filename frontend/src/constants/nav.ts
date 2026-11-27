// 🗺️ แผนที่เมนูฝั่ง admin — ที่เดียวที่ประกาศ "มีอะไรในเมนูบ้าง"
// การกรองสิทธิ์ (hasPermission) อยู่ที่ MainLayout

export interface NavItem {
  key: string
  label: string
  icon: string
  to: { name: string }
  permission?: string
}

export interface NavGroup {
  key: string
  label: string
  items: NavItem[]
}

export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'overview',
    label: 'ภาพรวม',
    items: [
      { key: 'home', label: 'แดชบอร์ด', icon: 'bi-grid-1x2', to: { name: 'admin-home' } },
    ],
  },
  // Phase 3/4 จะเพิ่มกลุ่ม "ออกแบบ" (stunts / palettes) และ "ควบคุม" (live / rosters) ที่นี่
]

/** ชื่อหน้าสำหรับหัวแถบ — route ใหม่ต้องเพิ่มชื่อที่นี่ */
export const routeTitles: Record<string, string> = {
  'admin-home': 'แดชบอร์ด',
  'admin-password': 'เปลี่ยนรหัสผ่าน',
}
