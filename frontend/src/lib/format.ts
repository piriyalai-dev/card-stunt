/** ตัวช่วยแปลงค่าที่ใช้ใน UI — ภาษาไทยล้วน (ไม่มี i18n ตาม design §8.1) */

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('th-TH').format(value)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('th-TH', { dateStyle: 'medium' }).format(date)
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('th-TH', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

/** วันที่ของ `<input type="date">` (YYYY-MM-DD) จาก ISO */
export function toDateInputValue(iso: string | null | undefined): string {
  if (!iso) return ''
  return iso.slice(0, 10)
}

export function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message) return error.message
  return 'เกิดข้อผิดพลาดที่ไม่คาดคิด'
}
