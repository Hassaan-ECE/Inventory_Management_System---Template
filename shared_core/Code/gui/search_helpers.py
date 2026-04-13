"""Search-text helpers for equipment web lookups."""

from Code.db.models import Equipment


SEARCH_PLACEHOLDERS = {"-", "na", "n/a", "none", "null", "unknown", "need asset no"}


def build_search_text(eq: Equipment) -> str:
    """Build search-friendly text from make/model/description."""
    parts: list[str] = []
    seen: set[str] = set()

    for raw_value in (eq.manufacturer or eq.manufacturer_raw, eq.model, eq.description):
        value = " ".join(str(raw_value or "").split()).strip()
        if not value or value.casefold() in SEARCH_PLACEHOLDERS:
            continue

        key = value.casefold()
        if key in seen:
            continue

        seen.add(key)
        parts.append(value)

    return " ".join(parts).strip()


def build_age_search_subject(eq: Equipment) -> str:
    """Build the concise equipment name used in age-search prompts."""
    manufacturer = " ".join(str(eq.manufacturer or eq.manufacturer_raw or "").split()).strip()
    model = " ".join(str(eq.model or "").split()).strip()
    description = " ".join(str(eq.description or "").split()).strip()

    candidates = []
    if manufacturer and manufacturer.casefold() not in SEARCH_PLACEHOLDERS:
        candidates.append(manufacturer)
    if model and model.casefold() not in SEARCH_PLACEHOLDERS:
        candidates.append(model)

    if len(candidates) >= 2:
        return " ".join(candidates)

    if description and description.casefold() not in SEARCH_PLACEHOLDERS:
        candidates.append(description)

    return " ".join(candidates).strip()


def build_age_search_query(eq: Equipment) -> str:
    """Build the exact clipboard/search prompt used to look up equipment age."""
    subject = build_age_search_subject(eq)
    if not subject:
        return ""
    return f"how old is the {subject} in just years"


def build_search_query(eq: Equipment, mode: str = "general") -> str:
    """Build a browser query for the selected equipment row."""
    query = build_age_search_query(eq) if mode == "year" else build_search_text(eq)
    if not query:
        return ""

    return query
