"""Sanitization: wrap tool output as untrusted data, truncate, strip control chars."""

from __future__ import annotations

MAX_DETAIL_LENGTH = 4000
MAX_SUMMARY_LENGTH = 800


def sanitize_tool_output(text: str) -> str:
    """Wrap raw tool output as <untrusted_data> so prompt injections fail.

    - Truncate to MAX_DETAIL_LENGTH chars
    - Strip non-printable control characters (keep \n, \t)
    """
    safe = ""
    for ch in text:
        if ch in ("\n", "\t", "\r"):
            safe += ch
        elif 0x20 <= ord(ch) < 0x7F or ord(ch) >= 0xA0:
            safe += ch
        else:
            safe += " "
    if len(safe) > MAX_DETAIL_LENGTH:
        safe = safe[: MAX_DETAIL_LENGTH - 3] + "..."
    return f"<untrusted_data source='tool'>\n{safe}\n</untrusted_data>"


def truncate_summary(text: str) -> str:
    if len(text) > MAX_SUMMARY_LENGTH:
        return text[: MAX_SUMMARY_LENGTH - 3] + "..."
    return text


def wrap_in_untrusted(text: str) -> str:
    """Wrap arbitrary (already sanitized) tool output with source attribution."""
    return f"<untrusted_data source='tool'>\n{text}\n</untrusted_data>"
