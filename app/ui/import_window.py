import json

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QFrame, QMessageBox, QComboBox
)

from app.core.database import Database
from app.models.poem import CARD_TYPES


TYPE_FIELDS = {
    "poem": {
        "author": "作者（选填）",
        "dynasty": "朝代（选填）",
        "content_label": "📜 诗句内容（每行一句）",
        "content_placeholder": "移舟泊烟渚\n日暮客愁新\n野旷天低树\n江清月近人",
        "meaning_label": "📖 白话释义（每行一句，可选）",
        "meaning_placeholder": "把小船停靠在烟雾迷蒙的小洲旁\n日暮时分，思乡的愁绪又涌上心头\n...",
    },
    "question": {
        "author": "",
        "dynasty": "分类/科目（选填）",
        "content_label": "❓ 问题（每行一个）",
        "content_placeholder": "什么是光合作用？\n细胞的基本结构有哪些？",
        "meaning_label": "✅ 答案（每行一个，与问题对应）",
        "meaning_placeholder": "植物利用光能将二氧化碳和水转化为有机物的过程\n细胞膜、细胞质、细胞核",
    },
    "vocabulary": {
        "author": "",
        "dynasty": "词书/分类（选填）",
        "content_label": "📝 单词（每行一个）",
        "content_placeholder": "ephemeral\nubiquitous\nserendipity",
        "meaning_label": "📖 释义（每行一个，与单词对应）",
        "meaning_placeholder": "adj. 短暂的，瞬息的\nadj. 无所不在的\nn. 意外发现",
    },
    "article": {
        "author": "作者/来源（选填）",
        "dynasty": "分类（选填）",
        "content_label": "📄 段落（每行一段）",
        "content_placeholder": "春天来了，花儿开了。\n小鸟在枝头唱歌。",
        "meaning_label": "📖 摘要/笔记（每行一条，可选）",
        "meaning_placeholder": "描写了春天的景象\n表达了对大自然的热爱",
    },
    "formula": {
        "author": "",
        "dynasty": "学科/分类（选填）",
        "content_label": "📐 公式（每行一个）",
        "content_placeholder": "E=mc²\na²+b²=c²",
        "meaning_label": "📖 说明/推导（每行一条，可选）",
        "meaning_placeholder": "质能方程：能量等于质量乘以光速平方\n勾股定理：直角三角形两直角边的平方和等于斜边的平方",
    },
}


class ImportWindow(QWidget):

    saved = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._closed_emitted = False
        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        self.setWindowTitle("快速导入内容")
        self.resize(680, 620)
        self.setMinimumSize(500, 480)
        self.setWindowFlags(Qt.WindowType.Window)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(24, 20, 24, 20)
        self.main_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_label = QLabel("📥 快速导入内容")
        title_label.setObjectName("importTitle")
        title_row.addWidget(title_label)
        title_row.addStretch()
        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("closeBtn")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.clicked.connect(self._confirm_exit)
        title_row.addWidget(self.btn_close)
        self.main_layout.addLayout(title_row)

        hint = QLabel("每行一项，支持导入古诗、文章、知识点、单词等")
        hint.setObjectName("importHint")
        self.main_layout.addWidget(hint)

        type_row = QHBoxLayout()
        type_label = QLabel("类型：")
        type_label.setObjectName("fieldLabel")
        self.input_type = QComboBox()
        self.input_type.setObjectName("importInput")
        for key, label in CARD_TYPES.items():
            self.input_type.addItem(label, key)
        self.input_type.setMinimumWidth(120)
        self.input_type.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(type_label)
        type_row.addWidget(self.input_type)
        type_row.addStretch()
        self.main_layout.addLayout(type_row)

        self.fields_frame = QFrame()
        self.fields_frame.setObjectName("importFields")
        self.fields_layout = QVBoxLayout(self.fields_frame)
        self.fields_layout.setContentsMargins(16, 12, 16, 12)
        self.fields_layout.setSpacing(8)

        self.row_title = QHBoxLayout()
        self.input_title = QLineEdit()
        self.input_title.setPlaceholderText("标题（必填）")
        self.input_title.setObjectName("importInput")
        self.row_title.addWidget(self.input_title)
        self.fields_layout.addLayout(self.row_title)

        self.row_author_dynasty = QHBoxLayout()
        self.input_author = QLineEdit()
        self.input_author.setObjectName("importInput")
        self.input_dynasty = QLineEdit()
        self.input_dynasty.setObjectName("importInput")
        self.row_author_dynasty.addWidget(self.input_author)
        self.row_author_dynasty.addWidget(self.input_dynasty)
        self.fields_layout.addLayout(self.row_author_dynasty)

        self.main_layout.addWidget(self.fields_frame)

        content_frame = QFrame()
        content_frame.setObjectName("importFields")
        cfl = QVBoxLayout(content_frame)
        cfl.setContentsMargins(16, 12, 16, 12)
        cfl.setSpacing(6)

        self.content_label = QLabel("📝 内容（每行一项）")
        self.content_label.setObjectName("fieldLabel")
        cfl.addWidget(self.content_label)
        self.input_content = QTextEdit()
        self.input_content.setObjectName("importText")
        self.input_content.setMaximumHeight(140)
        cfl.addWidget(self.input_content)
        self.main_layout.addWidget(content_frame)

        meaning_frame = QFrame()
        meaning_frame.setObjectName("importFields")
        mfl = QVBoxLayout(meaning_frame)
        mfl.setContentsMargins(16, 12, 16, 12)
        mfl.setSpacing(6)

        self.meaning_label = QLabel("📖 对应释义/答案（每行一项，可选）")
        self.meaning_label.setObjectName("fieldLabel")
        mfl.addWidget(self.meaning_label)
        self.input_meaning = QTextEdit()
        self.input_meaning.setObjectName("importText")
        self.input_meaning.setMaximumHeight(140)
        mfl.addWidget(self.input_meaning)
        self.main_layout.addWidget(meaning_frame)

        self.main_layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_clear = QPushButton("清空")
        self.btn_clear.setObjectName("secondaryBtn")
        self.btn_clear.clicked.connect(self._clear_fields)
        self.btn_save = QPushButton("✅ 保存并导入")
        self.btn_save.setObjectName("primaryBtn")
        self.btn_save.setMinimumHeight(44)
        self.btn_save.clicked.connect(self._save)
        btn_row.addWidget(self.btn_clear)
        btn_row.addSpacing(10)
        btn_row.addWidget(self.btn_save)
        self.main_layout.addLayout(btn_row)

        self._on_type_changed()

    def _on_type_changed(self):
        card_type = self.input_type.currentData()
        fields = TYPE_FIELDS.get(card_type, TYPE_FIELDS["poem"])

        if fields["author"]:
            self.input_author.setPlaceholderText(fields["author"])
            self.input_author.setVisible(True)
        else:
            self.input_author.setVisible(False)

        if fields["dynasty"]:
            self.input_dynasty.setPlaceholderText(fields["dynasty"])
            self.input_dynasty.setVisible(True)
        else:
            self.input_dynasty.setVisible(False)

        self.content_label.setText(fields["content_label"])
        self.input_content.setPlaceholderText(fields["content_placeholder"])
        self.meaning_label.setText(fields["meaning_label"])
        self.input_meaning.setPlaceholderText(fields["meaning_placeholder"])

    def _parse_lines(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        return lines

    def _save(self):
        title = self.input_title.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入标题")
            return
        content_lines = self._parse_lines(self.input_content.toPlainText())
        if not content_lines:
            QMessageBox.warning(self, "提示", "请输入内容")
            return
        author = self.input_author.text().strip()
        dynasty = self.input_dynasty.text().strip()
        card_type = self.input_type.currentData()
        meaning_lines = self._parse_lines(self.input_meaning.toPlainText())

        content_json = json.dumps(content_lines, ensure_ascii=False)
        meaning_json = json.dumps(meaning_lines, ensure_ascii=False)

        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT id FROM cards WHERE title=? AND author=?",
            (title, author)
        )
        if cursor.fetchone():
            reply = QMessageBox.question(
                self, "已存草稿",
                f"「{title}」已存在，是否覆盖？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            cursor.execute(
                "UPDATE cards SET content=?, meaning=?, dynasty=?, card_type=? WHERE title=? AND author=?",
                (content_json, meaning_json, dynasty, card_type, title, author)
            )
            self.db.conn.commit()
        else:
            self.db.add_card(title, author, dynasty, content_json, meaning_json, card_type)

        self._save_to_json(title, author, dynasty, card_type, content_lines, meaning_lines)
        QMessageBox.information(self, "成功", f"「{title}」已导入！")
        self.saved.emit()
        self._clear_fields()

    def _save_to_json(self, title, author, dynasty, card_type, content, meaning):
        import app.config
        from pathlib import Path
        poems_dir = Path(app.config.POEMS_DIR)
        poems_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{title}.json"
        data = {
            "title": title,
            "author": author,
            "dynasty": dynasty,
            "card_type": card_type,
            "content": content,
            "meaning": meaning
        }
        try:
            with open(poems_dir / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _clear_fields(self):
        self.input_title.clear()
        self.input_author.clear()
        self.input_dynasty.clear()
        self.input_content.clear()
        self.input_meaning.clear()

    def _emit_closed(self):
        if not self._closed_emitted:
            self._closed_emitted = True
            self.saved.emit()

    def _confirm_exit(self):
        self._emit_closed()
        self.close()

    def closeEvent(self, event):
        self._emit_closed()
        event.accept()

    def _apply_theme(self):
        self.setStyleSheet("""
            * {
                font-family: -apple-system, 'Helvetica Neue', 'SF Pro Display',
                             'Segoe UI', Roboto, sans-serif;
            }
            QWidget#ImportWindow, QWidget {
                background-color: #F5F5F7;
            }
            QLabel#importTitle { font-size: 20px; font-weight: 700; color: #1D1D1F; letter-spacing: -0.3px; background-color: transparent; }
            QLabel#importHint { font-size: 12px; color: #86868B; font-weight: 400; background-color: transparent; }
            QPushButton#closeBtn {
                background-color: transparent; color: #86868B; border: none;
                font-size: 16px; font-weight: bold;
            }
            QPushButton#closeBtn:hover { color: #FF3B30; }
            QFrame#importFields { background-color: #FFFFFF; border: 1px solid #E8E8ED; border-radius: 14px; }
            QLabel#fieldLabel { font-size: 13px; font-weight: 600; color: #1D1D1F; background-color: transparent; }
            QLineEdit#importInput, QComboBox#importInput {
                background-color: #F5F5F7; border: 1px solid #E8E8ED;
                border-radius: 8px; padding: 8px 12px; font-size: 14px; color: #1D1D1F;
            }
            QLineEdit#importInput:focus, QComboBox#importInput:focus { border-color: #007AFF; }
            QComboBox#importInput::drop-down {
                border: none; padding-right: 8px;
            }
            QComboBox#importInput::down-arrow {
                image: none; border: none;
            }
            QTextEdit#importText {
                background-color: #F5F5F7; border: 1px solid #E8E8ED;
                border-radius: 8px; padding: 8px; font-size: 14px; color: #1D1D1F;
            }
            QTextEdit#importText:focus { border-color: #007AFF; }
            QTextEdit#importText QAbstractItemView {
                background-color: #F5F5F7;
            }
            QPushButton#primaryBtn {
                background-color: #007AFF; color: white; border: none;
                border-radius: 12px; font-size: 14px; font-weight: 600; padding: 12px 28px;
            }
            QPushButton#primaryBtn:hover { background-color: #0066D6; }
            QPushButton#secondaryBtn {
                background-color: #FFFFFF; color: #1D1D1F; border: 1px solid #D2D2D7;
                border-radius: 12px; font-size: 13px; font-weight: 500; padding: 10px 20px;
            }
            QPushButton#secondaryBtn:hover { border-color: #007AFF; color: #007AFF; }
        """)
