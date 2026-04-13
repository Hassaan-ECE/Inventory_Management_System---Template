"""Shared formatting helpers for equipment fields."""


def parse_age_years(value) -> float | None:
    """Parse an age value into a non-negative float."""
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return None

    try:
        age_value = float(text)
    except (TypeError, ValueError):
        return None

    if age_value < 0:
        return None

    return age_value


def format_age_years(value) -> str:
    """Format a stored age value for UI display."""
    if value is None:
        return ""

    try:
        age_value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if age_value.is_integer():
        return str(int(age_value))
    return f"{age_value:.1f}".rstrip("0").rstrip(".")
