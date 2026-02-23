"""Lead scraper service for SDR ingestion.

This module provides scraping-based lead ingestion that integrates with the SDR agent.
It does NOT call LLM - it only fetches, validates, and inserts leads with "New" status.

Safety guarantees:
- Atomic writes to CSV
- Error isolation per source
- Deduplication by email + company
- Schema validation before insertion
"""

from __future__ import annotations

import csv
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from app.config.scraper_sources import DEFAULT_FIELD_MAPPINGS, DEFAULT_SCRAPER_SOURCES
from app.utils.validators import sanitize_text

logger = logging.getLogger(__name__)

# Required fields for a valid lead
REQUIRED_LEAD_FIELDS = {"name", "email", "company"}

# Email validation regex
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def scrape_source(source_config: dict) -> list[dict]:
    """Fetch raw data from a single source.

    Args:
        source_config: Source configuration dict with url, type, selectors, etc.

    Returns:
        List of raw records from the source. Empty list on failure.
    """
    if not source_config.get("enabled", False):
        logger.info(
            "scraper.source.disabled",
            extra={"event": "scraper.source.disabled", "source": source_config.get("name", "unknown")},
        )
        return []

    source_name = source_config.get("name", "unknown")
    url = source_config.get("url")
    timeout = source_config.get("timeout_seconds", 30)

    if not url:
        logger.warning(
            "scraper.source.no_url",
            extra={"event": "scraper.source.no_url", "source": source_name},
        )
        return []

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        # Parse based on source type
        source_type = source_config.get("type", "html")
        if source_type == "html":
            return _parse_html_response(response.text, source_config)
        elif source_type == "json":
            return _parse_json_response(response.json(), source_config)
        else:
            logger.warning(
                "scraper.source.unknown_type",
                extra={"event": "scraper.source.unknown_type", "source": source_name, "type": source_type},
            )
            return []

    except requests.exceptions.Timeout:
        logger.error(
            "scraper.source.timeout",
            extra={"event": "scraper.source.timeout", "source": source_name, "url": url},
        )
        return []
    except requests.exceptions.RequestException as exc:
        logger.error(
            "scraper.source.request_failed",
            extra={"event": "scraper.source.request_failed", "source": source_name, "error": str(exc)},
        )
        return []
    except Exception as exc:
        logger.exception(
            "scraper.source.unexpected_error",
            extra={"event": "scraper.source.unexpected_error", "source": source_name, "error": str(exc)},
        )
        return []


def _parse_html_response(html: str, source_config: dict) -> list[dict]:
    """Parse HTML response into raw records.

    Note: This is a simplified parser. For production use, consider using BeautifulSoup.
    """
    # Placeholder - in production, use proper HTML parsing
    # This returns empty list as sources are disabled by default
    return []


def _parse_json_response(data: Any, source_config: dict) -> list[dict]:
    """Parse JSON response into raw records."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        # Look for common data envelope keys
        for key in ["data", "results", "items", "records"]:
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def normalize_lead(raw_record: dict, field_mappings: dict | None = None) -> dict:
    """Transform raw record to canonical lead schema.

    Args:
        raw_record: Raw data from source
        field_mappings: Optional custom field mappings

    Returns:
        Normalized lead dict with canonical field names
    """
    mappings = field_mappings or DEFAULT_FIELD_MAPPINGS
    normalized = {}

    for canonical_field, source_fields in mappings.items():
        for source_field in source_fields:
            if source_field in raw_record and raw_record[source_field]:
                normalized[canonical_field] = sanitize_text(str(raw_record[source_field]), max_len=2000)
                break

    return normalized


def validate_lead_schema(lead_dict: dict) -> tuple[bool, str]:
    """Validate required fields in lead dict.

    Args:
        lead_dict: Normalized lead dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    missing = REQUIRED_LEAD_FIELDS - set(lead_dict.keys())
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    # Validate email format
    email = lead_dict.get("email", "")
    if not EMAIL_PATTERN.match(email):
        return False, f"Invalid email format: {email}"

    # Validate non-empty required fields
    for field in REQUIRED_LEAD_FIELDS:
        if not lead_dict.get(field, "").strip():
            return False, f"Empty required field: {field}"

    return True, ""


def deduplicate_against_csv(lead_dict: dict, csv_path: str) -> bool:
    """Check if lead already exists in CSV by email + company.

    Args:
        lead_dict: Normalized lead dictionary
        csv_path: Path to leads.csv file

    Returns:
        True if lead is a duplicate, False if new
    """
    email = lead_dict.get("email", "").lower().strip()
    company = lead_dict.get("company", "").lower().strip()

    if not email or not company:
        return False

    csv_file = Path(csv_path)
    if not csv_file.exists():
        return False

    try:
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_email = row.get("email", "").lower().strip()
                existing_company = row.get("company", "").lower().strip()
                if existing_email == email and existing_company == company:
                    return True
    except Exception as exc:
        logger.error(
            "scraper.dedup.read_failed",
            extra={"event": "scraper.dedup.read_failed", "csv_path": csv_path, "error": str(exc)},
        )
        # On error, assume not duplicate to avoid blocking insertion
        return False

    return False


def deduplicate_against_db(lead_dict: dict) -> bool:
    """Check if lead already exists in database by email.

    Args:
        lead_dict: Normalized lead dictionary

    Returns:
        True if lead is a duplicate, False if new
    """
    from app.database.db import get_db_session
    from app.database.models import Lead

    email = lead_dict.get("email", "").lower().strip()
    if not email:
        return False

    try:
        with get_db_session() as session:
            existing = session.query(Lead).filter(Lead.email.ilike(email)).first()
            return existing is not None
    except Exception as exc:
        logger.error(
            "scraper.dedup.db_check_failed",
            extra={"event": "scraper.dedup.db_check_failed", "email": email, "error": str(exc)},
        )
        # On error, assume not duplicate to avoid blocking insertion
        return False


def insert_new_leads(leads: list[dict], csv_path: str = "db/leads.csv") -> int:
    """Insert validated, deduplicated leads to CSV.

    Uses atomic write pattern: write to temp file, then rename.

    Args:
        leads: List of normalized, validated lead dicts
        csv_path: Path to leads.csv file

    Returns:
        Count of leads actually inserted
    """
    if not leads:
        return 0

    csv_file = Path(csv_path)
    csv_file.parent.mkdir(parents=True, exist_ok=True)

    # Determine if we need to write header
    write_header = not csv_file.exists()

    # Prepare new records
    new_records = []
    for lead in leads:
        if deduplicate_against_csv(lead, csv_path):
            logger.info(
                "scraper.insert.duplicate_csv",
                extra={"event": "scraper.insert.duplicate_csv", "email": lead.get("email")},
            )
            continue
        if deduplicate_against_db(lead):
            logger.info(
                "scraper.insert.duplicate_db",
                extra={"event": "scraper.insert.duplicate_db", "email": lead.get("email")},
            )
            continue

        # Add metadata fields
        record = {
            "id": str(uuid.uuid4())[:8],  # Short ID for CSV
            "tenant_id": "1",
            "name": lead.get("name", ""),
            "email": lead.get("email", ""),
            "role": lead.get("role", ""),
            "company": lead.get("company", ""),
            "website": lead.get("website", ""),
            "location": lead.get("location", ""),
            "company_size": lead.get("company_size", ""),
            "industry": lead.get("industry", ""),
            "verified_insight": lead.get("verified_insight", ""),
            "negative_signals": "",
            "status": "New",
            "last_contacted": "",
            "signal_score": "",
            "confidence_score": "",
            "review_status": "New",
            "draft_message": "",
            "source": "scraper",
            "last_reply_at": "",
            "followup_count": "0",
            "next_followup_at": "",
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        new_records.append(record)

    if not new_records:
        logger.info("scraper.insert.no_new_records", extra={"event": "scraper.insert.no_new_records"})
        return 0

    # Atomic write: write to temp file, then rename
    try:
        # Read existing data if file exists
        existing_rows = []
        fieldnames = None
        if csv_file.exists():
            with open(csv_file, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                existing_rows = list(reader)

        # Set fieldnames for output
        if fieldnames is None:
            fieldnames = list(new_records[0].keys())

        # Write to temp file
        temp_fd, temp_path = tempfile.mkstemp(suffix=".csv", dir=csv_file.parent)
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                # Write existing rows
                for row in existing_rows:
                    writer.writerow(row)
                # Write new rows
                for record in new_records:
                    writer.writerow(record)

            # Atomic rename
            os.replace(temp_path, csv_file)

            logger.info(
                "scraper.insert.success",
                extra={
                    "event": "scraper.insert.success",
                    "count": len(new_records),
                    "csv_path": str(csv_path),
                },
            )
            return len(new_records)

        except Exception as exc:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    except Exception as exc:
        logger.exception(
            "scraper.insert.failed",
            extra={"event": "scraper.insert.failed", "csv_path": str(csv_path), "error": str(exc)},
        )
        return 0


def run_scraper_job(source_configs: list[dict] | None = None, csv_path: str = "db/leads.csv") -> dict:
    """Main entry point for scraper job.

    Args:
        source_configs: List of source configurations. Uses defaults if None.
        csv_path: Path to leads.csv file

    Returns:
        Summary dict with counts and errors
    """
    sources = source_configs or DEFAULT_SCRAPER_SOURCES
    correlation_id = uuid.uuid4().hex[:8]

    logger.info(
        "scraper.job.start",
        extra={"event": "scraper.job.start", "correlation_id": correlation_id, "source_count": len(sources)},
    )

    summary = {
        "correlation_id": correlation_id,
        "sources_processed": 0,
        "sources_failed": 0,
        "raw_records_fetched": 0,
        "valid_leads": 0,
        "duplicates_skipped": 0,
        "inserted": 0,
        "errors": [],
    }

    all_valid_leads = []

    for source_config in sources:
        source_name = source_config.get("name", "unknown")

        try:
            raw_records = scrape_source(source_config)
            summary["sources_processed"] += 1
            summary["raw_records_fetched"] += len(raw_records)

            for raw_record in raw_records:
                normalized = normalize_lead(raw_record)
                is_valid, error = validate_lead_schema(normalized)

                if is_valid:
                    summary["valid_leads"] += 1
                    all_valid_leads.append(normalized)
                else:
                    logger.debug(
                        "scraper.validation.failed",
                        extra={
                            "event": "scraper.validation.failed",
                            "source": source_name,
                            "error": error,
                        },
                    )

        except Exception as exc:
            summary["sources_failed"] += 1
            summary["errors"].append({"source": source_name, "error": str(exc)})
            logger.exception(
                "scraper.source.processing_failed",
                extra={"event": "scraper.source.processing_failed", "source": source_name},
            )

    # Insert all valid leads
    inserted = insert_new_leads(all_valid_leads, csv_path)
    summary["inserted"] = inserted
    summary["duplicates_skipped"] = summary["valid_leads"] - inserted

    logger.info(
        "scraper.job.complete",
        extra={
            "event": "scraper.job.complete",
            "correlation_id": correlation_id,
            "summary": summary,
        },
    )

    return summary
