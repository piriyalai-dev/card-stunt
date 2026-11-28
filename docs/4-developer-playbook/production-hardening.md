# Production Hardening — checklist ที่ยังไม่ได้ทำ (Wave 3+)

> งาน 3 อย่างที่เหลือของ "deploy swarm จริง" — แต่ละอย่างแตะ infra ที่แชร์กับทั้งเครื่อง
> หรือเปลี่ยนสัญญา deploy ⇒ **ต้องทำอย่างระวัง** และบางข้อต้องสิทธิ์ root/เจ้าของเครื่อง

---

## 1. 🔒 HTTPS / ACME (ใหญ่สุด — แตะ `global_proxy` traefik ที่แชร์)

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

---

## 2. 🔐 Docker secrets (ย้าย credential ออกจาก `env_file`)

**สถานะ:** `POSTGRES_PASSWORD / API_KEY / SECRET_KEY / JWT_SECRET` อยู่ใน `env_file: .env`
⇒ โผล่ใน `docker service inspect` + env ของ container · ควรย้ายเป็น swarm `secret`

**หมายเหตุ:** ยังมี password ฝังใน `DATABASE_URL` (backend) อยู่ — การทำ secrets เต็มตัวต้องให้
backend อ่าน password จาก `_FILE` แล้วประกอบ URL เอง (แก้ `core/config.py`) · งานนี้ยังไม่ทำ

### ขั้นตอน (แนวทาง)

```bash
# สร้าง secret ครั้งเดียว (ค่ามาจาก .env)
printf '%s' "$POSTGRES_PASSWORD" | docker secret create pixelstand_postgres_password -
printf '%s' "$API_KEY"           | docker secret create pixelstand_api_key -
printf '%s' "$SECRET_KEY"        | docker secret create pixelstand_secret_key -
printf '%s' "$JWT_SECRET"        | docker secret create pixelstand_jwt_secret -
```

- `docker-compose.infra.yml` db: `secrets: [pixelstand_postgres_password]` + `POSTGRES_PASSWORD_FILE=/run/secrets/pixelstand_postgres_password`
- `docker-compose.app.yml` backend/worker: mount secret แล้วอ่านใน `core/config.py` (pydantic รับ `_FILE` ไม่ได้โดยตรง ⇒ ต้อง wrapper)
- `setup.sh` เพิ่ม `docker secret create` (idempotent: `docker secret inspect` ก่อน)

---

## 3. 📐 Resource limits (กัน OOM บนเครื่องที่แชร์ RAM)

**สถานะ:** compose ไม่มี `deploy.resources` เลย ⇒ container ใช้ RAM ได้ไม่จำกัด
· เครื่องนี้ RAM 11.68 GB แชร์กับ `cmskrulak` (25%) + claude session (~20%) ⇒ ควรตั้งเพดาน

**แนวทาง (ค่าเริ่มต้น — ปรับตามโหลดจริง):**

```yaml
# worker (PDF = กิน RAM ที่สุด)
deploy:
  resources:
    limits:   { cpus: '1.0', memory: 2G }
    reservations: { cpus: '0.25', memory: 256M }

# backend
deploy:
  resources:
    limits:   { cpus: '1.0', memory: 1G }
    reservations: { cpus: '0.25', memory: 256M }
```

⚠️ ตั้ง `limits.memory` ต่ำเกิน → `Exited 137` (OOM kill) · ตั้งจาก **working set จริง** ไม่ใช่เดา
· วัดก่อนด้วย `docker stats` หลัง deploy · worker ที่ export PDF 5,000 ที่นั่งเป็นตัวเสี่ยงสุด

---

## 4. ✅ Checklist ที่ทำแล้ว (Wave 3)

- [x] CI รันเทสต์จริง (`.github/workflows/ci-tests.yml`: backend pytest + frontend 4 gates + E2E)
- [x] healthcheck: infra db (`pg_isready`) + redis (`redis-cli ping`) + frontend (nginx `wget`)
- [x] `.env.example` ครบทุก `Settings` field ที่มีผล (JWT/cache/media/roster/seed)
- [ ] HTTPS (ข้อ 1) — รอตัดสินใจ + แตะ shared traefik
- [ ] Docker secrets (ข้อ 2) — รอตัดสินใจ + แก้ `core/config.py`
- [ ] Resource limits (ข้อ 3) — วัด working set จริงก่อนตั้ง
