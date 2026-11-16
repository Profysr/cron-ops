"""Execution history + usage correlation (plan Chunk 3): last-10 ordering, the
finished-at join, missed/in-flight handling, unmatched reporting, complexity buckets."""
from tests import support
from plugin import metrics

JOB = "metricsjob01"


def _exec(eid, claimed, finished=None, status="completed", **over):
    row = {"id": eid, "job_id": JOB, "source": "builtin", "status": status,
           "claimed_at": claimed, "started_at": claimed, "finished_at": finished,
           "error": None, "delivery_outcome": "delivered"}
    row.update(over)
    return row


def _usage(ts, tokens, **over):
    rec = {"ts": ts, "job_id": JOB, "fire_id": "f" * 32,
           "prompt_tokens": tokens - 10, "completion_tokens": 10,
           "total_tokens": tokens, "response_silent": False,
           "deliver_target": "test", "model": "test/model-x",
           "duration_ms": 60000, "error": None}
    rec.update(over)
    return rec


class CorrelationTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_correlates_by_finish_instant_not_claim(self):
        # The live misattribution shape: E2's claim is nearer U1 than its own finish is.
        support.EXECUTIONS[JOB] = [
            _exec("exec00000002", "2026-10-24T12:32:27+00:00", "2026-10-24T12:35:30+00:00"),
            _exec("exec00000001", "2026-10-24T12:30:12+00:00", "2026-10-24T12:31:22+00:00"),
        ]
        support.set_usage("default", [
            _usage("2026-10-24T12:31:22Z", 1111),  # finish of exec00000001
            _usage("2026-10-24T12:35:28Z", 2222),  # finish of exec00000002
        ])
        res = metrics.last_executions(self.profile, JOB)
        by_id = {r["id"]: r for r in res["runs"]}
        self.assertEqual(by_id["exec00000002"]["total_tokens"], 2222)  # was 1111 pre-fix
        self.assertEqual(by_id["exec00000001"]["total_tokens"], 1111)
        for r in res["runs"]:
            self.assertEqual(r["usage_match"]["method"], "finished_at")
            self.assertEqual(r["usage_match"]["confidence"], "exact")
            self.assertLessEqual(r["usage_match"]["delta_s"], 5)
        self.assertEqual(res["unmatched_usage_records"], 0)

    def test_missed_row_never_consumes_usage(self):
        support.EXECUTIONS[JOB] = [
            _exec("execmissed01", "2026-10-24T12:31:10+00:00", status="missed"),
            _exec("exec00000001", "2026-10-24T12:30:12+00:00", "2026-10-24T12:31:22+00:00"),
        ]
        support.set_usage("default", [_usage("2026-10-24T12:31:22Z", 1111)])
        res = metrics.last_executions(self.profile, JOB)
        by_id = {r["id"]: r for r in res["runs"]}
        self.assertIsNone(by_id["execmissed01"]["usage_match"])
        self.assertIsNone(by_id["execmissed01"]["total_tokens"])
        self.assertEqual(by_id["exec00000001"]["total_tokens"], 1111)
        self.assertEqual(res["unmatched_usage_records"], 0)

    def test_unmatched_records_are_counted_not_silent(self):
        support.EXECUTIONS[JOB] = [
            _exec("exec00000002", "2026-10-24T12:32:27+00:00", "2026-10-24T12:35:30+00:00"),
        ]
        support.set_usage("default", [
            _usage("2026-10-24T12:31:22Z", 1111),   # belongs to a run outside the window
            _usage("2026-10-24T12:35:28Z", 2222),
        ])
        res = metrics.last_executions(self.profile, JOB)
        self.assertEqual(res["unmatched_usage_records"], 1)
        # no executions at all -> every record reported unmatched
        support.EXECUTIONS[JOB] = []
        res = metrics.last_executions(self.profile, JOB)
        self.assertEqual(res["runs"], [])
        self.assertEqual(res["unmatched_usage_records"], 2)

    def test_claimed_anchor_is_always_heuristic(self):
        support.EXECUTIONS[JOB] = [
            _exec("execnofinish1", "2026-10-24T12:31:00+00:00", finished=None),
        ]
        support.set_usage("default", [_usage("2026-10-24T12:31:05Z", 500)])
        res = metrics.last_executions(self.profile, JOB)
        match = res["runs"][0]["usage_match"]
        self.assertEqual(match["method"], "claimed_at")
        self.assertEqual(match["confidence"], "heuristic")  # never presented as exact
        self.assertEqual(res["runs"][0]["total_tokens"], 500)

    def test_in_flight_row_never_matches(self):
        support.EXECUTIONS[JOB] = [
            _exec("execrunning01", "2026-10-24T12:31:00+00:00", status="running"),
        ]
        support.set_usage("default", [_usage("2026-10-24T12:31:05Z", 500)])
        res = metrics.last_executions(self.profile, JOB)
        self.assertIsNone(res["runs"][0]["usage_match"])
        self.assertEqual(res["unmatched_usage_records"], 1)

    def test_order_and_limit_pass_through_newest_first(self):
        # ledger contract: rows come back newest-first, so store them that way
        support.EXECUTIONS[JOB] = [
            _exec(f"exec{i:08d}", f"2026-10-24T12:{30 + i:02d}:00+00:00")
            for i in range(11, -1, -1)
        ]
        support.set_usage("default", [])
        res = metrics.last_executions(self.profile, JOB, limit=10)
        self.assertEqual(len(res["runs"]), 10)
        self.assertEqual([r["id"] for r in res["runs"]],
                         [f"exec{i:08d}" for i in range(11, 1, -1)])
        res3 = metrics.last_executions(self.profile, JOB, limit=3)
        self.assertEqual(len(res3["runs"]), 3)

    def test_unknown_cpu_ram_and_duration_from_ledger(self):
        support.EXECUTIONS[JOB] = [
            _exec("exec00000001", "2026-10-24T12:30:00+00:00",
                  "2026-10-24T12:31:00+00:00"),
        ]
        support.set_usage("default", [])
        row = metrics.last_executions(self.profile, JOB)["runs"][0]
        self.assertEqual(row["duration_ms"], 60_000)
        self.assertIsNone(row["cpu_percent"])
        self.assertIsNone(row["ram_mb"])


class ComplexityTest(support.StubbedTestCase):
    def test_token_thresholds(self):
        cases = [(9_999, "trivial"), (10_000, "light"), (99_999, "light"),
                 (100_000, "moderate"), (499_999, "moderate"), (500_000, "heavy"),
                 (500_001, "heavy")]
        for tokens, expected in cases:
            with self.subTest(tokens=tokens):
                self.assertEqual(metrics.complexity(tokens, None, False), expected)

    def test_no_agent_uses_duration_only(self):
        cases = [(9_999, "trivial"), (10_000, "light"), (59_999, "light"),
                 (60_000, "moderate"), (299_999, "moderate"), (300_000, "heavy")]
        for ms, expected in cases:
            with self.subTest(ms=ms):
                self.assertEqual(metrics.complexity(None, ms, True), expected)
        # tokens ignored for no-agent runs even when present
        self.assertEqual(metrics.complexity(999_999, 5_000, True), "trivial")

    def test_missing_data_is_unknown(self):
        self.assertEqual(metrics.complexity(None, None, False), "unknown")
        self.assertEqual(metrics.complexity(None, None, True), "unknown")


class SummarizeTest(support.StubbedTestCase):
    def test_summary_shape_and_unmatched(self):
        rows = [
            {"status": "completed", "total_tokens": 100, "duration_ms": 1000,
             "model": "m1", "complexity": "trivial", "usage_match": None},
            {"status": "failed", "total_tokens": 300, "duration_ms": 3000,
             "model": "m2", "complexity": "trivial", "usage_match": None},
        ]
        s = metrics.summarize(rows, unmatched_usage_records=7)
        self.assertEqual(s["runs"], 2)
        self.assertEqual(s["statuses"], {"completed": 1, "failed": 1})
        self.assertEqual(s["total_tokens"], 400)
        self.assertEqual(s["avg_tokens"], 200)
        self.assertEqual(s["avg_duration_ms"], 2000)
        self.assertEqual(s["models"], ["m1", "m2"])
        self.assertEqual(s["unmatched_usage_records"], 7)
        self.assertIsNone(s["cpu_percent"])
        self.assertIsNone(s["ram_mb"])

    def test_empty_summary_keeps_unmatched(self):
        s = metrics.summarize([], unmatched_usage_records=3)
        self.assertEqual(s["runs"], 0)
        self.assertEqual(s["unmatched_usage_records"], 3)
        self.assertEqual(s["complexity"], "unknown")
