import { describe, it, expect } from 'vitest'
import { safeRedirect } from '@/router/redirect'

describe('safeRedirect', () => {
  it('ยอมรับ path ที่ขึ้นต้น /admin/', () => {
    expect(safeRedirect('/admin/home')).toBe('/admin/home')
  })

  it('ปฏิเสธ path นอก /admin/ (open redirect)', () => {
    expect(safeRedirect('https://evil.example')).toBeNull()
    expect(safeRedirect('//evil.example')).toBeNull()
    expect(safeRedirect('/app/home')).toBeNull()
    expect(safeRedirect('/login')).toBeNull()
    expect(safeRedirect('/')).toBeNull()
  })

  it('ปฏิเสธ backslash (protocol-relative bypass)', () => {
    expect(safeRedirect('/admin/\\evil.example')).toBeNull()
  })

  it('ปฏิเสธค่าที่ไม่ใช่ string', () => {
    expect(safeRedirect(undefined)).toBeNull()
    expect(safeRedirect(123)).toBeNull()
  })
})
