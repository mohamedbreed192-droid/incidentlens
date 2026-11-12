import re

# Preserve newlines so evidence line numbers remain stable. Pattern coverage is deliberately finite.
PATTERNS = [
    (r"(?i)\b(authorization\s*:\s*(?:bearer|basic)\s+)[^\s,;]+", r"\1[REDACTED]"),
    (
        r"(?i)(\b(?:password|passwd|pwd|token|api[_-]?key|secret|client_secret|access_token)\b[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]+",
        r"\1[REDACTED]",
    ),
    (r"(?i)([a-z][a-z0-9+.-]*://)[^\s/@:]+:[^\s/@]+@", r"\1[REDACTED]@"),
    (r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED_JWT]"),
    (r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9_]{20,})\b", "[REDACTED_KEY]"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
]


def redact(text):
    for pattern, replacement in PATTERNS:

        def preserve(match):
            changed = match.expand(replacement)
            return changed + "\n" * (match.group().count("\n") - changed.count("\n"))

        text = re.sub(pattern, preserve, text)
    return text
