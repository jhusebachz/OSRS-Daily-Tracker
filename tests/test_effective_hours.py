import unittest
from pathlib import Path

from main import (
    build_effective_hours_summary,
    build_last_seven_days_summary,
    build_plain_text,
)


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

    def test_plain_text_report_includes_effective_hours_line(self):
        report = build_plain_text(
            {"hunter": 98000, "overall": 98000},
            {},
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
        )

        self.assertIn("Effective hours played today: 1.4 hours", report)
        self.assertIn("Last 7 days: 98,000 xp | 1.4 hours | 1 active days", report)
        self.assertIn("Last 7 day breakdown:", report)

    def test_daily_workflow_runs_four_hours_earlier(self):
        workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily.yml"
        content = workflow.read_text(encoding="utf-8")

        self.assertIn('cron: "30 8 * * *"', content)


if __name__ == "__main__":
    unittest.main()
