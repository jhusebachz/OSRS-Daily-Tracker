import copy
import json
import unittest
from datetime import date
from pathlib import Path

import main as tracker
import max_pace
import ironman_milestones


class NewProgressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((Path(__file__).parents[1] / "data" / "last_stats.json").read_text())

    def test_max_baseline_starts_at_zero_cumulative_hours(self):
        summary = max_pace.build_summary(tracker, self.snapshot["jhusebachz"], date(2026, 11, 10))
        self.assertEqual(summary["completedTimedHours"], 0)
        self.assertEqual(summary["expectedTimedHours"], 0)
        self.assertEqual(summary["hoursAhead"], 0)
        self.assertEqual(summary["maxedSkills"], 5)
        self.assertAlmostEqual(summary["xpProgressPct"], 67.7, delta=0.1)
        self.assertEqual({item["skill"] for item in summary["untimedCombat"]}, max_pace.COMBAT_SKILLS)
        self.assertTrue(all(item["skill"] not in max_pace.COMBAT_SKILLS for item in summary["timedSkills"]))

    def test_cumulative_hours_are_xp_based_and_combat_never_counts(self):
        stats = copy.deepcopy(self.snapshot["jhusebachz"])
        stats["agility"]["experience"] += 50000
        stats["attack"]["experience"] += 1000000
        summary = max_pace.build_summary(tracker, stats, date(2026, 11, 11))
        self.assertEqual(summary["completedTimedHours"], 1)
        self.assertAlmostEqual(
            summary["hoursAhead"],
            1 - summary["startingTimedHours"] / (date(2027, 12, 31) - date(2026, 11, 10)).days,
            places=3,
        )
        stats["attack"]["experience"] += 1000000
        self.assertEqual(max_pace.build_summary(tracker, stats, date(2026, 11, 11))["hoursAhead"], summary["hoursAhead"])

    def test_ironman_base_tiers_advance_and_preview_future_progress(self):
        stats = copy.deepcopy(self.snapshot["JorbisBTW"])
        summary = ironman_milestones.build_summary(tracker, stats)
        self.assertEqual((summary["targetLevel"], summary["completed"], summary["totalSkills"]), (30, 19, 24))
        self.assertEqual((summary["nextTier"]["level"], summary["nextTier"]["completed"]), (40, 13))
        self.assertEqual(len(summary["remaining"]), 5)
        for skill in ("hunter", "construction", "fletching", "herblore", "slayer"):
            stats[skill]["level"] = 30
        summary = ironman_milestones.build_summary(tracker, stats)
        self.assertEqual(summary["targetLevel"], 40)
        self.assertEqual(summary["completed"], 13)

    def test_missing_skill_stats_do_not_count_as_completed(self):
        stats = copy.deepcopy(self.snapshot["JorbisBTW"])
        stats.pop("hunter")
        self.assertFalse(ironman_milestones.build_summary(tracker, stats)["available"])
        stats = copy.deepcopy(self.snapshot["jhusebachz"])
        stats.pop("agility")
        self.assertFalse(max_pace.build_summary(tracker, stats)["available"])

    def test_scheduled_roster_contains_ironxdabber_as_friend_once(self):
        import run_current

        self.assertIn("IronXDabber", run_current.tracker.FRIENDS)
        names = list(dict.fromkeys([*run_current.tracker.IRONMAN_ACCOUNTS, *run_current.tracker.FRIENDS]))
        self.assertEqual(names.count("IronXDabber"), 1)


if __name__ == "__main__":
    unittest.main()
