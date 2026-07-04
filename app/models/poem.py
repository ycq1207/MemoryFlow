from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


CARD_TYPES = {
    "poem": "古诗",
    "article": "文章",
    "question": "题目",
    "vocabulary": "单词",
    "formula": "公式",
}


@dataclass
class Card:
    id: int = 0
    title: str = ""
    author: str = ""
    dynasty: str = ""
    content: str = ""
    meaning: str = ""
    card_type: str = "poem"
    created_at: str = ""


@dataclass
class Progress:
    card_id: int = 0
    difficulty: float = 5.0
    stability: float = 0.4
    retrievability: float = 1.0
    review_count: int = 0
    last_review: Optional[str] = None
    next_review: Optional[str] = None
    lapses: int = 0


@dataclass
class StudyHistory:
    id: int = 0
    card_id: int = 0
    rating: int = 0
    stability_before: float = 0.0
    difficulty_before: float = 0.0
    retrievability_before: float = 0.0
    stability_after: float = 0.0
    difficulty_after: float = 0.0
    elapsed_days: float = 0.0
    reviewed_at: str = ""


@dataclass
class DailyStats:
    date: str = ""
    new_count: int = 0
    review_count: int = 0
    correct_count: int = 0
    total_count: int = 0

    @property
    def accuracy(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.correct_count / self.total_count
