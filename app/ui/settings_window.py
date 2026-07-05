from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSpinBox, QFormLayout, QGroupBox, QMessageBox,
    QCheckBox, QLineEdit
)

from app.config import APP_NAME, APP_VERSION, DEFAULT_NEW_POEMS, DEFAULT_REVIEW_LIMIT
from app.core.database import Database


class SettingsWindow(QWidget):

    closed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._build_ui()
        self._load_settings()
        self._apply_theme()

    def _build_ui(self):
        self.setWindowTitle("设置")
        self.resize(500, 400)
        self.setMinimumSize(400, 300)
        self.setWindowFlags(Qt.WindowType.Window)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setObjectName("settingsTitle")
        layout.addWidget(title)

        study_group = QGroupBox("学习设置")
        study_group.setObjectName("settingsGroup")
        form = QFormLayout(study_group)
        form.setSpacing(12)
        form.setContentsMargins(16, 20, 16, 16)

        self.new_per_day = QSpinBox()
        self.new_per_day.setRange(1, 50)
        self.new_per_day.setValue(DEFAULT_NEW_POEMS)
        self.new_per_day.setObjectName("settingsSpin")
        form.addRow("每天新诗数量:", self.new_per_day)

        self.review_limit = QSpinBox()
        self.review_limit.setRange(5, 200)
        self.review_limit.setValue(DEFAULT_REVIEW_LIMIT)
        self.review_limit.setObjectName("settingsSpin")
        form.addRow("每日复习上限:", self.review_limit)

        layout.addWidget(study_group)

        data_group = QGroupBox("数据管理")
        data_group.setObjectName("settingsGroup")
        data_layout = QVBoxLayout(data_group)
        data_layout.setContentsMargins(16, 20, 16, 16)
        data_layout.setSpacing(8)

        info_label = QLabel("重置所有学习进度，内容数据将保留。")
        info_label.setObjectName("settingsInfo")
        data_layout.addWidget(info_label)

        self.btn_reset = QPushButton("重置学习进度")
        self.btn_reset.setObjectName("dangerBtn")
        self.btn_reset.clicked.connect(self._reset_progress)
        data_layout.addWidget(self.btn_reset)

        layout.addWidget(data_group)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_save = QPushButton("保存设置")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.clicked.connect(self._save_settings)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("secondaryBtn")
        self.btn_cancel.clicked.connect(self.close)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_cancel)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _load_settings(self):
        new_val = self.db.get_setting("new_poems_per_day")
        if new_val is not None:
            self.new_per_day.setValue(int(new_val))
        review_val = self.db.get_setting("review_limit")
        if review_val is not None:
            self.review_limit.setValue(int(review_val))

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def _save_settings(self):
        self.db.set_setting("new_poems_per_day", str(self.new_per_day.value()))
        self.db.set_setting("review_limit", str(self.review_limit.value()))
        QMessageBox.information(self, "成功", "设置已保存！")
        self.closed.emit()
        self.close()

    def _reset_progress(self):
        reply = QMessageBox.warning(
            self, "确认重置",
            "确定要重置所有学习进度吗？\n此操作不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM progress")
            cursor.execute("DELETE FROM study_history")
            cursor.execute("DELETE FROM daily_stats")
            self.db.conn.commit()
            QMessageBox.information(self, "完成", "学习进度已重置！")

    def _apply_theme(self):
        self.setStyleSheet("""
            * {
                font-family: -apple-system, 'Helvetica Neue', 'SF Pro Display',
                             'Segoe UI', Roboto, sans-serif;
            }
            QWidget { background-color: #F5F5F7; }
            QLabel#settingsTitle { font-size: 22px; font-weight: 700; color: #1D1D1F; letter-spacing: -0.5px; }
            QGroupBox#settingsGroup {
                background-color: #FFFFFF; border: 1px solid #E8E8ED;
                border-radius: 14px; margin-top: 8px;
                font-size: 13px; font-weight: 600; color: #1D1D1F;
            }
            QGroupBox#settingsGroup::title {
                subcontrol-origin: margin; left: 16px; padding: 0 6px;
            }
            QSpinBox#settingsSpin {
                background-color: #FFFFFF; border: 1px solid #E8E8ED;
                border-radius: 8px; padding: 6px 12px;
                font-size: 13px; color: #1D1D1F; min-width: 80px;
            }
            QSpinBox#settingsSpin:focus { border-color: #007AFF; }
            QLabel#settingsInfo { font-size: 12px; color: #86868B; font-weight: 400; }
            QPushButton#primaryBtn {
                background-color: #007AFF; color: white; border: none;
                border-radius: 12px; padding: 10px 24px; font-size: 13px; font-weight: 600;
            }
            QPushButton#primaryBtn:hover { background-color: #0066D6; }
            QPushButton#secondaryBtn {
                background-color: #FFFFFF; color: #1D1D1F; border: 1px solid #D2D2D7;
                border-radius: 12px; padding: 10px 24px; font-size: 13px; font-weight: 500;
            }
            QPushButton#secondaryBtn:hover { border-color: #007AFF; color: #007AFF; }
            QPushButton#dangerBtn {
                background-color: #FF3B30; color: white; border: none;
                border-radius: 12px; padding: 10px 20px; font-size: 13px; font-weight: 600;
            }
            QPushButton#dangerBtn:hover { background-color: #D63031; }
        """)
