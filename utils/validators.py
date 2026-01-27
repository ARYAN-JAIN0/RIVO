def validate_structure(email_text: str) -> bool:
    """
    Deterministic structural validation.
    No LLM calls. No scoring. Pure rules.
    """

    if not email_text or not isinstance(email_text, str):
        return False

    text = email_text.strip()

    # Must start with a greeting
    valid_greetings = ("hi ", "hello ", "dear ")
    if not text.lower().startswith(valid_greetings):
        return False

    # Must NOT contain placeholders
    forbidden_tokens = [
        "[your name]",
        "[your company]",
        "[your position]",
        "[contact information]",
        "[specific date]",
        "[time]"
    ]

    for token in forbidden_tokens:
        if token.lower() in text.lower():
            return False

    # Must end with a sign-off
    valid_signoffs = ("best,", "best regards,", "regards,", "thanks,", "thank you,")
    if not any(text.lower().rstrip().endswith(s) for s in valid_signoffs):
        return False

    # Minimum length check (avoid 2-line junk)
    if len(text.split()) < 30:
        return False

    return True
