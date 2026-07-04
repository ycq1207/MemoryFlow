import sys
import os
import json
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Database
from app.core.poem_manager import CardManager


class TestCardManager(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        import app.config
        self._orig_db = app.config.DATABASE_FILE
        self._orig_poems = app.config.POEMS_DIR
        app.config.DATABASE_FILE = os.path.join(self.tmpdir, "test.db")
        app.config.POEMS_DIR = os.path.join(self.tmpdir, "empty_poems")
        os.makedirs(app.config.POEMS_DIR, exist_ok=True)
        self.db = Database()
        self.cm = CardManager(self.db)

    def tearDown(self):
        self.db.close()
        import app.config
        app.config.DATABASE_FILE = self._orig_db
        app.config.POEMS_DIR = self._orig_poems
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_all_cards(self):
        self.db.add_card("shi1", "zuozhe1", "chao1", '["hang1"]')
        self.db.add_card("shi2", "zuozhe2", "chao2", '["hang2"]')
        cards = self.cm.get_all_cards()
        self.assertGreaterEqual(len(cards), 2)

    def test_get_card(self):
        cid = self.db.add_card("jingyesi", "libai", "tang", '["chuangqianmingyueguang"]')
        card = self.cm.get_card(cid)
        self.assertIsNotNone(card)
        self.assertEqual(card.title, "jingyesi")

    def test_get_card_content_lines(self):
        cid = self.db.add_card("jingyesi", "libai", "tang", '["chuangqianmingyueguang","yishidishangshuang"]')
        lines = self.cm.get_card_content_lines(cid)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "chuangqianmingyueguang")

    def test_get_card_meaning_lines(self):
        cid = self.db.add_card("jingyesi", "libai", "tang", '["a"]', '["yisi1","yisi2"]')
        meanings = self.cm.get_card_meaning_lines(cid)
        self.assertEqual(len(meanings), 2)
        self.assertEqual(meanings[0], "yisi1")

    def test_get_card_content_nonexistent(self):
        lines = self.cm.get_card_content_lines(9999)
        self.assertEqual(lines, [])

    def test_get_card_count(self):
        initial = self.cm.get_card_count()
        self.db.add_card("xinshi", "xin", "xin", '["xinhang"]')
        self.assertEqual(self.cm.get_card_count(), initial + 1)

    def test_export_to_json(self):
        cid = self.db.add_card("daochushi", "daochu", "daochuchao", '["hang1"]', '["yisi1"]')
        out = self.cm.export_to_json(cid)
        self.assertIsNotNone(out)
        self.assertTrue(out.exists())
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["title"], "daochushi")
        self.assertEqual(data["content"], ["hang1"])
        self.assertEqual(data["meaning"], ["yisi1"])

    def test_export_nonexistent(self):
        result = self.cm.export_to_json(9999)
        self.assertIsNone(result)

    def test_get_new_cards(self):
        cid = self.db.add_card("xinshi", "xin", "xin", '["xinhang"]')
        new = self.cm.get_new_cards(limit=5)
        self.assertIsInstance(new, list)

    def test_get_due_reviews(self):
        due = self.cm.get_due_reviews(limit=10)
        self.assertIsInstance(due, list)

    def test_get_cards_by_type(self):
        self.db.add_card("gushi1", "zuozhe1", "tang", '["hang1"]', card_type="poem")
        self.db.add_card("timu1", "", "", '["wenti"]', '["daan"]', card_type="question")
        poems = self.cm.get_cards_by_type("poem")
        questions = self.cm.get_cards_by_type("question")
        self.assertEqual(len(poems), 1)
        self.assertEqual(len(questions), 1)


if __name__ == "__main__":
    unittest.main()
