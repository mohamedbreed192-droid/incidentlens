import pytest

from app.parsing import classify, parse_log
from app.redaction import redact


@pytest.mark.parametrize("raw", [b"", b"   ", b"\xff", b"a\x00b", b"a" * 65537, b"x\n" * 1201])
def test_reject_bad_logs(raw):
    with pytest.raises(ValueError):
        parse_log(raw)


def test_line_numbers_and_newlines():
    text = parse_log(b"INFO start\r\nERROR postgres connection refused\r\n")
    assert classify(text) == ("database", [2])
    assert "\r" not in text


def test_unknown_and_ambiguous():
    assert classify("INFO ready")[0] == "unknown"
    assert classify("postgres connection refused\nHTTP 503 Service Unavailable")[0] == "unknown"


@pytest.mark.parametrize(
    "value,secret",
    [
        ("password=hidden-secret", "hidden-secret"),
        ('{"api_key":"hidden-secret"}', "hidden-secret"),
        ("Authorization: Bearer hidden-secret", "hidden-secret"),
        ("postgres://alice:hidden-secret@db/test", "hidden-secret"),
        ("token=hidden-secret", "hidden-secret"),
        ("key sk-synthetic12345678901234567890", "sk-synthetic12345678901234567890"),
        ("eyJtest.payload.signature", "eyJtest.payload.signature"),
    ],
)
def test_redaction(value, secret):
    assert secret not in redact(value)


def test_redaction_keeps_line_positions():
    raw = "start\n-----BEGIN PRIVATE KEY-----\nabcdef\n-----END PRIVATE KEY-----\nend"
    result = redact(raw)
    assert "abcdef" not in result
    assert result.splitlines()[4] == "end"
