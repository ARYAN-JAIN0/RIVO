"""Configuration for lead scraping sources."""

from __future__ import annotations

# Default scraping source configurations
# Each source defines how to fetch and parse lead data

DEFAULT_SCRAPER_SOURCES = [
    # =============================================================================
    # MOCK DATA SOURCE - Generates realistic synthetic leads for testing
    # =============================================================================
    {
        "name": "mock_leads",
        "type": "mock",
        "enabled": True,  # Enabled for testing
        "count": 10,  # Number of leads to generate per run
    },
    # =============================================================================
    # REAL DATA SOURCES - Configure and enable as needed
    # =============================================================================
    # Example: Company career pages for hiring signals
    {
        "name": "example_careers",
        "type": "html",
        "url": "https://example.com/careers",
        "enabled": False,  # Disabled by default - configure before enabling
        "timeout_seconds": 30,
        "rate_limit_seconds": 2,
        "selectors": {
            "job_listings": ".job-listing",
            "title": ".job-title",
            "location": ".job-location",
        },
    },
    # Example: Industry directory
    {
        "name": "example_directory",
        "type": "html",
        "url": "https://example.com/directory",
        "enabled": False,
        "timeout_seconds": 30,
        "rate_limit_seconds": 2,
        "selectors": {
            "companies": ".company-card",
            "name": ".company-name",
            "website": ".company-website",
            "industry": ".company-industry",
        },
    },
]

# Field mapping from source to canonical lead schema
DEFAULT_FIELD_MAPPINGS = {
    "name": ["name", "contact_name", "full_name"],
    "email": ["email", "email_address", "contact_email"],
    "company": ["company", "company_name", "organization"],
    "role": ["role", "title", "job_title", "position"],
    "industry": ["industry", "sector", "vertical"],
    "company_size": ["company_size", "employee_count", "size"],
    "website": ["website", "url", "domain"],
    "location": ["location", "city", "address"],
    "verified_insight": ["insight", "notes", "description"],
}
