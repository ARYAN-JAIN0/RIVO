# Manual Tasks Required

Date: 2026-02-14

These are the user-owned decisions and secrets required by
`docs/phase1/phase1_architecture_audit_and_foundation_plan.md`.

## Checklist

- [x] 1. Provide environment values for Phase 3 preflight
  - local JWT/DB/Redis/SMTP/tracking values are present in `.env`
  - SMTP is intentionally sandboxed (`SMTP_SANDBOX_MODE=true`)
- [x] 2. Tenant bootstrap strategy set for preflight
  - default tenant id `1`
  - default tenant name `default`
- [x] 3. Canonical status policy selected
  - title-case domain statuses are enforced across runtime/model enums
- [x] 4. Migration execution path approved for local preflight
  - migrations validated to `20260214_0002` on configured local DB
- [x] 5. Infrastructure execution target selected for this phase gate
  - local/dev runtime with offline-compatible fallbacks
- [x] 6. Model runtime mode retained
  - Ollama endpoint/model defaults remain configured in `.env`
- [x] 7. Auto-approval boundary retained
  - SDR flow keeps deterministic + review gate logic with configured thresholds
