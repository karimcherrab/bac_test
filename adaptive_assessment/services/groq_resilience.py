import random
import re
import time


class GroqTemporaryFailure(RuntimeError):
    """Temporary Groq/network failure after all safe retries are exhausted."""


def _response_from_exception(exc):
    return getattr(exc, "response", None)


def _headers_from_exception(exc):
    response = _response_from_exception(exc)
    headers = getattr(response, "headers", None)
    return headers or {}


def _status_code(exc):
    status = getattr(exc, "status_code", None)
    if status:
        return status
    response = _response_from_exception(exc)
    return getattr(response, "status_code", None)


def is_rate_limit_error(exc):
    if _status_code(exc) == 429:
        return True
    name = exc.__class__.__name__.lower()
    if "ratelimit" in name or "rate_limit" in name:
        return True
    text = str(exc).lower()
    return "429" in text and ("rate limit" in text or "rate_limit" in text)


def is_transient_error(exc):
    status = _status_code(exc)
    if status in {408, 409, 429, 500, 502, 503, 504}:
        return True
    name = exc.__class__.__name__.lower()
    return any(
        marker in name
        for marker in (
            "timeout",
            "connection",
            "ratelimit",
            "rate_limit",
            "internalserver",
            "serviceunavailable",
        )
    )


def _duration_to_seconds(value):
    """
    Parse Groq/OpenAI-style durations, including:
      157.5ms, 2.3s, 1m2.5s, 1m, 00:01:02 (best effort).
    """
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    # Plain Retry-After seconds.
    try:
        return float(text)
    except (TypeError, ValueError):
        pass

    # 1m2.5s / 2.5s / 157ms
    m = re.fullmatch(
        r"(?:(?P<minutes>[0-9]+(?:\.[0-9]+)?)m)?\s*"
        r"(?:(?P<seconds>[0-9]+(?:\.[0-9]+)?)s)?\s*"
        r"(?:(?P<millis>[0-9]+(?:\.[0-9]+)?)ms)?",
        text,
    )
    if m and any(m.groupdict().values()):
        minutes = float(m.group("minutes") or 0)
        seconds = float(m.group("seconds") or 0)
        millis = float(m.group("millis") or 0)
        return minutes * 60.0 + seconds + millis / 1000.0

    # Some headers can look like 1m2s but regex ambiguity with ms is easier
    # handled token-by-token.
    total = 0.0
    found = False
    for amount, unit in re.findall(r"([0-9]+(?:\.[0-9]+)?)\s*(ms|m|s)", text):
        found = True
        number = float(amount)
        if unit == "ms":
            total += number / 1000.0
        elif unit == "m":
            total += number * 60.0
        else:
            total += number
    return total if found else None


def retry_after_seconds(exc, *, attempt=1, minimum=0.40, maximum=120.0):
    """
    Respect provider timing before exponential backoff.

    Groq commonly returns Retry-After and/or x-ratelimit-reset-tokens. The
    latter is especially useful for TPM errors because it indicates when enough
    token capacity becomes available again.
    """
    headers = _headers_from_exception(exc)

    candidates = []
    for key in (
        "retry-after",
        "Retry-After",
        "x-ratelimit-reset-tokens",
        "X-RateLimit-Reset-Tokens",
        "x-ratelimit-reset-requests",
        "X-RateLimit-Reset-Requests",
    ):
        parsed = _duration_to_seconds(headers.get(key))
        if parsed is not None:
            candidates.append(parsed)

    # Parse provider message e.g. "Please try again in 157.5ms".
    text = str(exc)
    match = re.search(
        r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*(ms|s|m)",
        text,
        re.I,
    )
    if match:
        number = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "ms":
            number /= 1000.0
        elif unit == "m":
            number *= 60.0
        candidates.append(number)

    if candidates:
        # Use the longest provider hint. This avoids retrying too early when
        # request and token buckets reset at different times.
        wait = max(candidates) + 0.25
        return max(minimum, min(wait, maximum))

    # Safe exponential fallback with jitter for network/5xx errors or SDKs that
    # do not expose rate-limit headers.
    base = min(0.8 * (2 ** max(attempt - 1, 0)), maximum)
    return max(minimum, min(base + random.uniform(0.05, 0.30), maximum))


def call_with_retries(callable_, *, attempts=10, label="Groq request"):
    """
    Execute one Groq request while transparently absorbing 429/5xx/network
    failures. JSON/content retries are handled separately by the caller.
    """
    last_error = None
    total_attempts = max(1, int(attempts or 1))

    for attempt in range(1, total_attempts + 1):
        try:
            return callable_()
        except Exception as exc:  # SDK classes differ across Groq versions.
            last_error = exc
            if not is_transient_error(exc):
                raise
            if attempt >= total_attempts:
                raise
            time.sleep(retry_after_seconds(exc, attempt=attempt))

    raise GroqTemporaryFailure(
        f"{label} failed after {total_attempts} attempts: {last_error}"
    )
