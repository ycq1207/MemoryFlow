import math
from datetime import datetime, date, timedelta
from typing import Optional

from app.models.poem import Progress


class FSRSScheduler:
    """
    FSRS-5 (Free Spaced Repetition Scheduler v5)

    Core parameters (w[0]..w[16]):
      w[0]  = initial stability (days)
      w[1]  = initial difficulty
      w[2]  = initial difficulty offset
      w[3]  = 0  (unused in simplified version)
      w[4]  = 0
      w[5]  = 0.94  -> difficulty decrease for "good"
      w[6]  = 0.86  -> difficulty decrease for "easy"
      w[7]  = 0.01  -> difficulty increase for "hard"
      w[8]  = 1.49  -> recall stability scaling factor
      w[9]  = 0.14  -> recall stability exponent (negative)
      w[10] = 0.94  -> recall stability retrievability exponent
      w[11] = 2.18  -> forget stability multiplier
      w[12] = 0.05  -> forget stability difficulty exponent (negative)
      w[13] = 0.34  -> forget stability exponent
      w[14] = 1.26  -> forget stability retrievability exponent
      w[15] = 0.29  -> difficulty delta for R
      w[16] = 2.61  -> difficulty delta offset

    Rating scale (SM-2 like):
      1 = forgotten / again
      2 = hard
      3 = good
      4 = easy
    """

    # FSRS-5 optimized default parameters
    w = [
        0.4,    # w[0]
        5.0,    # w[1]
        5.0,    # w[2]
        0.0,    # w[3]
        0.0,    # w[4]
        0.94,   # w[5]
        0.86,   # w[6]
        0.01,   # w[7]
        1.49,   # w[8]
        0.14,   # w[9]
        0.94,   # w[10]
        2.18,   # w[11]
        0.05,   # w[12]
        0.34,   # w[13]
        1.26,   # w[14]
        0.29,   # w[15]
        2.61    # w[16]
    ]

    @staticmethod
    def init_progress(card_id: int) -> Progress:
        return Progress(
            card_id=card_id,
            difficulty=FSRSScheduler.w[1],
            stability=FSRSScheduler.w[0],
            retrievability=1.0,
            review_count=0,
            last_review=None,
            next_review=date.today().isoformat(),
            lapses=0
        )

    @staticmethod
    def retrievability(stability: float, elapsed_days: float) -> float:
        if stability <= 0:
            return 0.0
        return (1.0 + elapsed_days / stability) ** -1.0

    @staticmethod
    def next_interval(stability: float, desired_r: float = 0.9) -> float:
        if stability <= 0:
            return 0.0
        return stability * ((1.0 / desired_r) - 1.0)

    @staticmethod
    def _clamp(value: float, lo: float = 1.0, hi: float = 10.0) -> float:
        return max(lo, min(hi, value))

    @staticmethod
    def review(progress: Progress, rating: int, elapsed_days: float) -> Progress:
        d = progress.difficulty
        s = progress.stability
        r = FSRSScheduler.retrievability(s, elapsed_days)

        w = FSRSScheduler.w

        if rating >= 3:
            factor = 1.0 + math.exp(w[8]) * (11.0 - d) * (s ** -w[9]) * (math.exp(w[10] * r) - 1.0)
            s_new = s * factor
        else:
            s_new = (
                w[11]
                * (d ** -w[12])
                * ((s + 1.0) ** w[13] - 1.0)
                * math.exp(w[14] * (1.0 - r))
            )

        s_new = max(0.01, s_new)

        if rating == 1:
            d_prime = d + w[15] - (w[15] / (1.0 - w[16])) * (1.0 - r)
        elif rating == 2:
            d_prime = d - w[15] * r + w[16]
        elif rating == 3:
            d_prime = d - w[15] * r
        else:
            d_prime = d - w[15] * r + w[16] - (w[16] - w[15]) * r

        d_new = FSRSScheduler._clamp(d_prime, 1.0, 10.0)

        today = date.today()
        interval_days = FSRSScheduler.next_interval(s_new, 0.9)
        next_review_date = today + timedelta(days=max(1, round(interval_days)))

        return Progress(
            card_id=progress.card_id,
            difficulty=d_new,
            stability=s_new,
            retrievability=1.0,
            review_count=progress.review_count + 1,
            last_review=today.isoformat(),
            next_review=next_review_date.isoformat(),
            lapses=progress.lapses + (1 if rating < 3 else 0)
        )

    @staticmethod
    def schedule_short_review(progress: Progress, minutes: int = 15) -> Progress:
        now = datetime.now()
        short_time = now + timedelta(minutes=minutes)
        return Progress(
            card_id=progress.card_id,
            difficulty=progress.difficulty,
            stability=progress.stability,
            retrievability=progress.retrievability,
            review_count=progress.review_count,
            last_review=progress.last_review,
            next_review=short_time.strftime("%Y-%m-%d %H:%M:%S"),
            lapses=progress.lapses
        )
