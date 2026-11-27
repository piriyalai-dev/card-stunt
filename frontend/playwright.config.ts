import { defineConfig, devices } from '@playwright/test'

/**
 * E2E — รันกับ `npm run preview` (dist ที่ build แล้ว) และ **mock API ด้วย route interception**
 *
 * ⇒ ไม่ต้องมี backend/Postgres/Redis ตอนรัน `npm run test:e2e`
 *   (เทสต์ UI/route/offline cache/live-control โดยไม่ผูกกับข้อมูลจริง)
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    // ⚠️ `vite preview` bind `localhost` (IPv6 ::1 บนเครื่องนี้) — ใช้ 127.0.0.1 จะ connect ไม่ได้
    baseURL: 'http://localhost:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // viewer เป็น mobile-first — ใช้ viewport มือถือ; test admin override เองได้
    ...devices['Pixel 5'],
  },
  projects: [{ name: 'chromium', use: {} }],
  webServer: {
    command: 'npm run preview -- --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
