"""argparse coverage, --json dispatch for every subcommand, limit clamp, exit codes.

Rich table paths are intentionally untested (rich is not a test dependency);
every dispatch test drives the --json branch.
"""
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest import mock

from tests import support
from plugin import cli
from plugin import manage


def _parser():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    cli.setup_cli(parser)
    return parser


def _run(argv):
    args = _parser().parse_args(argv)
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.command(args)
    return code, buf.getvalue()


def _job(job_id, expr="0 9 * * *", **over):
    job = {"id": job_id, "name": f"job {job_id}", "enabled": True,
           "schedule": {"kind": "cron", "expr": expr}}
    job.update(over)
    return job


class ArgparseTest(unittest.TestCase):
    def test_every_subcommand_accepts_json_flag(self):
        cases = [
            ["list"], ["metrics", "j1"], ["history", "j1"],
            ["validate", "0 9 * * *"], ["inspect", "j1"], ["pause", "j1"],
            ["resume", "j1"], ["delete", "j1"], ["doctor"],
        ]
        for argv in cases:
            with self.subTest(argv=argv):
                args = _parser().parse_args(argv + ["--json"])
                self.assertTrue(args.json_out)

    def test_history_limit_defaults_to_ten(self):
        self.assertEqual(_parser().parse_args(["history", "j1"]).limit, 10)
        self.assertEqual(_parser().parse_args(["history", "j1", "--limit", "5"]).limit, 5)
        self.assertFalse(hasattr(_parser().parse_args(["metrics", "j1"]), "limit"))

    def test_no_action_prints_usage_and_exits_zero(self):
        args = _parser().parse_args([])
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.command(args)
        self.assertEqual(code, 0)
        self.assertIn("usage:", buf.getvalue())


class ListDispatchTest(support.StubbedTestCase):
    def test_list_json_returns_rows(self):
        support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]
        code, out = _run(["list", "--json"])
        self.assertEqual(code, 0)
        rows = json.loads(out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["profile"], "default")
        self.assertEqual(rows[0]["status"], "scheduled")

    def test_list_unknown_profile_is_1(self):
        support.add_profile("default")
        code, out = _run(["list", "--profile", "ghost", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("unknown profile", out)

    def test_list_status_filter(self):
        support.add_profile("default")
        support.JOBS["default"] = [_job("on1"), _job("off1", enabled=False)]
        code, out = _run(["list", "--status", "paused", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual([r["id"] for r in json.loads(out)], ["off1"])


class RunsDispatchTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]
        support.EXECUTIONS["jobaaaaaaa1"] = [
            {"id": f"exec{i:08d}", "job_id": "jobaaaaaaa1", "status": "completed",
             "claimed_at": f"2026-11-16T04:00:{i:02d}+00:00",
             "started_at": f"2026-11-16T04:00:{i:02d}+00:00",
             "finished_at": f"2026-11-16T04:01:{i:02d}+00:00"}
            for i in range(3)
        ]

    def test_history_json_shape(self):
        code, out = _run(["history", "jobaaaaaaa1", "--json"])
        self.assertEqual(code, 0)
        result = json.loads(out)
        self.assertIn("runs", result)
        self.assertIn("unmatched_usage_records", result)
        self.assertEqual(len(result["runs"]), 3)

    def test_history_limit_clamp_to_one(self):
        code, out = _run(["history", "jobaaaaaaa1", "--limit", "0", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)["runs"]), 1)

    def test_metrics_json_summary(self):
        code, out = _run(["metrics", "jobaaaaaaa1", "--json"])
        self.assertEqual(code, 0)
        summary = json.loads(out)
        self.assertEqual(summary["runs"], 3)
        self.assertEqual(summary["unmatched_usage_records"], 0)

    def test_unknown_job_is_1(self):
        code, out = _run(["history", "nope0000000", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("not found", out)


class ValidateDispatchTest(support.StubbedTestCase):
    AT = "2026-11-16T12:00:00+00:00"

    def setUp(self):
        super().setUp()
        support.add_profile("default")

    def test_overlap_exits_1_clean_exits_0(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]
        code, out = _run(["validate", "0 9 * * *", "--at", self.AT, "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["conflicts"][0]["level"], "overlap")

        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 15 * * *")]
        code, out = _run(["validate", "0 8 * * *", "--at", self.AT, "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["conflicts"], [])

    def test_bad_expression_exits_1(self):
        code, out = _run(["validate", "not a cron", "--at", self.AT, "--json"])
        self.assertEqual(code, 1)
        self.assertIn("invalid expression", out)

    def test_bad_at_exits_1(self):
        code, out = _run(["validate", "0 9 * * *", "--at", "yesterday", "--json"])
        self.assertEqual(code, 1)
        self.assertIn("invalid --at", out)

    def test_deterministic_output_for_same_at(self):
        support.JOBS["default"] = [_job("jobaaaaaaa1", "0 9 * * *")]
        _, first = _run(["validate", "*/5 * * * *", "--at", self.AT, "--json"])
        _, second = _run(["validate", "*/5 * * * *", "--at", self.AT, "--json"])
        self.assertEqual(first, second)


class DoctorDispatchTest(support.StubbedTestCase):
    def test_healthy_exits_0_findings_exit_1(self):
        p = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]
        code, out = _run(["doctor", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["healthy"])

        support.BROKEN.add("default")
        code, out = _run(["doctor", "--json"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["healthy"])


class ManageDispatchTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]

    def test_inspect_json_row(self):
        code, out = _run(["inspect", "jobaaaaaaa1", "--json"])
        self.assertEqual(code, 0)
        row = json.loads(out)
        self.assertEqual(row["id"], "jobaaaaaaa1")
        self.assertEqual(row["profile"], "default")

    def test_pause_success_and_failure_exit_codes(self):
        with mock.patch.object(manage, "run_hermes", return_value=(0, "ok")):
            code, out = _run(["pause", "jobaaaaaaa1", "--json"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

        with mock.patch.object(manage, "run_hermes", return_value=(1, "denied")):
            code, out = _run(["pause", "jobaaaaaaa1", "--json"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out)["ok"])

    def test_pause_unknown_job_is_1_and_never_mutates(self):
        with mock.patch.object(manage, "run_hermes") as run:
            code, out = _run(["pause", "nope0000000", "--json"])
        self.assertEqual(code, 1)
        run.assert_not_called()   # guardrail: resolve first, mutate only on a hit


if __name__ == "__main__":
    unittest.main()
