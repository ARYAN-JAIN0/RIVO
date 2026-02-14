# Manual Tasks Required

Date: 2026-02-14

These are the user-owned decisions and secrets required by
`docs/phase1/phase1_architecture_audit_and_foundation_plan.md`.

## Checklist

- [ ] 1. Provide production secrets and environment values
  - JWT secret/private key
  - database credentials
  - Redis credentials
  - SMTP credentials
- [ ] 2. Confirm tenant bootstrap strategy
  - default tenant naming
  - admin bootstrap email
- [ ] 3. Decide canonical machine-safe status enum policy
  - recommended lowercase enums (for DB/API interoperability)
- [ ] 4. Approve migration downtime window
  - required for tenant backfill and non-null enforcement revisions
- [ ] 5. Confirm infrastructure deployment target
  - Docker Compose only or Kubernetes-ready conventions
- [ ] 6. Confirm Qwen 7B runtime mode
  - Ollama model path, GPU availability, fallback policy
- [ ] 7. Define auto-approval policy boundaries
  - confidence threshold and low-risk action scope
