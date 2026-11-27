/**
 * 🔗 "กลับไปที่ที่ผู้ใช้ตั้งใจจะไป" หลังล็อกอิน — สัญญาระหว่าง guard กับหน้า Login
 *
 * 🔒 ค่านี้มาจาก URL ⇒ ถือเป็นข้อมูลที่ผู้ใช้ควบคุมได้ — ต้องกรองเสมอ
 *    (กัน open redirect: `/login?redirect=https://evil.example`)
 */

export const REDIRECT_QUERY = 'redirect'

/** แปลง `route.query.redirect` เป็น path ที่ปลอดภัย — คืน `null` ถ้าไม่ผ่าน */
export function safeRedirect(raw: unknown): string | null {
  const value = Array.isArray(raw) ? raw[0] : raw
  if (typeof value !== 'string') return null
  if (!value.startsWith('/admin/')) return null
  if (value.includes('\\')) return null
  return value
}
