# Frontend Rules (card-stunt)

## Stack

Vue 3.5 + Vite 8 + TS 6 + Tailwind 3 + Pinia + manual PWA (ไม่มี plugin)
Composition API `<script setup lang="ts">` · **ห้าม `any`**

## โครงสร้าง (Layer)

`types/` (interface ข้อมูล) → `services/` (เรียก API เท่านั้น — ห้ามเรียก `api.get` ใน view) →
`views/` (UI logic) → `components/` (`ui/` = design system · `layout/` = shell) ·
`composables/` `constants/` `utils/`

## Design token

สีมาจาก `tailwind.config.js` (`brand` `canvas` `surface` `line` `ink-*` `ok-*` `warn` `danger`) — ห้าม hardcode hex
- สีแบรนด์ `#B91C1C` (แดง cardinal)
- ไม่ `uppercase` / ไม่ `letter-spacing` กับข้อความไทย
- ปุ่ม/การ์ด/แท็บ ต้องมาจาก `components/ui/` — เพิ่ม variant ที่ component กลาง ดีกว่าเขียน utility ใหม่
- `<style>` = ค่าเริ่มต้นไม่ใช้ (ใช้ได้เมื่อ Tailwind แสดงไม่ได้ เช่น keyframes — ใส่ `scoped` เสมอ)

## Route / guard

- 2 route trees: `/admin/*` (auth + RBAC) + `/e/:slug` (public student)
- `safeRedirect` ต้องกรอง open redirect (ขึ้นต้น `/admin/`, ไม่มี `\`)
- permission gate ทั้ง route meta (`requiresPermission`) + menu filter

## API / State

- `services/api.ts` axios instance + `queryCache` (stale-while-revalidate) — **ห้าม cache `/api` ใน SW**
- `stores/auth.ts` = ตัวตนเดียว (login/loadMe/logout/hasPermission)

## Loading / ว่าง / พัง

- 🔴 **"ว่าง" ≠ "พัง" ≠ "ยังโหลดไม่เสร็จ"** — เช็คแค่ `list.length === 0` จะอ่านว่า "ไม่มีข้อมูล"
  ตอน server ล่ม · ทุกเงื่อนไข "ว่าง" ต้องมี `!loading && !error`
- ⚠️ `const list = data?.items ?? []` กลืน "พัง" ให้เป็น "ว่าง" → อ่านจากตัวแปร error/loading แทน
- มีข้อมูลเก่าจาก cache (stale-while-revalidate) → **ห้าม**แสดง skeleton/spinner ทับข้อมูลเก่า

## ก่อน commit

`npm run type-check && npm run lint && npm run test:unit && npm run build` ผ่านครบ 4
