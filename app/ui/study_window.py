import json
from datetime import date, datetime
from difflib import SequenceMatcher

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy, QMessageBox, QProgressBar,
    QLineEdit
)

from app.core.database import Database
from app.core.scheduler import FSRSScheduler
from app.core.poem_manager import CardManager
from app.models.poem import Card, Progress, StudyHistory, CARD_TYPES


SEGMENT_SIZE = 2
SHORT_REVIEW_MINUTES = 15
TYPING_THRESHOLD = 0.75


class StudyWindow(QWidget):

    closed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.card_manager = CardManager(db)
        self.scheduler = FSRSScheduler()
        self.cards: list[Card] = []
        self.current_index = 0
        self.original_lines: list[str] = []
        self.original_meanings: list[str] = []
        self.card_type = "poem"
        self._closed_emitted = False

        self.segments: list[list[int]] = []
        self.current_segment = 0

        self.phase = "read"
        self.test_results: list[bool] = []
        self.test_inputs: list[str] = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False

        self.input_fields: list[QLineEdit] = []
        self.hint_labels: list[QLabel] = []

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        self.setWindowTitle("学习模式")
        self.resize(780, 620)
        self.setMinimumSize(520, 440)
        self.setWindowFlags(Qt.WindowType.Window)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget()
        content.setObjectName("studyBg")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        self.phase_label = QLabel("📖 阅读理解阶段")
        self.phase_label.setObjectName("phaseLabel")
        top_bar.addWidget(self.phase_label)
        top_bar.addStretch()
        self.btn_back = QPushButton("← 返回主页")
        self.btn_back.setObjectName("topNavBtn")
        self.btn_back.clicked.connect(self._confirm_exit)
        top_bar.addWidget(self.btn_back)
        layout.addLayout(top_bar)

        header = QHBoxLayout()
        self.title_label = QLabel("标题")
        self.title_label.setObjectName("studyTitle")
        self.author_label = QLabel("作者")
        self.author_label.setObjectName("studyAuthor")
        self.progress_label = QLabel("1/1")
        self.progress_label.setObjectName("studyProgress")
        header.addWidget(self.title_label)
        header.addSpacing(8)
        header.addWidget(self.author_label)
        header.addStretch()
        header.addWidget(self.progress_label)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("studyProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(4)
        self.progress_bar.setMaximumHeight(4)
        layout.addWidget(self.progress_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("studyScroll")
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("studyScrollContent")
        self.card_layout = QVBoxLayout(self.scroll_content)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setSpacing(0)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll, stretch=1)

        self.bottom_bar = QHBoxLayout()
        self.bottom_bar.setSpacing(10)
        layout.addLayout(self.bottom_bar)

        self.middle_bar = QHBoxLayout()
        self.middle_bar.setSpacing(10)
        layout.addLayout(self.middle_bar)

        outer.addWidget(content)

    def _clear_all_bars(self):
        self._clear_layout(self.bottom_bar)
        self._clear_layout(self.middle_bar)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _clear_card(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.input_fields.clear()
        self.hint_labels.clear()

    def _emit_closed(self):
        if not self._closed_emitted:
            self._closed_emitted = True
            self.closed.emit()

    def _confirm_exit(self):
        reply = QMessageBox.question(
            self, "确认退出",
            "确定要停止背诵并返回主页吗？\n本次学习进度不会保存。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._emit_closed()
            self.close()

    def closeEvent(self, event):
        self._emit_closed()
        event.accept()

    # ─── Load ───────────────────────────────────────────────────────

    def load_new_cards(self, force_all: bool = False):
        self._closed_emitted = False
        limit = 10 if force_all else 1
        new_cards = self.card_manager.get_new_cards(limit=limit)
        if not new_cards:
            QMessageBox.information(self, "提示", "所有内容都已学过！去复习吧")
            self.close()
            return
        self.cards = new_cards
        self.current_index = 0
        self._load_card(0)

    def load_specific_card(self, card_id: int):
        self._closed_emitted = False
        card = self.card_manager.get_card(card_id)
        if card:
            self.cards = [card]
            self.current_index = 0
            self._load_card(0)

    def _load_card(self, index: int):
        if index >= len(self.cards):
            QMessageBox.information(self, "完成", "所有学习已完成")
            self._emit_closed()
            self.close()
            return

        card = self.cards[index]
        self.card_type = card.card_type
        self.title_label.setText(card.title)
        if card.card_type == "poem":
            self.author_label.setText(f"{card.dynasty} · {card.author}")
        else:
            self.author_label.setText(CARD_TYPES.get(card.card_type, card.card_type))
        self.progress_label.setText(f"{index + 1}/{len(self.cards)}")

        self.original_lines = self.card_manager.get_card_content_lines(card.id)
        self.original_meanings = self.card_manager.get_card_meaning_lines(card.id)

        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False

        self._build_segments()
        self.current_segment = 0
        self.phase = "read"
        self._show_segment_read()

    def _build_segments(self):
        self.segments = []
        total = len(self.original_lines)
        for i in range(0, total, SEGMENT_SIZE):
            seg = list(range(i, min(i + SEGMENT_SIZE, total)))
            self.segments.append(seg)

    # ─── Segment Read Phase ─────────────────────────────────────────

    def _show_segment_read(self):
        self._clear_card()
        self._clear_all_bars()
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False

        total_segs = len(self.segments)
        seg_indices = self.segments[self.current_segment]
        total_lines = len(self.original_lines)
        done_lines = sum(len(s) for s in self.segments[:self.current_segment])
        self.progress_bar.setValue(int(done_lines / total_lines * 100) if total_lines > 0 else 0)

        type_labels = {
            "poem": "📖 阅读理解",
            "question": "📖 学习知识点",
            "vocabulary": "📖 学习单词",
            "article": "📖 阅读文章",
            "formula": "📖 学习公式",
        }
        title = f"{type_labels.get(self.card_type, '📖 阅读')} ({self.current_segment + 1}/{total_segs})"
        self.phase_label.setText(title)

        hint_texts = {
            "poem": "请阅读以下诗句及释义，理解后点击下方按钮开始背诵",
            "question": "请阅读以下问题和答案，理解后点击下方按钮开始背诵",
            "vocabulary": "请阅读以下单词和释义，理解后点击下方按钮开始背诵",
            "article": "请阅读以下段落，理解后点击下方按钮开始背诵",
            "formula": "请阅读以下公式和说明，理解后点击下方按钮开始背诵",
        }
        hint = QLabel(hint_texts.get(self.card_type, "请阅读以下内容，理解后点击下方按钮开始背诵"))
        hint.setObjectName("readIntro")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(hint)

        for i in seg_indices:
            pair = QFrame()
            pair.setObjectName("meaningPair")
            pl = QVBoxLayout(pair)
            pl.setContentsMargins(16, 10, 16, 10)
            pl.setSpacing(4)
            ll = QLabel(f"<b>{self.original_lines[i]}</b>")
            ll.setObjectName("readLine")
            mt = self.original_meanings[i] if i < len(self.original_meanings) else ""
            ml = QLabel(mt)
            ml.setObjectName("readMeaning")
            pl.addWidget(ll)
            if mt:
                pl.addWidget(ml)
            self.card_layout.addWidget(pair)

        self.card_layout.addStretch()
        btn = QPushButton("✅ 我已理解，开始背诵 →")
        btn.setObjectName("primaryBtn")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._start_segment_test)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(btn)
        self.bottom_bar.addStretch()

    # ─── Segment Test Phase ─────────────────────────────────────────

    def _start_segment_test(self):
        self.phase = "test"
        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False
        self._show_segment_test()

    def _show_segment_test(self):
        self._clear_card()
        self._clear_all_bars()

        seg_indices = self.segments[self.current_segment]
        total_in_seg = len(seg_indices)
        done = self.current_test_index
        total_segs = len(self.segments)

        seg_lines_done = sum(len(s) for s in self.segments[:self.current_segment]) + done
        total_lines = len(self.original_lines)
        self.progress_bar.setValue(int(seg_lines_done / total_lines * 100) if total_lines > 0 else 0)

        if done >= total_in_seg:
            self._segment_test_done()
            return

        type_labels = {
            "poem": "✍️ 背诵",
            "question": "✍️ 回忆答案",
            "vocabulary": "✍️ 回忆释义",
            "article": "✍️ 背诵段落",
            "formula": "✍️ 回忆公式",
        }

        if self.is_verification:
            self.phase_label.setText(f"✍️ 默写验证 - 无提示 ({self.current_segment + 1}/{total_segs})")
        else:
            self.phase_label.setText(f"{type_labels.get(self.card_type, '✍️ 背诵')} ({self.current_segment + 1}/{total_segs})")

        global_line_num = seg_indices[done] + 1
        prompt_texts = {
            "poem": f"请输入第 {global_line_num} 句（不需要标点）",
            "question": f"请输入第 {global_line_num} 题的答案",
            "vocabulary": f"请输入第 {global_line_num} 个单词的释义",
            "article": f"请输入第 {global_line_num} 段内容",
            "formula": f"请输入第 {global_line_num} 个公式",
        }
        line_num = QLabel(prompt_texts.get(self.card_type, f"请输入第 {global_line_num} 项"))
        line_num.setObjectName("reciteLineNum")
        line_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(line_num)

        self.input_fields.clear()
        self.hint_labels.clear()

        for i in range(done + 1):
            if i >= total_in_seg:
                break
            gi = seg_indices[i]
            card = QFrame()
            is_current = (i == done)

            if is_current:
                card.setObjectName("reciteCardCurrent")
            elif i < len(self.test_results) and self.test_results[i]:
                card.setObjectName("reciteCard")
            elif i < len(self.test_results) and not self.test_results[i]:
                card.setObjectName("reciteCardMistake")
            else:
                card.setObjectName("reciteCard")

            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 10, 20, 10)
            cl.setSpacing(4)

            if i < done:
                ll = QLabel(self.test_inputs[i] if i < len(self.test_inputs) else "")
                ll.setObjectName("reciteLineDone")
                ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(ll)

                is_ok = self.test_results[i] if i < len(self.test_results) else False
                tag = QLabel("✅ 正确" if is_ok else "❌ 有误")
                tag.setObjectName("reciteTag" if is_ok else "mistakeTag")
                tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(tag)

                if not is_ok:
                    corr = QLabel(self.original_lines[gi])
                    corr.setObjectName("correctLine")
                    corr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(corr)
            else:
                if self.card_type == "question":
                    question_label = QLabel(f"❓{self.original_lines[gi]}")
                    question_label.setObjectName("reciteLineDone")
                    question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(question_label)

                input_field = QLineEdit()
                input_field.setObjectName("typingInput")
                placeholder_texts = {
                    "poem": "请输入诗句…",
                    "question": "请输入答案…",
                    "vocabulary": "请输入释义…",
                    "article": "请输入段落内容…",
                    "formula": "请输入公式…",
                }
                input_field.setPlaceholderText(placeholder_texts.get(self.card_type, "请输入…"))
                input_field.returnPressed.connect(self._submit_segment)
                self.input_fields.append(input_field)
                cl.addWidget(input_field)

                if not self.is_verification:
                    hint_label = QLabel()
                    hint_label.setObjectName("typingHint")
                    hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    hint_label.setVisible(False)
                    self.hint_labels.append(hint_label)
                    cl.addWidget(hint_label)

            self.card_layout.addWidget(card)

        self.card_layout.addStretch()

        if done > 0:
            btn_back = QPushButton("← 上一句")
            btn_back.setObjectName("backBtn")
            btn_back.clicked.connect(self._prev_segment_test)
            self.middle_bar.addWidget(btn_back)
            self.middle_bar.addSpacing(12)

        if not self.is_verification:
            btn_hint = QPushButton("💡 显示提示" if not self.hint_visible else "💡 隐藏提示")
            btn_hint.setObjectName("hintBtn")
            btn_hint.clicked.connect(self._toggle_hint)
            self.middle_bar.addWidget(btn_hint)
            self.middle_bar.addSpacing(12)

        btn_submit = QPushButton("✅ 提交")
        btn_submit.setObjectName("primaryBtn")
        btn_submit.setMinimumHeight(44)
        btn_submit.clicked.connect(self._submit_segment)

        self.middle_bar.addStretch()
        self.middle_bar.addWidget(btn_submit)
        self.middle_bar.addStretch()

        if self.hint_visible and not self.is_verification:
            self._apply_hint()

    def _toggle_hint(self):
        self.hint_visible = not self.hint_visible
        if self.hint_visible:
            self.hints_used = True
        self._apply_hint()
        self._show_segment_test()

    def _apply_hint(self):
        if not self.hint_labels:
            return
        seg_indices = self.segments[self.current_segment]
        done = self.current_test_index
        if done < len(seg_indices):
            gi = seg_indices[done]
            first_char = self.original_lines[gi][0] if self.original_lines[gi] else ""
            for label in self.hint_labels:
                if self.hint_visible:
                    label.setText(f"提示：[{first_char}] ___。")
                else:
                    label.setText("")
                label.setVisible(self.hint_visible)

    def _submit_segment(self):
        if not self.input_fields:
            return
        user_input = self.input_fields[0].text().strip()
        if not user_input:
            return

        seg_indices = self.segments[self.current_segment]
        correct_text = self.original_lines[seg_indices[self.current_test_index]]
        score = SequenceMatcher(None, user_input, correct_text).ratio()
        is_correct = score >= TYPING_THRESHOLD

        self.test_results.append(is_correct)
        self.test_inputs.append(user_input)
        self.current_test_index += 1
        self._show_segment_test()

    def _prev_segment_test(self):
        if self.current_test_index > 0:
            self.current_test_index -= 1
            if self.test_results:
                self.test_results.pop()
            if self.test_inputs:
                self.test_inputs.pop()
            self._show_segment_test()

    def _segment_test_done(self):
        if self.hints_used and not self.is_verification:
            self.is_verification = True
            self.test_results = []
            self.test_inputs = []
            self.current_test_index = 0
            self.hint_visible = False
            self._show_segment_test()
            return

        total_segs = len(self.segments)
        self.current_segment += 1
        if self.current_segment < total_segs:
            self._show_segment_read()
        else:
            self._show_final_test_intro()

    # ─── Final Test Intro ───────────────────────────────────────────

    def _show_final_test_intro(self):
        self._clear_card()
        self._clear_all_bars()
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False
        self.progress_bar.setValue(100)

        type_labels = {
            "poem": "✍️ 全诗默写",
            "question": "✍️ 全部默写",
            "vocabulary": "✍️ 全部默写",
            "article": "✍️ 全文默写",
            "formula": "✍️ 全部默写",
        }
        self.phase_label.setText(type_labels.get(self.card_type, "✍️ 全部默写"))

        title_texts = {
            "poem": "最后一步：默写全诗",
            "question": "最后一步：默写全部答案",
            "vocabulary": "最后一步：默写全部释义",
            "article": "最后一步：默写全文",
            "formula": "最后一步：默写全部公式",
        }
        title = QLabel(title_texts.get(self.card_type, "最后一步：默写全部内容"))
        title.setObjectName("resultSummary")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(title)

        desc = QLabel("请逐项输入内容\n不确定时可以点击「显示提示」查看首字")
        desc.setObjectName("readIntro")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(desc)

        self.card_layout.addStretch()
        btn = QPushButton("开始默写 →")
        btn.setObjectName("primaryBtn")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._start_final_test)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(btn)
        self.bottom_bar.addStretch()

    # ─── Final Full Test ────────────────────────────────────────────

    def _start_final_test(self):
        self.phase = "test"
        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False
        self._show_final_test()

    def _show_final_test(self):
        self._clear_card()
        self._clear_all_bars()

        total = len(self.original_lines)
        done = self.current_test_index
        self.progress_bar.setValue(int(done / total * 100) if total > 0 else 0)

        if done >= total:
            self._final_test_done()
            return

        type_labels = {
            "poem": "✍️ 全诗默写",
            "question": "✍️ 默写答案",
            "vocabulary": "✍️ 默写释义",
            "article": "✍️ 全文默写",
            "formula": "✍️ 默写公式",
        }

        if self.is_verification:
            self.phase_label.setText(f"✍️ 默写验证 - 无提示 ({done + 1}/{total})")
        else:
            self.phase_label.setText(f"{type_labels.get(self.card_type, '✍️ 默写')} ({done + 1}/{total})")

        prompt_texts = {
            "poem": f"请输入第 {done + 1} 句（不需要标点）",
            "question": f"请输入第 {done + 1} 题的答案",
            "vocabulary": f"请输入第 {done + 1} 个单词的释义",
            "article": f"请输入第 {done + 1} 段内容",
            "formula": f"请输入第 {done + 1} 个公式",
        }
        line_num = QLabel(prompt_texts.get(self.card_type, f"请输入第 {done + 1} 项"))
        line_num.setObjectName("reciteLineNum")
        line_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(line_num)

        self.input_fields.clear()
        self.hint_labels.clear()

        for i in range(done + 1):
            if i >= total:
                break

            card = QFrame()
            is_current = (i == done)

            if is_current:
                card.setObjectName("reciteCardCurrent")
            elif i < len(self.test_results) and self.test_results[i]:
                card.setObjectName("reciteCard")
            elif i < len(self.test_results) and not self.test_results[i]:
                card.setObjectName("reciteCardMistake")
            else:
                card.setObjectName("reciteCard")

            cl = QVBoxLayout(card)
            cl.setContentsMargins(20, 10, 20, 10)
            cl.setSpacing(4)

            if i < done:
                ll = QLabel(self.test_inputs[i] if i < len(self.test_inputs) else "")
                ll.setObjectName("reciteLineDone")
                ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(ll)

                is_ok = self.test_results[i] if i < len(self.test_results) else False
                tag = QLabel("✅ 正确" if is_ok else "❌ 有误")
                tag.setObjectName("reciteTag" if is_ok else "mistakeTag")
                tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
                cl.addWidget(tag)

                if not is_ok:
                    corr = QLabel(self.original_lines[i])
                    corr.setObjectName("correctLine")
                    corr.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(corr)
            else:
                if self.card_type == "question":
                    question_label = QLabel(f"❓{self.original_lines[i]}")
                    question_label.setObjectName("reciteLineDone")
                    question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(question_label)

                input_field = QLineEdit()
                input_field.setObjectName("typingInput")
                placeholder_texts = {
                    "poem": "请输入诗句…",
                    "question": "请输入答案…",
                    "vocabulary": "请输入释义…",
                    "article": "请输入段落内容…",
                    "formula": "请输入公式…",
                }
                input_field.setPlaceholderText(placeholder_texts.get(self.card_type, "请输入…"))
                input_field.returnPressed.connect(self._submit_final)
                self.input_fields.append(input_field)
                cl.addWidget(input_field)

                if not self.is_verification:
                    hint_label = QLabel()
                    hint_label.setObjectName("typingHint")
                    hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    hint_label.setVisible(False)
                    self.hint_labels.append(hint_label)
                    cl.addWidget(hint_label)

            self.card_layout.addWidget(card)

        self.card_layout.addStretch()

        if done > 0:
            btn_back = QPushButton("← 上一句")
            btn_back.setObjectName("backBtn")
            btn_back.clicked.connect(self._prev_final_test)
            self.middle_bar.addWidget(btn_back)
            self.middle_bar.addSpacing(12)

        if not self.is_verification:
            btn_hint = QPushButton("💡 显示提示" if not self.hint_visible else "💡 隐藏提示")
            btn_hint.setObjectName("hintBtn")
            btn_hint.clicked.connect(self._toggle_final_hint)
            self.middle_bar.addWidget(btn_hint)
            self.middle_bar.addSpacing(12)

        btn_submit = QPushButton("✅ 提交")
        btn_submit.setObjectName("primaryBtn")
        btn_submit.setMinimumHeight(44)
        btn_submit.clicked.connect(self._submit_final)

        self.middle_bar.addStretch()
        self.middle_bar.addWidget(btn_submit)
        self.middle_bar.addStretch()

        if self.hint_visible and not self.is_verification:
            self._apply_final_hint()

    def _toggle_final_hint(self):
        self.hint_visible = not self.hint_visible
        if self.hint_visible:
            self.hints_used = True
        self._apply_final_hint()
        self._show_final_test()

    def _apply_final_hint(self):
        if not self.hint_labels:
            return
        done = self.current_test_index
        if done < len(self.original_lines):
            first_char = self.original_lines[done][0] if self.original_lines[done] else ""
            for label in self.hint_labels:
                if self.hint_visible:
                    label.setText(f"提示：[{first_char}] ___。")
                else:
                    label.setText("")
                label.setVisible(self.hint_visible)

    def _submit_final(self):
        if not self.input_fields:
            return
        user_input = self.input_fields[0].text().strip()
        if not user_input:
            return

        correct_text = self.original_lines[self.current_test_index]
        score = SequenceMatcher(None, user_input, correct_text).ratio()
        is_correct = score >= TYPING_THRESHOLD

        self.test_results.append(is_correct)
        self.test_inputs.append(user_input)
        self.current_test_index += 1
        self._show_final_test()

    def _prev_final_test(self):
        if self.current_test_index > 0:
            self.current_test_index -= 1
            if self.test_results:
                self.test_results.pop()
            if self.test_inputs:
                self.test_inputs.pop()
            self._show_final_test()

    def _final_test_done(self):
        if self.hints_used and not self.is_verification:
            self.is_verification = True
            self.test_results = []
            self.test_inputs = []
            self.current_test_index = 0
            self.hint_visible = False
            self._show_final_test()
            return

        self._show_result()

    # ─── Result ─────────────────────────────────────────────────────

    def _show_result(self):
        self._clear_card()
        self._clear_all_bars()
        self.hint_visible = False
        self.phase_label.setText("🏆 背诵结果")
        self.progress_bar.setValue(100)

        total = len(self.original_lines)
        correct = sum(self.test_results)
        wrong = total - correct

        summary = QLabel(f"🎯 对了 {correct} 句，❌ 错了 {wrong} 句")
        summary.setObjectName("resultSummary")
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(summary)

        if wrong > 0:
            hint = QLabel("以下诗句需要加强记忆：")
            hint.setObjectName("resultHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(hint)

            for idx, is_ok in enumerate(self.test_results):
                if not is_ok:
                    card = QFrame()
                    card.setObjectName("reciteCardMistake")
                    cl = QVBoxLayout(card)
                    cl.setContentsMargins(20, 10, 20, 10)

                    ll = QLabel(self.original_lines[idx])
                    ll.setObjectName("reciteLineDone")
                    ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(ll)

                    ml = QLabel(f"你的输入：{self.test_inputs[idx]}")
                    ml.setObjectName("userInput")
                    ml.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    cl.addWidget(ml)

                    if idx < len(self.original_meanings):
                        meaning = QLabel(self.original_meanings[idx])
                        meaning.setObjectName("reciteResultMeaning")
                        meaning.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        cl.addWidget(meaning)

                    self.card_layout.addWidget(card)

        self.card_layout.addStretch()

        if wrong > 0:
            review_btn = QPushButton("🔁 复习错句")
            review_btn.setObjectName("secondaryBtn")
            review_btn.setMinimumHeight(44)
            review_btn.clicked.connect(self._review_mistakes)
            self.bottom_bar.addWidget(review_btn)
            self.bottom_bar.addSpacing(10)

        repeat_btn = QPushButton("🔁 再背一次")
        repeat_btn.setObjectName("secondaryBtn")
        repeat_btn.setMinimumHeight(44)
        repeat_btn.clicked.connect(self._start_from_beginning)

        finish_btn = QPushButton("✅ 完成学习")
        finish_btn.setObjectName("primaryBtn")
        finish_btn.setMinimumHeight(44)
        finish_btn.clicked.connect(self._finish_poem)

        self.bottom_bar.addWidget(repeat_btn)
        self.bottom_bar.addWidget(finish_btn)
        self.bottom_bar.addStretch()

    def _start_from_beginning(self):
        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False
        self.current_segment = 0
        self._build_segments()
        self._show_segment_read()

    # ─── Review Mistakes ────────────────────────────────────────────

    def _review_mistakes(self):
        mistake_indices = [i for i, ok in enumerate(self.test_results) if not ok]
        original_lines = self.card_manager.get_card_content_lines(self.cards[self.current_index].id)
        original_meanings = self.card_manager.get_card_meaning_lines(self.cards[self.current_index].id)

        self.original_lines = [original_lines[i] for i in mistake_indices]
        self.original_meanings = [original_meanings[i] if i < len(original_meanings) else "" for i in mistake_indices]

        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self.is_verification = False
        self._build_segments()
        self.current_segment = 0
        self.phase = "read"
        self._show_segment_read()

    # ─── Finish ─────────────────────────────────────────────────────

    def _finish_poem(self):
        if self.current_index < len(self.cards):
            card = self.cards[self.current_index]
            progress = self.db.get_progress(card.id)
            if progress is None:
                progress = self.scheduler.init_progress(card.id)
            new_progress = self.scheduler.review(progress, 3, 0)
            self.db.init_progress(card.id)
            self.db.save_progress(new_progress)
            short_progress = self.scheduler.schedule_short_review(new_progress, SHORT_REVIEW_MINUTES)
            self.db.save_progress(short_progress)
            today_str = date.today().isoformat()
            self.db.update_daily_stats(today_str, new_count=1, review_count=1, correct=1, total=1)

        self.current_index += 1
        if self.current_index < len(self.cards):
            self._load_card(self.current_index)
        else:
            QMessageBox.information(
                self, "完成",
                f"今日学习已完成！\n{SHORT_REVIEW_MINUTES} 分钟后会安排一次短复习，记得回来 ~"
            )
            self._emit_closed()
            self.close()

    # ─── Theme ──────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet("""
            * {
                font-family: -apple-system, 'Helvetica Neue', 'SF Pro Display',
                             'Segoe UI', Roboto, sans-serif;
            }
            QWidget#studyBg { background-color: #F5F5F7; }
            QScrollArea#studyScroll { background-color: #F5F5F7; border: none; }
            QWidget#studyScrollContent { background-color: #F5F5F7; }
            QLabel#phaseLabel {
                font-size: 13px; font-weight: 600; color: #007AFF;
                background-color: #E8F0FE; border-radius: 8px; padding: 4px 14px;
            }
            QPushButton#topNavBtn {
                background-color: transparent; color: #007AFF; border: none;
                font-size: 13px; font-weight: 500;
            }
            QPushButton#topNavBtn:hover { text-decoration: underline; }
            QLabel#studyTitle { font-size: 18px; font-weight: 700; color: #1D1D1F; }
            QLabel#studyAuthor { font-size: 12px; color: #86868B; padding-top: 5px; }
            QLabel#studyProgress { font-size: 12px; color: #86868B; font-weight: 500; }
            QProgressBar#studyProgressBar { background-color: #E8E8ED; border: none; border-radius: 2px; }
            QProgressBar#studyProgressBar::chunk { background-color: #007AFF; border-radius: 2px; }
            QLabel#readIntro { font-size: 12px; color: #86868B; padding: 6px 0 14px 0; }
            QFrame#meaningPair { background-color: #FFFFFF; border: 1px solid #E8E8ED; border-radius: 12px; margin: 3px 0; }
            QLabel#readLine { font-size: 17px; font-weight: 600; color: #1D1D1F; }
            QLabel#readMeaning { font-size: 13px; color: #86868B; padding-left: 4px; }
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
            QLabel#reciteLineNum { font-size: 12px; color: #86868B; padding: 6px; font-weight: 500; }
            QFrame#reciteCard { background-color: #FFFFFF; border: 1px solid #E8E8ED; border-radius: 14px; margin: 2px 0; }
            QFrame#reciteCardCurrent { background-color: #FFFFFF; border: 2px solid #007AFF; border-radius: 14px; margin: 2px 0; }
            QFrame#reciteCardMistake { background-color: #FFF5F5; border: 1px solid #FFD0D0; border-radius: 14px; margin: 2px 0; }
            QLabel#reciteLineDone { font-size: 16px; color: #1D1D1F; padding: 2px; font-weight: 500; }
            QLabel#reciteTag { font-size: 11px; padding: 1px; font-weight: 500; }
            QLabel#mistakeTag { font-size: 11px; color: #FF3B30; padding: 1px; font-weight: 500; }
            QPushButton#backBtn {
                background-color: transparent; color: #86868B; border: 1px solid #D2D2D7;
                border-radius: 12px; font-size: 13px; font-weight: 500; padding: 12px 20px;
            }
            QPushButton#backBtn:hover { border-color: #007AFF; color: #007AFF; }
            QPushButton#hintBtn {
                background-color: #FFF3E0; color: #E65100; border: 1px solid #FFB74D;
                border-radius: 12px; font-size: 13px; font-weight: 500; padding: 10px 18px;
            }
            QPushButton#hintBtn:hover { background-color: #FFE0B2; border-color: #FF9800; }
            QLabel#resultSummary { font-size: 18px; font-weight: 700; color: #1D1D1F; padding: 16px; }
            QLabel#resultHint { font-size: 13px; color: #86868B; padding: 4px 0 12px 0; font-weight: 500; }
            QLabel#reciteResultMeaning { font-size: 13px; color: #86868B; padding-top: 2px; }
            QLabel#userInput { font-size: 13px; color: #FF9500; padding-top: 2px; font-style: italic; }
            QLabel#correctLine { font-size: 15px; color: #34C759; padding-top: 2px; font-weight: 600; }
            QLabel#typingHint { font-size: 15px; color: #FF9500; padding: 4px 0 0 0; font-weight: 600; }
            QLineEdit#typingInput {
                background-color: #F5F5F7; border: 2px solid #D2D2D7; border-radius: 10px;
                font-size: 18px; padding: 12px 16px; color: #1D1D1F;
                min-height: 24px;
            }
            QLineEdit#typingInput:focus { border-color: #007AFF; background-color: #FFFFFF; }
            QLineEdit#typingInput::placeholder { color: #C7C7CC; }
        """)
