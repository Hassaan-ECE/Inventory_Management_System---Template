"""Search/filter helpers extracted from the main window integration class."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

from Code.db.database import search_equipment


def schedule_search(window) -> None:
    """Debounce search/filter changes."""
    window._timer.start()


def update_search_placeholder(window) -> None:
    """Update the search prompt to match the current record scope."""
    if window._is_archive_view():
        text = "Search archived records — manufacturer, model, description, location, or notes"
    else:
        text = 'Search equipment — type anything: model, serial, manufacturer, location, "scrapped", "calibrated"...'
    if hasattr(window, "search_input"):
        window.search_input.setPlaceholderText(text)


def do_search(window) -> None:
    """Run the search query and populate the results table."""
    query = window.search_input.text().strip()
    filters = window._current_column_filter_values()
    results = search_equipment(
        window.conn,
        query,
        lifecycle=filters.get("lifecycle_status", ""),
        calibration=filters.get("calibration_status", ""),
        working=filters.get("working_status", ""),
        location=filters.get("location", ""),
        asset_number=filters.get("asset_number", ""),
        manufacturer=filters.get("manufacturer", ""),
        model=filters.get("model", ""),
        description=filters.get("description", ""),
        estimated_age_years=filters.get("estimated_age_years", ""),
        archived=window._record_scope,
    )
    window.table.set_theme_name(window._theme_name)
    window.table.set_color_rows_enabled(window.color_rows_checkbox.isChecked())
    window.table.populate(results)
    window._refresh_view_tabs()

    count = len(results)
    has_filters = window._has_active_column_filters()
    record_label = "archived records" if window._is_archive_view() else "equipment records"
    if not query:
        if window._is_archive_view() and count == 0 and not has_filters:
            window.results_label.setText("No archived records yet")
        elif has_filters:
            window.results_label.setText(f"Showing {count} filtered {record_label}")
        else:
            window.results_label.setText(f"Showing all {count} {record_label}")
        window.not_found_widget.hide()
    elif count > 0:
        suffix = " after column filters" if has_filters else ""
        if window._is_archive_view():
            window.results_label.setText(
                f'{count} archived result{"s" if count != 1 else ""} for "{query}"{suffix}'
            )
        else:
            window.results_label.setText(f'{count} result{"s" if count != 1 else ""} for "{query}"{suffix}')
        window.not_found_widget.hide()
    else:
        if window._is_archive_view():
            window.results_label.setText(f'No archived results for "{query}"')
            window.not_found_widget.hide()
        else:
            window.results_label.setText(f'No results for "{query}"')
            window.not_found_widget.show()


def current_column_filter_values(window) -> dict[str, str]:
    """Return current per-column filter values in a DB-friendly shape."""
    values: dict[str, str] = {}
    for field, widget in window.column_filters.items():
        if isinstance(widget, QComboBox):
            value = widget.currentText().strip()
            values[field] = "" if value.startswith("All ") else value
        else:
            values[field] = widget.text().strip()
    return values


def has_active_column_filters(window) -> bool:
    """Return whether any column filter currently has a value."""
    return any(window._current_column_filter_values().values())


def clear_column_filters(window) -> None:
    """Reset all per-column filter widgets."""
    for widget in window.column_filters.values():
        if isinstance(widget, QComboBox):
            widget.setCurrentIndex(0)
        else:
            widget.clear()
    window._do_search()


__all__ = [
    "clear_column_filters",
    "current_column_filter_values",
    "do_search",
    "has_active_column_filters",
    "schedule_search",
    "update_search_placeholder",
]
