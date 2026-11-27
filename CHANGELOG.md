# Changelog

## [Unreleased] — Pixel Stand (Phase 2 scaffold)

- Backend: auth (login / me / change-password) + RBAC 3 roles + test harness
- Frontend: design system + login + admin shell (MainLayout) + route trees (`/admin/*` + `/e/:slug`)
- Infra: 4 docker-compose (infra / app / proxy / test) · `.env.example` · setup.sh

**Migration:** ยังไม่มี — DB schema เริ่มจาก `core/init_db.py` (users) + migration `001_init_auth`
