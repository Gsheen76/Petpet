"""Reusable warm controls shared by Petpet settings surfaces."""

from PyQt5.QtCore import QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class ToggleSwitch(QAbstractButton):
    """Compact iOS-style on/off control used for boolean settings."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(60, 32)
        self.setFocusPolicy(Qt.StrongFocus)
        self.toggled.connect(lambda _checked: self.update())

    def sizeHint(self):
        return QSize(60, 32)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 2, self.width() - 2, self.height() - 4)
        track_color = (
            QColor("#f08e72") if self.isChecked() else QColor("#d8c8bd")
        )
        if not self.isEnabled():
            track_color.setAlpha(120)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(track, 14, 14)
        knob_size = 24
        knob_x = self.width() - knob_size - 4 if self.isChecked() else 4
        painter.setBrush(QColor("#fffdf9"))
        painter.drawEllipse(QRectF(knob_x, 4, knob_size, knob_size))
        painter.end()


class StepperControl(QWidget):
    """Spin box with large, friendly minus/plus buttons."""

    def __init__(self, minimum, maximum, step, value, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self.minus = QPushButton("−")
        self.plus = QPushButton("+")
        for button in (self.minus, self.plus):
            button.setObjectName("stepButton")
            button.setFixedSize(38, 38)
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(350)
            button.setAutoRepeatInterval(90)

        if isinstance(step, float):
            self.spin = QDoubleSpinBox()
            self.spin.setDecimals(2 if step < 0.1 else 1)
        else:
            self.spin = QSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setAlignment(Qt.AlignCenter)
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.spin.setFixedSize(104, 38)
        self.minus.clicked.connect(self.spin.stepDown)
        self.plus.clicked.connect(self.spin.stepUp)
        layout.addWidget(self.minus)
        layout.addWidget(self.spin)
        layout.addWidget(self.plus)

    def value(self):
        return self.spin.value()

    def setValue(self, value):
        self.spin.setValue(value)

    def setToolTip(self, text):
        super().setToolTip(text)
        self.minus.setToolTip(text)
        self.spin.setToolTip(text)
        self.plus.setToolTip(text)


class ThreeLevelSlider(QWidget):
    """A friendly pill-tab selector constrained to exactly three options.

    Styled after rounded tab pills: the row sits inside a pill-shaped
    container and the selected option fills as a pill; there is no
    separate slider track.
    """

    def __init__(self, labels, parent=None):
        super().__init__(parent)
        if len(labels) != 3:
            raise ValueError("ThreeLevelSlider requires exactly three labels")
        self.setObjectName("threeLevelTrack")
        # Plain QWidget only paints QSS backgrounds with this attribute.
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self._value = 0
        self.level_buttons = []
        for index, text in enumerate(labels):
            button = QPushButton(text)
            button.setObjectName("threeLevelOption")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, value=index: self.setValue(value)
            )
            layout.addWidget(button, 1)
            self.level_buttons.append(button)
        self._refresh_selection(self._value)

    def _refresh_selection(self, value):
        self._value = max(0, min(2, int(value)))
        for index, button in enumerate(self.level_buttons):
            button.setChecked(index == self._value)

    def value(self):
        return self._value

    def setValue(self, value):
        self._refresh_selection(value)
