/**
 * 🪪 ชื่อไทยของบทบาท — ตรงกับ `backend/config/roles.json`
 */
export const ROLE_LABELS: Record<string, string> = {
  admin: 'แอดมิน',
  designer: 'นักออกแบบ',
  staff: 'สตาฟ',
}

export function roleLabel(code: string | null | undefined): string {
  if (!code) return ''
  return ROLE_LABELS[code] ?? code
}
