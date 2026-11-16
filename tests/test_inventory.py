"""Inventory: normalization, dedup by (profile, id), status filter, per-profile errors,
and the secret scrub (prompt/origin never leave the module)."""
import json

from tests import support
from plugin import inventory

SECRET_PROMPT = "top-secret-prompt-value"


def _job(job_id="jobaaaaaaa1", **over):
    job = {
        "id": job_id, "name": f"job {job_id}", "enabled": True, "no_agent": False,
        "model": "test/model-x", "prompt": SECRET_PROMPT, "origin": "chat:999888777",
        "schedule": {"kind": "cron", "expr": "0 9 * * *"},
    }
    job.update(over)
    return job


class NormalizeTest(support.StubbedTestCase):
    def test_row_shape_and_scrub(self):
        row = inventory.normalize(_job(), "default")
        self.assertEqual(set(row), {"id", "name", "profile", "schedule", "model",
                                    "execution_type", "status"})
        blob = json.dumps(row)
        self.assertNotIn(SECRET_PROMPT, blob)
        self.assertNotIn("999888777", blob)
        self.assertEqual(row["execution_type"], "agent")
        self.assertEqual(row["status"], "scheduled")

    def test_schedule_display_prefers_display_then_expr(self):
        job = _job(schedule={"kind": "cron", "expr": "0 9 * * *", "display": "daily 9am"})
        self.assertEqual(inventory.normalize(job, "p")["schedule"], "daily 9am")
        job2 = _job(schedule={"kind": "cron", "expr": "0 9 * * *"})
        self.assertEqual(inventory.normalize(job2, "p")["schedule"], "0 9 * * *")

    def test_no_agent_is_script_and_disabled_is_paused(self):
        job = _job(no_agent=True, enabled=False)
        row = inventory.normalize(job, "p")
        self.assertEqual(row["execution_type"], "script")
        self.assertEqual(row["status"], "paused")


class CollectTest(support.StubbedTestCase):
    def test_one_row_per_profile_and_id(self):
        a = support.add_profile("alpha")
        b = support.add_profile("beta")
        support.JOBS["alpha"] = [_job("dup00000001"), _job("dup00000001"), _job("jobaaaaaaa2")]
        support.JOBS["beta"] = [_job("dup00000001")]
        rows, errors = inventory.collect([a, b])
        self.assertEqual(errors, [])
        # same id twice in one store collapses; the other profile's copy is a distinct row
        self.assertEqual([(r["profile"], r["id"]) for r in rows],
                         [("alpha", "dup00000001"), ("alpha", "jobaaaaaaa2"),
                          ("beta", "dup00000001")])

    def test_status_filter(self):
        a = support.add_profile("alpha")
        support.JOBS["alpha"] = [_job("on1"), _job("off1", enabled=False)]
        rows, _ = inventory.collect([a], status="PAUSED")  # case-insensitive
        self.assertEqual([r["id"] for r in rows], ["off1"])
        rows, _ = inventory.collect([a], status="scheduled")
        self.assertEqual([r["id"] for r in rows], ["on1"])

    def test_broken_store_is_captured_and_others_survive(self):
        good = support.add_profile("good")
        bad = support.add_profile("bad")
        support.JOBS["good"] = [_job()]
        support.BROKEN.add("bad")
        rows, errors = inventory.collect([good, bad])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("bad", errors[0])
