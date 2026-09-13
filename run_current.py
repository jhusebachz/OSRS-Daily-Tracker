"""Current tracker configuration layered over the stable report generator.

This keeps historical tracker data intact while allowing username and goal changes
without duplicating the full report implementation in main.py.
"""

from __future__ import annotations

from datetime import date
import re

import main as tracker


# Active friend roster. 3Sixteen is the current name of the account formerly
# tracked as gwahpy.
tracker.FRIENDS = ["3Sixteen", "beefmissle13", "kingxdabber", "hedith", "TooClose42"]

# Active goals. The completed Total Level 2250 / RuneFest target is retained in
# the historical helper code but is no longer rendered as an active goal.
tracker.GOAL_ONE_DATE = date(2026, 12, 31)
tracker.GOAL_MAX_DATE = date(2027, 12, 31)


_original_calculate_gains = tracker.calculate_gains


def calculate_gains_with_name_history(old_all: dict, username: str, current_stats: dict) -> dict[str, int]:
    """Preserve one-step XP continuity across the gwahpy -> 3Sixteen rename."""
    if username == "3Sixteen" and old_all and username not in old_all and "gwahpy" in old_all:
        old_all = {**old_all, username: old_all["gwahpy"]}

    return _original_calculate_gains(old_all, username, current_stats)


tracker.calculate_gains = calculate_gains_with_name_history


_original_goal_one_html = tracker.goal_one_html


def goal_one_html_year_end(stats: dict, gains: dict) -> str:
    return _original_goal_one_html(stats, gains).replace("RuneFest", "Year End")


tracker.goal_one_html = goal_one_html_year_end


# Total Level 2250 is complete, so remove the old RuneFest card from active reports.
def completed_total_level_html(_stats: dict, _gains: dict) -> str:
    return ""


tracker.total_level_html = completed_total_level_html


_original_max_progress_html = tracker.max_progress_html


def max_progress_html_year_end(stats: dict, gains: dict) -> str:
    return (
        _original_max_progress_html(stats, gains)
        .replace("Goal 3 - Max Cape by 33rd Birthday", "Goal 2 - Max Cape by End of 2027")
        .replace("33rd birthday", "year-end target")
    )


tracker.max_progress_html = max_progress_html_year_end


_original_coaching_html = tracker.coaching_html


def coaching_html_without_runefest(stats: dict) -> str:
    html = _original_coaching_html(stats)
    return re.sub(
        r'<p[^>]*>\s*RuneFest 2250.*?</p>',
        "",
        html,
        flags=re.DOTALL,
    )


tracker.coaching_html = coaching_html_without_runefest


if __name__ == "__main__":
    tracker.main()
