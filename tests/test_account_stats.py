import json
from pathlib import Path
import subprocess
import sys
import unittest

import main as tracker
import account_stats


def player(level=393, xp=153600):
    stats = {skill: {"rank": -1, "level": 1, "experience": 0} for skill in tracker.SKILLS}
    stats["overall"] = {"rank": -1, "level": level, "experience": xp}
    stats["attack"] = {"rank": -1, "level": 5, "experience": 500}
    return stats


class AccountStatsTests(unittest.TestCase):
    def test_exact_owned_accounts_and_all_skills_use_current_absolute_stats(self):
        report = account_stats.build_report(tracker, {
            "jhusebachz": player(2200, 200000000), "JorbisBTW": player(), "IronXDabber": player(),
        }, "2026-11-02T08:30:00Z")
        self.assertEqual([account["name"] for account in report["accounts"]], ["jhusebachz", "JorbisBTW"])
        primary, ironman = report["accounts"]
        self.assertEqual((primary["totalLevel"], primary["totalXp"]), (2200, 200000000))
        self.assertEqual((ironman["totalLevel"], ironman["totalXp"]), (393, 153600))
        self.assertEqual([stat["skill"] for stat in ironman["skills"]], tracker.SKILLS)
        self.assertEqual(ironman["skills"][0], {"skill": "attack", "level": 5, "xp": 500})
        for output in (account_stats.build_html(tracker, report), account_stats.build_plain_text(tracker, report)):
            self.assertIn("200,000,000", output)
            self.assertIn("153,600", output)
            self.assertIn("Sailing", output)
            self.assertIn("2026-11-02 03:30 AM EST", output)
            self.assertNotIn("IronXDabber", output)

    def test_missing_account_and_missing_or_unranked_skills_are_not_fake_zeros(self):
        stats = player()
        del stats["sailing"]
        stats["attack"].update(level=-1, experience=-1)
        report = account_stats.build_report(tracker, {"jhusebachz": stats}, None)
        primary, ironman = report["accounts"]
        self.assertIsNone(primary["skills"][0]["xp"])
        self.assertIsNone(primary["skills"][-1]["level"])
        self.assertFalse(ironman["available"])
        self.assertIsNone(ironman["totalXp"])
        for output in (account_stats.build_html(tracker, report), account_stats.build_plain_text(tracker, report)):
            self.assertIn("Timestamp unavailable", output)
            self.assertIn("Unavailable", output)

    def test_timestamp_uses_the_saved_run_time_and_handles_daylight_saving(self):
        self.assertEqual(account_stats.timestamp_label({"generatedAt": "2026-10-29T08:30:00Z"}), "2026-10-29 04:30 AM EDT")
        self.assertEqual(account_stats.timestamp_label({"generatedAt": "2026-11-02T08:30:00Z"}), "2026-11-02 03:30 AM EST")
        self.assertEqual(account_stats.timestamp_label({"generatedAt": "not-a-date"}), "Timestamp unavailable")

    def test_scheduled_entrypoint_removes_diary_and_places_saved_stats_after_boss_activity(self):
        # A fresh interpreter keeps run_current's report extensions isolated from
        # the unit tests that import the original main.py functions.
        script = r'''
import contextlib, copy, io, json, tempfile
from pathlib import Path
from unittest.mock import patch
import main as tracker
import run_current
primary = {skill: {**values, "rank": 1} for skill, values in tracker.GOAL_PROGRESS_BASELINE.items()}
ironman = {skill: {"rank": -1, "level": 1, "experience": 0} for skill in tracker.SKILLS}
ironman["overall"] = {"rank": -1, "level": 42, "experience": 9999}
ironman["attack"] = {"rank": -1, "level": 5, "experience": 500}
previous = {"_meta": {"bosses": {tracker.USERNAME: {"Vorkath": 0}}}}
run_current._latest_boss_kcs_by_player = {tracker.USERNAME: {"Vorkath": 1}}
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "last_stats.json"
    with patch.object(tracker, "fetch_all_stats", return_value=(primary, {"JorbisBTW": ironman})), patch.object(tracker, "load_previous", return_value=previous), patch.object(tracker, "DATA_FILE", str(output)), patch.object(tracker, "send_email") as send, contextlib.redirect_stdout(io.StringIO()):
        tracker.main()
    send.assert_called_once()
    html, plain = send.call_args.args
    saved = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({"html": html, "plain": plain, "saved": saved}))
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        html, plain, saved = output["html"], output["plain"], output["saved"]
        self.assertNotIn("diary", html.lower())
        self.assertNotIn("Goal 2", html)
        self.assertLess(html.index("Daily Coaching Insight"), html.index("Current Account Stats"))
        self.assertLess(plain.index("BOSS KILLS SINCE LAST UPDATE"), plain.index("CURRENT ACCOUNT STATS"))
        self.assertIn("JorbisBTW", html.split("Current Account Stats", 1)[1])
        self.assertNotIn("IronXDabber", html.split("Current Account Stats", 1)[1])
        self.assertEqual(saved["JorbisBTW"]["overall"]["experience"], 9999)
        self.assertIn("9,999", html.split("Current Account Stats", 1)[1])
        expected_time = account_stats.timestamp_label({"generatedAt": saved["_meta"]["generatedAt"]})
        self.assertIn(expected_time, html)
        self.assertIn(expected_time, plain)
        self.assertTrue(plain.rstrip().endswith("Sailing: Lv1 | 0 xp"))


if __name__ == "__main__":
    unittest.main()
