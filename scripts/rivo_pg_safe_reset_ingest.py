from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class SeedLead:
    full_name: str
    work_email: str
    designation: str
    company_name: str
    company_size: str
    industry: str
    linkedin_url: str
    phone_number: str


SEED_LEADS: list[SeedLead] = [
    SeedLead("Ava Thompson", "ava.thompson@northstarhealth.com", "VP Operations", "Northstar Health", "500-1000", "Healthcare", "https://www.linkedin.com/in/ava-thompson-ops", "+1-415-555-1101"),
    SeedLead("Liam Carter", "liam.carter@acmefintech.io", "CTO", "Acme FinTech", "100-500", "Fintech", "https://www.linkedin.com/in/liam-carter-cto", "+1-415-555-1102"),
    SeedLead("Noah Patel", "noah.patel@brightlogistics.co", "Director IT", "Bright Logistics", "500-1000", "Logistics", "https://www.linkedin.com/in/noah-patel-it", "+1-415-555-1103"),
    SeedLead("Emma Rodriguez", "emma.rodriguez@horizonretail.com", "Head of Digital", "Horizon Retail", "1000+", "E-commerce", "https://www.linkedin.com/in/emma-rodriguez-digital", "+1-415-555-1104"),
    SeedLead("Olivia Kim", "olivia.kim@vertexmanufacturing.com", "CIO", "Vertex Manufacturing", "1000+", "Manufacturing", "https://www.linkedin.com/in/olivia-kim-cio", "+1-415-555-1105"),
    SeedLead("Ethan Brooks", "ethan.brooks@cloudlane.ai", "Founder", "CloudLane AI", "50-100", "SaaS", "https://www.linkedin.com/in/ethan-brooks-founder", "+1-415-555-1106"),
    SeedLead("Mia Johnson", "mia.johnson@securegrid.io", "CISO", "SecureGrid", "100-500", "Cybersecurity", "https://www.linkedin.com/in/mia-johnson-ciso", "+1-415-555-1107"),
    SeedLead("Lucas Green", "lucas.green@pulseedtech.org", "VP Product", "Pulse EdTech", "100-500", "EdTech", "https://www.linkedin.com/in/lucas-green-product", "+1-415-555-1108"),
    SeedLead("Sophia Nguyen", "sophia.nguyen@medflowsystems.com", "COO", "MedFlow Systems", "500-1000", "Healthcare", "https://www.linkedin.com/in/sophia-nguyen-coo", "+1-415-555-1109"),
    SeedLead("James Walker", "james.walker@atlaspayments.com", "Head of Engineering", "Atlas Payments", "100-500", "Fintech", "https://www.linkedin.com/in/james-walker-eng", "+1-415-555-1110"),
]


def _log(message: str) -> None:
    print(f"[RIVO-RESET] {message}")


def _configure_env(database_url: str | None) -> str:
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    active = os.getenv("DATABASE_URL", "").strip()
    if not active:
        raise RuntimeError("DATABASE_URL is required. Set it in env or pass --database-url.")
    if not active.startswith(("postgresql://", "postgresql+psycopg2://")):
        raise RuntimeError(f"PostgreSQL URL required for this script, got: {active}")
    os.environ["DB_CONNECTIVITY_REQUIRED"] = "true"
    return active


def _import_runtime():
    from app.database.db import SessionLocal, get_engine
    from app.database.models import Base
    from app.database.models import (
        AgentRun,
        Contract,
        Deal,
        DealStageAudit,
        EmailLog,
        Invoice,
        LLMLog,
        Lead,
        NegotiationMemory,
        ReviewAudit,
        Tenant,
    )
    from app.database.db_handler import (
        fetch_pending_contract_reviews,
        fetch_pending_deal_reviews,
        fetch_pending_dunning_reviews,
        fetch_pending_reviews,
    )

    return {
        "Base": Base,
        "SessionLocal": SessionLocal,
        "get_engine": get_engine,
        "models": {
            "Tenant": Tenant,
            "Lead": Lead,
            "Deal": Deal,
            "DealStageAudit": DealStageAudit,
            "Contract": Contract,
            "NegotiationMemory": NegotiationMemory,
            "Invoice": Invoice,
            "AgentRun": AgentRun,
            "EmailLog": EmailLog,
            "LLMLog": LLMLog,
            "ReviewAudit": ReviewAudit,
        },
        "fetchers": {
            "pending_sdr": fetch_pending_reviews,
            "pending_sales": fetch_pending_deal_reviews,
            "pending_neg": fetch_pending_contract_reviews,
            "pending_fin": fetch_pending_dunning_reviews,
        },
    }


def _table_counts(session, models: dict) -> dict[str, int]:
    return {
        "leads": session.query(models["Lead"]).count(),
        "deals": session.query(models["Deal"]).count(),
        "contracts": session.query(models["Contract"]).count(),
        "invoices": session.query(models["Invoice"]).count(),
        "email_logs": session.query(models["EmailLog"]).count(),
        "llm_logs": session.query(models["LLMLog"]).count(),
        "agent_runs": session.query(models["AgentRun"]).count(),
        "review_audit": session.query(models["ReviewAudit"]).count(),
        "deal_stage_audit": session.query(models["DealStageAudit"]).count(),
        "negotiation_memory": session.query(models["NegotiationMemory"]).count(),
        "tenants": session.query(models["Tenant"]).count(),
    }


def _print_counts(header: str, counts: dict[str, int]) -> None:
    _log(header)
    for key in sorted(counts.keys()):
        _log(f"  {key}: {counts[key]}")


def purge_operational_data(session, models: dict) -> None:
    _log("Phase 1: ORM operational purge (dependency-safe order)")
    order: list[tuple[str, object]] = [
        ("review_audit", models["ReviewAudit"]),
        ("llm_logs", models["LLMLog"]),
        ("email_logs", models["EmailLog"]),
        ("agent_runs", models["AgentRun"]),
        ("invoices", models["Invoice"]),
        ("negotiation_memory", models["NegotiationMemory"]),
        ("contracts", models["Contract"]),
        ("deal_stage_audit", models["DealStageAudit"]),
        ("deals", models["Deal"]),
        ("leads", models["Lead"]),
    ]

    try:
        for label, model in order:
            before = session.query(model).count()
            deleted = session.query(model).delete(synchronize_session=False)
            _log(f"  {label}: before={before}, deleted={deleted}")
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError(f"Phase 1 purge failed and was rolled back: {exc}") from exc


def ingest_leads(session, models: dict, tenant_id: int) -> None:
    _log("Phase 2: Insert 10 realistic contactable leads")
    Lead = models["Lead"]
    try:
        for row in SEED_LEADS:
            insight = (
                f"LinkedIn: {row.linkedin_url} | Phone: {row.phone_number} | "
                "Priority signal: hiring aggressively, migrating core tech stack, "
                "budget approved for immediate rollout, expanding into new markets."
            )
            lead = Lead(
                tenant_id=tenant_id,
                name=row.full_name,
                email=row.work_email,
                role=row.designation,
                company=row.company_name,
                company_size=row.company_size,
                industry=row.industry,
                verified_insight=insight,
                status="New",
                source="manual",
                review_status="New",
            )
            session.add(lead)
        session.commit()
    except SQLAlchemyError as exc:
        session.rollback()
        raise RuntimeError(f"Phase 2 lead ingestion failed and was rolled back: {exc}") from exc

    # Validation checks.
    lead_count = session.query(Lead).filter(Lead.tenant_id == tenant_id).count()
    dupes = (
        session.query(Lead.email, func.count(Lead.id))
        .filter(Lead.tenant_id == tenant_id)
        .group_by(Lead.email)
        .having(func.count(Lead.id) > 1)
        .all()
    )
    _log(f"  leads for tenant {tenant_id}: {lead_count}")
    _log(f"  duplicate email groups for tenant {tenant_id}: {len(dupes)}")
    if lead_count != 10:
        raise RuntimeError(f"Expected 10 leads after ingestion, found {lead_count}.")
    if dupes:
        raise RuntimeError(f"Found duplicate lead emails for tenant {tenant_id}: {dupes}")


def run_pipeline_stages(database_url: str, stages: Iterable[str]) -> None:
    _log("Phase 3: Trigger pipeline stages")
    env = dict(os.environ)
    env["DATABASE_URL"] = database_url
    env["DB_CONNECTIVITY_REQUIRED"] = "true"
    for stage in stages:
        cmd = [sys.executable, "app/orchestrator.py", stage]
        _log(f"  running: {' '.join(cmd)}")
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, capture_output=True, text=True)
        print(proc.stdout.strip())
        if proc.returncode != 0:
            print(proc.stderr.strip())
            raise RuntimeError(f"Pipeline stage '{stage}' failed with code {proc.returncode}")


def validate_dashboard_consistency(session, models: dict, fetchers: dict) -> None:
    _log("Phase 4: DB + dashboard consistency checks")
    Lead = models["Lead"]
    Deal = models["Deal"]
    Contract = models["Contract"]
    Invoice = models["Invoice"]
    pending_sdr_db = session.query(Lead).filter(Lead.review_status == "Pending").count()
    pending_sales_db = session.query(Deal).filter(Deal.review_status == "Pending").count()
    pending_neg_db = session.query(Contract).filter(Contract.review_status == "Pending").count()
    pending_fin_db = session.query(Invoice).filter(Invoice.review_status == "Pending").count()

    pending_sdr_app = len(fetchers["pending_sdr"]())
    pending_sales_app = len(fetchers["pending_sales"]())
    pending_neg_app = len(fetchers["pending_neg"]())
    pending_fin_app = len(fetchers["pending_fin"]())

    _log(f"  pending_sdr: db={pending_sdr_db}, app={pending_sdr_app}")
    _log(f"  pending_sales: db={pending_sales_db}, app={pending_sales_app}")
    _log(f"  pending_negotiation: db={pending_neg_db}, app={pending_neg_app}")
    _log(f"  pending_finance: db={pending_fin_db}, app={pending_fin_app}")

    mismatches = []
    if pending_sdr_db != pending_sdr_app:
        mismatches.append("SDR")
    if pending_sales_db != pending_sales_app:
        mismatches.append("Sales")
    if pending_neg_db != pending_neg_app:
        mismatches.append("Negotiation")
    if pending_fin_db != pending_fin_app:
        mismatches.append("Finance")

    if mismatches:
        raise RuntimeError(f"Dashboard/data mismatch in: {', '.join(mismatches)}")


def final_assertions(session, models: dict, tenant_id: int) -> None:
    _log("Phase 5: Final integrity checklist")
    Lead = models["Lead"]
    Deal = models["Deal"]
    Contract = models["Contract"]
    Invoice = models["Invoice"]
    AgentRun = models["AgentRun"]
    LLMLog = models["LLMLog"]
    ReviewAudit = models["ReviewAudit"]

    lead_count = session.query(Lead).filter(Lead.tenant_id == tenant_id).count()
    leads_with_draft = session.query(Lead).filter(Lead.draft_message.isnot(None)).count()
    deal_count = session.query(Deal).count()
    contract_count = session.query(Contract).count()
    agent_runs_count = session.query(AgentRun).count()
    llm_logs_count = session.query(LLMLog).count()
    review_audit_count = session.query(ReviewAudit).count()

    orphan_deals = session.query(Deal).filter(Deal.lead_id.is_(None)).count()
    orphan_contracts = session.query(Contract).filter(Contract.deal_id.is_(None)).count()
    orphan_invoices = session.query(Invoice).filter(Invoice.contract_id.is_(None)).count()

    duplicate_emails = (
        session.query(Lead.email, func.count(Lead.id))
        .filter(Lead.tenant_id == tenant_id)
        .group_by(Lead.email)
        .having(func.count(Lead.id) > 1)
        .count()
    )

    _log(f"  leads={lead_count}")
    _log(f"  leads_with_draft={leads_with_draft}")
    _log(f"  deals={deal_count}")
    _log(f"  contracts={contract_count}")
    _log(f"  agent_runs={agent_runs_count}")
    _log(f"  llm_logs={llm_logs_count}")
    _log(f"  review_audit={review_audit_count}")
    _log(f"  orphan_deals={orphan_deals}, orphan_contracts={orphan_contracts}, orphan_invoices={orphan_invoices}")
    _log(f"  duplicate_emails={duplicate_emails}")

    if lead_count != 10:
        raise RuntimeError(f"Final validation failed: lead_count={lead_count} (expected 10)")
    if duplicate_emails != 0:
        raise RuntimeError("Final validation failed: duplicate lead emails detected")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe Postgres reset + clean lead ingestion for RIVO.")
    parser.add_argument("--database-url", help="PostgreSQL SQLAlchemy URL. If omitted, DATABASE_URL env is used.")
    parser.add_argument("--tenant-id", type=int, default=1, help="Tenant ID for inserted leads (default: 1).")
    parser.add_argument(
        "--stages",
        nargs="*",
        default=["sdr", "sales", "negotiation", "finance"],
        help="Orchestrator stages to run in order.",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip stage execution and perform only purge + ingestion + validation.",
    )
    args = parser.parse_args()

    database_url = _configure_env(args.database_url)
    _log(f"Using DATABASE_URL={database_url}")

    runtime = _import_runtime()
    Base = runtime["Base"]
    SessionLocal = runtime["SessionLocal"]
    get_engine = runtime["get_engine"]
    models = runtime["models"]
    fetchers = runtime["fetchers"]

    # Hard stop if DB is not reachable.
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))

    # Non-destructive: create only missing tables/columns defined in ORM metadata.
    Base.metadata.create_all(bind=get_engine())

    session = SessionLocal()
    try:
        before_counts = _table_counts(session, models)
        _print_counts("Counts before purge", before_counts)

        purge_operational_data(session, models)
        after_purge = _table_counts(session, models)
        _print_counts("Counts after purge", after_purge)

        ingest_leads(session, models, args.tenant_id)
        after_ingest = _table_counts(session, models)
        _print_counts("Counts after ingestion", after_ingest)

        if not args.skip_pipeline:
            run_pipeline_stages(database_url, args.stages)

        validate_dashboard_consistency(session, models, fetchers)
        final_assertions(session, models, args.tenant_id)
    finally:
        session.close()

    _log("Completed successfully.")


if __name__ == "__main__":
    main()
