"""Shared application theme utilities for the TE Lab Equipment Inventory Manager."""

from pathlib import Path
from string import Template


DEFAULT_THEME_NAME = "light"

_CHEVRON_DOWN_PATH = (Path(__file__).resolve().parent / "assets" / "chevron_down_gray.svg").as_posix()

_THEME_TEMPLATE = Template(
    """
QApplication {
    font-family: "Inter", "Segoe UI", sans-serif;
    font-size: 13px;
    color: ${app_text};
}

QMainWindow, QDialog {
    background: ${window_background};
}

QWidget#heroCard,
QWidget#panelCard,
QWidget#toolbarCard,
QWidget#summaryCard,
QWidget#heroMetricCard {
    background: ${panel_background};
    border: 1px solid ${panel_border};
    border-radius: 16px;
}

QWidget#heroCard {
    background: ${hero_background};
    border: none;
}

QWidget#toolbarCard {
    padding: 6px;
}

QWidget#summaryCard {
    background: ${summary_background};
}

QWidget#heroMetricCard {
    background: ${metric_background};
    border: 1px solid ${metric_border};
    border-radius: 10px;
}

QLabel {
    color: ${label_text};
    font-size: 13px;
}

QLabel#pageTitle {
    color: ${page_title_text};
    font-size: 28px;
    font-weight: 700;
}

QLabel#pageSubtitle {
    color: ${page_subtitle_text};
    font-size: 13px;
}

QLabel#heroEyebrow {
    color: ${hero_eyebrow_text};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

QLabel#sectionHeader {
    color: ${section_header_text};
    font-size: 18px;
    font-weight: 650;
}

QLabel#sectionSubheader {
    color: ${section_subheader_text};
    font-size: 12px;
}

QLabel#statsLabel,
QLabel#mutedLabel {
    color: ${stats_label_text};
    font-size: 12px;
}

QLabel#statValue {
    color: ${stat_value_text};
    font-size: 24px;
    font-weight: 700;
    font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
}

QLabel#statCaption {
    color: ${stat_caption_text};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

QLabel#heroStatValue {
    color: ${hero_stat_value_text};
    font-size: 22px;
    font-weight: 700;
    font-family: "JetBrains Mono", "Cascadia Mono", "Consolas", monospace;
}

QLabel#heroStatCaption {
    color: ${hero_stat_caption_text};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

QLabel#detailTitle {
    color: ${detail_title_text};
    font-size: 16px;
    font-weight: 650;
}

QLabel#detailMeta,
QLabel#tableHint {
    color: ${detail_meta_text};
    font-size: 12px;
}

QLabel#emptyState {
    color: ${empty_state_text};
    font-size: 13px;
    padding: 12px 4px;
}

QTabWidget::pane {
    border: none;
    background: transparent;
    top: -1px;
}

QTabBar::tab {
    background: ${tab_background};
    color: ${tab_text};
    padding: 12px 20px;
    margin-right: 8px;
    border: 1px solid ${tab_border};
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background: ${tab_selected_background};
    color: ${tab_selected_text};
    border: 1px solid ${tab_selected_border};
}

QTabBar::tab:hover:!selected {
    background: ${tab_hover_background};
}

QLineEdit,
QComboBox,
QTextEdit,
QPlainTextEdit,
QDateEdit {
    background: ${input_background};
    color: ${input_text};
    border: 1px solid ${input_border};
    border-radius: 10px;
    padding: 9px 12px;
    selection-background-color: ${input_selection_background};
}

QTextEdit,
QPlainTextEdit {
    padding: 10px 12px;
}

QLineEdit:focus,
QComboBox:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QDateEdit:focus {
    border: 1px solid ${focus_border};
}

QComboBox {
    min-width: 120px;
    padding-right: 24px;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 30px;
    background: ${combo_dropdown_background};
    border-left: 1px solid ${combo_dropdown_border};
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
}

QComboBox::drop-down:hover {
    background: ${combo_dropdown_hover_background};
}

QComboBox#quickEditCombo {
    background: ${quickedit_background};
    border: 1px solid ${quickedit_border};
    padding-right: 30px;
    font-weight: 600;
}

QComboBox#quickEditCombo::drop-down {
    width: 34px;
    background: ${quickedit_dropdown_background};
    border-left: 1px solid ${quickedit_dropdown_border};
}

QComboBox#quickEditCombo::drop-down:hover {
    background: ${quickedit_dropdown_hover_background};
}

QComboBox::down-arrow,
QComboBox#quickEditCombo::down-arrow {
    image: url("${chevron_down_path}");
    width: 12px;
    height: 8px;
}

QComboBox QAbstractItemView {
    background: ${item_view_background};
    color: ${item_view_text};
    border: 1px solid ${item_view_border};
    selection-background-color: ${item_view_selection_background};
    selection-color: ${item_view_selection_text};
}

QPushButton {
    background: ${button_background};
    color: ${button_text};
    border: 1px solid ${button_border};
    border-radius: 10px;
    padding: 9px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton:hover {
    background: ${button_hover_background};
    border-color: ${button_hover_border};
}

QPushButton:pressed {
    background: ${button_pressed_background};
}

QPushButton:disabled {
    color: ${button_disabled_text};
    background: ${button_disabled_background};
    border-color: ${button_disabled_border};
}

QPushButton#primaryButton {
    background: ${primary_button_background};
    color: ${primary_button_text};
    border: 1px solid ${primary_button_border};
}

QPushButton#primaryButton:hover {
    background: ${primary_button_hover_background};
    border-color: ${primary_button_hover_border};
}

QPushButton#secondaryButton {
    background: ${secondary_button_background};
    color: ${secondary_button_text};
    border: 1px solid ${secondary_button_border};
}

QPushButton#secondaryButton:hover {
    background: ${secondary_button_hover_background};
}

QPushButton#dangerButton {
    background: ${danger_button_background};
    color: ${danger_button_text};
    border: 1px solid ${danger_button_border};
}

QPushButton#dangerButton:hover {
    background: ${danger_button_hover_background};
    border-color: ${danger_button_hover_background};
}

QCheckBox {
    color: ${checkbox_text};
    spacing: 8px;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid ${checkbox_indicator_border};
    background: ${checkbox_indicator_background};
}

QCheckBox::indicator:checked {
    background: ${checkbox_checked_background};
    border-color: ${checkbox_checked_border};
}

QCheckBox::indicator:hover {
    border-color: ${checkbox_hover_border};
}

QTableWidget,
QTableView {
    background: ${table_background};
    color: ${table_text};
    alternate-background-color: ${table_alt_background};
    border: 1px solid ${table_border};
    border-radius: 14px;
    gridline-color: ${table_gridline};
    selection-background-color: ${table_selection_background};
    selection-color: ${table_selection_text};
}

QTableWidget::item,
QTableView::item {
    color: ${table_text};
    padding: 7px 8px;
}

QTableWidget::item:selected,
QTableView::item:selected {
    color: ${table_selection_text};
    background: ${table_selection_background};
}

QHeaderView::section {
    background: ${header_background};
    color: ${header_text};
    border: none;
    border-bottom: 1px solid ${header_border};
    padding: 10px 8px;
    font-size: 12px;
    font-weight: 700;
}

QTableCornerButton::section {
    background: ${corner_background};
    border: none;
    border-bottom: 1px solid ${corner_border};
    border-right: 1px solid ${corner_border};
}

QGroupBox {
    background: ${group_background};
    border: 1px solid ${group_border};
    border-radius: 14px;
    margin-top: 16px;
    padding: 18px 14px 14px 14px;
    font-size: 13px;
    font-weight: 700;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: ${group_title_text};
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 12px;
    margin: 4px 0 4px 0;
}

QScrollBar::handle:vertical {
    background: ${scroll_handle_background};
    border-radius: 6px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: ${scroll_handle_hover_background};
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    height: 0;
    background: transparent;
}

QSplitter::handle {
    background: transparent;
    width: 12px;
    height: 12px;
}

QStatusBar {
    background: ${status_background};
    color: ${status_text};
    border-top: 1px solid ${status_border};
    font-size: 12px;
}

QDialogButtonBox QPushButton {
    min-width: 110px;
}

QFrame#separatorLine {
    background: ${separator_color};
    color: ${separator_color};
    border: none;
}

QToolTip {
    background: ${tooltip_background};
    color: ${tooltip_text};
    border: 1px solid ${tooltip_border};
    padding: 6px 8px;
}
"""
)

_DARK_PALETTE = {
    "app_text": "#e6e8ee",
    "window_background": "#111317",
    "panel_background": "#1a1c22",
    "panel_border": "#2c313a",
    "hero_background": "#1a1c22",
    "summary_background": "#171a20",
    "metric_background": "#262830",
    "metric_border": "#35383f",
    "label_text": "#e7e9ef",
    "page_title_text": "#ffffff",
    "page_subtitle_text": "#8a8f9e",
    "hero_eyebrow_text": "#93b4f5",
    "section_header_text": "#f3f4f6",
    "section_subheader_text": "#8a8f9e",
    "stats_label_text": "#8a8f9e",
    "stat_value_text": "#f4f5f8",
    "stat_caption_text": "#8a8f9e",
    "hero_stat_value_text": "#6ba3f7",
    "hero_stat_caption_text": "#6b7080",
    "detail_title_text": "#f3f4f6",
    "detail_meta_text": "#8a8f9e",
    "empty_state_text": "#8a8f9e",
    "tab_background": "#171a20",
    "tab_text": "#8a8f9e",
    "tab_border": "#2d3138",
    "tab_selected_background": "#252838",
    "tab_selected_text": "#f3f4f6",
    "tab_selected_border": "#3a4052",
    "tab_hover_background": "#1d2128",
    "input_background": "#14181d",
    "input_text": "#ececec",
    "input_border": "#313640",
    "input_selection_background": "#33415c",
    "focus_border": "#2563eb",
    "combo_dropdown_background": "#20242c",
    "combo_dropdown_border": "#485264",
    "combo_dropdown_hover_background": "#272d36",
    "quickedit_background": "#171b21",
    "quickedit_border": "#4b5563",
    "quickedit_dropdown_background": "#262c35",
    "quickedit_dropdown_border": "#5c6676",
    "quickedit_dropdown_hover_background": "#303844",
    "item_view_background": "#171a20",
    "item_view_text": "#ececec",
    "item_view_border": "#313640",
    "item_view_selection_background": "#252f47",
    "item_view_selection_text": "#ffffff",
    "button_background": "#1a1d24",
    "button_text": "#ececec",
    "button_border": "#313640",
    "button_hover_background": "#20242c",
    "button_hover_border": "#485264",
    "button_pressed_background": "#15181d",
    "button_disabled_text": "#747b84",
    "button_disabled_background": "#14181c",
    "button_disabled_border": "#262b31",
    "primary_button_background": "#2563eb",
    "primary_button_text": "#ffffff",
    "primary_button_border": "#2563eb",
    "primary_button_hover_background": "#1d4ed8",
    "primary_button_hover_border": "#1d4ed8",
    "secondary_button_background": "#1b2027",
    "secondary_button_text": "#e6e6e6",
    "secondary_button_border": "#313640",
    "secondary_button_hover_background": "#222730",
    "danger_button_background": "#bf3f3f",
    "danger_button_text": "#ffffff",
    "danger_button_border": "#bf3f3f",
    "danger_button_hover_background": "#a73434",
    "checkbox_text": "#e6e8ee",
    "checkbox_indicator_border": "#485264",
    "checkbox_indicator_background": "#14181d",
    "checkbox_checked_background": "#2563eb",
    "checkbox_checked_border": "#2563eb",
    "checkbox_hover_border": "#6b7a90",
    "table_background": "#15181d",
    "table_text": "#ececec",
    "table_alt_background": "#1a1d23",
    "table_border": "#2d3138",
    "table_gridline": "#232831",
    "table_selection_background": "#252f47",
    "table_selection_text": "#ffffff",
    "header_background": "#1a1c22",
    "header_text": "#8a8f9e",
    "header_border": "#2d3138",
    "corner_background": "#1a1c22",
    "corner_border": "#2d3138",
    "group_background": "#171a20",
    "group_border": "#2d3138",
    "group_title_text": "#ececec",
    "scroll_handle_background": "#3a414c",
    "scroll_handle_hover_background": "#566172",
    "status_background": "#14171c",
    "status_text": "#8a8f9e",
    "status_border": "#2d3138",
    "tooltip_background": "#252838",
    "tooltip_text": "#ffffff",
    "tooltip_border": "#3a4052",
    "separator_color": "#2d3138",
}

_LIGHT_PALETTE = {
    "app_text": "#243447",
    "window_background": "#f4f7fb",
    "panel_background": "#ffffff",
    "panel_border": "#d5dde8",
    "hero_background": "#ffffff",
    "summary_background": "#f9fbfd",
    "metric_background": "#f3f7fc",
    "metric_border": "#dbe3ee",
    "label_text": "#243447",
    "page_title_text": "#0f172a",
    "page_subtitle_text": "#5f6c7b",
    "hero_eyebrow_text": "#245ea8",
    "section_header_text": "#122235",
    "section_subheader_text": "#5f6c7b",
    "stats_label_text": "#5f6c7b",
    "stat_value_text": "#0f172a",
    "stat_caption_text": "#66768a",
    "hero_stat_value_text": "#1d4ed8",
    "hero_stat_caption_text": "#748092",
    "detail_title_text": "#122235",
    "detail_meta_text": "#5f6c7b",
    "empty_state_text": "#66768a",
    "tab_background": "#eef3f8",
    "tab_text": "#5f6c7b",
    "tab_border": "#d5dde8",
    "tab_selected_background": "#ffffff",
    "tab_selected_text": "#0f172a",
    "tab_selected_border": "#bfd1e4",
    "tab_hover_background": "#e7edf5",
    "input_background": "#ffffff",
    "input_text": "#122235",
    "input_border": "#c7d2df",
    "input_selection_background": "#dbeafe",
    "focus_border": "#2563eb",
    "combo_dropdown_background": "#eef3f8",
    "combo_dropdown_border": "#c7d2df",
    "combo_dropdown_hover_background": "#e5ecf5",
    "quickedit_background": "#f8fbff",
    "quickedit_border": "#9fb3ca",
    "quickedit_dropdown_background": "#edf3fb",
    "quickedit_dropdown_border": "#b6c6d9",
    "quickedit_dropdown_hover_background": "#e2ebf7",
    "item_view_background": "#ffffff",
    "item_view_text": "#122235",
    "item_view_border": "#c7d2df",
    "item_view_selection_background": "#dbeafe",
    "item_view_selection_text": "#0f172a",
    "button_background": "#f3f6fa",
    "button_text": "#17324d",
    "button_border": "#c7d2df",
    "button_hover_background": "#e8edf5",
    "button_hover_border": "#b7c4d4",
    "button_pressed_background": "#dfe7f1",
    "button_disabled_text": "#93a0b0",
    "button_disabled_background": "#edf2f7",
    "button_disabled_border": "#d7e0ea",
    "primary_button_background": "#2563eb",
    "primary_button_text": "#ffffff",
    "primary_button_border": "#2563eb",
    "primary_button_hover_background": "#1d4ed8",
    "primary_button_hover_border": "#1d4ed8",
    "secondary_button_background": "#f3f6fa",
    "secondary_button_text": "#17324d",
    "secondary_button_border": "#c7d2df",
    "secondary_button_hover_background": "#e8edf5",
    "danger_button_background": "#dc2626",
    "danger_button_text": "#ffffff",
    "danger_button_border": "#dc2626",
    "danger_button_hover_background": "#b91c1c",
    "checkbox_text": "#243447",
    "checkbox_indicator_border": "#94a3b8",
    "checkbox_indicator_background": "#ffffff",
    "checkbox_checked_background": "#2563eb",
    "checkbox_checked_border": "#2563eb",
    "checkbox_hover_border": "#64748b",
    "table_background": "#ffffff",
    "table_text": "#122235",
    "table_alt_background": "#f8fafc",
    "table_border": "#d5dde8",
    "table_gridline": "#e5ebf2",
    "table_selection_background": "#dbeafe",
    "table_selection_text": "#0f172a",
    "header_background": "#f3f6fb",
    "header_text": "#556374",
    "header_border": "#dbe3ee",
    "corner_background": "#f3f6fb",
    "corner_border": "#dbe3ee",
    "group_background": "#f8fafc",
    "group_border": "#d5dde8",
    "group_title_text": "#122235",
    "scroll_handle_background": "#c3ccd9",
    "scroll_handle_hover_background": "#aeb8c7",
    "status_background": "#edf3f8",
    "status_text": "#58697d",
    "status_border": "#d5dde8",
    "tooltip_background": "#16324b",
    "tooltip_text": "#ffffff",
    "tooltip_border": "#16324b",
    "separator_color": "#dbe3ee",
}

_SEMANTIC_COLORS = {
    "dark": {
        "verified": {"checked": "#4ade80", "unchecked": "#555a66"},
        "lifecycle": {
            "active": "#4ade80",
            "repair": "#f59e0b",
            "scrapped": "#ef4444",
            "missing": "#fb7185",
            "rental": "#c5ccd6",
            "default": "#d5d9df",
        },
        "working": {
            "working": "#4ade80",
            "limited": "#f59e0b",
            "not_working": "#ef4444",
            "unknown": "#94a3b8",
            "default": "#d5d9df",
        },
        "calibration": {
            "calibrated": "#4ade80",
            "reference_only": "#c5ccd6",
            "out_to_cal": "#f59e0b",
            "unknown": "#94a3b8",
            "default": "#d5d9df",
        },
        "row_background": {
            "active": "#16241b",
            "repair": "#2b2114",
            "scrapped": "#2b1719",
            "missing": "#2a1620",
            "rental": "#1d232b",
            "default": "#15181d",
        },
    },
    "light": {
        "verified": {"checked": "#16a34a", "unchecked": "#64748b"},
        "lifecycle": {
            "active": "#15803d",
            "repair": "#b45309",
            "scrapped": "#b91c1c",
            "missing": "#be123c",
            "rental": "#475569",
            "default": "#334155",
        },
        "working": {
            "working": "#15803d",
            "limited": "#b45309",
            "not_working": "#b91c1c",
            "unknown": "#64748b",
            "default": "#334155",
        },
        "calibration": {
            "calibrated": "#15803d",
            "reference_only": "#475569",
            "out_to_cal": "#b45309",
            "unknown": "#64748b",
            "default": "#334155",
        },
        "row_background": {
            "active": "#ecfdf3",
            "repair": "#fff7e6",
            "scrapped": "#feeeee",
            "missing": "#fdeef4",
            "rental": "#eff6ff",
            "default": "#ffffff",
        },
    },
}


def _build_stylesheet(palette: dict[str, str]) -> str:
    return _THEME_TEMPLATE.substitute({**palette, "chevron_down_path": _CHEVRON_DOWN_PATH})


LIGHT_THEME = _build_stylesheet(_LIGHT_PALETTE)
DARK_THEME = _build_stylesheet(_DARK_PALETTE)

_THEME_STYLESHEETS = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
}


def normalize_theme_name(theme_name: str | None) -> str:
    if theme_name in _THEME_STYLESHEETS:
        return theme_name
    return DEFAULT_THEME_NAME


def get_stylesheet(theme_name: str | None) -> str:
    return _THEME_STYLESHEETS[normalize_theme_name(theme_name)]


def verified_color(theme_name: str | None, is_verified: bool) -> str:
    key = "checked" if is_verified else "unchecked"
    theme = _SEMANTIC_COLORS[normalize_theme_name(theme_name)]
    return theme["verified"][key]


def lifecycle_color(theme_name: str | None, value: str) -> str:
    theme = _SEMANTIC_COLORS[normalize_theme_name(theme_name)]["lifecycle"]
    return theme.get(value, theme["default"])


def working_color(theme_name: str | None, value: str) -> str:
    theme = _SEMANTIC_COLORS[normalize_theme_name(theme_name)]["working"]
    return theme.get(value, theme["default"])


def calibration_color(theme_name: str | None, value: str) -> str:
    theme = _SEMANTIC_COLORS[normalize_theme_name(theme_name)]["calibration"]
    return theme.get(value, theme["default"])


def row_background_color(theme_name: str | None, value: str) -> str:
    theme = _SEMANTIC_COLORS[normalize_theme_name(theme_name)]["row_background"]
    return theme.get(value, theme["default"])
