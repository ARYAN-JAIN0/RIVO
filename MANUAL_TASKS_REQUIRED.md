# Manual Tasks Required

Date: 2026-02-19 (Updated)

These are the user-owned decisions and secrets required for production deployment.

## Phase 1-3 Completed Checklist

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

---

## Phase 4 Production Readiness - Human Intervention Required

The following tasks **MUST** be completed by a human before production deployment.

### 1. Ollama Installation and Configuration (CRITICAL)

The RAG service requires Ollama with an embedding model for semantic search.

**Steps:**
```bash
# 1. Install Ollama from https://ollama.ai
#    Follow the installation instructions for your OS

# 2. Pull the embedding model
ollama pull nomic-embed-text

# 3. Verify Ollama is running
curl http://localhost:11434/api/tags

# 4. Test embedding generation
curl http://localhost:11434/api/embeddings \
  -d '{"model": "nomic-embed-text", "prompt": "test embedding"}'
```

**Environment Variables:**
```env
OLLAMA_URL=http://localhost:11434
OLLAMA_GENERATE_URL=http://localhost:11434/api/generate
OLLAMA_EMBEDDING_URL=http://localhost:11434/api/embeddings
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
RAG_USE_REAL_EMBEDDINGS=true
```

**Without this:** RAG will fall back to hash-based embeddings (NOT semantic).

---

### 2. Database Migration Execution (CRITICAL)

New columns have been added to support negotiation turn tracking.

**Steps:**
```bash
# Navigate to project directory
cd /path/to/RIVO

# Run migrations
alembic upgrade head

# Verify migration
alembic current
# Should show: 20260220_0005
```

**New columns added:**
- `contracts.tenant_id` - Multi-tenant support
- `contracts.negotiation_turn` - Tracks negotiation rounds
- `contracts.confidence_score` - Stores negotiation confidence

---

### 3. Production Environment Variables (CRITICAL)

Set these environment variables in production:

```env
# Application
APP_NAME=RIVO
APP_VERSION=1.0.0
DEBUG=false
API_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql://user:password@host:5432/rivo

# Redis (for Celery and rate limiting)
REDIS_URL=redis://host:6379/0

# JWT Authentication
JWT_SECRET=<generate-secure-random-string>
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=14
JWT_PERMISSIONS_VERSION=1

# Ollama
OLLAMA_URL=http://localhost:11434
OLLAMA_GENERATE_URL=http://localhost:11434/api/generate
OLLAMA_EMBEDDING_URL=http://localhost:11434/api/embeddings
OLLAMA_MODEL=llama3:latest
OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# RAG
RAG_USE_REAL_EMBEDDINGS=true
RAG_EMBEDDING_DIMS=768

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_AUTH=10/minute
RATE_LIMIT_ADMIN=30/minute
RATE_LIMIT_TRACKING=1000/minute

# Email (SDR path)
GMAIL_SMTP_HOST=smtp.gmail.com
GMAIL_SMTP_PORT=587
GMAIL_SMTP_USER=your-user
GMAIL_SMTP_APP_PASSWORD=<secure-password>
GMAIL_FROM_EMAIL=noreply@example.com
SMTP_SANDBOX_MODE=false
TRACKING_BASE_URL=https://api.example.com

# Multi-tenancy
AUTO_PIPELINE_TENANT_ID=1
```

**Security Notes:**
- `JWT_SECRET` must be a cryptographically secure random string (32+ characters)
- Never commit `.env` files to version control
- Use a secrets manager in production (AWS Secrets Manager, HashiCorp Vault, etc.)

---

### 4. Redis Configuration (REQUIRED for Production)

Redis is required for:
- Celery task queue
- Rate limiting (production mode)

**Steps:**
```bash
# Install Redis
# Ubuntu/Debian:
sudo apt-get install redis-server

# macOS:
brew install redis

# Start Redis
redis-server

# Verify
redis-cli ping
# Should return: PONG
```

**For production rate limiting with SlowAPI:**
```bash
pip install slowapi[redis]
```

Set environment variable:
```env
RATELIMIT_STORAGE_URL=redis://localhost:6379/1
```

---

### 5. Celery Worker Setup (REQUIRED)

Celery workers are needed for async agent execution.

**Steps:**
```bash
# Start Celery worker
celery -A app.tasks.scheduler worker --loglevel=info

# Start Celery beat (scheduler) in separate terminal
celery -A app.tasks.celery_app beat --loglevel=info
```

**For production, use a process manager (supervisor, systemd):**
```ini
# /etc/supervisor/conf.d/rivo-worker.conf
[program:rivo-worker]
command=celery -A app.tasks.scheduler worker --loglevel=info
directory=/path/to/RIVO
user=rivo
autostart=true
autorestart=true
```

---

### 6. Initial Admin User Creation (REQUIRED)

Create an admin user for API access:

```bash
# Using Python shell
python -c "
from app.database.db import get_db_session
from app.database.models import User, Tenant
from app.core.security import hash_password

with get_db_session() as session:
    # Ensure default tenant exists
    tenant = session.query(Tenant).filter(Tenant.id == 1).first()
    if not tenant:
        tenant = Tenant(id=1, name='default')
        session.add(tenant)
        session.flush()
    
    # Create admin user
    admin = session.query(User).filter(User.tenant_id == 1, User.email == 'admin@example.com').first()
    if not admin:
        admin = User(
            tenant_id=1,
            email='admin@example.com',
            hashed_password=hash_password('secure-password'),
            role='admin',
            is_active=True
        )
        session.add(admin)
    session.commit()
    print('Admin user ready')
"
```

---

### 7. SSL/TLS Configuration (REQUIRED for Production)

The API must be served over HTTPS in production.

**Using Nginx as reverse proxy:**
```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

### 8. Monitoring and Logging Setup (RECOMMENDED)

Configure structured logging and monitoring:

```env
# Logging
LOG_LEVEL=INFO
LOG_FILE=rivo.log

# Optional: External monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
```

---

## Verification Checklist

After completing the above tasks, verify:

- [ ] Ollama is running and embedding model is available
- [ ] Database migrations have been applied
- [ ] Redis is running and accessible
- [ ] Celery workers are running
- [ ] Admin user can authenticate via API
- [ ] Rate limiting is working (test with rapid requests)
- [ ] RAG semantic search is working (not using hash fallback)
- [ ] All API endpoints return expected responses
- [ ] SSL/TLS is configured (production)

---

## Quick Start (Development)

For local development without full setup:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Ensure local PostgreSQL is reachable via DATABASE_URL in .env

# 3. Run migrations
alembic upgrade head

# 4. Start API (without Celery - sync mode)
uvicorn app.main:app --reload

# 5. Access API docs
open http://localhost:8000/docs
```

Note: Without Ollama, RAG will use hash embeddings (not semantic).
Without Redis, rate limiting uses in-memory storage (not suitable for multi-worker).
