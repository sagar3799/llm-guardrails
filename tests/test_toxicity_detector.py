from guardrails.toxicity_detector import get_toxicity_detector

OBVIOUS_TOXIC = [
    "You are a worthless idiot and everyone hates you.",
    "I will find you and hurt you, you disgusting piece of trash.",
    "Shut up, you stupid moron, nobody wants you here.",
]

CLEAN_TEXT = [
    "Thanks for your help, I really appreciate the detailed explanation.",
    "The quarterly report shows a 12% increase in revenue year over year.",
    "I disagree with this approach, but I understand the reasoning behind it.",
]


def test_flags_obvious_toxicity():
    detector = get_toxicity_detector()
    flagged = [text for text in OBVIOUS_TOXIC if detector.check(text).is_toxic]
    assert len(flagged) >= 2, f"only flagged {len(flagged)}/{len(OBVIOUS_TOXIC)}: {flagged}"


def test_does_not_flag_clean_text():
    detector = get_toxicity_detector()
    false_positives = [text for text in CLEAN_TEXT if detector.check(text).is_toxic]
    assert not false_positives, f"false positives: {false_positives}"


def test_result_has_matched_rules_when_flagged():
    detector = get_toxicity_detector()
    result = detector.check(OBVIOUS_TOXIC[0])
    assert result.is_toxic
    assert result.matched_rules
    assert 0.0 <= result.confidence <= 1.0
