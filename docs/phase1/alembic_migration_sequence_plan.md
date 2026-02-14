# Alembic Migration Sequence Plan (Phase 1 Artifact)

Date: 2026-02-14

This document is the execution-ready migration plan referenced by:
- `docs/phase1/phase1_architecture_audit_and_foundation_plan.md` section 3.5

It defines the ordered revisions to evolve the baseline schema toward the target tenant-aware architecture.

## Preconditions

- Backup snapshot completed.
- Maintenance window approved.
- Baseline migration (`20260213_0001`) already applied.
- Default tenant bootstrap values confirmed.

## Ordered Revisions

1. Revision A (`20260214_0002_create_tenants_users`)
- Create `tenants` and `users` tables.
- Add role enum for users.
- Seed bootstrap tenant (`tenant_key=default`) and optional admin bootstrap row guard.

2. Revision B (`20260214_0003_add_tenant_id_nullable`)
- Add nullable `tenant_id` to existing domain tables:
  - `leads`, `deals`, `contracts`, `invoices`
- Backfill all existing rows to default tenant id.

3. Revision C (`20260214_0004_enforce_tenant_constraints`)
- Set `tenant_id` as `NOT NULL` on all domain tables.
- Replace global uniqueness with tenant-scoped uniqueness:
  - `leads (tenant_id, email)`
  - `contracts (tenant_id, deal_id)`
  - `invoices (tenant_id, contract_id)`

4. Revision D (`20260214_0005_create_operational_tables`)
- Create:
  - `pipeline_stages`
  - `negotiation_history`
  - `email_logs`
  - `agent_runs`
  - `llm_logs`

5. Revision E (`20260214_0006_audit_columns_and_indexes`)
- Add `created_at`, `updated_at`, `deleted_at` to all domain and operational tables.
- Add composite indexes:
  - `(tenant_id, status)`
  - `(tenant_id, stage)` where relevant
  - `(tenant_id, created_at)` where relevant

6. Revision F (`20260214_0007_status_enum_migration`)
- Convert string status columns to strict DB enums:
  - `leads.status`
  - `deals.stage`
  - `contracts.status`
  - `invoices.status`
  - `agent_runs.status`
- Validate all existing values before applying enum constraints.

7. Revision G (`20260214_0008_pgvector_activation`)
- Enable `pgvector` extension.
- Add vector storage table(s) required by RAG activation.
- Create vector index strategy per retrieval policy.

## Data Safety and Validation Checklist

Pre-migration checks:
- row counts by table
- orphan FK detection
- distinct status values by table

Backfill safeguards:
- idempotent scripts keyed by migration marker
- updates filtered with `WHERE tenant_id IS NULL`

Post-migration checks:
- row counts unchanged for migrated tables
- all `tenant_id` fields non-null
- uniqueness checks pass under new tenant-scoped constraints
- enum columns contain only allowed values

## Rollback Guidance

- Revisions A-E support deterministic downgrade.
- Revision F (enum conversion) requires explicit cast-safe downgrade script.
- Revision G rollback should preserve extension decision based on deployment policy.
