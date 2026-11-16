"""Next-occurrence math: */15 steps, hour ranges, day-of-week, intervals, bad exprs."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from tests import support  # noqa: F401  (installs Hermes stubs)
from plugin import validate as v

UTC = timezone.utc
KHI = ZoneInfo("Asia/Karachi")


class CronOccurrencesTest(support.StubbedTestCase):
    def test_15_minute_steps_from_mid_interval(self):
        # 12:03 UTC = 17:03 Karachi; next */15 wall clocks are 17:15, 17:30, 17:45.
        at = datetime(2026, 11, 16, 12, 3, tzinfo=UTC)
        occ = v.cron_occurrences("*/15 * * * *", at, KHI, 3)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-16T12:15:00+00:00",
            "2026-11-16T12:30:00+00:00",
            "2026-11-16T12:45:00+00:00",
        ])

    def test_hour_range(self):
        # 10:00 UTC = 15:00 Karachi; range 9-17 fires 16:00, 17:00 today, then 09:00 tomorrow.
        at = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
        occ = v.cron_occurrences("0 9-17 * * *", at, KHI, 3)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-16T11:00:00+00:00",
            "2026-11-16T12:00:00+00:00",
            "2026-11-17T04:00:00+00:00",
        ])

    def test_day_of_week(self):
        # Monday 2026-11-16 15:00 Karachi: 09:00 Monday already passed -> next Monday.
        at = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)
        occ = v.cron_occurrences("0 9 * * 1", at, KHI, 1)
        self.assertEqual(occ[0].isoformat(), "2026-11-23T04:00:00+00:00")

    def test_occurrences_are_utc_and_strictly_increasing(self):
        at = datetime(2026, 11, 16, 12, 3, tzinfo=UTC)
        occ = v.cron_occurrences("*/7 * * * *", at, KHI, 5)
        self.assertTrue(all(o.tzinfo is not None for o in occ))
        self.assertTrue(all(b > a for a, b in zip(occ, occ[1:])))
        self.assertTrue(all(o > at for o in occ))

    def test_malformed_expression_raises_value_error(self):
        with self.assertRaises(ValueError):
            v.cron_occurrences("not a cron at all", datetime(2026, 11, 16, tzinfo=UTC), KHI)


class IntervalOccurrencesTest(support.StubbedTestCase):
    def test_anchor_before_start_steps_forward(self):
        at = datetime(2026, 11, 16, 12, 10, tzinfo=UTC)
        anchor = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
        occ = v.interval_occurrences(30, at, anchor, 3)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-16T12:30:00+00:00",
            "2026-11-16T13:00:00+00:00",
            "2026-11-16T13:30:00+00:00",
        ])

    def test_anchor_after_start_starts_at_anchor(self):
        at = datetime(2026, 11, 16, 12, 10, tzinfo=UTC)
        anchor = datetime(2026, 11, 16, 13, 0, tzinfo=UTC)
        occ = v.interval_occurrences(30, at, anchor, 2)
        self.assertEqual(occ[0], anchor)
        self.assertEqual(occ[1], anchor + timedelta(minutes=30))

    def test_job_occurrences_dispatches_interval_kind(self):
        at = datetime(2026, 11, 16, 12, 10, tzinfo=UTC)
        job = {"id": "int1", "schedule": {"kind": "interval", "minutes": 45},
               "last_run_at": "2026-11-16T12:00:00+00:00"}
        occ = v.job_occurrences(job, KHI, at, 3)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-16T12:45:00+00:00",
            "2026-11-16T13:30:00+00:00",
            "2026-11-16T14:15:00+00:00",
        ])
