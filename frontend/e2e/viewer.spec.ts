import { expect, test } from '@playwright/test'
import { mockPublicApi } from './fixtures'

test.beforeEach(async ({ page }) => {
  await mockPublicApi(page)
})

test('ผู้ชม: ใส่รหัสล็อกอิน → โพย → โฟกัส → ฉากถัดไป', async ({ page }) => {
  await page.goto('/e/sport69')

  await expect(page.getByRole('heading', { name: 'กีฬาสี 69 — โซนกลาง' })).toBeVisible()

  // ใส่รหัสล็อกอินที่พิมพ์แจก
  await page.getByPlaceholder(/รหัสล็อกอิน/).fill('ABCD1234')
  await page.getByRole('button', { name: 'เข้าดูโพย' }).click()

  await expect(page.getByRole('heading', { name: 'แถว A · ที่นั่ง 1' })).toBeVisible()
  await expect(page.getByText('นาย ตัวอย่าง')).toBeVisible()
  await expect(page.getByText('เปิดตัว').first()).toBeVisible()

  await page.getByRole('button', { name: 'เปิดโหมดโฟกัส' }).click()

  await expect(page.getByTestId('focus-code')).toHaveText('ด้าน A')
  await expect(page.getByTestId('next-cue')).toContainText('02 (ขาว)')

  await page.getByRole('button', { name: 'ฉากถัดไป' }).click()
  await expect(page.getByTestId('focus-code')).toHaveText('ด้าน B')
  await expect(page.getByTestId('next-cue')).toContainText('01 (แดงสด)')
})

test('ผู้ชม: ออฟไลน์แล้วยังเปิดโพยจาก cache ได้', async ({ page }) => {
  await page.goto('/e/sport69')
  await page.getByPlaceholder(/รหัสล็อกอิน/).fill('ABCD1234')
  await page.getByRole('button', { name: 'เข้าดูโพย' }).click()
  await expect(page.getByRole('heading', { name: 'แถว A · ที่นั่ง 1' })).toBeVisible()

  // ตัดเน็ตเฉพาะ API แล้ว reload — meta/claim ต้องมาจาก localStorage
  await page.unroute('**/api/v1/public/events/**')
  await page.route('**/api/v1/public/events/**', (route) => route.abort())
  await page.reload()

  await expect(page.getByText(/กำลังใช้ข้อมูลออฟไลน์/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'แถว A · ที่นั่ง 1' })).toBeVisible()
  await expect(page.getByText('เปิดตัว').first()).toBeVisible()
})
