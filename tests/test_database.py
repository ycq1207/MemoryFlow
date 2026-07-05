import sys
import os
import json
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Database
from app.core.scheduler import FSRSScheduler
from app.models.poem import Card, Progress, StudyHistory


class TestDatabase(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import app.config
        self._orig_db = app.config.DATABASE_FILE
        self._orig_poems = app.config.POEMS_DIR
        app.config.DATABASE_FILE = os.path.join(self.tmpdir, "test.db")
        app.config.POEMS_DIR = os.path.join(self.tmpdir, "empty_poems")
        os.makedirs(app.config.POEMS_DIR, exist_ok=True)
        self.db = Database()

    def tearDown(self):
        self.db.close()
        import app.config
        app.config.DATABASE_FILE = self._orig_db
        app.config.POEMS_DIR = self._orig_poems
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_card(self):
        card_id = self.db.add_card("jingyesi", "libai", "tang", '["chuangqianmingyueguang"]')
        self.assertGreater(card_id, 0)

    def test_get_card(self):
        cid = self.db.add_card("jingyesi", "libai", "tang", '["chuangqianmingyueguang"]')
        card = self.db.get_card(cid)
        self.assertIsNotNone(card)
        self.assertEqual(card.title, "jingyesi")
        self.assertEqual(card.author, "libai")

    def test_get_all_cards(self):
        self.db.add_card("shi1", "zuozhe1", "chao1", '["hang1"]')
        self.db.add_card("shi2", "zuozhe2", "chao2", '["hang2"]')
        cards = self.db.get_all_cards()
        self.assertGreaterEqual(len(cards), 2)

    def test_card_count(self):
        initial = self.db.get_card_count()
        self.db.add_card("xinshi", "xinzuo", "xinchao", '["xinhang"]')
        self.assertEqual(self.db.get_card_count(), initial + 1)

    def test_progress_save_and_get(self):
        cid = self.db.add_card("ceshishi", "ceshi", "ceshichao", '["ceshihang"]')
        self.db.init_progress(cid)
        p = Progress(card_id=cid, difficulty=6.0, stability=2.0, review_count=3)
        self.db.save_progress(p)
        loaded = self.db.get_progress(cid)
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(loaded.difficulty, 6.0)
        self.assertAlmostEqual(loaded.stability, 2.0)
        self.assertEqual(loaded.review_count, 3)

    def test_progress_upsert(self):
        cid = self.db.add_card("ceshishi", "ceshi", "ceshichao", '["ceshihang"]')
        self.db.init_progress(cid)
        p1 = Progress(card_id=cid, difficulty=5.0, stability=1.0, review_count=1)
        self.db.save_progress(p1)
        p2 = Progress(card_id=cid, difficulty=4.0, stability=3.0, review_count=2)
        self.db.save_progress(p2)
        loaded = self.db.get_progress(cid)
        self.assertAlmostEqual(loaded.difficulty, 4.0)
        self.assertEqual(loaded.review_count, 2)

    def test_study_history(self):
        cid = self.db.add_card("ceshishi", "ceshi", "ceshichao", '["ceshihang"]')
        h = StudyHistory(
            card_id=cid, rating=3,
            stability_before=0.4, difficulty_before=5.0,
            retrievability_before=1.0, stability_after=2.0,
            difficulty_after=4.5, elapsed_days=0,
            reviewed_at="2026-01-01 12:00:00"
        )
        self.db.add_study_history(h)
        history = self.db.get_study_history(cid)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].rating, 3)

    def test_daily_stats(self):
        self.db.update_daily_stats("2026-07-01", new_count=1, review_count=2, correct=2, total=3)
        stats = self.db.get_daily_stats("2026-07-01")
        self.assertIsNotNone(stats)
        self.assertEqual(stats.new_count, 1)
        self.assertEqual(stats.review_count, 2)

    def test_daily_stats_upsert(self):
        self.db.update_daily_stats("2026-07-02", new_count=1, review_count=1, correct=0, total=1)
        self.db.update_daily_stats("2026-07-02", new_count=1, review_count=1, correct=0, total=1)
        stats = self.db.get_daily_stats("2026-07-02")
        self.assertEqual(stats.new_count, 2)
        self.assertEqual(stats.correct_count, 0)

    def test_settings(self):
        self.db.set_setting("theme", "dark")
        self.assertEqual(self.db.get_setting("theme"), "dark")
        self.db.set_setting("theme", "light")
        self.assertEqual(self.db.get_setting("theme"), "light")

    def test_settings_nonexistent(self):
        self.assertIsNone(self.db.get_setting("nonexistent"))

    def test_new_cards(self):
        initial = len(self.db.get_new_cards(limit=999))
        cid = self.db.add_card("xinshi", "xin", "xin", '["xinhang"]')
        new = self.db.get_new_cards(limit=999)
        self.assertEqual(len(new), initial + 1)

    def test_new_cards_excludes_learned(self):
        cid = self.db.add_card("yixueshi", "zuozhe", "chaodai", '["hang"]')
        self.db.init_progress(cid)
        p = Progress(card_id=cid, review_count=1)
        self.db.save_progress(p)
        new = self.db.get_new_cards(limit=10)
        ids = [c.id for c in new]
        self.assertNotIn(cid, ids)

    def test_mastered_count(self):
        cid = self.db.add_card("zhangwoshi", "zuozhe", "chaodai", '["hang"]')
        self.db.init_progress(cid)
        p = Progress(card_id=cid, stability=25.0, review_count=5)
        self.db.save_progress(p)
        count = self.db.get_mastered_count()
        self.assertGreaterEqual(count, 1)

    def test_heatmap_data(self):
        from datetime import date as _date
        today = _date.today().isoformat()
        self.db.update_daily_stats(today, new_count=1, review_count=0, correct=0, total=1)
        data = self.db.get_heatmap_data(365)
        self.assertIn(today, data)
        self.assertEqual(data[today], 1)

    def test_cards_by_type(self):
        self.db.add_card("gushi1", "zuozhe1", "tang", '["hang1"]', card_type="poem")
        self.db.add_card("timu1", "", "", '["wenti"]', '["daan"]', card_type="question")
        poems = self.db.get_cards_by_type("poem")
        questions = self.db.get_cards_by_type("question")
        self.assertEqual(len(poems), 1)
        self.assertEqual(len(questions), 1)


if __name__ == "__main__":
    unittest.main()
