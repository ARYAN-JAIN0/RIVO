from __future__ import annotations

from utils.validators import sanitize_text, validate_structure


def test_validate_structure_accepts_valid_email():
    email = (
        "Hi Alex, I noticed your team is expanding cloud operations and likely handling higher deployment volume. "
        "We help teams reduce rollout friction while keeping reporting clean across sales and engineering. "
        "If useful, I can share two quick examples from similar SaaS teams this week.\n\n"
        "Best regards,\n"
        "RIVO Team"
    )
    assert validate_structure(email) is True


def test_validate_structure_rejects_placeholders():
    email = (
        "Hi [your name], we saw [your company] expanding quickly and wanted to help with growth planning and process optimization.\n\n"
        "Best regards,\n"
        "RIVO Team"
    )
    assert validate_structure(email) is False


def test_sanitize_text_strips_null_and_trims():
    assert sanitize_text("  hello\x00world  ") == "helloworld"

