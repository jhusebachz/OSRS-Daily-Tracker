import unittest
from pathlib import Path

from main import build_effective_hours_summary, build_plain_text


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
        )

        self.assertIn("Effective hours played today: 1.4 hours", report)
        self.assertIn("Top effective-hour contributors:", report)

    def test_daily_workflow_runs_four_hours_earlier(self):
        workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "daily.yml"
        content = workflow.read_text(encoding="utf-8")

        self.assertIn('cron: "30 8 * * *"', content)


if __name__ == "__main__":
    unittest.main()
