import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.scheduler import FSRSScheduler
from app.models.poem import Progress


class TestFSRSScheduler(unittest.TestCase):

    def test_init_progress(self):
        p = FSRSScheduler.init_progress(card_id=1)
        self.assertEqual(p.card_id, 1)
        self.assertEqual(p.difficulty, 5.0)
        self.assertAlmostEqual(p.stability, 0.4)
        self.assertEqual(p.review_count, 0)
        self.assertIsNone(p.last_review)
        self.assertEqual(p.lapses, 0)

    def test_retrievability(self):
        self.assertAlmostEqual(FSRSScheduler.retrievability(7.0, 0.0), 1.0)
        self.assertAlmostEqual(FSRSScheduler.retrievability(7.0, 7.0), 0.5)
        self.assertAlmostEqual(FSRSScheduler.retrievability(1.0, 1.0), 0.5)
        self.assertAlmostEqual(FSRSScheduler.retrievability(0.01, 0.0), 1.0)

    def test_retrievability_decays(self):
        r1 = FSRSScheduler.retrievability(10.0, 1.0)
        r2 = FSRSScheduler.retrievability(10.0, 5.0)
        r3 = FSRSScheduler.retrievability(10.0, 10.0)
        self.assertGreater(r1, r2)
        self.assertGreater(r2, r3)

    def test_next_interval(self):
        interval = FSRSScheduler.next_interval(7.0, 0.9)
        self.assertGreater(interval, 0)

    def test_review_good_increases_stability(self):
        p = FSRSScheduler.init_progress(1)
        new_p = FSRSScheduler.review(p, 3, 0)
        self.assertGreater(new_p.stability, p.stability)
        self.assertEqual(new_p.review_count, 1)
        self.assertIsNotNone(new_p.next_review)

    def test_review_easy_increases_stability_more(self):
        p = FSRSScheduler.init_progress(1)
        good = FSRSScheduler.review(p, 3, 3)
        easy = FSRSScheduler.review(p, 4, 3)
        self.assertGreaterEqual(easy.stability, good.stability)

    def test_review_again_decreases_stability(self):
        p = FSRSScheduler.init_progress(1)
        good = FSRSScheduler.review(p, 3, 0)
        again = FSRSScheduler.review(p, 1, 0)
        self.assertLess(again.stability, good.stability)
        self.assertGreater(again.lapses, p.lapses)

    def test_review_hard_moderate(self):
        p = FSRSScheduler.init_progress(1)
        good = FSRSScheduler.review(p, 3, 0)
        hard = FSRSScheduler.review(p, 2, 0)
        self.assertGreaterEqual(good.stability, hard.stability)

    def test_difficulty_stays_in_range(self):
        p = FSRSScheduler.init_progress(1)
        for _ in range(20):
            p = FSRSScheduler.review(p, 1, 1)
        self.assertGreaterEqual(p.difficulty, 1.0)
        self.assertLessEqual(p.difficulty, 10.0)

    def test_stability_never_negative(self):
        p = FSRSScheduler.init_progress(1)
        for _ in range(10):
            p = FSRSScheduler.review(p, 1, 0)
        self.assertGreater(p.stability, 0)

    def test_review_with_elapsed_days(self):
        p = FSRSScheduler.init_progress(1)
        p2 = FSRSScheduler.review(p, 3, 5)
        self.assertGreater(p2.stability, 0)
        self.assertIsNotNone(p2.next_review)


if __name__ == "__main__":
    unittest.main()
