"""Dialog for adding and editing equipment records."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from Code.db.database import get_distinct_equipment_values, insert_equipment, update_equipment
from Code.db.models import Equipment
from Code.gui.ui_components import CardWidget
from Code.importer.normalizer import normalize_manufacturer
from Code.utils.equipment_fields import format_age_years, parse_age_years


class AddEditDialog(QDialog):
    """Dialog for creating or updating a single equipment record."""

    def __init__(self, conn, equipment: Equipment = None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.equipment = equipment
        self.is_edit = equipment is not None

        self.setWindowTitle("Edit Equipment" if self.is_edit else "Add Equipment")
        self.setMinimumSize(920 if self.is_edit else 680, 580)

        self._setup_ui()
        if self.is_edit:
            self._populate_fields()

    # ── UI construction ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(16)

        # Content: form + optional sidebar
        content = QHBoxLayout()
        content.setSpacing(20)

        form = self._build_form()
        content.addLayout(form, 1)

        if self.is_edit:
            sidebar = self._build_context_sidebar()
            content.addWidget(sidebar)

        root.addLayout(content, 1)

        # Footer buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)

        save_btn = buttons.button(QDialogButtonBox.Save)
        if save_btn is not None:
            save_btn.setObjectName("primaryButton")
            save_btn.setText("Save Record")

        cancel_btn = buttons.button(QDialogButtonBox.Cancel)
        if cancel_btn is not None:
            cancel_btn.setObjectName("secondaryButton")

        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _build_form(self) -> QVBoxLayout:
        """Build the editable form as a 2x2 grid of sections."""
        outer = QVBoxLayout()
        outer.setSpacing(0)

        sections_grid = QGridLayout()
        sections_grid.setHorizontalSpacing(24)
        sections_grid.setVerticalSpacing(20)

        # ── Top-left: Identity ───────────────────────────────────────────────
        identity = self._build_identity_section()
        sections_grid.addWidget(identity, 0, 0)

        # ── Top-right: Location & Status ─────────────────────────────────────
        location = self._build_location_section()
        sections_grid.addWidget(location, 0, 1)

        # ── Bottom-left: Calibration ─────────────────────────────────────────
        calibration = self._build_calibration_section()
        sections_grid.addWidget(calibration, 1, 0)

        # ── Bottom-right: Condition & Notes ──────────────────────────────────
        notes = self._build_notes_section()
        sections_grid.addWidget(notes, 1, 1)

        outer.addLayout(sections_grid, 1)
        return outer

    def _build_identity_section(self) -> QWidget:
        """Identity fields: asset, serial, manufacturer, model, description."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(_section_label("Identity"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self.asset_input = QLineEdit()
        self.asset_input.setPlaceholderText("e.g. VPEQ0000014")
        _add_field(grid, 0, 0, "Asset Number", self.asset_input)

        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Serial or internal label")
        _add_field(grid, 0, 1, "Serial Number", self.serial_input)

        self.manufacturer_input = QLineEdit()
        self.manufacturer_input.setPlaceholderText("e.g. Fluke, Keysight")
        self._attach_completer(self.manufacturer_input, "manufacturer")
        _add_field(grid, 2, 0, "Manufacturer", self.manufacturer_input)

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Instrument model")
        self._attach_completer(self.model_input, "model")
        _add_field(grid, 2, 1, "Model", self.model_input)

        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Short description")
        _add_field(grid, 4, 0, "Description", self.description_input, colspan=2)

        layout.addLayout(grid)
        layout.addStretch()
        return container

    def _build_location_section(self) -> QWidget:
        """Location, assignment, and status fields."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(_section_label("Location & Status"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self.location_input = QLineEdit()
        self.location_input.setPlaceholderText("Lab, room, bench")
        self._attach_completer(self.location_input, "location")
        _add_field(grid, 0, 0, "Location", self.location_input)

        self.assigned_to_input = QLineEdit()
        self.assigned_to_input.setPlaceholderText("Technician or team")
        _add_field(grid, 0, 1, "Assigned To", self.assigned_to_input)

        self.lifecycle_combo = QComboBox()
        self.lifecycle_combo.addItems(["active", "repair", "scrapped", "missing", "rental"])
        _add_field(grid, 2, 0, "Lifecycle", self.lifecycle_combo)

        self.working_combo = QComboBox()
        self.working_combo.addItems(["unknown", "working", "limited", "not_working"])
        _add_field(grid, 2, 1, "Working Status", self.working_combo)

        self.ownership_combo = QComboBox()
        self.ownership_combo.addItems(["owned", "rental", "unknown"])
        _add_field(grid, 4, 0, "Ownership", self.ownership_combo)

        self.age_input = QLineEdit()
        self.age_input.setPlaceholderText("Age in years, e.g. 10")
        _add_field(grid, 4, 1, "Est. Age (Years)", self.age_input)

        layout.addLayout(grid)
        layout.addStretch()
        return container

    def _build_calibration_section(self) -> QWidget:
        """Calibration status, vendor, and dates."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(_section_label("Calibration"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self.cal_status_combo = QComboBox()
        self.cal_status_combo.addItems(["unknown", "calibrated", "reference_only", "out_to_cal"])
        _add_field(grid, 0, 0, "Cal Status", self.cal_status_combo)

        self.cal_vendor_input = QLineEdit()
        self.cal_vendor_input.setPlaceholderText("Vendor or internal lab")
        self._attach_completer(self.cal_vendor_input, "calibration_vendor")
        _add_field(grid, 0, 1, "Cal Vendor", self.cal_vendor_input)

        self.last_cal_input = QLineEdit()
        self.last_cal_input.setPlaceholderText("YYYY-MM-DD")
        _add_field(grid, 2, 0, "Last Calibration", self.last_cal_input)

        self.cal_due_input = QLineEdit()
        self.cal_due_input.setPlaceholderText("YYYY-MM-DD")
        _add_field(grid, 2, 1, "Calibration Due", self.cal_due_input)

        layout.addLayout(grid)
        layout.addStretch()
        return container

    def _build_notes_section(self) -> QWidget:
        """Condition and notes fields."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(_section_label("Condition & Notes"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        self.condition_input = QLineEdit()
        self.condition_input.setPlaceholderText("Visual condition or operating note")
        _add_field(grid, 0, 0, "Condition", self.condition_input, colspan=2)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Operational notes, repair history, or provenance.")
        self.notes_input.setMinimumHeight(80)
        _add_field(grid, 2, 0, "Notes", self.notes_input, colspan=2)

        layout.addLayout(grid)
        return container

    def _build_context_sidebar(self) -> QWidget:
        """Build the read-only context panel for edit mode."""
        card = CardWidget("summaryCard")
        card.setFixedWidth(260)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        header = QLabel("Record Context")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        self._context_layout = layout
        return card

    # ── Data population ──────────────────────────────────────────────────────

    def _populate_fields(self) -> None:
        """Fill form fields from an existing equipment record."""
        eq = self.equipment

        self.asset_input.setText(eq.asset_number)
        self.serial_input.setText(eq.serial_number)
        self.manufacturer_input.setText(eq.manufacturer)
        self.model_input.setText(eq.model)
        self.description_input.setText(eq.description)
        self.location_input.setText(eq.location)
        self.assigned_to_input.setText(eq.assigned_to)
        _set_combo(self.ownership_combo, eq.ownership_type)
        self.age_input.setText(format_age_years(eq.estimated_age_years))
        _set_combo(self.cal_status_combo, eq.calibration_status)
        self.last_cal_input.setText(eq.last_calibration_date)
        self.cal_due_input.setText(eq.calibration_due_date)
        self.cal_vendor_input.setText(eq.calibration_vendor)
        _set_combo(self.lifecycle_combo, eq.lifecycle_status)
        _set_combo(self.working_combo, eq.working_status)
        self.condition_input.setText(eq.condition)
        self.notes_input.setPlainText(eq.notes)

        self._populate_context_sidebar()

    def _populate_context_sidebar(self) -> None:
        """Fill the read-only sidebar with record metadata."""
        if not self.is_edit or self.equipment is None:
            return

        eq = self.equipment
        layout = self._context_layout

        # Record metadata
        _add_context_row(layout, "Record ID", str(eq.record_id or "-"))
        _add_context_row(layout, "Created", eq.created_at or "-")
        _add_context_row(layout, "Updated", eq.updated_at or "-")

        layout.addWidget(_separator())

        # Audit
        verified_text = "Verified" if eq.verified_in_survey else "Not verified"
        _add_context_row(layout, "Verified", verified_text)

        if eq.blue_dot_ref:
            _add_context_row(layout, "Blue Dot", eq.blue_dot_ref)

        if eq.acquired_date:
            _add_context_row(layout, "Acquired", eq.acquired_date)
        elif eq.estimated_age_years is not None:
            basis = eq.age_basis or "estimated"
            _add_context_row(layout, "Age", f"{format_age_years(eq.estimated_age_years)} yr ({basis})")

        _add_context_row(layout, "Manual Entry", "Yes" if eq.manual_entry else "No")

        # Source references
        refs = eq.parsed_source_refs()
        if refs:
            layout.addWidget(_separator())
            src_label = QLabel("Sources")
            src_label.setObjectName("sectionSubheader")
            layout.addWidget(src_label)

            for ref in refs:
                file_name = str(ref.get("file", "?"))
                if "Master" in file_name:
                    file_name = "Master List"
                elif "Survey" in file_name:
                    file_name = "Survey"
                sheet = ref.get("sheet", "?")
                row = ref.get("row", "?")
                src = QLabel(f"{file_name} \u2192 {sheet} \u2192 row {row}")
                src.setObjectName("sectionSubheader")
                src.setWordWrap(True)
                layout.addWidget(src)

        layout.addStretch()

    # ── Autocomplete ─────────────────────────────────────────────────────────

    def _attach_completer(self, line_edit: QLineEdit, field: str) -> None:
        """Attach an autocomplete completer to a line edit."""
        try:
            values = get_distinct_equipment_values(self.conn, field)
        except Exception:
            return

        if not values:
            return

        completer = QCompleter(values, line_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        line_edit.setCompleter(completer)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        """Validate and save the equipment record."""
        manufacturer_raw = self.manufacturer_input.text().strip()
        age_text = self.age_input.text().strip()

        if self.is_edit:
            eq = self.equipment
        else:
            eq = Equipment()
            eq.manual_entry = True

        original_age = eq.estimated_age_years

        eq.asset_number = self.asset_input.text().strip()
        eq.serial_number = self.serial_input.text().strip()
        eq.manufacturer = normalize_manufacturer(manufacturer_raw)
        eq.manufacturer_raw = manufacturer_raw
        eq.model = self.model_input.text().strip()
        eq.description = self.description_input.text().strip()
        eq.location = self.location_input.text().strip()
        eq.assigned_to = self.assigned_to_input.text().strip()
        eq.ownership_type = self.ownership_combo.currentText()

        age_value = parse_age_years(age_text)
        if age_text and age_value is None:
            QMessageBox.warning(
                self,
                "Invalid Age",
                "Enter age in years as a number, for example 10 or 10.5.",
            )
            return

        eq.estimated_age_years = age_value
        if age_value is None:
            eq.age_basis = "unknown"
        elif age_value != original_age:
            eq.age_basis = "estimated_manual"

        eq.calibration_status = self.cal_status_combo.currentText()
        eq.last_calibration_date = self.last_cal_input.text().strip()
        eq.calibration_due_date = self.cal_due_input.text().strip()
        eq.calibration_vendor = self.cal_vendor_input.text().strip()
        eq.lifecycle_status = self.lifecycle_combo.currentText()
        eq.working_status = self.working_combo.currentText()
        eq.condition = self.condition_input.text().strip()
        eq.notes = self.notes_input.toPlainText().strip()

        if not eq.asset_number and not eq.serial_number and not eq.model:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Provide at least an asset number, serial number, or model before saving.",
            )
            return

        try:
            if self.is_edit:
                update_equipment(self.conn, eq)
            else:
                insert_equipment(self.conn, eq)
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save the record:\n{exc}")


# ── Layout helpers ───────────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    """Create a section heading for the form."""
    label = QLabel(text)
    label.setObjectName("sectionHeader")
    return label


def _field_label(text: str) -> QLabel:
    """Create a small muted label above a form field."""
    label = QLabel(text)
    label.setObjectName("sectionSubheader")
    return label


def _separator() -> QFrame:
    """Create a thin horizontal line."""
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setObjectName("separatorLine")
    return line


def _add_field(grid: QGridLayout, row: int, col: int,
               label_text: str, widget: QWidget, colspan: int = 1) -> None:
    """Add a label + widget pair to a grid layout.

    The label goes in `row` and the widget in `row + 1`.
    Each field occupies one column by default, or `colspan` columns.
    """
    label = _field_label(label_text)
    grid.addWidget(label, row, col, 1, colspan)
    grid.addWidget(widget, row + 1, col, 1, colspan)


def _add_context_row(layout: QVBoxLayout, key: str, value: str) -> None:
    """Add a key-value row to the context sidebar."""
    row = QHBoxLayout()
    row.setSpacing(8)

    key_label = QLabel(key)
    key_label.setObjectName("sectionSubheader")
    key_label.setFixedWidth(85)
    row.addWidget(key_label)

    val_label = QLabel(value)
    val_label.setWordWrap(True)
    row.addWidget(val_label, 1)

    layout.addLayout(row)


def _set_combo(combo: QComboBox, value: str) -> None:
    """Set a combo box to the given value when present."""
    index = combo.findText(value)
    if index >= 0:
        combo.setCurrentIndex(index)
