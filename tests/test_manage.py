"""Guardrails: exact-id find_job resolution, argv-only mutations through the
public `hermes cron` CLI, and the doctor health-sweep findings.
"""
from unittest import mock

from tests import support
from plugin import hermes_bridge as hb
from plugin import manage


def _job(job_id, **over):
    job = {"id": job_id, "name": f"job {job_id}", "enabled": True,
           "schedule": {"kind": "cron", "expr": "0 9 * * *"}}
    job.update(over)
    return job


class FindJobTest(support.StubbedTestCase):
    def test_exact_id_in_one_profile(self):
        p = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]
        profile, job, error = hb.find_job("jobaaaaaaa1", None)
        self.assertIsNone(error)
        self.assertEqual(profile.name, "default")
        self.assertEqual(job["id"], "jobaaaaaaa1")

    def test_ambiguous_id_requires_profile(self):
        support.add_profile("alpha")
        support.add_profile("beta")
        support.JOBS["alpha"] = [_job("dup00000001")]
        support.JOBS["beta"] = [_job("dup00000001")]
        profile, job, error = hb.find_job("dup00000001", None)
        self.assertIsNone(profile)
        self.assertIn("multiple profiles", error)
        self.assertIn("alpha", error)
        self.assertIn("beta", error)
        # naming one profile resolves it
        profile, job, error = hb.find_job("dup00000001", "beta")
        self.assertIsNone(error)
        self.assertEqual(profile.name, "beta")

    def test_unknown_id_and_unknown_profile_error(self):
        support.add_profile("default")
        _, _, error = hb.find_job("nope0000000", None)
        self.assertEqual(error, "job 'nope0000000' not found")
        _, _, error = hb.find_job("jobaaaaaaa1", "ghost")
        self.assertIn("unknown profile 'ghost'", error)

    def test_broken_store_never_crashes_lookup(self):
        support.add_profile("default")
        support.BROKEN.add("default")
        _, _, error = hb.find_job("jobaaaaaaa1", None)
        self.assertEqual(error, "job 'jobaaaaaaa1' not found")


class MutateTest(support.StubbedTestCase):
    def setUp(self):
        super().setUp()
        self.profile = support.add_profile("default")

    def test_pause_builds_public_cli_argv(self):
        with mock.patch.object(manage, "run_hermes", return_value=(0, "ok")) as run:
            result = manage.mutate("pause", "jobaaaaaaa1", self.profile)
        run.assert_called_once_with(
            ["-p", "default", "cron", "pause", "jobaaaaaaa1"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["job_id"], "jobaaaaaaa1")

    def test_delete_maps_to_remove_verb(self):
        with mock.patch.object(manage, "run_hermes", return_value=(0, "")) as run:
            manage.mutate("delete", "jobaaaaaaa1", self.profile)
        self.assertEqual(run.call_args.args[0][-2:], ["remove", "jobaaaaaaa1"])

    def test_failed_invocation_reports_not_ok(self):
        with mock.patch.object(manage, "run_hermes", return_value=(1, "nope")):
            result = manage.mutate("resume", "jobaaaaaaa1", self.profile)
        self.assertFalse(result["ok"])
        self.assertEqual(result["hermes_output"], "nope")

    def test_missing_hermes_executable_is_127(self):
        with mock.patch.object(manage.shutil, "which", return_value=None):
            code, output = manage.run_hermes(["cron", "list"])
        self.assertEqual(code, 127)
        self.assertIn("not found", output)

    def test_run_hermes_passes_list_argv_never_a_shell_string(self):
        proc = mock.Mock(returncode=0, stdout="ok", stderr="")
        with mock.patch.object(manage.shutil, "which", return_value="C:/fake/hermes"), \
                mock.patch.object(manage.subprocess, "run", return_value=proc) as run:
            code, output = manage.run_hermes(["-p", "default", "cron", "pause", "id1"])
        self.assertEqual(code, 0)
        self.assertEqual(output, "ok")
        args, kwargs = run.call_args
        self.assertIsInstance(args[0], list)          # list argv, no shell interpolation
        self.assertEqual(args[0][0], "C:/fake/hermes")
        self.assertNotIn("shell", kwargs)             # never shell=True
        self.assertTrue(kwargs["capture_output"])


class DoctorTest(support.StubbedTestCase):
    def test_healthy_profile_has_no_findings(self):
        p = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1")]
        report = manage.doctor([p])
        self.assertTrue(report["healthy"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["jobs"], 1)
        self.assertEqual(report["profiles"], ["default"])

    def test_missing_profile_is_a_finding(self):
        p = support.add_profile("ghost", missing=True)
        report = manage.doctor([p])
        self.assertFalse(report["healthy"])
        self.assertEqual(report["findings"][0]["type"], "missing_profile")

    def test_unreadable_store_is_a_finding(self):
        p = support.add_profile("default")
        support.BROKEN.add("default")
        report = manage.doctor([p])
        self.assertFalse(report["healthy"])
        self.assertEqual(report["findings"][0]["type"], "unreadable_store")

    def test_duplicate_id_across_profiles_is_a_finding(self):
        a = support.add_profile("alpha")
        b = support.add_profile("beta")
        support.JOBS["alpha"] = [_job("dup00000001")]
        support.JOBS["beta"] = [_job("dup00000001")]
        report = manage.doctor([a, b])
        dup = [f for f in report["findings"] if f["type"] == "duplicate_id"]
        self.assertEqual(len(dup), 1)
        self.assertIn("alpha, beta", dup[0]["detail"])

    def test_failure_streak_state_and_delivery_findings(self):
        p = support.add_profile("default")
        support.JOBS["default"] = [
            _job("jobaaaaaaa1", state="error"),
            _job("jobaaaaaaa2", failure_streak=3, last_error="boom"),
            _job("jobaaaaaaa3", last_delivery_error="smtp down"),
        ]
        report = manage.doctor([p])
        types = {f["type"] for f in report["findings"]}
        self.assertEqual(types, {"job_state", "failure_streak", "delivery_failure"})
        by_type = {f["type"]: f for f in report["findings"]}
        self.assertEqual(by_type["job_state"]["detail"], "state=error")
        self.assertIn("failure_streak=3", by_type["failure_streak"]["detail"])
        self.assertIn("boom", by_type["failure_streak"]["detail"])
        self.assertEqual(by_type["delivery_failure"]["detail"], "smtp down")

    def test_paused_job_is_not_a_finding(self):
        p = support.add_profile("default")
        support.JOBS["default"] = [_job("jobaaaaaaa1", enabled=False)]
        report = manage.doctor([p])
        self.assertTrue(report["healthy"])


class InspectTest(support.StubbedTestCase):
    def test_inspect_row_includes_last_run(self):
        p = support.add_profile("default")
        job = _job("jobaaaaaaa1", next_run_at="2026-11-17T04:00:00+00:00",
                   failure_streak=2, last_error="boom")
        support.EXECUTIONS["jobaaaaaaa1"] = [{
            "id": "exec00000001", "job_id": "jobaaaaaaa1", "status": "completed",
            "claimed_at": "2026-11-16T04:00:10+00:00",
            "started_at": "2026-11-16T04:00:10+00:00",
            "finished_at": "2026-11-16T04:00:40+00:00",
        }]
        row = manage.inspect(p, job)
        self.assertEqual(row["next_run_at"], "2026-11-17T04:00:00+00:00")
        self.assertEqual(row["failure_streak"], 2)
        self.assertEqual(row["last_run"]["id"], "exec00000001")
        self.assertEqual(row["last_run"]["duration_ms"], 30_000)
