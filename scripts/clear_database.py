"""Clear all pipeline data from the database, preserving tenants and users.

This script deletes all pipeline-related data in the correct order to respect
foreign key constraints. It preserves:
- Tenants (needed for multi-tenant infrastructure)
- Users (needed for authentication)
- Prompt Templates (contain LLM prompts)

Usage:
    python scripts/clear_database.py
    python scripts/clear_database.py --confirm
    python scripts/clear_database.py --include-users
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import get_db_session
from app.database.models import (
    AgentRun,
    Contract,
    Deal,
    DealStageAudit,
    EmailLog,
    Embedding,
    Invoice,
    KnowledgeBase,
    Lead,
    LLMLog,
    NegotiationMemory,
    ReviewAudit,
    User,
    Tenant,
)


def clear_pipeline_data(include_users: bool = False, confirm: bool = False) -> dict[str, int]:
    """Clear all pipeline data, keeping tenant and user infrastructure.
    
    Args:
        include_users: If True, also delete users (keeps default tenant).
        confirm: If True, actually perform the deletion. Otherwise, just count.
        
    Returns:
        Dictionary mapping table names to deleted record counts.
    """
    deleted_counts = {}
    
    with get_db_session() as session:
        # Count existing records first
        counts = {
            "invoices": session.query(Invoice).count(),
            "contracts": session.query(Contract).count(),
            "negotiation_memory": session.query(NegotiationMemory).count(),
            "deal_stage_audit": session.query(DealStageAudit).count(),
            "deals": session.query(Deal).count(),
            "email_logs": session.query(EmailLog).count(),
            "llm_logs": session.query(LLMLog).count(),
            "embeddings": session.query(Embedding).count(),
            "knowledge_base": session.query(KnowledgeBase).count(),
            "review_audit": session.query(ReviewAudit).count(),
            "agent_runs": session.query(AgentRun).count(),
            "leads": session.query(Lead).count(),
        }
        
        if include_users:
            counts["users"] = session.query(User).count()
        
        print("\n" + "=" * 50)
        print("DATABASE CLEARANCE REPORT")
        print("=" * 50)
        print("\nRecords that will be deleted:")
        total = 0
        for table, count in counts.items():
            print(f"  {table}: {count}")
            total += count
        print(f"\n  TOTAL: {total} records")
        print("=" * 50)
        
        if not confirm:
            print("\n[DRY RUN] No records were deleted.")
            print("Run with --confirm to actually delete records.")
            return counts
        
        if total == 0:
            print("\nNo records to delete. Database is already clean.")
            return counts
        
        # Delete in reverse dependency order (respecting foreign keys)
        print("\nDeleting records...")
        
        deleted_counts["invoices"] = session.query(Invoice).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['invoices']} invoices")
        
        deleted_counts["contracts"] = session.query(Contract).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['contracts']} contracts")
        
        deleted_counts["negotiation_memory"] = session.query(NegotiationMemory).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['negotiation_memory']} negotiation_memory")
        
        deleted_counts["deal_stage_audit"] = session.query(DealStageAudit).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['deal_stage_audit']} deal_stage_audit")
        
        deleted_counts["deals"] = session.query(Deal).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['deals']} deals")
        
        deleted_counts["email_logs"] = session.query(EmailLog).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['email_logs']} email_logs")
        
        deleted_counts["llm_logs"] = session.query(LLMLog).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['llm_logs']} llm_logs")
        
        deleted_counts["embeddings"] = session.query(Embedding).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['embeddings']} embeddings")
        
        deleted_counts["knowledge_base"] = session.query(KnowledgeBase).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['knowledge_base']} knowledge_base")
        
        deleted_counts["review_audit"] = session.query(ReviewAudit).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['review_audit']} review_audit")
        
        deleted_counts["agent_runs"] = session.query(AgentRun).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['agent_runs']} agent_runs")
        
        deleted_counts["leads"] = session.query(Lead).delete(synchronize_session=False)
        print(f"  ✓ Deleted {deleted_counts['leads']} leads")
        
        if include_users:
            deleted_counts["users"] = session.query(User).delete(synchronize_session=False)
            print(f"  ✓ Deleted {deleted_counts['users']} users")
        
        # Commit the transaction
        session.commit()
        
        print("\n" + "=" * 50)
        print("✓ Database cleared successfully!")
        print("=" * 50)
        
        # Verify tenant still exists
        tenant_count = session.query(Tenant).count()
        print(f"\nPreserved: {tenant_count} tenants (required for infrastructure)")
        
        if not include_users:
            user_count = session.query(User).count()
            print(f"Preserved: {user_count} users")
        
        return deleted_counts


def main() -> None:
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Clear all pipeline data from the database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/clear_database.py              # Dry run (just count records)
    python scripts/clear_database.py --confirm    # Actually delete records
    python scripts/clear_database.py --confirm --include-users  # Also delete users
        """,
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Actually perform the deletion (default is dry run)",
    )
    parser.add_argument(
        "--include-users",
        action="store_true",
        help="Also delete user accounts (keeps tenants)",
    )
    
    args = parser.parse_args()
    
    try:
        clear_pipeline_data(include_users=args.include_users, confirm=args.confirm)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
