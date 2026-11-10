"""Cumulative, XP-rate-based max-cape pacing for the main account.

The fixed baseline is the November 10, 2026 saved HiScores snapshot. Only
independently trained skills, including Slayer, participate in the hours clock.
Combat skills gain XP while training Slayer and are tracked without an ETA.
"""

from __future__ import annotations

from datetime import date


START_DATE = date(2026, 11, 10)
DEADLINE = date(2027, 12, 31)
COMBAT_SKILLS = frozenset({"attack", "strength", "defence", "hitpoints", "ranged", "magic"})

# Captured from data/last_stats.json at 2026-11-10T16:30:09Z.
# This baseline must not advance with each report.
BASELINE_XP = {
    "attack": 6911064, "defence": 7346630, "strength": 8978556,
    "hitpoints": 11963566, "ranged": 9539002, "prayer": 5913748,
    "magic": 10269148, "cooking": 13068433, "woodcutting": 13079713,
    "fletching": 13071209, "fishing": 7969315, "firemaking": 13044442,
    "crafting": 6615502, "smithing": 6570952, "mining": 7364278,
    "herblore": 6558088, "agility": 6368115, "thieving": 6521043,
    "slayer": 6881525, "farming": 14439043, "runecraft": 5351333,
    "hunter": 6529179, "construction": 6537896, "sailing": 12331208,
}


def build_summary(tracker, stats: dict | None, today: date | None = None) -> dict:
    report_date = today or tracker.get_tracker_now().date()
    xp_for_99 = tracker.level_to_xp(99)
    if not isinstance(stats, dict) or any(
        not isinstance(stats.get(skill), dict)
        or not isinstance(stats[skill].get("experience"), (int, float))
        or stats[skill]["experience"] < 0
        or not isinstance(stats[skill].get("level"), int)
        or stats[skill]["level"] < 1
        for skill in tracker.SKILLS
    ):
        return {"available": False, "startDate": START_DATE.isoformat(), "deadline": DEADLINE.isoformat()}

    initial_hours = 0.0
    remaining_hours = 0.0
    remaining_timed = []
    combat = []
    unestimated = []
    maxed = 0
    capped_xp = 0

    for skill in tracker.SKILLS:
        level = stats[skill]["level"]
        xp = stats[skill]["experience"]
        capped_xp += min(xp, xp_for_99)
        maxed += int(level >= 99)
        if skill in COMBAT_SKILLS:
            if level < 99:
                combat.append({"skill": skill, "level": level, "remainingXp": max(xp_for_99 - xp, 0)})
            continue

        plan = tracker.GOAL_TRAINING_PLANS.get(skill)
        rate = plan.get("xp_per_hour", 0) if isinstance(plan, dict) else 0
        if rate <= 0:
            if level < 99:
                unestimated.append(skill)
            continue
        starting = max(xp_for_99 - BASELINE_XP[skill], 0) / rate
        remaining = max(xp_for_99 - xp, 0) / rate
        initial_hours += starting
        remaining_hours += remaining
        if level < 99:
            remaining_timed.append({
                "skill": skill, "level": level, "remainingXp": max(xp_for_99 - xp, 0),
                "hoursLeft": remaining, "xpPerHour": rate,
            })

    remaining_timed.sort(key=lambda item: item["hoursLeft"], reverse=True)
    elapsed_days = max(min((report_date - START_DATE).days, (DEADLINE - START_DATE).days), 0)
    total_days = max((DEADLINE - START_DATE).days, 1)
    expected_hours = initial_hours * elapsed_days / total_days
    completed_hours = initial_hours - remaining_hours
    return {
        "available": True,
        "startDate": START_DATE.isoformat(),
        "deadline": DEADLINE.isoformat(),
        "daysLeft": max((DEADLINE - report_date).days, 0),
        "maxedSkills": maxed,
        "totalSkills": len(tracker.SKILLS),
        "totalLevel": stats["overall"]["level"] if isinstance(stats.get("overall"), dict) else sum(stats[s]["level"] for s in tracker.SKILLS),
        "xpProgressPct": round(100 * capped_xp / (len(tracker.SKILLS) * xp_for_99), 2),
        "startingTimedHours": round(initial_hours, 4),
        "completedTimedHours": round(completed_hours, 4),
        "expectedTimedHours": round(expected_hours, 4),
        "remainingTimedHours": round(remaining_hours, 4),
        "hoursAhead": round(completed_hours - expected_hours, 4),
        "timedProgressPct": round(100 * completed_hours / initial_hours, 2) if initial_hours else 100.0,
        "timedSkills": remaining_timed,
        "untimedCombat": combat,
        "unestimatedSkills": unestimated,
    }


def build_html(tracker, summary: dict) -> str:
    if not summary.get("available"):
        return tracker.section("Road to Max Cape - December 31, 2027", "<p>HiScores data unavailable.</p>")

    delta = summary["hoursAhead"]
    status = f"{abs(delta):.1f} hours {'ahead' if delta >= 0 else 'behind'}"
    content = (
        '<table width="100%" cellpadding="0" cellspacing="0">'
        + tracker.row("Maxed skills", f'{summary["maxedSkills"]}/{summary["totalSkills"]}')
        + tracker.row("Total level", f'{summary["totalLevel"]:,}/{summary["totalSkills"] * 99:,}')
        + tracker.row("XP toward all 99s", f'{summary["xpProgressPct"]:.1f}%')
        + tracker.row("Timed grind remaining", f'{summary["remainingTimedHours"]:.1f} hours')
        + tracker.row("Cumulative timed work completed", f'{summary["completedTimedHours"]:.1f} hours')
        + tracker.row("Expected by today", f'{summary["expectedTimedHours"]:.1f} hours')
        + tracker.row("Against deadline", status)
        + tracker.row("Deadline", f'{summary["deadline"]} ({summary["daysLeft"]} days left)')
        + '</table>'
        + tracker.progress_bar(summary["xpProgressPct"], "#ec4899")
        + '<p style="font-size:12px;color:#6b7280;">The hours clock starts November 10, 2026. '
          'Combat skills are tracked toward 99 without an hourly deadline because Slayer also trains them.</p>'
    )
    if summary["timedSkills"]:
        content += '<div style="font-size:12px;font-weight:700;margin:8px 0;">Largest remaining timed skills</div>'
        for skill in summary["timedSkills"][:5]:
            content += (
                f'<div style="font-size:12px;padding:3px 0;">'
                f'<b>{tracker.format_skill_name(skill["skill"])}</b> '
                f'Lv{skill["level"]} · {skill["hoursLeft"]:.1f}h to 99</div>'
            )
    return tracker.section("Road to Max Cape - December 31, 2027", content)


def build_plain_text(tracker, summary: dict) -> str:
    if not summary.get("available"):
        return "ROAD TO MAX CAPE: HiScores unavailable."
    delta = summary["hoursAhead"]
    lines = [
        "ROAD TO MAX CAPE - DECEMBER 31, 2027",
        f'Maxed: {summary["maxedSkills"]}/{summary["totalSkills"]} | Total level: {summary["totalLevel"]:,}',
        f'All-99 XP progress: {summary["xpProgressPct"]:.1f}%',
        f'Timed hours: {summary["completedTimedHours"]:.1f} completed / {summary["expectedTimedHours"]:.1f} expected',
        f'Cumulative pace: {abs(delta):.1f} hours {"ahead" if delta >= 0 else "behind"}',
        f'Timed hours remaining: {summary["remainingTimedHours"]:.1f}',
        "Combat skills have no hourly deadline; Slayer trains them concurrently.",
        "Largest timed grinds:",
    ]
    lines.extend(
        f'- {tracker.format_skill_name(item["skill"])} Lv{item["level"]}: {item["hoursLeft"]:.1f}h'
        for item in summary["timedSkills"][:5]
    )
    return "\n".join(lines)
