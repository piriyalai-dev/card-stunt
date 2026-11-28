# Production Hardening — checklist

> งานของ "deploy swarm จริง" — **Wave 7 ทำแล้ว:** Docker secrets · resource limits · coverage
> **HTTPS (ข้อ 1)** ตัดสินใจใช้ **Cloudflare edge TLS** — ไม่แตะ shared traefik (ดูข้อ 1)

---

## 1. 🔒 HTTPS — ใช้ Cloudflare (edge TLS) · ไม่แตะ shared traefik

**ตัดสินใจ (2026-11-28):** ไม่ทำ ACME บน `global_proxy` traefik — มัน route ทุกเว็บของเครื่อง
และ redeploy stack `global` กระทบทุก site ⇒ ใช้ **Cloudflare** เทอร์มินัล TLS ที่ edge แทน
origin (traefik port 80) ยัง HTTP ตามเดิม ⇒ **ไม่ต้องแก้ traefik หรือระบบอื่น**

**ฝั่ง Cloudflare (เจ้าของเครื่องทำ):** DNS `pixel.singto1597.xyz` + `pixel-api.singto1597.xyz`
แบบ proxied (orange cloud) หรือ Cloudflare Tunnel (`cloudflared.service` ที่รันอยู่แล้ว)
· TLS mode **Full** · เปิด **Always Use HTTPS** (redirect http→https ที่ edge)

**ฝั่ง card-stunt (แค่ `.env` + rebuild — ไม่แตะ infra ที่แชร์):**

```env
REFRESH_COOKIE_SECURE=true                          # cookie ต้อง Secure บน https
VITE_API_BASE_URL=https://pixel-api.singto1597.xyz  # rebuild frontend — URL bake ลง bundle
```

- `CORS_ORIGINS` มี `https://pixel.singto1597.xyz` อยู่แล้วใน default → ไม่ต้องแก้
- media signed URL ใช้ relative path → ใช้ได้บน https โดยไม่ต้องเปลี่ยน

> ⚠️ Cloudflare Tunnel เป็นช่องทางออก ไม่ใช่เปิดพอร์ต — origin traefik (80) ยังรัน HTTP ตามเดิม
> ไม่ต้องเปิด `:443` ที่ origin เลย

---

## 1a. (สำรอง) traefik + Let's Encrypt — ถ้าไม่ใช้ Cloudflare

<details>
<summary>แนวทาง ACME บน shared traefik (ไม่ได้ใช้ — เก็บไว้อ้างอิง)</summary>

**ความเสี่ยง:** traefik ตัวนี้ route **ทุกเว็บของเครื่อง** ⇒ แก้แล้วต้อง redeploy stack `global`
ซึ่งกระทบทุก site · ทำช่วง traffic น้อย + เตรียม rollback

### ขั้นตอน

1. **DNS พร้อม:** `pixel.singto1597.xyz` / `pixel-api.singto1597.xyz` ชี้เข้าเครื่อง
   (ตรงๆ หรือผ่าน Cloudflare) · Let's Encrypt ต้องยืนยันเจ้าของโดเมนได้ (HTTP-01 ต้องเปิด 80
   จากภายนอกได้ · ถ้าอยู่หลัง Cloudflare ให้ใช้ DNS-01 + Cloudflare API token)

2. **แก้ `~/ops/deploy/traefik-proxy/docker-compose.yml`** เพิ่ม:

```yaml
    command:
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=<อีเมล>"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      # (Cloudflare) แทน tlschallenge ด้วย dnsChallenge + env CF_API_EMAIL/CF_API_KEY
    ports:
      - "80:80"
      - "443:443"
```

   ⚠️ ACME: `tlschallenge` ง่ายสุด (ต้องให้ 443 เปิดจากภายนอก) · หลัง Cloudflare ใช้ `dnschallenge`
   · เพิ่ม volume `letsencrypt:/letsencrypt` เพื่อให้ cert รอดการ redeploy

3. **Redeploy:** `docker stack deploy -c docker-compose.yml global` (จากโฟลเดอร์ traefik-proxy)
4. **เปิด tls label ของ card-stunt:** ใน `docker-compose.app.yml` uncomment 3 บรรทัด
   (`entrypoints=websecure` + `tls=true` + `tls.certresolver=letsencrypt`) ของทั้ง backend/frontend
   · `./pull_all.sh` redeploy · แล้วเช็ค `https://pixel.singto1597.xyz`
5. **อัปเดต `CORS_ORIGINS` + `VITE_API_BASE_URL`** ให้เป็น `https://…` แล้ว rebuild frontend
   · เปิด `REFRESH_COOKIE_SECURE=true`

</details>

---

## 2. 🔐 Docker secrets ✅ (Wave 7)

ย้าย `POSTGRES_PASSWORD / API_KEY / SECRET_KEY / JWT_SECRET` ออกจาก env เป็น swarm secret

- **`core/config.py`**: `_read_secret(name)` อ่าน `/run/secrets/<name>` · validator `_secret_or_required`
  (API_KEY/SECRET_KEY/JWT_SECRET: secret → env → error ตอน boot) · `_inject_db_password` ต่อ password
  ลง `DATABASE_URL` ที่ไม่มี password (`user@host/db`)
- **`docker-compose.infra.yml`**: db ใช้ `POSTGRES_PASSWORD_FILE=/run/secrets/pixelstand_postgres_password`
  (postgres image อ่าน password จาก secret โดยตรง)
- **`docker-compose.app.yml`**: backend/worker mount 4 secrets · `environment:` override ค่า sensitive
  เป็นว่าง + `DATABASE_URL` ไม่มี password ⇒ `core/config.py` อ่าน secret แทน
- **`setup.sh` / `pull_all.sh`**: `ensure_secret()` สร้าง 4 secrets แบบ idempotent ก่อน deploy
- **test**: `tests/test_config.py` — secret field ว่าง+ไม่มี secret → error · URL injection / ไม่แตะ URL ที่มี password

> ⚠️ secret เป็น `external: true` ⇒ ต้องถูกสร้างก่อน deploy (scripts ทำแล้ว) · ถ้าสร้างไม่ทัน
> `docker stack deploy` fail ชัดเจน (ไม่ silent)

---

## 3. 📐 Resource limits ✅ (Wave 7)

`deploy.resources.limits/reservations` ใน compose ทั้งสองไฟล์ — ค่าเริ่มต้น (วัด `docker stats` ปรับทีหลัง):

| service | limits (cpu / mem) | reservations |
|---|---|---|
| backend | 1.0 / 1G | 0.25 / 256M |
| worker (PDF) | 1.5 / 2G | 0.25 / 256M |
| frontend | 0.5 / 128M | 0.1 / 32M |
| db | 1.0 / 1G | 0.25 / 256M |
| redis | 0.5 / 256M | 0.1 / 32M |

⚠️ `limits.memory` ต่ำเกิน → `Exited 137` (OOM kill) · ตั้งจาก **working set จริง** ไม่ใช่เดา
· worker ที่ export PDF 5,000 ที่นั่งเสี่ยงสุด · วัดด้วย `docker stats` หลัง deploy แล้วปรับ

---

## 4. ✅ Checklist

- [x] CI รันเทสต์จริง (`.github/workflows/ci-tests.yml`: backend pytest + frontend 4 gates + E2E)
- [x] healthcheck: infra db (`pg_isready`) + redis (`redis-cli ping`) + frontend (nginx `wget`)
- [x] `.env.example` ครบทุก `Settings` field ที่มีผล (JWT/cache/media/roster/seed)
- [x] Docker secrets (ข้อ 2) — `core/config.py` + compose + setup/pull_all
- [x] Resource limits (ข้อ 3) — `deploy.resources` ทั้ง 5 services
- [x] Coverage (Wave 7) — test_runner รัน pytest `--cov` (report ขึ้น CI log)
- [ ] HTTPS (ข้อ 1) — ใช้ Cloudflare edge TLS · รอเจ้าของเครื่องตั้ง DNS/tunnel + flip `REFRESH_COOKIE_SECURE=true` + rebuild frontend (`VITE_API_BASE_URL=https://…`)
