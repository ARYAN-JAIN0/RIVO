-- Run this as a PostgreSQL admin/superuser.
-- Purpose: allow role `rivodbs` to run Alembic migrations for Phase 2/3.

\c rivo

-- Ensure migration role can create/alter objects in the default schema.
GRANT USAGE, CREATE ON SCHEMA public TO rivodbs;
ALTER SCHEMA public OWNER TO rivodbs;

-- Ensure migration role can ALTER existing baseline tables created by postgres.
ALTER TABLE IF EXISTS public.leads OWNER TO rivodbs;
ALTER TABLE IF EXISTS public.deals OWNER TO rivodbs;
ALTER TABLE IF EXISTS public.contracts OWNER TO rivodbs;
ALTER TABLE IF EXISTS public.invoices OWNER TO rivodbs;
ALTER TABLE IF EXISTS public.alembic_version OWNER TO rivodbs;

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT sequence_schema, sequence_name
           FROM information_schema.sequences
           WHERE sequence_schema = 'public'
  LOOP
    EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO rivodbs', r.sequence_schema, r.sequence_name);
  END LOOP;
END
$$;

-- Ensure full DML/DDL compatibility for existing and future objects.
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rivodbs;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rivodbs;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO rivodbs;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rivodbs;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rivodbs;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO rivodbs;
