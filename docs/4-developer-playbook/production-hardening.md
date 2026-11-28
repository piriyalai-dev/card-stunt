# Production Hardening — checklist

> งานของ "deploy swarm จริง" — **Wave 7 ทำแล้ว:** Docker secrets · resource limits · coverage
> **เหลือแค่ HTTPS** (ข้อ 1) ที่แตะ `global_proxy` traefik ที่แชร์กับทั้งเครื่อง ⇒ ต้องทำอย่างระวัง
> + สิทธิ์ root/เจ้าของเครื่อง (ดู `~/CLAUDE.md`)

---

## 1. 🔒 HTTPS / ACME (ยังไม่ได้ทำ — แตะ `global_proxy` traefik ที่แชร์)

**สถานะตอนนี้:** `global_proxy` traefik (`~/ops/deploy/traefik-proxy/docker-compose.yml`)
มีแค่ entrypoint `web` (`:80`) · **ไม่มี** `:443` · **ไม่มี** certresolver ⇒ JWT/รหัสผ่าน/โพย
วิ่ง cleartext · card-stunt ยัง HTTP ล้วน

**ความเสี่ยง:** traefik ตัวนี้ route **ทุกเว็บของเครื่อง** (production/staging/tools) ⇒ แก้แล้ว
ต้อง redeploy stack `global` ซึ่งกระทบทุก site · ทำช่วง traffic น้อย + เตรียม rollback

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
   · เปิด `REFRESH_COOKIE_SECURE=true` (cookie ต้อง secure บน HTTPS)

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
- [ ] HTTPS (ข้อ 1) — รอตัดสินใจ + แตะ shared traefik
