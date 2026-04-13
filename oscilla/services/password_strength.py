"""Password strength validation using the zxcvbn library.

zxcvbn scores passwords on a scale of 0–4:
  0 — too guessable (e.g., "password", "123456")
  1 — very guessable
  2 — somewhat guessable             ← minimum acceptable (OWASP-aligned)
  3 — safely unguessable
  4 — very unguessable

Score 2 is the configured minimum. It rejects the most common passwords while
avoiding over-rejection of reasonable, memorable passphrases. The zxcvbn
suggestions are surfaced directly in the API 422 response to guide users.
"""

import zxcvbn as zxcvbn_lib  # type: ignore[import-untyped]

from oscilla.settings import settings


def validate_password_strength(password: str) -> None:
    """Raise ``ValueError`` if the password does not meet the minimum strength requirement.

    Args:
        password: Plain-text password to evaluate.

    Raises:
        ValueError: If the zxcvbn score is below ``settings.min_password_strength``,
            with a human-readable suggestion from zxcvbn or a generic fallback message.
    """
    result = zxcvbn_lib.zxcvbn(password)
    if result["score"] < settings.min_password_strength:
        suggestions = result.get("feedback", {}).get("suggestions", [])
        message = suggestions[0] if suggestions else "Password is too weak."
        raise ValueError(message)
