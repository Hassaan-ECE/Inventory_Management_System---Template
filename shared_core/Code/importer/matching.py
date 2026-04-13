"""Duplicate-aware matching helpers for imported equipment rows."""

from collections import defaultdict
from dataclasses import dataclass

from Code.db.models import Equipment


@dataclass
class MatchResult:
    """The outcome of resolving an import row to a base equipment record."""

    record: Equipment | None = None
    status: str = "unmatched"  # matched, unmatched, conflict
    summary: str = ""


def build_equipment_indexes(
    records: list[Equipment],
) -> tuple[dict[str, list[Equipment]], dict[str, list[Equipment]], dict[str, list[Equipment]]]:
    """Build duplicate-preserving lookup indexes for base equipment records."""
    by_asset: dict[str, list[Equipment]] = defaultdict(list)
    by_serial: dict[str, list[Equipment]] = defaultdict(list)
    by_import_key: dict[str, list[Equipment]] = defaultdict(list)

    for eq in records:
        asset_key = _normalize_key(eq.asset_number)
        serial_key = _normalize_key(eq.serial_number)
        import_key = _normalize_key(eq.primary_import_key())
        if asset_key:
            by_asset[asset_key].append(eq)
        if serial_key:
            by_serial[serial_key].append(eq)
        if import_key:
            by_import_key[import_key].append(eq)

    return dict(by_asset), dict(by_serial), dict(by_import_key)


def resolve_equipment_match(
    by_asset: dict[str, list[Equipment]],
    by_serial: dict[str, list[Equipment]],
    by_import_key: dict[str, list[Equipment]] | None = None,
    asset_number: str = "",
    serial_number: str = "",
    import_key: str = "",
) -> MatchResult:
    """Resolve a source row to exactly one equipment record when possible."""
    asset_value = asset_number.strip()
    serial_value = serial_number.strip()
    import_value = import_key.strip()
    asset_key = _normalize_key(asset_value)
    serial_key = _normalize_key(serial_value)
    import_lookup = by_import_key or {}
    import_matches = list(import_lookup.get(_normalize_key(import_value), [])) if import_value else []

    if import_value:
        if len(import_matches) == 1:
            return MatchResult(record=import_matches[0], status="matched")
        if len(import_matches) > 1:
            return MatchResult(
                status="conflict",
                summary=f"matches multiple base records for import key '{import_value}'",
            )

    if not asset_key and not serial_key:
        return MatchResult(
            status="unmatched",
            summary="does not include an asset number, serial number, or import key",
        )

    asset_matches = list(by_asset.get(asset_key, [])) if asset_key else []
    serial_matches = list(by_serial.get(serial_key, [])) if serial_key else []

    if asset_key and serial_key:
        if asset_matches and serial_matches:
            shared = [
                candidate for candidate in asset_matches
                if any(candidate is other for other in serial_matches)
            ]
            if len(shared) == 1:
                return MatchResult(record=shared[0], status="matched")
            if len(shared) > 1:
                return MatchResult(
                    status="conflict",
                    summary=(
                        f"matches multiple base records for asset number '{asset_value}' "
                        f"and serial number '{serial_value}'"
                    ),
                )
            if len(asset_matches) == 1 and len(serial_matches) == 1:
                return MatchResult(
                    status="conflict",
                    summary=(
                        f"asset number '{asset_value}' and serial number "
                        f"'{serial_value}' point to different base records"
                    ),
                )
            return MatchResult(
                status="conflict",
                summary=(
                    f"asset number '{asset_value}' and serial number "
                    f"'{serial_value}' do not identify a single base record"
                ),
            )
        if asset_matches:
            return _resolve_single_key("asset number", asset_value, asset_matches)
        if serial_matches:
            return _resolve_single_key("serial number", serial_value, serial_matches)
        return MatchResult(
            status="unmatched",
            summary=(
                f"has no base inventory match for asset number '{asset_value}' "
                f"or serial number '{serial_value}'"
            ),
        )

    if asset_key:
        if asset_matches:
            return _resolve_single_key("asset number", asset_value, asset_matches)
        return MatchResult(
            status="unmatched",
            summary=f"has no base inventory match for asset number '{asset_value}'",
        )

    if serial_matches:
        return _resolve_single_key("serial number", serial_value, serial_matches)
    return MatchResult(
        status="unmatched",
        summary=f"has no base inventory match for serial number '{serial_value}'",
    )


def _normalize_key(value: str) -> str:
    """Normalize an identifier for case-insensitive matching."""
    return value.strip().upper()


def _resolve_single_key(
    label: str,
    value: str,
    matches: list[Equipment],
) -> MatchResult:
    """Resolve a match using a single identifier."""
    if len(matches) == 1:
        return MatchResult(record=matches[0], status="matched")
    return MatchResult(
        status="conflict",
        summary=f"matches multiple base records for {label} '{value}'",
    )
