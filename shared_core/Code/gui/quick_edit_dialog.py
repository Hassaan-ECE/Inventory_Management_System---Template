"""Field-aware quick edit dialog for single-cell equipment updates."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter, QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout


class QuickEditDialog(QDialog):
    """Small field-aware dialog used for quick edits from the results table."""

    def __init__(
        self,
        label: str,
        current_value: str = "",
        options: list[str] | None = None,
        suggestions: list[str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Quick Edit: {label}")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel(label)
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        if options:
            helper = QLabel("Choose a value from the dropdown.")
            helper.setObjectName("sectionSubheader")
            layout.addWidget(helper)

            self.editor = QComboBox()
            self.editor.setObjectName("quickEditCombo")
            self.editor.addItems(options)
            current_index = options.index(current_value) if current_value in options else 0
            self.editor.setCurrentIndex(current_index)
            self.editor.setToolTip("Dropdown field")
            layout.addWidget(self.editor)
        elif suggestions:
            helper = QLabel("Type to search existing values or use the dropdown.")
            helper.setObjectName("sectionSubheader")
            layout.addWidget(helper)

            self.editor = QComboBox()
            self.editor.setObjectName("quickEditCombo")
            self.editor.setEditable(True)
            self.editor.addItem("")
            for suggestion in suggestions:
                if suggestion and suggestion != current_value:
                    self.editor.addItem(suggestion)
            self.editor.setCurrentText(current_value)
            self.editor.setToolTip("Autocomplete field with suggestions")

            completer = QCompleter([self.editor.itemText(i) for i in range(self.editor.count())], self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            self.editor.setCompleter(completer)
            if self.editor.lineEdit() is not None:
                self.editor.lineEdit().setPlaceholderText("Type here or open the dropdown")
            layout.addWidget(self.editor)
        else:
            helper = QLabel("Update the field value below.")
            helper.setObjectName("sectionSubheader")
            layout.addWidget(helper)

            self.editor = QLineEdit()
            self.editor.setText(current_value)
            layout.addWidget(self.editor)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        save_button = buttons.button(QDialogButtonBox.Save)
        if save_button is not None:
            save_button.setObjectName("primaryButton")
            save_button.setText("Apply Change")

        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if cancel_button is not None:
            cancel_button.setObjectName("secondaryButton")

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self) -> str:
        """Return the current editor value."""
        if isinstance(self.editor, QComboBox):
            return self.editor.currentText()
        return self.editor.text()
