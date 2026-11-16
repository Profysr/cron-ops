"""Cross-profile schedule validation: overlap/warning/none, the */5-vs-daily
common-horizon regression, DST fall-back folds, Toronto pin, --at determinism,
recommendation, naive-once resolution, script-job context, catch_up key.
"""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from tests import support
from plugin import validate as v

UTC = timezone.utc
KHI = ZoneInfo("Asia/Karachi")
YYZ = ZoneInfo("America/Toronto")
AT = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)  # 17:00 Karachi, 07:00 Toronto


def _job(job_id, expr, zone=None, **over):
    job = {"id": job_id, "name": f"job {job_id}", "enabled": True, "no_agent": False,
           "schedule": {"kind": "cron", "expr": expr}}
    if zone is not None:
        job["timezone"] = zone
    job.update(over)
    return job


class ValidateLevelsTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")  # zone: Asia/Karachi

    def test_identical_schedule_is_overlap(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]
        res = v.validate("0 9 * * *", [self.profile], None, AT)
        self.assertEqual(len(res["conflicts"]), 1)
        c = res["conflicts"][0]
        self.assertEqual(c["level"], "overlap")
        self.assertEqual(c["gap_minutes"], 0.0)
        self.assertEqual(c["job_id"], "jobaaaaaaa1")

    def test_forty_minute_gap_is_warning(self):
        # windows: candidate 08:00-08:10, job 08:30-08:40 -> 20 min gap
        support.JOBS["default"] = [_job("jobaaaaaaa1", "30 8 * * *")]
        res = v.validate("0 8 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"][0]["level"], "warning")
        self.assertEqual(res["conflicts"][0]["gap_minutes"], 20.0)

    def test_far_apart_is_clean(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 15 * * *")]
        res = v.validate("0 8 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"], [])
        self.assertEqual(res["context"], [])

    def test_paused_and_error_jobs_never_conflict(self):
        support.JOBS["default"] = [
            _job("jobaaaaaaa1", "0 9 * * *", enabled=False),
            _job("jobaaaaaaa2", "0 9 * * *", state="error"),
        ]
        res = v.validate("0 9 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"], [])


class CommonHorizonTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_star5_candidate_vs_daily_job_detected(self):
        # 3x3 fixed comparison: candidate's next 3 runs (5-min steps) never touch the
        # daily job's next 3 (tomorrow onward) -> missed. Common horizon must catch it.
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]
        res = v.validate("*/5 * * * *", [self.profile], None, AT)
        self.assertEqual([c["level"] for c in res["conflicts"]], ["overlap"])

    def test_occurrence_preview_still_three_entries(self):
        support.JOBS["default"] = []
        res = v.validate("*/5 * * * *", [self.profile], None, AT)
        self.assertEqual(len(res["occurrences"]), 3)
        self.assertEqual(res["occurrences"][0], "2026-11-16T12:05:00+00:00")


class DstTest(support.StubbedTestCase):
    def test_fall_back_second_fold_picks_later_pass(self):
        # 2026-11-01 Toronto falls back 02:00 EDT -> 01:00 EST; wall 01:30 repeats
        # (05:30Z EDT, 06:30Z EST). From 06:15Z the next "30 1" must be the later
        # 06:30Z pass, never the already-past 05:30Z fold.
        at = datetime(2026, 11, 1, 6, 15, tzinfo=UTC)
        occ = v.cron_occurrences("30 1 * * *", at, YYZ, 2)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-01T06:30:00+00:00",
            "2026-11-02T06:30:00+00:00",
        ])
        self.assertTrue(all(o > at for o in occ))

    def test_fall_back_starting_at_repeated_instant_goes_to_next_day(self):
        at = datetime(2026, 11, 1, 6, 30, tzinfo=UTC)  # exactly the 01:30 EST pass
        occ = v.cron_occurrences("30 1 * * *", at, YYZ, 2)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-11-02T06:30:00+00:00",
            "2026-11-03T06:30:00+00:00",
        ])

    def test_spring_forward_nonexistent_wall_never_in_the_past(self):
        # 2026-03-08 Toronto: wall 02:30 does not exist (02:00 -> 03:00). Core's
        # fold-0-first rule resolves it to 07:30Z (03:30 EDT local). The invariant
        # that matters: strictly after `at`, strictly increasing.
        at = datetime(2026, 3, 8, 6, 0, tzinfo=UTC)  # 01:00 EST
        occ = v.cron_occurrences("30 2 * * *", at, YYZ, 2)
        self.assertEqual([o.isoformat() for o in occ], [
            "2026-03-08T07:30:00+00:00",
            "2026-03-09T06:30:00+00:00",
        ])
        self.assertTrue(all(o > at for o in occ))


class TorontoPinTest(support.StubbedTestCase):
    def test_job_timezone_overrides_profile_zone(self):
        # profile zone Karachi but job pinned to Toronto: job fires 06:00 Toronto
        # (11:00Z EST) while the candidate lands on 06:00 Karachi (01:00Z) -> clean.
        self.profile = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 6 * * *", zone="America/Toronto")]
        res = v.validate("0 6 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"], [])

    def test_candidate_profile_selects_interpreter_zone(self):
        self.profile = support.add_profile("default")
        toronto = support.add_profile("torontop", zone=YYZ)
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 6 * * *", zone="America/Toronto")]
        # candidate interpreted in Toronto too -> both 06:00 EST = 11:00Z -> overlap
        res = v.validate("0 6 * * *", [self.profile], toronto, AT)
        self.assertEqual(res["conflicts"][0]["level"], "overlap")
        self.assertEqual(res["conflicts"][0]["job_at"], "2026-11-17T11:00:00+00:00")


class DeterminismTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]

    def test_same_at_same_result(self):
        r1 = v.validate("*/5 * * * *", [self.profile], None, AT)
        r2 = v.validate("*/5 * * * *", [self.profile], None, AT)
        self.assertEqual(json.dumps(r1, sort_keys=True), json.dumps(r2, sort_keys=True))
        self.assertEqual(r1["at"], AT.isoformat())

    def test_bad_expression_raises_value_error(self):
        with self.assertRaises(ValueError):
            v.validate("not a cron", [self.profile], None, AT)


class RecommendationTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_free_slot_recommends_first_occurrence(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 15 * * *")]
        res = v.validate("0 8 * * *", [self.profile], None, AT)
        self.assertEqual(res["recommendation"], res["occurrences"][0])

    def test_blocked_slot_reports_none(self):
        # daily job at the same hour blocks every +/-45 min step
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]
        res = v.validate("0 9 * * *", [self.profile], None, AT)
        self.assertIsNone(res["recommendation"])


class NaiveOnceTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_naive_run_at_resolves_in_schedule_zone(self):
        job = {"id": "oncejob0001", "enabled": True,
               "schedule": {"kind": "once", "run_at": "2026-11-17T09:00:00"}}
        occ = v.job_occurrences(job, KHI, AT)
        self.assertEqual([o.isoformat() for o in occ], ["2026-11-17T04:00:00+00:00"])

    def test_naive_run_at_falls_back_to_at_zone(self):
        job = {"id": "oncejob0001", "enabled": True,
               "schedule": {"kind": "once", "run_at": "2026-11-17T09:00:00"}}
        occ = v.job_occurrences(job, None, AT)
        self.assertEqual([o.isoformat() for o in occ], ["2026-11-17T09:00:00+00:00"])

    def test_past_run_at_yields_nothing(self):
        job = {"id": "oncejob0001", "enabled": True,
               "schedule": {"kind": "once", "run_at": "2020-01-01T09:00:00+00:00"}}
        self.assertEqual(v.job_occurrences(job, KHI, AT), [])

    def test_once_job_conflicts_in_validate(self):
        support.JOBS["default"] = [{
            "id": "oncejob0001", "name": "once", "enabled": True, "no_agent": False,
            "schedule": {"kind": "once", "run_at": "2026-11-17T09:00:00"},
        }]
        # naive 09:00 resolves in the profile zone (Karachi) -> 04:00Z; candidate
        # 09:00 Karachi lands on the same instant -> overlap
        res = v.validate("0 9 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"][0]["level"], "overlap")
        self.assertEqual(res["conflicts"][0]["job_at"], "2026-11-17T04:00:00+00:00")


class ContextAndCatchUpTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_script_job_is_context_never_conflict(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "30 8 * * *", no_agent=True)]
        res = v.validate("0 8 * * *", [self.profile], None, AT)
        self.assertEqual(res["conflicts"], [])
        self.assertEqual(len(res["context"]), 1)
        self.assertEqual(res["context"][0]["job_id"], "jobaaaaaaa1")
        self.assertEqual(res["context"][0]["gap_minutes"], 20.0)

    def test_catch_up_missed_is_reported_true(self):
        support.JOBS["default"] = []
        res = v.validate("0 8 * * *", [self.profile], None, AT)
        self.assertIs(res["catch_up_missed"], True)


class ExpandCapTest(support.StubbedTestCase):
    def test_expand_stops_at_cap(self):
        target = datetime(2100, 1, 1, tzinfo=UTC)
        start = datetime(2026, 1, 1, tzinfo=UTC)

        def fn(count):
            return [start + v.STEP * k for k in range(count)]

        out = fn(3)
        grown = v._expand(fn, target, out, 3)
        self.assertLessEqual(len(grown), v._MAX_OCCURRENCES)

    def test_window_gap_overlap_is_none(self):
        a0, a1 = AT, AT + v.DEFAULT_DURATION
        b0, b1 = AT + v.STEP, AT + v.STEP + v.DEFAULT_DURATION
        self.assertIsNone(v.window_gap(a0, a1, b0, b1))
        # non-intersecting: b starts 5 min after a ends
        self.assertEqual(v.window_gap(a0, a1, b1, b1 + v.DEFAULT_DURATION),
                         v.STEP)
