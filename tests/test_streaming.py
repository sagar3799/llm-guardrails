from guardrails.streaming import StreamingGuard

CLEAN_TOKENS = ["Thanks", "for", "reaching", "out", "we", "will", "get", "back", "to", "you", "within", "two", "business", "days"]
TOXIC_TOKENS = ["Well", "let", "me", "just", "say", "that", "you", "are", "a", "worthless", "idiot", "and", "everyone", "around", "you", "hates", "you", "deeply"]


def test_feed_returns_empty_until_window_full():
    guard = StreamingGuard(window_size=10, stride=5)
    for token in CLEAN_TOKENS[:9]:
        assert guard.feed(token) == []


def test_feed_checks_window_once_full_and_stride_reached():
    guard = StreamingGuard(window_size=8, stride=4)
    results = []
    for token in TOXIC_TOKENS:
        results.extend(guard.feed(token))
    assert any(r.action.value == "block" for r in results), "expected a block on the toxic window"


def test_clean_stream_never_triggers():
    guard = StreamingGuard(window_size=8, stride=4)
    results = []
    for token in CLEAN_TOKENS:
        results.extend(guard.feed(token))
    assert results == []


def test_stride_must_be_smaller_than_window():
    import pytest

    with pytest.raises(ValueError):
        StreamingGuard(window_size=10, stride=10)


def test_flush_checks_remaining_buffer():
    guard = StreamingGuard(window_size=100, stride=50)
    for token in TOXIC_TOKENS:
        guard.feed(token)
    results = guard.flush()
    assert any(r.action.value == "block" for r in results)
