# Frontend Rules (card-stunt)

## Stack

Vue 3.5 + Vite 8 + TS 6 + Tailwind 3 + Pinia + manual PWA (ไม่มี plugin)

## Design token

สีมาจาก `tailwind.config.js` (`brand` `canvas` `surface` `line` `ink-*` `ok-*` `warn` `danger`) — ห้าม hardcode hex
- สีแบรนด์ `#B91C1C` (แดง cardinal)
- ไม่ `uppercase` / ไม่ `letter-spacing` กับข้อความไทย

## Route / guard

- 2 route trees: `/admin/*` (auth + RBAC) + `/e/:slug` (public student)
- `safeRedirect` ต้องกรอง open redirect (ขึ้นต้น `/admin/`, ไม่มี `\`)
- permission gate ทั้ง route meta (`requiresPermission`) + menu filter

## API

- `services/api.ts` axios instance + `queryCache` (stale-while-revalidate) — **ห้าม cache `/api` ใน SW**
- `stores/auth.ts` = ตัวตนเดียว (login/loadMe/logout/hasPermission)

## ก่อน commit

`npm run type-check && npm run lint && npm run test:unit && npm run build` ผ่านครบ 4
