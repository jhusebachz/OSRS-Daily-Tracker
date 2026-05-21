import unittest
from pathlib import Path

from main import (
    GOAL_PROGRESS_BASELINE,
    SKILLS,
    build_last_seven_days_top_skills,
    build_current_week_summary,
    build_daily_summary,
    build_effective_hours_summary,
    build_html_email,
    build_last_seven_days_summary,
    build_plain_text,
    build_snapshot_metadata,
    effective_levels_remaining,
)


def build_stats(skill_overrides=None, overall_overrides=None):
    skill_overrides = skill_overrides or {}
    overall_overrides = overall_overrides or {}
    stats = {
        "overall": {
            "level": overall_overrides.get("level", GOAL_PROGRESS_BASELINE["overall"]["level"]),
            "experience": overall_overrides.get("experience", GOAL_PROGRESS_BASELINE["overall"]["experience"]),
        }
    }

    for skill in SKILLS:
        baseline = GOAL_PROGRESS_BASELINE[skill]
        overrides = skill_overrides.get(skill, {})
        stats[skill] = {
            "level": overrides.get("level", baseline["level"]),
            "experience": overrides.get("experience", baseline["experience"]),
        }

    return stats


class EffectiveHoursTests(unittest.TestCase):
    def test_effective_hours_uses_configured_xp_rates(self):
        summary = build_effective_hours_summary(
            {
                "hunter": 98000,
                "herblore": 160000,
                "slayer": 24000,
            }
        )

        self.assertAlmostEqual(summary["totalHours"], 2.8)
        self.assertEqual(summary["bySkill"]["hunter"], 1.4)
        self.assertEqual(summary["bySkill"]["herblore"], 0.8)
        self.assertEqual(summary["bySkill"]["slayer"], 0.6)

    def test_effective_hours_skips_skills_without_assumptions(self):
        summary = build_effective_hours_summary(
            {
                "hunter": 70000,
                "unknownskill": 50000,
            }
        )

        self.assertEqual(summary["totalHours"], 1.0)
        self.assertEqual(summary["skippedSkills"], ["unknownskill"])

    def test_effective_hours_ignores_combat_skills_for_efficient_hour_totals(self):
        summary = build_effective_hours_summary(
            {
                "defence": 41221,
                "hitpoints": 54879,
                "magic": 54880,
                "herblore": 178,
                "slayer": 42330,
            }
        )

        self.assertAlmostEqual(summary["totalHours"], 1.0591)
        self.assertEqual(
            summary["bySkill"],
            {
                "slayer": 1.0582,
                "herblore": 0.0009,
            },
        )

    def test_effective_hours_ignores_combat_gains_even_without_slayer_xp(self):
        summary = build_effective_hours_summary(
            {
                "attack": 24000,
                "ranged": 42000,
                "hitpoints": 13000,
                "hunter": 70000,
            }
        )

        self.assertEqual(summary["totalHours"], 1.0)
        self.assertEqual(
            summary["bySkill"],
            {
                "hunter": 1.0,
            },
        )

    def test_last_seven_days_summary_rolls_forward_with_today_entry(self):
        summary = build_last_seven_days_summary(
            {
                "_meta": {
                    "lastSevenDays": {
                        "jhusebachz": {
                            "days": [
                                {
                                    "dateKey": "2026-05-15",
                                    "label": "May 15",
                                    "totalXp": 100000,
                                    "effectiveHours": 1.2,
                                    "topSkills": [{"skill": "hunter", "xp": 100000}],
                                }
                            ]
                        }
                    }
                }
            },
            "jhusebachz",
            {"overall": 150000, "hunter": 100000, "slayer": 50000},
            {"totalHours": 2.1, "bySkill": {"hunter": 1.4, "slayer": 0.7}, "skippedSkills": []},
            "2026-05-16",
        )

        self.assertEqual(summary["daysTracked"], 2)
        self.assertEqual(summary["days"][0]["dateKey"], "2026-05-16")
        self.assertEqual(summary["totalXp"], 250000)
        self.assertAlmostEqual(summary["totalEffectiveHours"], 3.3)

    def test_last_seven_days_summary_accumulates_same_day_manual_reruns(self):
        summary = build_last_seven_days_summary(
            {
                "_meta": {
                    "lastSevenDays": {
                        "jhusebachz": {
                            "days": [
                                {
                                    "dateKey": "2026-05-16",
                                    "label": "May 16",
                                    "totalXp": 100000,
                                    "effectiveHours": 1.4,
                                    "topSkills": [{"skill": "hunter", "xp": 100000}],
                                    "gainsBySkill": {"hunter": 100000},
                                }
                            ]
                        }
                    }
                }
            },
            "jhusebachz",
            {"overall": 50000, "hunter": 30000, "slayer": 20000},
            {"totalHours": 0.9, "bySkill": {"hunter": 0.5, "slayer": 0.4}, "skippedSkills": []},
            "2026-05-16",
        )

        self.assertEqual(summary["daysTracked"], 1)
        self.assertEqual(summary["days"][0]["totalXp"], 150000)
        self.assertAlmostEqual(summary["days"][0]["effectiveHours"], 2.3)
        self.assertEqual(summary["days"][0]["gainsBySkill"]["hunter"], 130000)
        self.assertEqual(summary["days"][0]["gainsBySkill"]["slayer"], 20000)

    def test_daily_summary_accumulates_same_day_manual_reruns(self):
        stats = build_stats(
            {
                "hunter": {"experience": GOAL_PROGRESS_BASELINE["hunter"]["experience"] + 130000},
                "slayer": {"experience": GOAL_PROGRESS_BASELINE["slayer"]["experience"] + 20000},
            },
            {"experience": GOAL_PROGRESS_BASELINE["overall"]["experience"] + 150000},
        )
        summary = build_daily_summary(
            "jhusebachz",
            {"overall": 50000, "hunter": 30000, "slayer": 20000},
            stats,
            {},
            {
                "_meta": {
                    "reportDateKey": "2026-05-16",
                    "dailySummary": {
                        "byPlayer": {
                            "jhusebachz": {
                                "totalXp": 100000,
                                "topSkills": [{"skill": "hunter", "xp": 100000, "level": stats["hunter"]["level"]}],
                                "gainsBySkill": {"hunter": 100000},
                            }
                        }
                    },
                }
            },
            "2026-05-16",
        )

        self.assertEqual(summary["byPlayer"]["jhusebachz"]["totalXp"], 150000)
        self.assertEqual(summary["byPlayer"]["jhusebachz"]["gainsBySkill"]["hunter"], 130000)
        self.assertEqual(summary["byPlayer"]["jhusebachz"]["gainsBySkill"]["slayer"], 20000)

    def test_plain_text_report_includes_effective_hours_line(self):
        report = build_plain_text(
            {"hunter": 98000, "overall": 98000},
            build_stats(
                {"hunter": {"experience": GOAL_PROGRESS_BASELINE["hunter"]["experience"] + 98000}},
                {"experience": GOAL_PROGRESS_BASELINE["overall"]["experience"] + 98000},
            ),
            {},
            {
                "totalHours": 1.4,
                "bySkill": {"hunter": 1.4},
                "skippedSkills": [],
            },
            {
                "daysTracked": 1,
                "activeDays": 1,
                "totalXp": 98000,
                "totalEffectiveHours": 1.4,
                "averageXp": 98000,
                "averageEffectiveHours": 1.4,
                "days": [
                    {
                        "dateKey": "2026-05-16",
                        "label": "May 16",
                        "totalXp": 98000,
                        "effectiveHours": 1.4,
                        "topSkills": [{"skill": "hunter", "xp": 98000}],
                    }
                ],
            },
            {
                "weekStartDateKey": "2026-05-12",
                "baselineDateKey": "2026-05-12",
                "baselineOverallXp": GOAL_PROGRESS_BASELINE["overall"]["experience"],
                "baselineSkillXp": {"hunter": GOAL_PROGRESS_BASELINE["hunter"]["experience"]},
                "totalXp": 98000,
                "totalEffectiveHours": 1.4,
                "activeDays": 1,
                "daysTracked": 1,
                "topSkills": [{"skill": "hunter", "xp": 98000}],
            },
        )

        self.assertIn("Effective hours played since last report: 1.4 hours", report)
        self.assertNotIn("This week:", report)
        self.assertIn("Last 7 days: 98,000 xp | 1.4 hours | 1 active days", report)
        self.assertIn("Last 7 day top skills:", report)
        self.assertNotIn("Last 7 day breakdown:", report)

    def test_current_week_summary_uses_week_baseline_instead_of_latest_delta(self):
        current_stats = build_stats(
            {
                "hunter": {"experience": GOAL_PROGRESS_BASELINE["hunter"]["experience"] + 70000},
                "slayer": {"experience": GOAL_PROGRESS_BASELINE["slayer"]["experience"] + 50000},
            },
            {"experience": GOAL_PROGRESS_BASELINE["overall"]["experience"] + 120000},
        )
        summary = build_current_week_summary(
            {
                "_meta": {
                    "currentWeek": {
                        "jhusebachz": {
                            "weekStartDateKey": "2026-05-11",
                            "baselineOverallXp": GOAL_PROGRESS_BASELINE["overall"]["experience"],
                            "baselineSkillXp": {
                                "hunter": GOAL_PROGRESS_BASELINE["hunter"]["experience"],
                                "slayer": GOAL_PROGRESS_BASELINE["slayer"]["experience"],
                            },
                        }
                    }
                }
            },
            "jhusebachz",
            current_stats,
            "2026-05-13",
            {
                "days": [
                    {
                        "dateKey": "2026-05-13",
                        "label": "May 13",
                        "totalXp": 50000,
                        "effectiveHours": 1.1,
                        "topSkills": [{"skill": "hunter", "xp": 50000}],
                        "gainsBySkill": {"hunter": 50000},
                    },
                    {
                        "dateKey": "2026-05-12",
                        "label": "May 12",
                        "totalXp": 70000,
                        "effectiveHours": 1.4,
                        "topSkills": [{"skill": "slayer", "xp": 50000}],
                        "gainsBySkill": {"hunter": 20000, "slayer": 50000},
                    },
                ]
            },
        )

        self.assertEqual(summary["weekStartDateKey"], "2026-05-11")
        self.assertEqual(summary["baselineOverallXp"], GOAL_PROGRESS_BASELINE["overall"]["experience"])
        self.assertEqual(summary["totalXp"], 120000)
        self.assertAlmostEqual(summary["totalEffectiveHours"], 2.5)
        self.assertEqual(summary["activeDays"], 2)
        self.assertEqual(summary["daysTracked"], 2)
        self.assertEqual(summary["topSkills"][0]["skill"], "hunter")
        self.assertEqual(summary["topSkills"][0]["xp"], 70000)

    def test_snapshot_metadata_includes_generated_timestamp_for_app_sync(self):
        metadata = build_snapshot_metadata(
            "jhusebachz",
            {"totalHours": 1.4, "bySkill": {"hunter": 1.4}, "skippedSkills": []},
            {"daysTracked": 0, "activeDays": 0, "totalXp": 0, "totalEffectiveHours": 0, "days": []},
            {"byPlayer": {"jhusebachz": {"totalXp": 98000, "topSkills": []}}},
            {"weekStartDateKey": "2026-05-12", "totalXp": 98000, "totalEffectiveHours": 1.4},
            "2026-05-17",
        )

        self.assertRegex(metadata["generatedAt"], r"^\d{4}-\d{2}-\d{2}T")
        self.assertEqual(metadata["reportDateKey"], "2026-05-17")
        self.assertEqual(metadata["timeZone"], "America/New_York")

    def test_goal_two_html_uses_levels_still_needed_and_goal_three_has_clean_separators(self):
        stats = build_stats(
            {
                "hunter": {"experience": GOAL_PROGRESS_BASELINE["hunter"]["experience"] + 98000},
                "slayer": {"experience": GOAL_PROGRESS_BASELINE["slayer"]["experience"] + 24000},
            },
            {"experience": GOAL_PROGRESS_BASELINE["overall"]["experience"] + 122000},
        )
        html = build_html_email(
            {"hunter": 98000, "slayer": 24000, "overall": 122000},
            stats,
            {},
            {},
            {"totalHours": 2.0, "bySkill": {"hunter": 1.4, "slayer": 0.6}, "skippedSkills": []},
            {
                "daysTracked": 1,
                "activeDays": 1,
                "totalXp": 122000,
                "totalEffectiveHours": 2.0,
                "averageXp": 122000,
                "averageEffectiveHours": 2.0,
                "days": [
                    {
                        "dateKey": "2026-05-17",
                        "label": "May 17",
                        "totalXp": 122000,
                        "effectiveHours": 2.0,
                        "topSkills": [{"skill": "hunter", "xp": 98000}],
                    }
                ],
            },
            {
                "weekStartDateKey": "2026-05-12",
                "baselineDateKey": "2026-05-12",
                "baselineOverallXp": GOAL_PROGRESS_BASELINE["overall"]["experience"],
                "baselineSkillXp": {"hunter": GOAL_PROGRESS_BASELINE["hunter"]["experience"]},
                "totalXp": 122000,
                "totalEffectiveHours": 2.0,
                "activeDays": 1,
                "daysTracked": 1,
                "topSkills": [{"skill": "hunter", "xp": 98000}],
            },
        )

        self.assertIn("Levels still needed", html)
        self.assertIn("Fastest next levels", html)
        self.assertIn("Effective hours played since last report", html)
        self.assertNotIn("This week:", html)
        self.assertNotIn("full levels/day", html)
        self.assertNotIn("Â·", html)
        self.assertIn("Top skills", html)
        closest_to_99 = html.split("Closest to 99", 1)[1]
        self.assertNotIn("Attack", closest_to_99)

    def test_goal_one_and_goal_three_follow_app_ordering(self):
        stats = build_stats(
            {
                "hunter": {
                    "level": 91,
                    "experience": GOAL_PROGRESS_BASELINE["hunter"]["experience"] + 180000,
                },
                "agility": {
                    "level": 98,
                    "experience": 12950000,
                },
                "runecraft": {
                    "level": 86,
                    "experience": GOAL_PROGRESS_BASELINE["runecraft"]["experience"],
                },
            },
            {"experience": GOAL_PROGRESS_BASELINE["overall"]["experience"] + 180000},
        )
        html = build_html_email(
            {"hunter": 180000, "overall": 180000},
            stats,
            {},
            {},
            {"totalHours": 2.6, "bySkill": {"hunter": 2.6}, "skippedSkills": []},
            {
                "daysTracked": 1,
                "activeDays": 1,
                "totalXp": 180000,
                "totalEffectiveHours": 2.6,
                "averageXp": 180000,
                "averageEffectiveHours": 2.6,
                "days": [],
            },
            {
                "weekStartDateKey": "2026-05-19",
                "baselineDateKey": "2026-05-19",
                "baselineOverallXp": GOAL_PROGRESS_BASELINE["overall"]["experience"],
                "baselineSkillXp": {"hunter": GOAL_PROGRESS_BASELINE["hunter"]["experience"]},
                "totalXp": 180000,
                "totalEffectiveHours": 2.6,
                "activeDays": 1,
                "daysTracked": 1,
                "topSkills": [{"skill": "hunter", "xp": 180000}],
            },
        )

        goal_one_section = html.split("Still needed", 1)[1]
        self.assertLess(goal_one_section.index("Hunter"), goal_one_section.index("Runecraft"))

        closest_to_99 = html.split("Closest to 99", 1)[1]
        self.assertLess(closest_to_99.index("Agility"), closest_to_99.index("Runecraft"))

    def test_last_seven_days_top_skills_aggregate_across_the_full_window(self):
        summary = {
            "days": [
                {
                    "dateKey": "2026-05-17",
                    "label": "May 17",
                    "totalXp": 200000,
                    "effectiveHours": 2.0,
                    "topSkills": [{"skill": "hunter", "xp": 140000}],
                    "gainsBySkill": {"hunter": 140000, "slayer": 60000},
                },
                {
                    "dateKey": "2026-05-16",
                    "label": "May 16",
                    "totalXp": 180000,
                    "effectiveHours": 1.8,
                    "topSkills": [{"skill": "runecraft", "xp": 90000}],
                    "gainsBySkill": {"hunter": 40000, "runecraft": 90000, "slayer": 50000},
                },
            ]
        }

        self.assertEqual(
            build_last_seven_days_top_skills(summary),
            [("hunter", 180000), ("slayer", 110000), ("runecraft", 90000)],
        )

    def test_daily_workflow_runs_four_hours_earlier(self):
        workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily.yml"
        content = workflow.read_text(encoding="utf-8")

        self.assertIn('cron: "30 8 * * *"', content)

    def test_effective_levels_remaining_counts_partial_progress(self):
        stats = {
            "overall": {"level": 2249, "experience": 0},
            "runecraft": {"level": 85, "experience": 3585248},
        }

        self.assertLess(effective_levels_remaining(stats, 2250), 1.0)


if __name__ == "__main__":
    unittest.main()
