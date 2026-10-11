from app.utils.text import clean_transcript, estimate_tokens, truncate_to_tokens


def test_clean_transcript_normalizes_whitespace():
    assert clean_transcript("hello\n\n  world ") == "hello world"


def test_clean_transcript_drops_control_chars():
    assert clean_transcript("hi\x00there") == "hithere"


def test_clean_transcript_collapses_repeated_punctuation():
    assert clean_transcript("wow!!!!! cool") == "wow! cool"


def test_estimate_tokens_at_least_one():
    assert estimate_tokens("") == 1
    assert estimate_tokens("abcd") >= 1


def test_truncate_to_tokens_pads_ellipsis():
    long = "x" * 1000
    out = truncate_to_tokens(long, max_tokens=10)
    assert out.endswith("…")
