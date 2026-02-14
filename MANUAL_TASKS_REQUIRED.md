# Manual Tasks Required

## 1. Rotate Previously Exposed Database Credential
- Priority: `Critical`
- Why manual: credential rotation must be executed against your real PostgreSQL instance and secret store.
- Commands:
```bash
# Generate a strong password
openssl rand -base64 32

# Update DB user password (replace values)
psql -U postgres -d rivo -c "ALTER USER rivo_app WITH PASSWORD 'REPLACE_WITH_STRONG_PASSWORD';"
```
- Follow-up:
  - Update deployment secrets (`DATABASE_URL`) in your runtime platform.
  - Remove any old leaked credentials from secret managers/history.

## 2. Configure Production Secrets Source
- Priority: `Critical`
- Why manual: cloud secret-store wiring is environment-specific.
- Steps:
  1. Store `DATABASE_URL`, SMTP credentials, and LLM settings in your secrets manager.
  2. Inject those env vars into runtime (`ENV=production`, `DEBUG=False`).
  3. Verify application starts with `python app/orchestrator.py health`.

## 3. Apply Alembic Migrations in Target Environment
- Priority: `Important`
- Why manual: migration execution order and rollback policy must align with production change windows.
- Commands:
```bash
alembic upgrade head
```

## 4. Pull Required Ollama Model in Deployment
- Priority: `Important`
- Why manual: model availability is runtime-host dependent.
- Commands:
```bash
ollama pull qwen2.5:7b
```

## 5. Enable External Monitoring/Alerting
- Priority: `Important`
- Why manual: integration requires organization-specific tooling (Sentry/Datadog/ELK).
- Steps:
  1. Forward application logs from `LOG_FILE`/stdout to your logging backend.
  2. Create alerts for:
     - repeated `llm.call.unavailable`
     - repeated `database.connection_failed`
     - high pending review backlog

## 6. Configure Infrastructure TLS and Firewall Rules
- Priority: `Important`
- Why manual: certificates, network ACLs, and ingress are infra-specific.
- Steps:
  1. Restrict DB ingress to app subnet only.
  2. Terminate TLS at ingress/load balancer.
  3. Expose only required ports (`8501` dashboard, `11434` internal-only where possible).

## 7. Reinitialize Local Chroma Store (if previously corrupted)
- Priority: `Optional`
- Why manual: local artifact health depends on workstation state and can be safely recreated.
- Commands:
```bash
# Linux/macOS
rm -rf memory/chroma_db

# Windows PowerShell
Remove-Item -Recurse -Force memory\chroma_db
```
Then rerun:
```bash
python app/orchestrator.py health
```
