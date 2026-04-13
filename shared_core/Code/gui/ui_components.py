"""Reusable UI building blocks for the TE Lab Equipment Inventory Manager."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CardWidget(QWidget):
    """Styled container widget that opts into stylesheet backgrounds."""

    def __init__(self, object_name: str = "panelCard", parent=None):
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WA_StyledBackground, True)


class SectionHeading(QWidget):
    """Compact title and subtitle block used at the top of sections."""

    def __init__(self, title: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("sectionHeader")
        layout.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("sectionSubheader")
            subtitle_label.setWordWrap(True)
            layout.addWidget(subtitle_label)


class MetricCard(CardWidget):
    """Simple metric display with value and caption."""

    def __init__(
        self,
        caption: str,
        value: str = "--",
        object_name: str = "summaryCard",
        value_object_name: str = "statValue",
        caption_object_name: str = "statCaption",
        parent=None,
    ):
        super().__init__(object_name=object_name, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self.value_label = QLabel(value)
        self.value_label.setObjectName(value_object_name)
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.value_label)

        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName(caption_object_name)
        self.caption_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)

    def set_caption(self, caption: str) -> None:
        self.caption_label.setText(caption)


class EmptyStateLabel(QLabel):
    """Consistent muted message for empty or unselected panels."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("emptyState")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)
