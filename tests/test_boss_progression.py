import unittest
from types import SimpleNamespace

import boss_progression


TRACKER = SimpleNamespace(METADATA_KEY="_meta")


def boss_snapshot(**overrides):
    values = {boss: 0 for boss in boss_progression.BOSS_DIFFICULTY_ORDER}
    values.update(overrides)
    return values


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeRequests:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def get(self, url, headers, timeout):
        self.url = url
        return FakeResponse(self.payload)


class BossProgressionTests(unittest.TestCase):
    def test_fetch_uses_json_activity_names_and_normalizes_unranked_scores(self):
        requests = FakeRequests(
            {
                "activities": [
                    {"name": "Vorkath", "score": 407},
                    {"name": "Clue Scrolls (all)", "score": 99},
                    {"name": "Sarachnis", "score": -1},
                ]
            }
        )
        tracker = SimpleNamespace(requests=requests, HISCORE_HEADERS={})

        result = boss_progression.fetch_boss_kcs(tracker, "Player Name")

        self.assertEqual(
            requests.url,
            "https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player=Player_Name",
        )
        self.assertEqual(result["Vorkath"], 407)
        self.assertEqual(result["Sarachnis"], 0)
        self.assertNotIn("Clue Scrolls (all)", result)

    def test_full_remaining_checklist_preserves_tier_and_curated_order(self):
        progression = boss_progression.build_boss_progression(boss_snapshot())

        self.assertEqual(progression["triedCount"], 0)
        self.assertEqual(
            progression["untriedCount"],
            len(boss_progression.BOSS_DIFFICULTY_ORDER),
        )
        self.assertNotIn("nextUntried", progression)
        self.assertEqual(
            list(progression["remainingByTier"]),
            list(boss_progression.BOSS_LADDER_TIERS),
        )
        for tier, configured in boss_progression.BOSS_LADDER_TIERS.items():
            self.assertEqual(
                [item["name"] for item in progression["remainingByTier"][tier]],
                configured,
            )

    def test_completed_bosses_are_omitted_without_blocking_later_entries(self):
        progression = boss_progression.build_boss_progression(
            boss_snapshot(**{"Thermonuclear Smoke Devil": 1, "Mimic": 0, "The Royal Titans": 0})
        )

        medium = [item["name"] for item in progression["remainingByTier"]["Medium"]]
        self.assertNotIn("Thermonuclear Smoke Devil", medium)
        self.assertLess(medium.index("Mimic"), medium.index("The Royal Titans"))

    def test_multiple_boss_gains_are_summed_for_one_player(self):
        previous = {
            "_meta": {
                "bosses": {
                    "jhusebachz": boss_snapshot(Vorkath=402, **{"Phantom Muspah": 2})
                }
            }
        }
        activity = boss_progression.build_daily_boss_activity(
            TRACKER,
            {
                "jhusebachz": boss_snapshot(Vorkath=407, **{"Phantom Muspah": 5})
            },
            previous,
            ["jhusebachz"],
        )

        self.assertEqual(activity["byPlayer"]["jhusebachz"]["totalBossKcGained"], 8)
        self.assertEqual(
            activity["byPlayer"]["jhusebachz"]["bossGains"],
            {"Vorkath": 5, "Phantom Muspah": 3},
        )

    def test_first_run_establishes_baseline_without_historical_gains(self):
        activity = boss_progression.build_daily_boss_activity(
            TRACKER,
            {"3Sixteen": boss_snapshot(Vorkath=250, Zulrah=900)},
            {},
            ["3Sixteen"],
        )

        self.assertEqual(
            activity["byPlayer"]["3Sixteen"],
            {"totalBossKcGained": 0, "bossGains": {}},
        )
        self.assertEqual(activity["topPlayers"], [])

    def test_name_history_uses_gwahpy_boss_snapshot_for_3sixteen(self):
        previous = {"_meta": {"bosses": {"gwahpy": boss_snapshot(Vorkath=10)}}}
        activity = boss_progression.build_daily_boss_activity(
            TRACKER,
            {"3Sixteen": boss_snapshot(Vorkath=12)},
            previous,
            ["3Sixteen"],
        )

        self.assertEqual(activity["byPlayer"]["3Sixteen"]["bossGains"], {"Vorkath": 2})

    def test_leaderboard_limits_to_top_three_players_with_deterministic_ties(self):
        players = [
            "jhusebachz",
            "3Sixteen",
            "beefmissle13",
            "kingxdabber",
            "hedith",
            "TooClose42",
        ]
        previous = {
            "_meta": {"bosses": {player: boss_snapshot(Vorkath=0) for player in players}}
        }
        totals = {
            "jhusebachz": 8,
            "3Sixteen": 4,
            "beefmissle13": 4,
            "kingxdabber": 1,
            "hedith": 12,
            "TooClose42": 0,
        }
        current = {
            player: boss_snapshot(Vorkath=total)
            for player, total in totals.items()
        }

        activity = boss_progression.build_daily_boss_activity(
            TRACKER,
            current,
            previous,
            players,
        )

        self.assertEqual(
            [player["name"] for player in activity["topPlayers"]],
            ["hedith", "jhusebachz", "3Sixteen"],
        )
        self.assertEqual(set(activity["byPlayer"]), set(players))

    def test_no_kills_omits_boss_activity_email_section(self):
        tracker = SimpleNamespace(section=lambda title, content: f"{title}:{content}")

        self.assertEqual(
            boss_progression.build_daily_boss_activity_html(
                tracker,
                {"byPlayer": {}, "topPlayers": []},
            ),
            "",
        )

    def test_boss_html_contains_every_remaining_boss_without_next_label(self):
        tracker = SimpleNamespace(
            row=lambda label, value: f"{label}:{value}",
            progress_bar=lambda pct, color: f"progress:{pct}",
            section=lambda title, content: f"{title}:{content}",
            clamp_pct=lambda value: max(0, min(100, value)),
        )

        html = boss_progression.build_boss_html(tracker, boss_snapshot())

        for boss in boss_progression.BOSS_DIFFICULTY_ORDER:
            self.assertIn(boss, html)
        for tier in boss_progression.BOSS_LADDER_TIERS:
            self.assertIn(tier, html)
        self.assertNotIn("NEXT", html)

    def test_weekly_raid_goal_remains_binary_when_multiple_metrics_increase(self):
        week_summary = {"weekStartDateKey": "2026-09-21"}
        previous = {
            "_meta": {
                "currentWeek": {
                    "jhusebachz": {
                        "weekStartDateKey": "2026-09-21",
                        "raidGoal": {
                            "baselineKcs": boss_snapshot(
                                **{
                                    "Tombs of Amascut": 15,
                                    "Tombs of Amascut: Expert Mode": 0,
                                }
                            )
                        },
                    }
                }
            }
        }
        current = boss_snapshot(
            **{
                "Tombs of Amascut": 16,
                "Tombs of Amascut: Expert Mode": 1,
            }
        )

        goal = boss_progression.build_weekly_raid_goal(
            TRACKER,
            week_summary,
            previous,
            "jhusebachz",
            current,
        )

        self.assertEqual(goal["completed"], 1)
        self.assertEqual(len(goal["gainsByRaid"]), 2)


if __name__ == "__main__":
    unittest.main()
