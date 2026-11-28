import { expect, test } from '@playwright/test'
import { mockAdminApi } from './fixtures'

// ไม่ต้อง seed localStorage แล้ว — access token อยู่ใน memory · หน้าแรก bootstrap เรียก
// `POST /auth/refresh` (ถูก mock ใน fixtures.ts) เพื่อขอ token + user

test('staff: รายชื่อ + สั่ง export แล้ว poll จนเสร็จ', async ({ page }) => {
  const mock = await mockAdminApi(page)
  await page.goto('/admin/events/1/exports')

  await expect(page.getByRole('heading', { name: 'รายชื่อในงาน' })).toBeVisible()
  await expect(page.getByText('นาย ตัวอย่าง')).toBeVisible()
  await expect(page.getByText('เสร็จ', { exact: true })).toHaveCount(1)

  await page.getByRole('button', { name: /PDF โพยรายที่นั่ง/ }).click()
  await expect(page.getByText(/สั่งสร้าง PDF โพยรายที่นั่ง แล้ว/)).toBeVisible()
  await expect(page.getByText('รอคิว', { exact: true })).toHaveCount(1)

  // จำลอง worker สร้างเสร็จ แล้ว poll รอบถัดไป (2.5 วิ) เห็น done
  mock.setNewJobStatus('done')
  await expect(page.getByText('เสร็จ', { exact: true })).toHaveCount(2, { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'ดาวน์โหลด' })).toHaveCount(2)
})

test('staff: คุมคิวสด next เปลี่ยนฉากปัจจุบัน', async ({ page }) => {
  await mockAdminApi(page)
  await page.goto('/admin/events/1/live')

  const current = page.locator('p', { hasText: 'ฉากปัจจุบัน' })
  await expect(current).toContainText('เปิดตัว')

  await page.getByRole('button', { name: 'ฉากถัดไป' }).click()
  await expect(current).toContainText('โลโก้โรงเรียน')
  await expect(page.getByText('● LIVE')).toBeVisible()
})
