"""HTML helpers for the current OSRS progression goals and milestone dashboard."""

from __future__ import annotations

from datetime import date


ALL_95_DATE = date(2027, 6, 30)


def build_all_95_goal_html(tracker, stats: dict) -> str:
    target_level = 95
    target_xp = tracker.level_to_xp(target_level)
    days_left = tracker.days_until(ALL_95_DATE)
    completed = []
    remaining = []

    for skill in tracker.SKILLS:
        if skill not in stats:
            continue
        level = stats[skill]["level"]
        if level >= target_level:
            completed.append(skill)
            continue

        remaining_xp = max(target_xp - stats[skill]["experience"], 0)
        hours_left, rate_text = tracker.projected_hours(skill, remaining_xp)
        remaining.append((skill, level, remaining_xp, hours_left, rate_text))

    remaining.sort(key=lambda item: (item[3] is None, item[3] or 0, item[2]))
    estimated_hours = sum(item[3] for item in remaining if item[3] is not None)
    manual_skills = [
        tracker.format_skill_name(item[0])
        for item in remaining
        if item[3] is None and not tracker.is_slayer_tracked_skill(item[0])
    ]
    hours_per_day = estimated_hours / days_left if days_left > 0 else None
    pace_status = tracker.classify_goal(hours_per_day, manual_skills)
    progress_pct = round((len(completed) / len(tracker.SKILLS)) * 100, 1)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {tracker.row("Deadline", f"{ALL_95_DATE} ({days_left} days left)")}
  {tracker.row("Skills at 95+", f"{len(completed)}/{len(tracker.SKILLS)}")}
  {tracker.row("Estimated direct grind", f"{estimated_hours:.1f} hours" if remaining else "Complete")}
  {tracker.row("Required pace", f"{hours_per_day:.2f} h/day" if hours_per_day is not None else "Manual estimate")}
  {tracker.row("Pace check", pace_status)}
</table>
{tracker.progress_bar(progress_pct, "#8b5cf6")}
"""

    if remaining:
        content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Still below 95</div>'
        for skill, level, remaining_xp, hours_left, rate_text in remaining:
            estimate = f"{hours_left:.1f}h" if hours_left is not None else rate_text
            content += (
                f'<div style="font-size:12px; color:#374151; padding:2px 0;">'
                f'&bull; <b>{tracker.format_skill_name(skill)}</b> Lv{level} / 95 '
                f'<span style="color:#6b7280;">&middot; {remaining_xp:,} xp &middot; {estimate}</span></div>'
            )
    else:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">All skills are 95+.</div>'

    return tracker.section("Goal 2 - All Skills 95+ by June 30, 2027", content)


def build_milestones_html(tracker, stats: dict) -> str:
    all_90_remaining = [
        (skill, stats[skill]["level"])
        for skill in tracker.SKILLS
        if skill in stats and stats[skill]["level"] < 90
    ]
    all_90_completed = len(tracker.SKILLS) - len(all_90_remaining)
    total_level = stats.get("overall", {}).get("level", 0)
    hunter_level = stats.get("hunter", {}).get("level", 0)
    hunter_xp = stats.get("hunter", {}).get("experience", 0)
    hunter_99_pct = tracker.clamp_pct(hunter_xp / max(tracker.level_to_xp(99), 1) * 100)
    maxed_count = sum(1 for skill in tracker.SKILLS if skill in stats and stats[skill]["level"] >= 99)

    all_90_pct = tracker.clamp_pct(all_90_completed / len(tracker.SKILLS) * 100)
    total_2300_pct = tracker.clamp_pct((total_level - 2250) / 50 * 100)
    eight_99_pct = tracker.clamp_pct(maxed_count / 8 * 100)
    ten_99_pct = tracker.clamp_pct(maxed_count / 10 * 100)
    remaining_90_text = " | ".join(
        f"{tracker.format_skill_name(skill)} {level}" for skill, level in all_90_remaining
    )

    content = f"""
<div style="font-size:13px; font-weight:700; color:#1e1b4b;">All skills 90+</div>
<div style="font-size:12px; color:#6b7280;">{all_90_completed}/{len(tracker.SKILLS)} skills complete</div>
{tracker.progress_bar(all_90_pct, "#8b5cf6")}
<div style="font-size:12px; color:#6b7280; margin-bottom:12px;">{f'Remaining: {remaining_90_text}' if remaining_90_text else 'Complete'}</div>

<div style="font-size:13px; font-weight:700; color:#1e1b4b;">2300 Total Level</div>
<div style="font-size:12px; color:#6b7280;">{total_level} / 2300</div>
{tracker.progress_bar(total_2300_pct, "#8b5cf6")}

<div style="font-size:13px; font-weight:700; color:#1e1b4b; margin-top:12px;">99 Hunter</div>
<div style="font-size:12px; color:#6b7280;">Hunter Lv{hunter_level} / 99</div>
{tracker.progress_bar(hunter_99_pct, "#8b5cf6")}

<div style="font-size:13px; font-weight:700; color:#1e1b4b; margin-top:12px;">8 Skills at 99</div>
<div style="font-size:12px; color:#6b7280;">{maxed_count} / 8</div>
{tracker.progress_bar(eight_99_pct, "#8b5cf6")}

<div style="font-size:13px; font-weight:700; color:#1e1b4b; margin-top:12px;">10 Skills at 99</div>
<div style="font-size:12px; color:#6b7280;">{maxed_count} / 10</div>
{tracker.progress_bar(ten_99_pct, "#8b5cf6")}
"""
    return tracker.section("Progress Milestones", content)


def build_progression_html(tracker, stats: dict) -> str:
    return build_all_95_goal_html(tracker, stats) + build_milestones_html(tracker, stats)
