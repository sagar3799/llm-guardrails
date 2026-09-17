from guardrails.pii_anonymizer import get_pii_anonymizer

EMAIL_TEXT = "My email is sagar.meena@example.com."
CLEAN_TEXT = "What's a good way to structure a README for an open-source project?"


def test_anonymizes_email():
    anonymizer = get_pii_anonymizer()
    result = anonymizer.anonymize(EMAIL_TEXT)
    assert "sagar.meena@example.com" not in result
    assert result != EMAIL_TEXT


def test_leaves_clean_text_unchanged():
    anonymizer = get_pii_anonymizer()
    result = anonymizer.anonymize(CLEAN_TEXT)
    assert result == CLEAN_TEXT
