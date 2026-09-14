"""Achievement Diary skill-goal helpers for the OSRS tracker."""

from __future__ import annotations


# Highest unboosted skill requirements needed across all Elite Achievement Diaries.
# Combat level, quest points, and one-off activity requirements are intentionally
# excluded here; this goal is specifically the skill-level checklist.
DIARY_SKILL_TARGETS = {
    "attack": 50,
    "defence": 70,
    "strength": 76,
    "hitpoints": 70,
    "ranged": 70,
    "prayer": 85,
    "magic": 96,
    "cooking": 95,
    "woodcutting": 90,
    "fletching": 95,
    "fishing": 96,
    "firemaking": 85,
    "crafting": 85,
    "smithing": 91,
    "mining": 85,
    "herblore": 90,
    "agility": 90,
    "thieving": 91,
    "slayer": 95,
    "farming": 91,
    "runecraft": 91,
    "hunter": 70,
    "construction": 78,
    "sailing": 62,
}


def get_diary_remaining(tracker, stats: dict) -> list[dict]:
    remaining = []

    for skill in tracker.SKILLS:
        target_level = DIARY_SKILL_TARGETS.get(skill)
        if target_level is None or skill not in stats:
            continue

        level = stats[skill]["level"]
        if level >= target_level:
            continue

        target_xp = tracker.level_to_xp(target_level)
        remaining_xp = max(target_xp - stats[skill]["experience"], 0)
        hours_left, rate_text = tracker.projected_hours(skill, remaining_xp)
        remaining.append(
            {
                "skill": skill,
                "level": level,
                "targetLevel": target_level,
                "remainingXp": remaining_xp,
                "hoursLeft": hours_left,
                "rateText": rate_text,
            }
        )

    remaining.sort(
        key=lambda item: (
            item["hoursLeft"] is None,
            item["hoursLeft"] or 0,
            item["remainingXp"],
        )
    )
    return remaining


def build_diary_summary(tracker, stats: dict) -> dict:
    remaining = get_diary_remaining(tracker, stats)
    tracked = len(DIARY_SKILL_TARGETS)
    completed = tracked - len(remaining)

    return {
        "completed": completed,
        "total": tracked,
        "remaining": remaining,
        "complete": len(remaining) == 0,
    }


def build_diary_goal_html(tracker, stats: dict) -> str:
    summary = build_diary_summary(tracker, stats)
    progress_pct = tracker.clamp_pct(summary["completed"] / max(summary["total"], 1) * 100)
    remaining = summary["remaining"]

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {tracker.row("Skills at diary requirement", f'{summary["completed"]}/{summary["total"]}')}
  {tracker.row("Skills still needed", str(len(remaining)))}
</table>
{tracker.progress_bar(progress_pct, "#8b5cf6")}
"""

    if not remaining:
        content += (
            '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">'
            "All Achievement Diary skill requirements are met.</div>"
        )
        return tracker.section("Goal 2 - Achievement Diary Skill Requirements", content)

    content += (
        '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; '
        'text-transform:uppercase; letter-spacing:.04em;">Still needed</div>'
    )
    for item in remaining:
        hours_left = item["hoursLeft"]
        estimate = f"{hours_left:.1f}h" if hours_left is not None else item["rateText"]
        content += (
            '<div style="font-size:12px; color:#374151; padding:3px 0;">'
            f'&bull; <b>{tracker.format_skill_name(item["skill"])}</b> '
            f'Lv{item["level"]} / {item["targetLevel"]} '
            f'<span style="color:#6b7280;">&middot; {item["remainingXp"]:,} xp &middot; {estimate}</span>'
            "</div>"
        )

    return tracker.section("Goal 2 - Achievement Diary Skill Requirements", content)
