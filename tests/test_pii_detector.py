from guardrails.pii_detector import get_pii_detector

TEXT_WITH_EMAIL = "Please send the invoice to sagar.meena@example.com by Friday."
TEXT_WITH_PHONE = "You can reach support at (415) 555-0198 during business hours."
TEXT_WITH_NAME = "My name is Sagar Meena and I'd like to update my account details."
CLEAN_TEXT = "Can you summarize the quarterly report into three bullet points?"


def test_flags_email():
    detector = get_pii_detector()
    result = detector.check(TEXT_WITH_EMAIL)
    assert result.has_pii
    assert "EMAIL_ADDRESS" in result.entity_types


def test_flags_phone_number():
    detector = get_pii_detector()
    result = detector.check(TEXT_WITH_PHONE)
    assert result.has_pii
    assert "PHONE_NUMBER" in result.entity_types


def test_flags_person_name():
    detector = get_pii_detector()
    result = detector.check(TEXT_WITH_NAME)
    assert result.has_pii
    assert "PERSON" in result.entity_types


def test_does_not_flag_clean_text():
    detector = get_pii_detector()
    result = detector.check(CLEAN_TEXT)
    assert not result.has_pii
    assert result.entity_types == []
