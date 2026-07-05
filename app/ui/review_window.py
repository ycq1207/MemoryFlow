# -*- coding: utf-8 -*-
"""Review window for spaced-repetition review session."""

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


TYPING_THRESHOLD = 0.75


class ReviewWindow(QWidget):

    closed = Signal()

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.card_manager = CardManager(db)
        self.scheduler = FSRSScheduler()
        self.reviews: list[dict] = []
        self.current_index = 0
        self._closed_emitted = False

        self.card_type = "poem"
        self.original_lines: list[str] = []
        self.original_meanings: list[str] = []
        self.current_test_index = 0
        self.test_results: list[bool] = []
        self.test_inputs: list[str] = []
        self.hint_visible = False
        self.hints_used = False

        self.input_fields: list[QLineEdit] = []
        self.hint_labels: list[QLabel] = []

        self._build_ui()
        self._apply_theme()

    def _build_ui(self):
        self.setWindowTitle("复习模式")
        self.resize(780, 620)
        self.setMinimumSize(520, 440)
        self.setWindowFlags(Qt.WindowType.Window)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content = QWidget()
        content.setObjectName("reviewBg")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 16, 28, 16)
        layout.setSpacing(12)

        top_bar = QHBoxLayout()
        self.phase_label = QLabel("📝 复习模式")
        self.phase_label.setObjectName("phaseLabel")
        top_bar.addWidget(self.phase_label)
        top_bar.addStretch()
        self.btn_back = QPushButton("← 返回主页")
        self.btn_back.setObjectName("topNavBtn")
        self.btn_back.clicked.connect(self._confirm_exit)
        top_bar.addWidget(self.btn_back)
        layout.addLayout(top_bar)

        header = QHBoxLayout()
        self.title_label = QLabel("")
        self.title_label.setObjectName("reviewTitle")
        self.author_label = QLabel("")
        self.author_label.setObjectName("reviewAuthor")
        self.progress_label = QLabel("0/0")
        self.progress_label.setObjectName("reviewProgress")
        header.addWidget(self.title_label)
        header.addSpacing(8)
        header.addWidget(self.author_label)
        header.addStretch()
        header.addWidget(self.progress_label)
        layout.addLayout(header)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("reviewProgressBar")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMinimumHeight(4)
        self.progress_bar.setMaximumHeight(4)
        layout.addWidget(self.progress_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setObjectName("reviewScroll")
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("reviewScrollContent")
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
            self,
            "确认退出",
            "确定要停止复习并返回主页吗？\n本次复习进度不会保存。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._emit_closed()
            self.close()

    def closeEvent(self, event):
        self._emit_closed()
        event.accept()

    # ── Load Reviews ──────────────────────────────────────────────────

    def load_reviews(self):
        self._closed_emitted = False
        self.reviews = self.card_manager.get_due_reviews(limit=50)
        if not self.reviews:
            QMessageBox.information(self, "完成", "暂无待复习的内容！去学习新内容吧。")
            self.close()
            return
        self.current_index = 0
        self._load_review(0)

    def _load_review(self, index: int):
        if index >= len(self.reviews):
            self._finish()
            return

        item = self.reviews[index]
        card = item["card"]
        self.card_type = card.card_type
        self.title_label.setText(card.title)
        if card.card_type == "poem":
            self.author_label.setText(f"{card.dynasty} · {card.author}")
        else:
            self.author_label.setText(CARD_TYPES.get(card.card_type, card.card_type))

        self.progress_label.setText(f"{index + 1}/{len(self.reviews)}")
        self.progress_bar.setValue(int(index / len(self.reviews) * 100) if self.reviews else 0)

        self.original_lines = self.card_manager.get_card_content_lines(card.id)
        self.original_meanings = self.card_manager.get_card_meaning_lines(card.id)
        self.current_test_index = 0
        self.test_results = []
        self.test_inputs = []
        self.hint_visible = False
        self.hints_used = False

        self._show_review()

    # ── Review Test Phase ─────────────────────────────────────────────

    def _show_review(self):
        self._clear_card()
        self._clear_all_bars()

        total = len(self.original_lines)
        done = self.current_test_index

        if done >= total:
            self._review_done()
            return

        type_labels = {
            "poem": "📝 复习默写",
            "question": "📝 复习问答",
            "vocabulary": "📝 复习单词",
            "article": "📝 复习段落",
            "formula": "📝 复习公式",
        }
        self.phase_label.setText(type_labels.get(self.card_type, "📝 复习"))

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
                card.setObjectName("reviewCardCurrent")
            elif i < len(self.test_results) and self.test_results[i]:
                card.setObjectName("reviewCard")
            elif i < len(self.test_results) and not self.test_results[i]:
                card.setObjectName("reviewCardMistake")
            else:
                card.setObjectName("reviewCard")

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
                    question_label = QLabel(f"❓ {self.original_lines[i]}")
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
                input_field.returnPressed.connect(self._submit_review)
                self.input_fields.append(input_field)
                cl.addWidget(input_field)

                hint_label = QLabel()
                hint_label.setObjectName("typingHint")
                hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                hint_label.setVisible(False)
                self.hint_labels.append(hint_label)
                cl.addWidget(hint_label)

            self.card_layout.addWidget(card)

        self.card_layout.addStretch()

        if done > 0:
            btn_back = QPushButton("◀ 上一句")
            btn_back.setObjectName("backBtn")
            btn_back.clicked.connect(self._prev_review)
            self.middle_bar.addWidget(btn_back)
            self.middle_bar.addSpacing(12)

        btn_hint = QPushButton("💡 显示提示" if not self.hint_visible else "💡 隐藏提示")
        btn_hint.setObjectName("hintBtn")
        btn_hint.clicked.connect(self._toggle_hint)
        self.middle_bar.addWidget(btn_hint)
        self.middle_bar.addSpacing(12)

        btn_submit = QPushButton("✅ 提交")
        btn_submit.setObjectName("primaryBtn")
        btn_submit.setMinimumHeight(44)
        btn_submit.clicked.connect(self._submit_review)

        self.middle_bar.addStretch()
        self.middle_bar.addWidget(btn_submit)
        self.middle_bar.addStretch()

        if self.hint_visible:
            self._apply_hint()

    def _toggle_hint(self):
        self.hint_visible = not self.hint_visible
        if self.hint_visible:
            self.hints_used = True
        self._apply_hint()
        self._show_review()

    def _apply_hint(self):
        if not self.hint_labels:
            return
        done = self.current_test_index
        if done < len(self.original_lines):
            first_char = self.original_lines[done][0] if self.original_lines[done] else ""
            for label in self.hint_labels:
                if self.hint_visible:
                    label.setText(f"提示：{first_char} ___。")
                else:
                    label.setText("")
                label.setVisible(self.hint_visible)

    def _submit_review(self):
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
        self._show_review()

    def _prev_review(self):
        if self.current_test_index > 0:
            self.current_test_index -= 1
            if self.test_results:
                self.test_results.pop()
            if self.test_inputs:
                self.test_inputs.pop()
            self._show_review()

    # ── Review Done ───────────────────────────────────────────────────

    def _review_done(self):
        self._clear_card()
        self._clear_all_bars()

        total = len(self.original_lines)
        correct = sum(self.test_results)
        wrong = total - correct
        self.progress_bar.setValue(100)

        if wrong > 0 and self.hints_used:
            self.phase_label.setText("✅ 无提示验证")
            title = QLabel("你使用了提示，请再默写一遍（无提示）")
            title.setObjectName("resultSummary")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(title)
            self.card_layout.addStretch()

            btn = QPushButton("开始无提示默写 →")
            btn.setObjectName("primaryBtn")
            btn.setMinimumHeight(48)
            btn.clicked.connect(self._start_verify)
            self.bottom_bar.addStretch()
            self.bottom_bar.addWidget(btn)
            self.bottom_bar.addStretch()
            return

        self.phase_label.setText("🎉 复习结果")
        summary = QLabel(f"🎉 对了 {correct} 句，❌ 错了 {wrong} 句")
        summary.setObjectName("resultSummary")
        summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(summary)

        if wrong > 0:
            hint = QLabel("以下内容需要加强记忆：")
            hint.setObjectName("resultHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(hint)

            for idx, is_ok in enumerate(self.test_results):
                if not is_ok:
                    card = QFrame()
                    card.setObjectName("reviewCardMistake")
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
            restudy_btn = QPushButton("🔄 重新背诵")
            restudy_btn.setObjectName("secondaryBtn")
            restudy_btn.setMinimumHeight(44)
            restudy_btn.clicked.connect(self._restudy)
            self.bottom_bar.addWidget(restudy_btn)
            self.bottom_bar.addSpacing(10)

        finish_btn = QPushButton("✅ 完成复习")
        finish_btn.setObjectName("primaryBtn")
        finish_btn.setMinimumHeight(44)
        finish_btn.clicked.connect(self._finish_current)

        self.bottom_bar.addWidget(finish_btn)
        self.bottom_bar.addStretch()

    def _start_verify(self):
        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self._show_review()

    # ── Re-study ──────────────────────────────────────────────────────

    def _restudy(self):
        self._clear_card()
        self._clear_all_bars()

        self.phase_label.setText("📖 重新学习")
        self.progress_bar.setValue(0)

        title = QLabel("请重新阅读以下内容：")
        title.setObjectName("resultSummary")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_layout.addWidget(title)

        for i, line in enumerate(self.original_lines):
            pair = QFrame()
            pair.setObjectName("meaningPair")
            pl = QVBoxLayout(pair)
            pl.setContentsMargins(16, 10, 16, 10)
            pl.setSpacing(4)

            ll = QLabel(f"<b>{line}</b>")
            ll.setObjectName("readLine")
            pl.addWidget(ll)

            if i < len(self.original_meanings) and self.original_meanings[i]:
                ml = QLabel(self.original_meanings[i])
                ml.setObjectName("readMeaning")
                pl.addWidget(ml)

            self.card_layout.addWidget(pair)

        self.card_layout.addStretch()

        btn = QPushButton("✅ 我已记住，开始默写 →")
        btn.setObjectName("primaryBtn")
        btn.setMinimumHeight(48)
        btn.clicked.connect(self._start_retest)
        self.bottom_bar.addStretch()
        self.bottom_bar.addWidget(btn)
        self.bottom_bar.addStretch()

    def _start_retest(self):
        self.test_results = []
        self.test_inputs = []
        self.current_test_index = 0
        self.hint_visible = False
        self.hints_used = False
        self._show_review()

    # ── Finish ────────────────────────────────────────────────────────

    def _finish_current(self):
        if self.current_index < len(self.reviews):
            item = self.reviews[self.current_index]
            card = item["card"]
            progress = self.db.get_progress(card.id)
            if progress is None:
                progress = self.scheduler.init_progress(card.id)

            correct = sum(self.test_results)
            total = len(self.test_results)
            if total > 0:
                accuracy = correct / total
                if accuracy >= 0.9:
                    rating = 4
                elif accuracy >= 0.7:
                    rating = 3
                elif accuracy >= 0.5:
                    rating = 2
                else:
                    rating = 1
            else:
                rating = 1

            old_d = progress.difficulty
            old_s = progress.stability
            old_r = progress.retrievability
            last_review = progress.last_review
            if last_review:
                try:
                    elapsed = (date.today() - date.fromisoformat(last_review)).days
                except ValueError:
                    elapsed = 0
            else:
                elapsed = 0

            new_progress = self.scheduler.review(progress, rating, max(0, elapsed))
            self.db.save_progress(new_progress)

            history = StudyHistory(
                card_id=card.id,
                rating=rating,
                stability_before=old_s,
                difficulty_before=old_d,
                retrievability_before=old_r,
                stability_after=new_progress.stability,
                difficulty_after=new_progress.difficulty,
                elapsed_days=elapsed,
                reviewed_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            self.db.add_study_history(history)

            today_str = date.today().isoformat()
            correct_count = 1 if rating >= 3 else 0
            self.db.update_daily_stats(
                today_str,
                new_count=0,
                review_count=1,
                correct=correct_count,
                total=1
            )

        self.current_index += 1
        self._load_review(self.current_index)

    def _finish(self):
        self.progress_bar.setValue(100)
        QMessageBox.information(self, "完成", "今日复习已完成！")
        self._emit_closed()
        self.close()

    # ── Theme ─────────────────────────────────────────────────────────

    def _apply_theme(self):
        self.setStyleSheet("""
            * {
                font-family: -apple-system, 'Helvetica Neue', 'SF Pro Display',
                             'Segoe UI', Roboto, sans-serif;
            }
            QWidget#reviewBg { background-color: #F5F5F7; }
            QScrollArea#reviewScroll { background-color: #F5F5F7; border: none; }
            QWidget#reviewScrollContent { background-color: #F5F5F7; }
            QLabel#phaseLabel {
                font-size: 13px; font-weight: 600; color: #007AFF;
                background-color: #E8F0FE; border-radius: 8px; padding: 4px 14px;
            }
            QPushButton#topNavBtn {
                background-color: transparent; color: #007AFF; border: none;
                font-size: 13px; font-weight: 500;
            }
            QPushButton#topNavBtn:hover { text-decoration: underline; }
            QLabel#reviewTitle { font-size: 18px; font-weight: 700; color: #1D1D1F; }
            QLabel#reviewAuthor { font-size: 12px; color: #86868B; padding-top: 5px; }
            QLabel#reviewProgress { font-size: 12px; color: #86868B; font-weight: 500; }
            QProgressBar#reviewProgressBar { background-color: #E8E8ED; border: none; border-radius: 2px; }
            QProgressBar#reviewProgressBar::chunk { background-color: #007AFF; border-radius: 2px; }
            QLabel#reciteLineNum { font-size: 12px; color: #86868B; padding: 6px; font-weight: 500; }
            QFrame#reviewCard { background-color: #FFFFFF; border: 1px solid #E8E8ED; border-radius: 14px; margin: 2px 0; }
            QFrame#reviewCardCurrent { background-color: #FFFFFF; border: 2px solid #007AFF; border-radius: 14px; margin: 2px 0; }
            QFrame#reviewCardMistake { background-color: #FFF5F5; border: 1px solid #FFD0D0; border-radius: 14px; margin: 2px 0; }
            QLabel#reciteLineDone { font-size: 16px; color: #1D1D1F; padding: 2px; font-weight: 500; }
            QLabel#reciteTag { font-size: 11px; padding: 1px; font-weight: 500; }
            QLabel#mistakeTag { font-size: 11px; color: #FF3B30; padding: 1px; font-weight: 500; }
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
            QFrame#meaningPair { background-color: #FFFFFF; border: 1px solid #E8E8ED; border-radius: 12px; margin: 3px 0; }
            QLabel#readLine { font-size: 17px; font-weight: 600; color: #1D1D1F; }
            QLabel#readMeaning { font-size: 13px; color: #86868B; padding-left: 4px; }
        """)
