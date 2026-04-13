"""Data normalization utilities — manufacturer names, dates, placeholders, statuses."""

import re
from datetime import date, datetime

# ── Manufacturer normalization ──────────────────────────────────────────────
# Maps messy raw names → clean canonical display names.
# We preserve the brand printed on the physical device rather than
# normalizing to corporate successors (e.g. Agilent stays Agilent,
# not Keysight), but we DO clean up typos and spacing.

MANUFACTURER_MAP: dict[str, str] = {
    # HP / Hewlett-Packard — keep as "HP" since that's what's on the equipment
    "hewlett-packard": "HP",
    "hewlett packard": "HP",
    "hp":             "HP",

    # Agilent — keep as "Agilent" (physical branding)
    "agilent":  "Agilent",
    "agilent ": "Agilent",
    "aglient":  "Agilent",  # typo in survey

    # Keysight — newer equipment, keep as Keysight
    "keysight": "Keysight",

    # LeCroy / Teledyne LeCroy
    "lecroy":          "LeCroy",
    "lecroy ":         "LeCroy",
    "teledyne lecroy": "LeCroy",

    # Tektronix
    "tektronix":  "Tektronix",
    "tektronix ": "Tektronix",

    # Fluke
    "fluke":  "Fluke",
    "fluke ": "Fluke",

    # Yokogawa
    "yokogawa":                    "Yokogawa",
    "yew":                         "Yokogawa",
    "yew (yokogawa elec works":    "Yokogawa",
    "yew (yokogawa elec works)":   "Yokogawa",

    # Fischer
    "fischer custom comm.":           "Fischer Custom Communications",
    "fischer custom comm":            "Fischer Custom Communications",
    "fischer custom communications":  "Fischer Custom Communications",

    # AEMC
    "aemc instr":       "AEMC Instruments",
    "aemc instruments": "AEMC Instruments",

    # Extech
    "extech instruments": "Extech",
    "extech":             "Extech",

    # Associated Research
    "assoc research inc":  "Associated Research",
    "associated research": "Associated Research",

    # GW Instek
    "gw":       "GW Instek",
    "gw instek": "GW Instek",

    # Voltech
    "voltech":  "Voltech",
    "voltech ": "Voltech",

    # Simpson
    "simpson": "Simpson",

    # Keithley
    "keithley": "Keithley",

    # Velleman
    "velleman": "Velleman",

    # Ergonomics
    "ergonomics inc.": "Ergonomics Inc.",
    "ergonomics inc":  "Ergonomics Inc.",

    # TDI
    "tdi": "TDI",

    # JBC
    "jbc": "JBC",
}


def normalize_manufacturer(raw: str) -> str:
    """Normalize a manufacturer name. Returns cleaned version or original if no mapping."""
    if not raw or not raw.strip():
        return ""
    key = raw.strip().lower()
    return MANUFACTURER_MAP.get(key, raw.strip())


# ── Placeholder detection ───────────────────────────────────────────────────

PLACEHOLDER_VALUES = {
    "na", "n/a", "nsn", "msn", "none", "unknown", "need asset no",
    "need asset no.", "tbd", "tba", "", "-", "--", "---",
}


def is_placeholder(value: str) -> bool:
    """Check if a value is a known placeholder / non-value."""
    if not value:
        return True
    return value.strip().lower() in PLACEHOLDER_VALUES


def clean_value(value) -> str:
    """Convert any cell value to a clean string. Strips whitespace, handles floats."""
    if value is None:
        return ""
    s = str(value).strip()
    # xlrd reads some numbers as floats — e.g. serial "77150443.0"
    # Strip trailing .0 for values that look like integers
    if s.endswith(".0"):
        try:
            float(s)
            s = s[:-2]
        except ValueError:
            pass
    return s


# ── Date parsing ────────────────────────────────────────────────────────────
# Dates in the master list appear as text in M.D.YY or M.DD.YY or MM.DD.YY format.
# Some are Excel date serial numbers (floats).

def parse_date(value) -> str:
    """Parse a date value from Excel into YYYY-MM-DD format.

    Returns empty string if unparseable or placeholder.
    """
    if value is None:
        return ""

    # Handle Excel serial date numbers (float)
    if isinstance(value, (int, float)):
        try:
            # xlrd stores dates as floats — days since 1899-12-30
            if 30000 < value < 60000:
                from xlrd import xldate_as_datetime
                dt = xldate_as_datetime(value, 0)
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        # Small numbers aren't dates
        return ""

    s = str(value).strip()
    if is_placeholder(s) or s.lower() in ("ref only", "reference only"):
        return ""

    # Try M.D.YY or M.DD.YY or MM.DD.YY
    m = re.match(r'^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$', s)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year = 2000 + year if year <= 40 else 1900 + year
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                d = date(year, month, day)
                return d.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Try standard formats
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%m-%d-%y"):
        try:
            d = datetime.strptime(s, fmt).date()
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return ""


# ── Working status inference ────────────────────────────────────────────────

def infer_working_status(condition: str) -> str:
    """Infer a simplified working status from free-text condition field.

    Returns: 'working', 'limited', 'not_working', or 'unknown'.
    """
    if not condition:
        return "unknown"
    c = condition.strip().lower()

    if c in ("fully functional", "functional", "working", "good", "ok"):
        return "working"

    if any(kw in c for kw in ("limited", "intermittent", "marginal")):
        return "limited"

    if any(kw in c for kw in (
        "suspect bad", "bad", "non-function", "not working", "non working",
        "broken", "failed", "removed from service", "oot", "out of tolerance",
        "defective", "dead", "inoperable",
    )):
        return "not_working"

    # If condition has text but we can't classify it, assume working
    # (most items with a condition note are still functional)
    if c:
        return "working"

    return "unknown"


# ── Calibration status helpers ──────────────────────────────────────────────

LIFECYCLE_PRECEDENCE = {
    "scrapped": 1,
    "missing": 2,
    "repair": 3,
    "rental": 4,
    "active": 5,
}

CALIBRATION_PRECEDENCE = {
    "out_to_cal": 1,
    "calibrated": 2,
    "reference_only": 3,
    "unknown": 4,
}


def higher_lifecycle(current: str, new: str) -> str:
    """Return whichever lifecycle status has higher precedence (lower number wins)."""
    cur_p = LIFECYCLE_PRECEDENCE.get(current, 99)
    new_p = LIFECYCLE_PRECEDENCE.get(new, 99)
    return new if new_p < cur_p else current


def higher_calibration(current: str, new: str) -> str:
    """Return whichever calibration status has higher precedence."""
    cur_p = CALIBRATION_PRECEDENCE.get(current, 99)
    new_p = CALIBRATION_PRECEDENCE.get(new, 99)
    return new if new_p < cur_p else current


# ── Cell address helper ─────────────────────────────────────────────────────

def col_to_letter(col: int) -> str:
    """Convert 0-based column index to Excel column letter(s)."""
    result = ""
    col += 1  # 1-based
    while col > 0:
        col, remainder = divmod(col - 1, 26)
        result = chr(65 + remainder) + result
    return result
