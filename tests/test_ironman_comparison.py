import copy
import unittest

import main as tracker
import ironman_comparison as comparison


START = "2026-10-28T08:30:00Z"
END = "2026-10-29T08:30:00Z"


def player(xp=1000, level=50, gains=None):
    stats = {skill: {"rank": -1, "level": 1, "experience": 0} for skill in tracker.SKILLS}
    for skill, (skill_xp, skill_level) in (gains or {}).items():
        stats[skill].update(experience=skill_xp, level=skill_level)
    stats["overall"] = {"rank": -1, "level": level, "experience": xp}
    return stats


class IronmanComparisonTests(unittest.TestCase):
    def setUp(self):
        self.old = {name: player() for name in tracker.IRONMAN_ACCOUNTS}
        self.previous = {**self.old, "_meta": {"generatedAt": START}}

    def test_same_period_totals_levels_and_top_five_sorted_by_xp(self):
        skills = {skill: (xp, level) for skill, xp, level in [
            ("attack", 100, 2), ("fishing", 600, 6), ("cooking", 500, 5),
            ("mining", 400, 4), ("smithing", 300, 3), ("strength", 200, 2),
        ]}
        current = {"JorbisBTW": player(3100, 60, skills), "IronXDabber": player(1900, 55, {"magic": (900, 9)})}
        result = comparison.build_comparison(tracker, current, self.previous, END)
        self.assertEqual((result["periodStart"], result["periodEnd"]), (START, END))
        left, right = result["accounts"]
        self.assertEqual((left["gainedXp"], left["gainedLevels"]), (2100, 10))
        self.assertEqual((right["gainedXp"], right["gainedLevels"]), (900, 5))
        self.assertEqual([skill["skill"] for skill in left["topSkills"]], ["fishing", "cooking", "mining", "smithing", "strength"])
        self.assertEqual(left["topSkills"][0]["levelsGained"], 5)
        self.assertEqual(comparison.comparison_leads(result), ["JorbisBTW gained 1,200 more XP.", "JorbisBTW gained 5 more total levels."])
        for output in (comparison.build_html(tracker, result), comparison.build_plain_text(tracker, result)):
            self.assertIn("JorbisBTW", output)
            self.assertIn("IronXDabber", output)
            self.assertIn("2,100", output)
            self.assertIn("Top 5 skill gains", output)
            self.assertIn("Oct 28", output)

    def test_new_friend_does_not_compare_his_lifetime_xp_to_jorbis_daily_gains(self):
        previous = {"JorbisBTW": player(), "_meta": {"generatedAt": START}}
        result = comparison.build_comparison(tracker, self.old, previous, END)
        self.assertEqual(result["status"], "baseline")
        self.assertIsNone(result["periodStart"])
        self.assertTrue(all(account["gainedXp"] is None for account in result["accounts"]))
        self.assertEqual(result["baseline"], self.old)
        self.assertEqual(result["baselineAt"], END)
        self.assertEqual(comparison.comparison_leads(result), [])

    def test_failure_preserves_pair_baseline_and_next_success_covers_same_longer_interval(self):
        self.previous["_meta"]["ironmanComparison"] = {"baseline": self.old, "baselineAt": START}
        current = {"JorbisBTW": player(1500, 52)}
        failed = comparison.build_comparison(tracker, current, self.previous, END)
        self.assertEqual(failed["status"], "unavailable")
        self.assertEqual(failed["baselineAt"], START)
        self.assertEqual(failed["baseline"], self.old)
        self.assertTrue(all(account["gainedXp"] is None for account in failed["accounts"]))
        after_failure = {**current, "_meta": {"generatedAt": END, "ironmanComparison": failed}}
        recovered = comparison.build_comparison(tracker, {"JorbisBTW": player(2000, 55), "IronXDabber": player(2500, 60)}, after_failure, "2026-10-30T08:30:00Z")
        self.assertEqual(recovered["periodStart"], START)
        self.assertEqual([account["gainedXp"] for account in recovered["accounts"]], [1000, 1500])

    def test_rerun_uses_previous_paired_pull_instead_of_accumulated_daily_summary(self):
        previous = copy.deepcopy(self.previous)
        previous["_meta"]["dailySummary"] = {"byPlayer": {"JorbisBTW": {"totalXp": 999999}}}
        result = comparison.build_comparison(tracker, self.old, previous, END)
        self.assertEqual(result["status"], "comparison")
        self.assertTrue(all(account["gainedXp"] == 0 for account in result["accounts"]))
        self.assertTrue(all(account["topSkills"] == [] for account in result["accounts"]))
        self.assertEqual(comparison.comparison_leads(result), ["XP gained: tied.", "total levels gained: tied."])

    def test_decreases_are_not_reported_as_negative_progress(self):
        result = comparison.build_comparison(tracker, {name: player(900, 49) for name in tracker.IRONMAN_ACCOUNTS}, self.previous, END)
        self.assertTrue(all(account["gainedXp"] == 0 and account["gainedLevels"] == 0 for account in result["accounts"]))

    def test_published_result_is_used_verbatim_in_both_email_formats(self):
        result = comparison.build_comparison(tracker, self.old, self.previous, END)
        html = tracker.build_html_email({}, tracker.GOAL_PROGRESS_BASELINE, self.old, {}, {}, {}, {}, result)
        plain = tracker.build_plain_text({}, self.old, {}, {}, {}, {}, result)
        self.assertIn(comparison.period_label(result), html)
        self.assertIn(comparison.period_label(result), plain)


if __name__ == "__main__":
    unittest.main()
