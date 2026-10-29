import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main as tracker
import ironman_comparison


def stats(xp=3495):
    player = {skill: {"rank": -1, "level": 1, "experience": 0} for skill in tracker.SKILLS}
    player["attack"] = {"rank": -1, "level": 5, "experience": xp}
    player["overall"] = {"rank": -1, "level": 52, "experience": xp}
    return player


class OwnAccountTests(unittest.TestCase):
    def test_fetch_and_save_include_ironman_without_adding_a_friend(self):
        with patch.object(tracker, "fetch_player", return_value=stats()) as fetch, patch.object(tracker.time, "sleep"):
            primary, accounts = tracker.fetch_all_stats()
        self.assertIn("JorbisBTW", [call.args[0] for call in fetch.call_args_list])
        self.assertIn("IronXDabber", [call.args[0] for call in fetch.call_args_list])
        self.assertNotIn("JorbisBTW", tracker.FRIENDS)
        self.assertNotIn("IronXDabber", tracker.FRIENDS)
        self.assertIn("JorbisBTW", accounts)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last_stats.json"
            with patch.object(tracker, "DATA_FILE", str(path)):
                tracker.save_current(primary, accounts, {})
            self.assertEqual(json.loads(path.read_text())["JorbisBTW"], stats())
            self.assertEqual(json.loads(path.read_text())["IronXDabber"], stats())

    def test_first_lookup_is_a_baseline_in_both_email_formats(self):
        accounts = {"JorbisBTW": stats(), "IronXDabber": stats()}
        comparison = ironman_comparison.build_comparison(tracker, accounts, {})
        self.assertIsNone(comparison["accounts"][0]["gainedXp"])
        self.assertEqual(comparison["status"], "baseline")
        html = ironman_comparison.build_html(tracker, comparison)
        plain = tracker.build_plain_text({}, accounts, {}, {}, {}, {})
        for output in (html, plain):
            self.assertIn("JorbisBTW - Ironman", output)
            self.assertIn("3,495", output)
            self.assertIn("Baseline established", output)
        friends_html = tracker.friend_comparison_html({}, accounts, {})
        self.assertNotIn("JorbisBTW", friends_html)
        self.assertNotIn("IronXDabber", friends_html)

    def test_daily_gains_merge_on_reruns_and_reset_on_the_next_day(self):
        day = tracker.get_report_date_key()
        previous = {
            "JorbisBTW": stats(),
            "_meta": {"reportDateKey": day, "dailySummary": {"byPlayer": {
                "JorbisBTW": {"gainsBySkill": {"attack": 1000}},
            }}},
        }
        current = {"JorbisBTW": stats(3995)}
        summary = tracker.build_daily_summary("jhusebachz", {}, {}, current, previous, day)
        self.assertEqual(summary["byPlayer"]["JorbisBTW"]["totalXp"], 1500)
        previous["_meta"]["reportDateKey"] = "2000-01-01"
        summary = tracker.build_daily_summary("jhusebachz", {}, {}, current, previous, day)
        self.assertEqual(summary["byPlayer"]["JorbisBTW"]["totalXp"], 500)

    def test_missing_ironman_keeps_the_report_working(self):
        comparison = ironman_comparison.build_comparison(tracker, {}, {})
        self.assertIn("HiScores data unavailable", ironman_comparison.build_html(tracker, comparison))
        self.assertIn("HiScores data unavailable", tracker.build_plain_text({}, {}, {}, {}, {}, {}))
        with patch.object(tracker, "fetch_player", side_effect=lambda name: (_ for _ in ()).throw(RuntimeError("unranked")) if name == "JorbisBTW" else stats()), patch.object(tracker.time, "sleep"):
            primary, accounts = tracker.fetch_all_stats()
        self.assertEqual(primary, stats())
        self.assertNotIn("JorbisBTW", accounts)
        self.assertIn(tracker.FRIENDS[0], accounts)


if __name__ == "__main__":
    unittest.main()
