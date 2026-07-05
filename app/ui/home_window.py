from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPainter, QColor, QBrush, QFont, QAction
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QMainWindow, QStatusBar, QMessageBox,
    QScrollArea, QSizePolicy, QMenu
)

from app.config import APP_NAME, APP_VERSION, WINDOW_WIDTH, WINDOW_HEIGHT
from app.core.database import Database
from app.core.scheduler import FSRSScheduler
from app.core.poem_manager import CardManager
from app.ui.study_window import StudyWindow
from app.ui.review_window import ReviewWindow
from app.ui.settings_window import SettingsWindow
from app.ui.import_window import ImportWindow
from app.models.poem import CARD_TYPES


THEME_LIGHT = {
    "bg": "#F5F5F7", "card_bg": "#FFFFFF", "card_border": "#E8E8ED",
    "text": "#1D1D1F", "text_secondary": "#86868B",
    "accent": "#007AFF", "accent_hover": "#0066D6",
    "success": "#34C759", "warning": "#FF9500", "danger": "#FF3B30",
    "streak_fire": "#FF6B35", "divider": "#E8E8ED",
    "heatmap_empty": "#EBEDF0", "heatmap_light": "#9BE9A8",
    "heatmap_mid": "#40C463", "heatmap_heavy": "#216E39",
}

THEME_DARK = {
    "bg": "#1C1C1E", "card_bg": "#2C2C2E", "card_border": "#3A3A3C",
    "text": "#F5F5F7", "text_secondary": "#98989D",
    "accent": "#0A84FF", "accent_hover": "#409CFF",
    "success": "#30D158", "warning": "#FF9F0A", "danger": "#FF453A",
    "streak_fire": "#FF6B35", "divider": "#3A3A3C",
    "heatmap_empty": "#2C2C2E", "heatmap_light": "#0E4429",
    "heatmap_mid": "#1E7E34", "heatmap_heavy": "#3DC45B",
}


class HeatmapWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.setMinimumHeight(130)
        self.setMaximumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: dict):
        self.data = data
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = THEME_LIGHT
        cell = 11
        gap = 3
        today = date.today()
        start = today - timedelta(days=111)
        rows = 7
        ox = 24
        oy = 18
        for i in range(112):
            d = start + timedelta(days=i)
            ds = d.isoformat()
            col = i // rows
            row = i % rows
            x = ox + col * (cell + gap)
            y = oy + row * (cell + gap)
            count = self.data.get(ds, 0)
            if count == 0:
                c = QColor(theme["heatmap_empty"])
            elif count <= 2:
                c = QColor(theme["heatmap_light"])
            elif count <= 6:
                c = QColor(theme["heatmap_mid"])
            else:
                c = QColor(theme["heatmap_heavy"])
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, cell, cell, 2, 2)
        painter.end()


class StatCard(QFrame):

    clicked = Signal()

    def __init__(self, title: str, value: str, color: str, subtitle: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(90)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("statTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: bold;")
        self.sub_label = QLabel(subtitle)
        self.sub_label.setObjectName("statSub")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)

    def set_value(self, value: str, subtitle: str = ""):
        self.value_label.setText(value)
        if subtitle:
            self.sub_label.setText(subtitle)

    def set_color(self, color: str):
        self.value_label.setStyleSheet(f"color: {color}; font-size: 26px; font-weight: bold;")

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class HomeWindow(QMainWindow):

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.card_manager = CardManager(db)
        self.scheduler = FSRSScheduler()
        self.dark_mode = False
        self.study_window = None
        self.review_window = None
        self.settings_window = None
        self.import_window = None
        self._init_window()
        self._create_menu()
        self._build_ui()
        self._apply_theme()
        self._refresh()

    def _init_window(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(800, 600)

    def _create_menu(self):
        menubar = self.menuBar()
        view_menu = menubar.addMenu("视图")
        toggle_action = QAction("切换深色模式", self)
        toggle_action.setCheckable(True)
        toggle_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_action)
        help_menu = menubar.addMenu("帮助")
        about_action = QAction("关于", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setObjectName("scrollArea")
        sw = QWidget()
        sw.setObjectName("scrollContent")
        self.sl = QVBoxLayout(sw)
        self.sl.setContentsMargins(32, 20, 32, 24)
        self.sl.setSpacing(16)
        scroll.setWidget(sw)
        main_layout.addWidget(scroll)
        self.setStatusBar(QStatusBar(self))

        self._build_header()
        self._build_method_card()
        self._build_stats()
        self._build_actions()
        self._build_plan_progress()
        self._build_heatmap()
        self._build_poem_list()

    def _build_header(self):
        h = QWidget()
        hl = QHBoxLayout(h)
        hl.setContentsMargins(0, 0, 0, 0)
        t = QLabel("MemoryFlow")
        t.setObjectName("appTitle")
        sub = QLabel("间隔重复 · 主动回忆 · FSRS算法")
        sub.setObjectName("appSubtitle")
        hl.addWidget(t)
        hl.addSpacing(12)
        hl.addWidget(sub)
        hl.addStretch()
        self.sl.addWidget(h)

    def _build_method_card(self):
        card = QFrame()
        card.setObjectName("methodCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(4)
        t = QLabel("🧠 MemoryFlow 学习方法")
        t.setObjectName("methodTitle")
        d = QLabel(
            "基于艾宾浩斯遗忘曲线 + 主动回忆（Active Recall）+ 间隔重复（Spaced Repetition）的原理。"
            "支持古诗、文章、知识点、单词、公式等内容，通过 FSRS-5 算法智能安排复习时间。"
        )
        d.setObjectName("methodDesc")
        d.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(d)
        self.sl.addWidget(card)

    def _build_stats(self):
        grid = QGridLayout()
        grid.setSpacing(10)
        self.card_new = StatCard("📖 今日新诗", "0", THEME_LIGHT["accent"], "每日 1 首")
        self.card_review = StatCard("🔄 待复习", "0", THEME_LIGHT["warning"], "到期需复习")
        self.card_streak = StatCard("🔥 连续学习", "0 天", THEME_LIGHT["streak_fire"], "保持好习惯")
        self.card_mastered = StatCard("✅ 已掌握", "0/11", THEME_LIGHT["success"], "稳定记忆")
        self.card_new.clicked.connect(self._start_study)
        self.card_review.clicked.connect(self._start_review)
        grid.addWidget(self.card_new, 0, 0)
        grid.addWidget(self.card_review, 0, 1)
        grid.addWidget(self.card_streak, 0, 2)
        grid.addWidget(self.card_mastered, 0, 3)
        self.sl.addLayout(grid)

    def _build_actions(self):
        row = QHBoxLayout()
        row.setSpacing(12)
        self.btn_study = QPushButton("📖 学习新诗")
        self.btn_study.setObjectName("primaryBtn")
        self.btn_study.setMinimumHeight(50)
        self.btn_study.clicked.connect(self._start_study)

        self.btn_review = QPushButton("🔄 复习")
        self.btn_review.setObjectName("secondaryBtn")
        self.btn_review.setMinimumHeight(50)
        self.btn_review.clicked.connect(self._start_review)

        self.btn_settings = QPushButton("⚙️ 设置")
        self.btn_settings.setObjectName("tertiaryBtn")
        self.btn_settings.setMinimumHeight(50)
        self.btn_settings.clicked.connect(self._open_settings)

        self.btn_import = QPushButton("📥 导入内容")
        self.btn_import.setObjectName("secondaryBtn")
        self.btn_import.setMinimumHeight(50)
        self.btn_import.clicked.connect(self._open_import)

        self.btn_backup = QPushButton("💾 备份导出")
        self.btn_backup.setObjectName("tertiaryBtn")
        self.btn_backup.setMinimumHeight(50)
        self.btn_backup.clicked.connect(self._backup_all)

        row.addWidget(self.btn_study)
        row.addWidget(self.btn_review)
        row.addWidget(self.btn_import)
        row.addWidget(self.btn_backup)
        row.addWidget(self.btn_settings)
        self.sl.addLayout(row)

    def _backup_all(self):
        count = self.card_manager.backup_all()
        QMessageBox.information(
            self, "备份完成",
            f"已导出 {count} 条内容为 JSON，保存到 poems/ 目录。"
        )

    def _build_plan_progress(self):
        frame = QFrame()
        frame.setObjectName("sectionCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 16)

        header_row = QHBoxLayout()
        t = QLabel("📊 12 天学习计划")
        t.setObjectName("sectionTitle")
        header_row.addWidget(t)
        self.plan_label = QLabel("第 1 天 / 共 12 天")
        self.plan_label.setObjectName("planDay")
        header_row.addStretch()
        header_row.addWidget(self.plan_label)
        layout.addLayout(header_row)

        bar = QFrame()
        bar.setObjectName("planBar")
        bar.setMinimumHeight(10)
        bar.setMaximumHeight(10)
        self.plan_fill = QFrame()
        self.plan_fill.setObjectName("planFill")
        self.plan_fill.setMinimumHeight(10)
        self.plan_fill.setMaximumHeight(10)
        bw = QHBoxLayout(bar)
        bw.setContentsMargins(0, 0, 0, 0)
        bw.addWidget(self.plan_fill)
        layout.addWidget(bar)

        self.plan_desc = QLabel("")
        self.plan_desc.setObjectName("planDesc")
        layout.addWidget(self.plan_desc)
        self.sl.addWidget(frame)

    def _build_heatmap(self):
        frame = QFrame()
        frame.setObjectName("sectionCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 16, 20, 10)
        t = QLabel("📅 学习热力图")
        t.setObjectName("sectionTitle")
        layout.addWidget(t)
        self.heatmap = HeatmapWidget()
        layout.addWidget(self.heatmap)
        self.sl.addWidget(frame)

    def _build_poem_list(self):
        frame = QFrame()
        frame.setObjectName("sectionCard")
        self.poem_list_layout = QVBoxLayout(frame)
        self.poem_list_layout.setContentsMargins(20, 16, 20, 16)
        t = QLabel("📚 内容库")
        t.setObjectName("sectionTitle")
        self.poem_list_layout.addWidget(t)
        self.sl.addWidget(frame)

    def _refresh(self):
        self._refresh_stats()
        self._refresh_plan()
        self._refresh_heatmap()
        self._refresh_poem_list()

    def _refresh_stats(self):
        total = self.card_manager.get_card_count()
        mastered = self.db.get_mastered_count()
        streak = self.db.get_streak_days()
        due = len(self.db.get_due_reviews(limit=999))
        new_remaining = len(self.db.get_new_cards(limit=999))
        studied = self.db.get_total_studied()

        self.card_new.set_value(str(new_remaining), f"已学 {studied}/{total}")
        self.card_review.set_value(str(due), f"今天要复习")
        self.card_streak.set_value(f"{streak} 天", "保持好习惯")
        self.card_mastered.set_value(f"{mastered}/{total}", "稳定记忆（≥21天）")

    def _refresh_plan(self):
        total = self.card_manager.get_card_count()
        studied = self.db.get_total_studied()
        day = min(studied + 1, 12)
        pct = min(studied / total * 100, 100) if total > 0 else 0
        self.plan_label.setText(f"第 {day} 天 / 共 12 天")
        self.plan_fill.setFixedWidth(int(pct / 100 * 400))
        remaining = total - studied
        if remaining > 0:
            self.plan_desc.setText(f"已学 {studied} 个，还剩 {remaining} 个待学习")
        else:
            self.plan_desc.setText("🎉 全部学完！坚持每日复习巩固记忆")

    def _refresh_heatmap(self):
        self.heatmap.set_data(self.db.get_heatmap_data(365))

    def _refresh_poem_list(self):
        while self.poem_list_layout.count() > 1:
            item = self.poem_list_layout.takeAt(1)
            if item:
                w = item.widget()
                if w:
                    w.deleteLater()
                l = item.layout()
                if l:
                    while l.count():
                        ci = l.takeAt(0)
                        if ci and ci.widget():
                            ci.widget().deleteLater()
        cards = self.card_manager.get_all_cards()
        today = date.today().isoformat()
        for card in cards:
            row = QHBoxLayout()
            card_frame = QFrame()
            card_frame.setObjectName("poemItemFrame")
            card_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            card_frame.mousePressEvent = lambda e, cid=card.id: self._on_card_click(e, cid)
            card_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            card_frame.customContextMenuRequested.connect(
                lambda pos, cf=card_frame, cid=card.id, c=card: self._show_card_menu(cf, pos, cid, c)
            )
            pfl = QHBoxLayout(card_frame)
            pfl.setContentsMargins(8, 4, 8, 4)
            type_name = CARD_TYPES.get(card.card_type, card.card_type)
            title_label = QLabel(f"[{type_name}] {card.title}")
            title_label.setObjectName("poemListItem")
            progress = self.db.get_progress(card.id)
            if progress is None or progress.review_count == 0:
                status = "📖 未学习"
                status_color = "#86868B"
            elif progress.stability >= 21:
                status = "✅ 已掌握"
                status_color = "#34C759"
            elif progress.next_review and progress.next_review <= today:
                status = "🔄 待复习"
                status_color = "#FF9500"
            else:
                status = "📚 学习中"
                status_color = "#007AFF"
            status_label = QLabel(status)
            status_label.setObjectName("poemStatus")
            status_label.setStyleSheet(f"color: {status_color}; font-size: 12px;")
            pfl.addWidget(title_label)
            pfl.addStretch()
            pfl.addWidget(status_label)
            row.addWidget(card_frame)
            self.poem_list_layout.addLayout(row)

    def _on_card_click(self, event, card_id: int):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_card_study(card_id)

    def _show_card_menu(self, frame, pos, card_id, card):
        menu = QMenu(self)
        act_study = menu.addAction("📖 学习此卡片")
        menu.addSeparator()
        act_edit = menu.addAction("✏️ 编辑")
        act_delete = menu.addAction("🗑️ 删除")
        chosen = menu.exec(frame.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_study:
            self._open_card_study(card_id)
        elif chosen is act_edit:
            self._open_card_edit(card_id)
        elif chosen is act_delete:
            self._confirm_delete(card_id, card.title)

    def _open_card_edit(self, card_id: int):
        if self.import_window is None:
            self.import_window = ImportWindow(self.db, self)
            self.import_window.saved.connect(self._on_import_closed)
        self.import_window._edit_card_id = None
        self.import_window.setWindowTitle("快速导入内容")
        self.import_window.title_label.setText("📝 快速导入内容")
        self.import_window.hint.setText("每行一项，支持导入古诗、文章、知识点、单词等")
        self.import_window.btn_save.setText("✅ 保存并导入")
        self.import_window._clear_fields()
        self.import_window.load_card_for_edit(card_id)
        self.import_window.show()
        self.import_window.raise_()

    def _confirm_delete(self, card_id: int, title: str):
        reply = QMessageBox.warning(
            self, "确认删除",
            f"确定删除《{title}》？\n相关学习进度也会一并清除，此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = self.card_manager.delete_card(card_id)
            if ok:
                self._refresh()
            else:
                QMessageBox.warning(self, "失败", "删除失败")

    def _open_card_study(self, card_id: int):
        if self.study_window is None:
            self.study_window = StudyWindow(self.db, self)
            self.study_window.closed.connect(self._on_study_closed)
        self.study_window.load_specific_card(card_id)
        self.study_window.show()
        self.study_window.raise_()

    def _start_study(self):
        if self.study_window is None:
            self.study_window = StudyWindow(self.db, self)
            self.study_window.closed.connect(self._on_study_closed)
        self.study_window.load_new_cards()
        self.study_window.show()
        self.study_window.raise_()

    def _on_study_closed(self):
        self._refresh()

    def _start_review(self):
        if self.review_window is None:
            self.review_window = ReviewWindow(self.db, self)
            self.review_window.closed.connect(self._on_review_closed)
        self.review_window.load_reviews()
        self.review_window.show()
        self.review_window.raise_()

    def _on_review_closed(self):
        self._refresh()

    def _open_settings(self):
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self.db, self)
            self.settings_window.closed.connect(self._on_settings_closed)
        self.settings_window.show()
        self.settings_window.raise_()

    def _on_settings_closed(self):
        self._refresh()

    def _open_import(self):
        if self.import_window is None:
            self.import_window = ImportWindow(self.db, self)
            self.import_window.saved.connect(self._on_import_closed)
        self.import_window._closed_emitted = False
        self.import_window._clear_fields()
        self.import_window.show()
        self.import_window.raise_()

    def _on_import_closed(self):
        self._refresh()

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _apply_theme(self):
        t = THEME_DARK if self.dark_mode else THEME_LIGHT
        bg, cb, cbd, tx, tx2, ac, ach, su, di = (
            t["bg"], t["card_bg"], t["card_border"], t["text"],
            t["text_secondary"], t["accent"], t["accent_hover"],
            t["success"], t["divider"]
        )
        shadow = "0 2px 8px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.06)"
        self.setStyleSheet(f"""
            * {{
                font-family: -apple-system, 'Helvetica Neue', 'SF Pro Display',
                             'Segoe UI', Roboto, sans-serif;
            }}
            QMainWindow{{background-color:{bg};}}
            QWidget#scrollContent{{background-color:{bg};}}
            QScrollArea#scrollArea{{background-color:{bg};border:none;}}
            QLabel#appTitle{{font-size:26px;font-weight:700;color:{tx};letter-spacing:-0.5px;}}
            QLabel#appSubtitle{{font-size:12px;color:{tx2};padding-top:7px;font-weight:400;}}
            QFrame#methodCard{{
                background-color:{cb};border:1px solid {cbd};
                border-radius:14px;
            }}
            QLabel#methodTitle{{font-size:14px;font-weight:600;color:{tx};}}
            QLabel#methodDesc{{font-size:13px;color:{tx2};line-height:1.7;}}
            QFrame#statCard{{
                background-color:{cb};border:1px solid {cbd};
                border-radius:14px;padding:8px;
            }}
            QFrame#statCard:hover{{border-color:{ac};}}
            QLabel#statTitle{{font-size:11px;color:{tx2};font-weight:500;text-transform:uppercase;letter-spacing:0.5px;}}
            QLabel#statValue{{font-size:26px;font-weight:700;letter-spacing:-0.3px;}}
            QLabel#statSub{{font-size:11px;color:{tx2};}}
            QPushButton#primaryBtn{{
                background-color:{ac};color:white;border:none;
                border-radius:12px;font-size:14px;font-weight:600;
                padding:12px 28px;
            }}
            QPushButton#primaryBtn:hover{{background-color:{ach};}}
            QPushButton#secondaryBtn{{
                background-color:{cb};color:{tx};border:1px solid {cbd};
                border-radius:12px;font-size:14px;font-weight:500;padding:12px 28px;
            }}
            QPushButton#secondaryBtn:hover{{border-color:{ac};color:{ac};}}
            QPushButton#tertiaryBtn{{
                background-color:transparent;color:{tx2};border:1px solid {cbd};
                border-radius:12px;font-size:13px;font-weight:500;padding:12px 20px;
            }}
            QPushButton#tertiaryBtn:hover{{border-color:{ac};color:{ac};}}
            QFrame#sectionCard{{
                background-color:{cb};border:1px solid {cbd};border-radius:14px;
            }}
            QLabel#sectionTitle{{font-size:14px;font-weight:600;color:{tx};padding-bottom:4px;}}
            QLabel#planDay{{font-size:12px;color:{tx2};font-weight:500;}}
            QFrame#planBar{{background-color:{di};border-radius:6px;}}
            QFrame#planFill{{background-color:{ac};border-radius:6px;}}
            QLabel#planDesc{{font-size:12px;color:{tx2};padding-top:4px;}}
            QFrame#poemItemFrame{{
                background-color:transparent;border:none;border-radius:8px;padding:2px;
            }}
            QFrame#poemItemFrame:hover{{
                background-color:{cb};border:1px solid {cbd};
            }}
            QLabel#poemListItem{{font-size:13px;color:{tx};padding:3px 0;font-weight:500;}}
            QLabel#poemStatus{{font-size:11px;padding:3px 0;font-weight:500;}}
            QStatusBar{{
                background-color:{cb};color:{tx2};border-top:1px solid {di};font-size:11px;
            }}
            QMenuBar{{background-color:{cb};color:{tx};border-bottom:1px solid {di};font-size:13px;}}
            QMenuBar::item:selected{{background-color:{ac};color:white;border-radius:6px;}}
            QMenu{{background-color:{cb};color:{tx};border:1px solid {cbd};border-radius:8px;padding:4px;}}
            QMenu::item{{border-radius:6px;padding:6px 24px;}}
            QMenu::item:selected{{background-color:{ac};color:white;}}
        """)
        fire = t["streak_fire"]
        self.card_new.set_color(ac)
        self.card_review.set_color(t["warning"])
        self.card_streak.set_color(fire)
        self.card_mastered.set_color(su)

    def _show_about(self):
        QMessageBox.about(
            self, "关于 MemoryFlow",
            f"<b>MemoryFlow</b> v{APP_VERSION}<br><br>"
            "基于艾宾浩斯遗忘曲线 + 主动回忆 + 间隔重复<br>"
            "采用 FSRS-5 算法智能安排复习<br><br>"
            "支持古诗、文章、知识点、单词、公式等内容的记忆"
        )

    def closeEvent(self, event):
        try:
            self.db.close()
        except Exception:
            pass
        for w in (self.study_window, self.review_window,
                   self.settings_window, self.import_window):
            if w is not None:
                w.deleteLater()
        super().closeEvent(event)
