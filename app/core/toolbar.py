"""Top bar: app name, project title, and the settings button. Everything else lives in settings."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QSizePolicy, QToolBar, QToolButton, QWidget


class TopBar(QToolBar):
    def __init__(self, win):
        super().__init__("top bar", win)
        self.setMovable(False)
        self.setFloatable(False)
        self.setObjectName("topBar")

        brand = QLabel("FAWS")
        brand.setObjectName("brand")
        self.addWidget(brand)
        self.title_label = QLabel("")
        self.title_label.setObjectName("barLabel")
        self.addWidget(self.title_label)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.addWidget(spacer)

        settings = QToolButton(self)
        settings.setText("⚙  settings")
        settings.setObjectName("barBtn")
        settings.setToolTip("modules, layout, project, preferences  (Cmd+,)")
        settings.clicked.connect(lambda: win.open_settings())
        self.addWidget(settings)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)
