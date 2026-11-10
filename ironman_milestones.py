"""Deadline-free, base-level progression for JorbisBTW."""

from __future__ import annotations


TIERS = (30, 40, 50, 60, 70, 80, 90, 99)


def build_summary(tracker, stats: dict | None, previous: dict | None = None) -> dict:
    if not isinstance(stats, dict) or any(
        not isinstance(stats.get(skill), dict)
        or not isinstance(stats[skill].get("level"), int)
        or stats[skill]["level"] < 1
        for skill in tracker.SKILLS
    ):
        return {"available": False, "account": "JorbisBTW"}

    stages = [
        {"level": tier, "completed": sum(stats[skill]["level"] >= tier for skill in tracker.SKILLS)}
        for tier in TIERS
    ]
    current_index = next((i for i, stage in enumerate(stages) if stage["completed"] < len(tracker.SKILLS)), len(TIERS) - 1)
    target = TIERS[current_index]
    remaining = sorted(
        ({"skill": skill, "level": stats[skill]["level"]} for skill in tracker.SKILLS if stats[skill]["level"] < target),
        key=lambda item: (item["level"], item["skill"]),
    )
    total_level = stats.get("overall", {}).get("level")
    if not isinstance(total_level, int) or total_level <= 0:
        total_level = sum(stats[skill]["level"] for skill in tracker.SKILLS)
    previous_level = previous.get("overall", {}).get("level") if isinstance(previous, dict) else None
    level_gain = max(total_level - previous_level, 0) if isinstance(previous_level, int) and previous_level > 0 else None
    return {
        "available": True,
        "account": "JorbisBTW",
        "totalLevel": total_level,
        "levelsGainedSincePrevious": level_gain,
        "targetLevel": target,
        "completed": stages[current_index]["completed"],
        "totalSkills": len(tracker.SKILLS),
        "remaining": remaining,
        "stages": stages,
        "nextTier": stages[current_index + 1] if current_index + 1 < len(stages) else None,
        "maxed": stages[-1]["completed"] == len(tracker.SKILLS),
    }


def build_html(tracker, summary: dict) -> str:
    if not summary.get("available"):
        return tracker.section("Ironman Milestones - JorbisBTW", "<p>HiScores data unavailable.</p>")
    total = summary["totalSkills"]
    content = (
        '<table width="100%" cellpadding="0" cellspacing="0">'
        + tracker.row("Total level", f'{summary["totalLevel"]:,}')
        + tracker.row("Current milestone", f'Base {summary["targetLevel"]}')
        + tracker.row("Skills at target", f'{summary["completed"]}/{total}')
        + tracker.row("Levels since previous report", f'+{summary["levelsGainedSincePrevious"]}' if summary["levelsGainedSincePrevious"] is not None else "Baseline pending")
        + (tracker.row("Next tier preview", f'Base {summary["nextTier"]["level"]}: {summary["nextTier"]["completed"]}/{total}') if summary["nextTier"] else "")
        + '</table>'
        + tracker.progress_bar(100 * summary["completed"] / total, "#16a34a")
    )
    if summary["maxed"]:
        content += '<p style="font-size:13px;color:#16a34a;">All skills at 99!</p>'
    elif summary["remaining"]:
        content += '<div style="font-size:12px;font-weight:700;margin:10px 0 4px;">Remaining for this milestone</div>'
        for item in summary["remaining"]:
            content += f'<div style="font-size:12px;padding:3px 0;">{tracker.format_skill_name(item["skill"])} Lv{item["level"]} / {summary["targetLevel"]}</div>'
    return tracker.section("Ironman Milestones - JorbisBTW", content)


def build_plain_text(tracker, summary: dict) -> str:
    if not summary.get("available"):
        return "IRONMAN MILESTONES: HiScores unavailable."
    lines = [
        "IRONMAN MILESTONES - JORBISBTW",
        f'Total level: {summary["totalLevel"]:,}',
        f'Base {summary["targetLevel"]}: {summary["completed"]}/{summary["totalSkills"]} skills',
    ]
    if summary["levelsGainedSincePrevious"] is not None:
        lines.append(f'Levels since previous report: +{summary["levelsGainedSincePrevious"]}')
    if summary["nextTier"]:
        lines.append(f'Base {summary["nextTier"]["level"]} preview: {summary["nextTier"]["completed"]}/{summary["totalSkills"]}')
    lines.extend(f'- {tracker.format_skill_name(item["skill"])}: Lv{item["level"]} / {summary["targetLevel"]}' for item in summary["remaining"])
    return "\n".join(lines)
