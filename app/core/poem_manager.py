import json
from pathlib import Path
from typing import Optional

import app.config
from app.core.database import Database
from app.models.poem import Card


class CardManager:

    def __init__(self, db: Database):
        self.db = db

    def get_all_cards(self) -> list[Card]:
        return self.db.get_all_cards()

    def get_cards_by_type(self, card_type: str) -> list[Card]:
        return self.db.get_cards_by_type(card_type)

    def get_card(self, card_id: int) -> Optional[Card]:
        return self.db.get_card(card_id)

    def get_card_content_lines(self, card_id: int) -> list[str]:
        card = self.db.get_card(card_id)
        if not card:
            return []
        try:
            return json.loads(card.content)
        except (json.JSONDecodeError, TypeError):
            return [line.strip() for line in card.content.split("\n") if line.strip()]

    def get_card_meaning_lines(self, card_id: int) -> list[str]:
        card = self.db.get_card(card_id)
        if not card or not card.meaning:
            return []
        try:
            return json.loads(card.meaning)
        except (json.JSONDecodeError, TypeError):
            return [line.strip() for line in card.meaning.split("\n") if line.strip()]

    def get_card_count(self) -> int:
        return self.db.get_card_count()

    def get_card_count_by_type(self, card_type: str) -> int:
        return self.db.get_card_count_by_type(card_type)

    def delete_card(self, card_id: int) -> bool:
        return self.db.delete_card(card_id)

    def update_card(self, card_id: int, title: str, author: str, dynasty: str,
                    content: str, meaning: str, card_type: str) -> bool:
        return self.db.update_card(
            card_id, title, author, dynasty, content, meaning, card_type
        )

    def get_due_reviews(self, limit: int = 20) -> list[dict]:
        return self.db.get_due_reviews(limit)

    def get_new_cards(self, limit: int = 3, card_type: Optional[str] = None) -> list[Card]:
        return self.db.get_new_cards(limit, card_type)

    def export_to_json(self, card_id: int, output_path: Optional[Path] = None) -> Optional[Path]:
        card = self.db.get_card(card_id)
        if not card:
            return None
        try:
            content_list = json.loads(card.content)
        except (json.JSONDecodeError, TypeError):
            content_list = [card.content]
        try:
            meaning_list = json.loads(card.meaning)
        except (json.JSONDecodeError, TypeError):
            meaning_list = []
        data = {
            "title": card.title,
            "author": card.author,
            "dynasty": card.dynasty,
            "card_type": card.card_type,
            "content": content_list,
            "meaning": meaning_list
        }
        if output_path is None:
            output_path = Path(app.config.POEMS_DIR) / f"{card.title}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return output_path

    def backup_all(self, output_dir: Optional[Path] = None) -> int:
        if output_dir is None:
            output_dir = Path(app.config.POEMS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for card in self.get_all_cards():
            safe_title = card.title.replace("/", "_").replace("\\", "_")
            out = output_dir / f"{safe_title}.json"
            try:
                self.export_to_json(card.id, out)
                count += 1
            except OSError as e:
                pass
        return count
