import re

MAX_BYTES = 64 * 1024
MAX_LINES = 1200
PATTERNS = {
    "database": [
        r"(?:database|postgres(?:ql)?|mysql|sqlalchemy|psycopg).{0,100}(?:connection refused|could not connect|connection timed out|connection failure|connection pool exhausted|too many connections)",
        r"(?:could not connect|connection refused|connection timed out).{0,80}(?:database|postgres|mysql|port 5432|:5432)",
        r"(?:SQLSTATE[ =:\[]*(?:08001|08006|53300)|remaining connection slots|pool timeout.*connection)",
    ],
    "credentials": [
        r"(?:token|credential|password|certificate|api.?key|authentication).{0,80}(?:expired|invalid|revoked|failed)",
        r"(?:expired|invalid|revoked).{0,40}(?:token|credential|password|certificate|api.?key)",
        r"(?:HTTP[ /0-9.]*401\b|\b401 Unauthorized\b|SQLSTATE[ =:\[]*28P01|password authentication failed)",
    ],
    "service": [
        r"(?:HTTP[ /0-9.]*50[234]\b|\b50[234] (?:Bad Gateway|Service Unavailable|Gateway Timeout))",
        r"(?:upstream|service|health.?check|endpoint).{0,80}(?:unavailable|unhealthy|no healthy|connection refused|timed out)",
        r"(?:no healthy upstream|ECONNREFUSED.{0,50}service|service.{0,40}ECONNREFUSED)",
    ],
}


def parse_log(raw: bytes):
    if len(raw) > MAX_BYTES:
        raise ValueError("Log exceeds the 64 KiB limit")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Log must be valid UTF-8 text") from exc
    if not text.strip():
        raise ValueError("Log cannot be empty")
    if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
        raise ValueError("Log contains unsupported control characters")
    if len(text.splitlines()) > MAX_LINES:
        raise ValueError("Log exceeds the 1,200 line limit")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def classify(text):
    found = {}
    for category, patterns in PATTERNS.items():
        lines = [
            i
            for i, line in enumerate(text.splitlines(), 1)
            if any(re.search(p, line, re.I) for p in patterns)
        ]
        if lines:
            found[category] = lines[:8]
    if len(found) != 1:
        return "unknown", sorted({n for lines in found.values() for n in lines})[:8]
    category = next(iter(found))
    return category, found[category]
