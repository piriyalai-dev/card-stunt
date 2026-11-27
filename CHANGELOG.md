# Changelog

## [Unreleased] — Phase 3 Backend Core

- Backend: schema 9 ตาราง (events/stands/palettes/palette_colors/stunts/stunt_revisions/seat_rosters/export_jobs/audit_logs) + RBAC + domain APIs ครบตาม design §7
- Public: `/api/v1/public/*` meta/seat/version + Redis cache/ETag
- Live Sync: SSE + PG NOTIFY channel `pixelstand_live`
- Workflow: mirror pirivoice (pull_all/setup/rollback/release/CI/version-manifest/ops backup) + prefix `/api/v1`

**Migration:** `002_domain_indexes` · `003_audit_logs_indexes` · `004_live_sync_notify`

## [0.1.0] — 2026-11-27 — Phase 2 scaffold

- Backend: auth (login / me / change-password) + RBAC 3 roles + test harness
- Frontend: design system + login + admin shell (MainLayout) + route trees (`/admin/*` + `/e/:slug`)
- Infra: 4 docker-compose (infra / app / proxy / test) · `.env.example` · setup.sh

**Migration:** `001_init_auth` — DB schema เริ่มจาก `core/init_db.py` (users)

[Unreleased]: https://github.com/piriyalai-dev/card-stunt/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/piriyalai-dev/card-stunt/compare/84bf061...v0.1.0
