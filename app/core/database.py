import json
import sqlite3
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import app.config
from app.models.poem import Card, Progress, StudyHistory, DailyStats

logger = logging.getLogger(__name__)


class Database:

    def __init__(self):
        self.db_path = Path(app.config.DATABASE_FILE)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.Error as e:
            logger.error(f"Database connection failed: {e}")
            raise
        self.create_tables()
        self._migrate()
        self.import_cards_from_json()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cards(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                dynasty TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT '[]',
                card_type TEXT NOT NULL DEFAULT 'poem',
                created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress(
                card_id INTEGER PRIMARY KEY,
                difficulty REAL NOT NULL DEFAULT 5.0,
                stability REAL NOT NULL DEFAULT 0.4,
                retrievability REAL NOT NULL DEFAULT 1.0,
                review_count INTEGER NOT NULL DEFAULT 0,
                last_review TEXT,
                next_review TEXT,
                lapses INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS study_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                stability_before REAL NOT NULL,
                difficulty_before REAL NOT NULL,
                retrievability_before REAL NOT NULL,
                stability_after REAL NOT NULL,
                difficulty_after REAL NOT NULL,
                elapsed_days REAL NOT NULL,
                reviewed_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(card_id) REFERENCES cards(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats(
                date TEXT NOT NULL,
                new_count INTEGER NOT NULL DEFAULT 0,
                review_count INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                total_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(date)
            )
        """)
        self.conn.commit()

    def _migrate(self):
        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT card_type FROM cards LIMIT 1")
        except sqlite3.OperationalError:
            try:
                cursor.execute("ALTER TABLE cards ADD COLUMN card_type TEXT NOT NULL DEFAULT 'poem'")
                self.conn.commit()
            except sqlite3.OperationalError:
                pass

        try:
            cursor.execute("SELECT poem_id FROM progress LIMIT 1")
            cursor.execute("ALTER TABLE progress RENAME COLUMN poem_id TO card_id")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("SELECT poem_id FROM study_history LIMIT 1")
            cursor.execute("ALTER TABLE study_history RENAME COLUMN poem_id TO card_id")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poems'")
            if cursor.fetchone():
                cursor.execute("ALTER TABLE poems RENAME TO cards")
                self.conn.commit()
        except sqlite3.OperationalError:
            pass

    # ----- Cards -----

    def add_card(self, title: str, author: str, dynasty: str,
                 content: str, meaning: str = "[]", card_type: str = "poem") -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO cards(title,author,dynasty,content,meaning,card_type) VALUES(?,?,?,?,?,?)",
                (title, author, dynasty, content, meaning, card_type)
            )
            self.conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Failed to add card '{title}': {e}")
            return -1

    def get_all_cards(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cards ORDER BY id")
        return [self._row_to_card(r) for r in cursor.fetchall()]

    def get_cards_by_type(self, card_type: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE card_type=? ORDER BY id", (card_type,))
        return [self._row_to_card(r) for r in cursor.fetchall()]

    def get_card(self, card_id: int) -> Optional[Card]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id=?", (card_id,))
        row = cursor.fetchone()
        return self._row_to_card(row) if row else None

    def get_card_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cards")
        return cursor.fetchone()[0]

    def get_card_count_by_type(self, card_type: str) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM cards WHERE card_type=?", (card_type,))
        return cursor.fetchone()[0]

    def delete_card(self, card_id: int) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM cards WHERE id=?", (card_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to delete card {card_id}: {e}")
            return False

    def update_card(self, card_id: int, title: str, author: str, dynasty: str,
                    content: str, meaning: str, card_type: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE cards SET
                    title=?, author=?, dynasty=?, content=?, meaning=?, card_type=?
                WHERE id=?
            """, (title, author, dynasty, content, meaning, card_type, card_id))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to update card {card_id}: {e}")
            return False

    # ----- Progress -----

    def get_progress(self, card_id: int) -> Optional[Progress]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM progress WHERE card_id=?", (card_id,))
        row = cursor.fetchone()
        return self._row_to_progress(row) if row else None

    def get_all_progress(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM progress")
        return [self._row_to_progress(r) for r in cursor.fetchall()]

    def save_progress(self, p: Progress):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO progress(
                    card_id,difficulty,stability,retrievability,
                    review_count,last_review,next_review,lapses
                ) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(card_id) DO UPDATE SET
                    difficulty=excluded.difficulty,
                    stability=excluded.stability,
                    retrievability=excluded.retrievability,
                    review_count=excluded.review_count,
                    last_review=excluded.last_review,
                    next_review=excluded.next_review,
                    lapses=excluded.lapses
            """, (
                p.card_id, p.difficulty, p.stability, p.retrievability,
                p.review_count, p.last_review, p.next_review, p.lapses
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to save progress for card {p.card_id}: {e}")

    def init_progress(self, card_id: int):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO progress(card_id) VALUES(?)",
            (card_id,)
        )
        self.conn.commit()

    # ----- Study History -----

    def add_study_history(self, h: StudyHistory):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO study_history(
                    card_id,rating,stability_before,difficulty_before,
                    retrievability_before,stability_after,difficulty_after,
                    elapsed_days,reviewed_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                h.card_id, h.rating,
                h.stability_before, h.difficulty_before,
                h.retrievability_before, h.stability_after,
                h.difficulty_after, h.elapsed_days, h.reviewed_at
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to add study history: {e}")

    def get_study_history(self, card_id: int) -> list:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM study_history WHERE card_id=? ORDER BY reviewed_at",
            (card_id,)
        )
        return [self._row_to_history(r) for r in cursor.fetchall()]

    def get_recent_history(self, days: int = 30) -> list:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM study_history
            WHERE reviewed_at >= datetime('now', ?)
            ORDER BY reviewed_at DESC
        """, (f"-{days} days",))
        return [self._row_to_history(r) for r in cursor.fetchall()]

    # ----- Daily Stats -----

    def update_daily_stats(self, date_str: str, new_count: int = 0,
                           review_count: int = 0, correct: int = 0, total: int = 0):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO daily_stats(date,new_count,review_count,correct_count,total_count)
                VALUES(?,?,?,?,?)
                ON CONFLICT(date) DO UPDATE SET
                    new_count = new_count + excluded.new_count,
                    review_count = review_count + excluded.review_count,
                    correct_count = correct_count + excluded.correct_count,
                    total_count = total_count + excluded.total_count
            """, (date_str, new_count, review_count, correct, total))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update daily stats: {e}")

    def get_daily_stats(self, date_str: str) -> Optional[DailyStats]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM daily_stats WHERE date=?", (date_str,))
        row = cursor.fetchone()
        return self._row_to_stats(row) if row else None

    def get_stats_range(self, start_date: str, end_date: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM daily_stats WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date)
        )
        return [self._row_to_stats(r) for r in cursor.fetchall()]

    # ----- Settings -----

    def get_setting(self, key: str) -> Optional[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

    def set_setting(self, key: str, value: str):
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value)
        )
        self.conn.commit()

    # ----- Review Queue -----

    def get_due_reviews(self, limit: int = 20) -> list:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today = date.today().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, pr.difficulty, pr.stability, pr.retrievability,
                   pr.review_count, pr.next_review, pr.lapses
            FROM cards c
            INNER JOIN progress pr ON pr.card_id = c.id
            WHERE pr.next_review IS NULL
               OR pr.next_review <= ?
               OR (length(pr.next_review) = 10 AND pr.next_review <= ?)
            ORDER BY pr.next_review ASC NULLS FIRST
            LIMIT ?
        """, (now, today, limit))
        return [self._row_to_review_item(r) for r in cursor.fetchall()]

    def get_new_cards(self, limit: int = 3, card_type: Optional[str] = None) -> list:
        cursor = self.conn.cursor()
        if card_type:
            cursor.execute("""
                SELECT c.*
                FROM cards c
                LEFT JOIN progress pr ON pr.card_id = c.id
                WHERE pr.card_id IS NULL AND c.card_type=?
                ORDER BY c.id
                LIMIT ?
            """, (card_type, limit))
        else:
            cursor.execute("""
                SELECT c.*
                FROM cards c
                LEFT JOIN progress pr ON pr.card_id = c.id
                WHERE pr.card_id IS NULL
                ORDER BY c.id
                LIMIT ?
            """, (limit,))
        return [self._row_to_card(r) for r in cursor.fetchall()]

    # ----- Statistics -----

    def get_total_studied(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT card_id) FROM study_history")
        return cursor.fetchone()[0]

    def get_total_reviews(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM study_history")
        return cursor.fetchone()[0]

    def get_mastered_count(self) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM progress WHERE stability >= 21"
        )
        return cursor.fetchone()[0]

    def get_streak_days(self) -> int:
        streak = 0
        d = date.today()
        while True:
            stats = self.get_daily_stats(d.isoformat())
            if stats and stats.total_count > 0:
                streak += 1
                d -= timedelta(days=1)
            else:
                break
        return streak

    def get_heatmap_data(self, days: int = 365) -> dict:
        start = (date.today() - timedelta(days=days)).isoformat()
        end = date.today().isoformat()
        stats_list = self.get_stats_range(start, end)
        data = {}
        for s in stats_list:
            data[s.date] = s.total_count
        return data

    # ----- JSON Import -----

    def import_cards_from_json(self):
        try:
            json_files = sorted(Path(app.config.POEMS_DIR).glob("*.json"))
        except OSError as e:
            logger.warning(f"Failed to list card files: {e}")
            return
        for fp in json_files:
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Skipping {fp.name}: {e}")
                continue
            title = data.get("title", fp.stem)
            author = data.get("author", "")
            dynasty = data.get("dynasty", "")
            card_type = data.get("card_type", data.get("category", "poem"))
            content_list = data.get("content", [])
            content = json.dumps(content_list, ensure_ascii=False)
            meaning_list = data.get("meaning", [])
            meaning = json.dumps(meaning_list, ensure_ascii=False)
            try:
                cursor = self.conn.cursor()
                cursor.execute(
                    "SELECT id FROM cards WHERE title=? AND author=?",
                    (title, author)
                )
                if cursor.fetchone() is None:
                    self.add_card(title, author, dynasty, content, meaning, card_type)
                else:
                    cursor.execute(
                        "UPDATE cards SET meaning=?, card_type=? WHERE title=? AND author=?",
                        (meaning, card_type, title, author)
                    )
            except sqlite3.Error as e:
                logger.warning(f"Failed to import {title}: {e}")

    # ----- Helpers -----

    def _row_to_card(self, row) -> Card:
        return Card(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            dynasty=row["dynasty"],
            content=row["content"],
            meaning=row["meaning"],
            card_type=row["card_type"],
            created_at=row["created_at"]
        )

    def _row_to_progress(self, row) -> Progress:
        return Progress(
            card_id=row["card_id"],
            difficulty=row["difficulty"],
            stability=row["stability"],
            retrievability=row["retrievability"],
            review_count=row["review_count"],
            last_review=row["last_review"],
            next_review=row["next_review"],
            lapses=row["lapses"]
        )

    def _row_to_history(self, row) -> StudyHistory:
        return StudyHistory(
            id=row["id"],
            card_id=row["card_id"],
            rating=row["rating"],
            stability_before=row["stability_before"],
            difficulty_before=row["difficulty_before"],
            retrievability_before=row["retrievability_before"],
            stability_after=row["stability_after"],
            difficulty_after=row["difficulty_after"],
            elapsed_days=row["elapsed_days"],
            reviewed_at=row["reviewed_at"]
        )

    def _row_to_stats(self, row) -> DailyStats:
        return DailyStats(
            date=row["date"],
            new_count=row["new_count"],
            review_count=row["review_count"],
            correct_count=row["correct_count"],
            total_count=row["total_count"]
        )

    def _row_to_review_item(self, row) -> dict:
        card = self._row_to_card(row)
        return {
            "card": card,
            "difficulty": row["difficulty"],
            "stability": row["stability"],
            "retrievability": row["retrievability"],
            "review_count": row["review_count"],
            "next_review": row["next_review"],
            "lapses": row["lapses"]
        }

    def close(self):
        self.conn.close()
