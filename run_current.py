"""Current tracker configuration layered over the stable report generator.

This keeps historical tracker data intact while allowing username and goal changes
without duplicating the full report implementation in main.py.
"""

from __future__ import annotations

from datetime import date

import boss_progression
import main as tracker
import progression_goals


# Active friend roster. 3Sixteen is the current name of the account formerly
# tracked as gwahpy.
tracker.FRIENDS = ["3Sixteen", "beefmissle13", "kingxdabber", "hedith", "TooClose42"]

# Base 92s remains the dated skill goal. Diary requirements are milestone-based.
tracker.GOAL_ONE_DATE = date(2026, 12, 31)

_latest_boss_kcs: dict[str, int] = {}
_latest_raid_goal: dict = {
    "target": 1,
    "completed": 0,
    "weekStartDateKey": None,
    "baselineKcs": {},
    "gainsByRaid": [],
}


_original_calculate_gains = tracker.calculate_gains


def calculate_gains_with_name_history(old_all: dict, username: str, current_stats: dict) -> dict[str, int]:
    """Preserve one-step XP continuity across the gwahpy -> 3Sixteen rename."""
    if username == "3Sixteen" and old_all and username not in old_all and "gwahpy" in old_all:
        old_all = {**old_all, username: old_all["gwahpy"]}

    return _original_calculate_gains(old_all, username, current_stats)


tracker.calculate_gains = calculate_gains_with_name_history


# Pull boss/activity KC from the same official HiScores source used for skills.
_original_fetch_player = tracker.fetch_player


def fetch_player_with_bosses(username: str) -> dict:
    global _latest_boss_kcs

    stats = _original_fetch_player(username)
    if username == tracker.USERNAME:
        try:
            _latest_boss_kcs = boss_progression.fetch_boss_kcs(tracker, username)
        except Exception as error:  # noqa: BLE001 - keep daily report alive if activity rows fail
            print(f"Warning: could not fetch boss HiScores for {username}: {error}")
    return stats


tracker.fetch_player = fetch_player_with_bosses


# Carry boss data into the Monday-based weekly summary and measure whether any
# supported raid KC increased since that week's baseline.
_original_build_current_week_summary = tracker.build_current_week_summary


def build_current_week_summary_with_raids(
    previous_all: dict,
    username: str,
    current_stats: dict,
    report_date_key: str,
    last_seven_days_summary: dict,
) -> dict:
    global _latest_boss_kcs, _latest_raid_goal

    summary = _original_build_current_week_summary(
        previous_all,
        username,
        current_stats,
        report_date_key,
        last_seven_days_summary,
    )

    if not _latest_boss_kcs:
        previous_bosses = (
            previous_all.get(tracker.METADATA_KEY, {})
            .get("bosses", {})
            .get(username, {})
        )
        if isinstance(previous_bosses, dict):
            _latest_boss_kcs = {
                str(name): max(int(kc), 0)
                for name, kc in previous_bosses.items()
                if isinstance(kc, (int, float))
            }

    _latest_raid_goal = boss_progression.build_weekly_raid_goal(
        tracker,
        summary,
        previous_all,
        username,
        _latest_boss_kcs,
    )
    summary["raidGoal"] = _latest_raid_goal
    return summary


tracker.build_current_week_summary = build_current_week_summary_with_raids


# Persist the boss KC snapshot and the already-sorted first-KC queue for Johnny.
_original_build_snapshot_metadata = tracker.build_snapshot_metadata


def build_snapshot_metadata_with_bosses(
    username: str,
    effective_hours_summary: dict,
    last_seven_days_summary: dict,
    daily_summary: dict,
    current_week_summary: dict,
    report_date_key: str,
) -> dict:
    metadata = _original_build_snapshot_metadata(
        username,
        effective_hours_summary,
        last_seven_days_summary,
        daily_summary,
        current_week_summary,
        report_date_key,
    )
    metadata["bosses"] = {username: _latest_boss_kcs}
    metadata["bossProgression"] = {
        username: boss_progression.build_boss_progression(_latest_boss_kcs)
    }
    return metadata


tracker.build_snapshot_metadata = build_snapshot_metadata_with_bosses


_original_goal_one_html = tracker.goal_one_html


def goal_one_html_year_end(stats: dict, gains: dict) -> str:
    return _original_goal_one_html(stats, gains).replace("RuneFest", "Year End")


tracker.goal_one_html = goal_one_html_year_end


# Goal 2 is now the exact skill-level checklist needed for every Achievement Diary.
def diary_goal_html(stats: dict, _gains: dict) -> str:
    return progression_goals.build_diary_goal_html(tracker, stats)


tracker.total_level_html = diary_goal_html


# Reuse the former max-cape report slot for first-KC progression + the weekly raid.
def boss_and_raid_goal_html(_stats: dict, _gains: dict) -> str:
    return boss_progression.build_boss_and_raid_html(
        tracker,
        _latest_boss_kcs,
        _latest_raid_goal,
    )


tracker.max_progress_html = boss_and_raid_goal_html


def current_coaching_html(stats: dict) -> str:
    base_remaining = [
        skill
        for skill in tracker.SKILLS
        if skill in stats and stats[skill]["level"] < tracker.goal_one_target_level(skill)
    ]
    diary_summary = progression_goals.build_diary_summary(tracker, stats)
    boss_summary = boss_progression.build_boss_progression(_latest_boss_kcs)
    next_bosses = boss_summary.get("nextUntried", [])
    next_boss = next_bosses[0]["name"] if next_bosses else None
    raid_done = int(_latest_raid_goal.get("completed", 0)) >= int(_latest_raid_goal.get("target", 1))

    paragraphs = [
        (
            f'Base 92s: <b>{len(tracker.SKILLS) - len(base_remaining)}/{len(tracker.SKILLS)} skills at target</b>. '
            + (
                "Keep chipping away at the remaining base levels."
                if base_remaining
                else "Base goal complete."
            )
        ),
        (
            f'Achievement Diary levels: <b>{diary_summary["completed"]}/{diary_summary["total"]} complete</b>. '
            + (
                f'{len(diary_summary["remaining"])} skill requirements remain.'
                if diary_summary["remaining"]
                else "All diary skill requirements are met."
            )
        ),
        (
            f'Next first-KC target: <b>{next_boss}</b>.'
            if next_boss
            else "First-KC boss queue is complete."
        ),
        (
            "Weekly raid: <b>complete</b>."
            if raid_done
            else "Weekly raid: <b>1 completion still needed</b> from CoX, ToA, or ToB."
        ),
    ]
    content = "".join(
        f'<p style="margin:0 0 10px 0; font-size:14px; color:#374151; line-height:1.6;">{text}</p>'
        for text in paragraphs
    )
    return tracker.section("Daily Coaching Insight", content)


tracker.coaching_html = current_coaching_html


if __name__ == "__main__":
    tracker.main()
