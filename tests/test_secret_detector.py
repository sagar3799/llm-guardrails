from guardrails.secret_detector import get_secret_detector

OBVIOUS_SECRETS = [
    "Here's the key you asked about: sk-proj-AbCdEfGh12345678901234567890.",
    "For testing, you can use this AWS access key: AKIAABCDEFGHIJKLMNOP.",
    "Your GitHub token is ghp_1234567890abcdefghijklmnopqrstuvwxyz12.",
]

CLEAN_TEXT = [
    "What's a good way to structure a README for an open-source project?",
    "I forgot my password, can you walk me through the reset process?",
    "The report shows a steady increase in engagement over the last two quarters.",
]


def test_flags_obvious_secrets():
    detector = get_secret_detector()
    flagged = [text for text in OBVIOUS_SECRETS if detector.check(text).has_secret]
    assert len(flagged) == len(OBVIOUS_SECRETS), f"only flagged {len(flagged)}/{len(OBVIOUS_SECRETS)}"


def test_does_not_flag_clean_text():
    detector = get_secret_detector()
    false_positives = [text for text in CLEAN_TEXT if detector.check(text).has_secret]
    assert not false_positives, f"false positives: {false_positives}"


def test_result_has_matched_type_when_flagged():
    detector = get_secret_detector()
    result = detector.check(OBVIOUS_SECRETS[0])
    assert result.has_secret
    assert "OPENAI_API_KEY" in result.matched_types
    assert result.confidence > 0.0
