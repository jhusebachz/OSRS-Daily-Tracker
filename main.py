"""OSRS daily tracker and email report generator.

This script:
- fetches official hiscores for one primary account and a friend group
- compares the latest pull against the previously saved snapshot
- builds an HTML + plain text summary
- emails the report
- saves the latest snapshot back to disk
"""

from __future__ import annotations

import json
import os
import smtplib
import time
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests


USERNAME = "jhusebachz"
FRIENDS = ["gwahpy", "beefmissle13", "kingxdabber", "hedith"]

DATA_FILE = "data/last_stats.json"
METADATA_KEY = "_meta"

GOAL_ONE_DATE = date(2026, 10, 3)
GOAL_RUNEFEST_DATE = date(2026, 10, 3)
GOAL_MAX_DATE = date(2027, 3, 15)
GOAL_PROGRESS_START = date(2026, 3, 25)

GOAL_RUNEFEST_LEVEL = 2250
MAX_SKILL_LEVEL = 99

HISCORE_SKILLS = [
    "overall",
    "attack",
    "defence",
    "strength",
    "hitpoints",
    "ranged",
    "prayer",
    "magic",
    "cooking",
    "woodcutting",
    "fletching",
    "fishing",
    "firemaking",
    "crafting",
    "smithing",
    "mining",
    "herblore",
    "agility",
    "thieving",
    "slayer",
    "farming",
    "runecraft",
    "hunter",
    "construction",
    "sailing",
]

SKILLS = HISCORE_SKILLS[1:]

EMAIL = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
TO_EMAIL = EMAIL
HISCORE_HEADERS = {"User-Agent": "OSRS-Daily-Tracker/1.0"}
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
GOAL_TRAINING_PLANS = {
    "attack": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "strength": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "defence": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "hitpoints": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "ranged": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "magic": {"xp_per_hour": 0, "mode": "trained via Slayer"},
    "slayer": {"xp_per_hour": 40000, "mode": "active"},
    "prayer": {"xp_per_hour": 150000, "mode": "semi-afk"},
    "runecraft": {"xp_per_hour": 50000, "mode": "active"},
    "construction": {"xp_per_hour": 220000, "mode": "active"},
    "herblore": {"xp_per_hour": 200000, "mode": "active"},
    "agility": {"xp_per_hour": 50000, "mode": "active"},
    "crafting": {"xp_per_hour": 200000, "mode": "active"},
    "smithing": {"xp_per_hour": 220000, "mode": "active"},
    "woodcutting": {"xp_per_hour": 70000, "mode": "afk"},
    "fishing": {"xp_per_hour": 40000, "mode": "afk"},
    "mining": {"xp_per_hour": 40000, "mode": "afk"},
    "hunter": {"xp_per_hour": 70000, "mode": "afk"},
    "thieving": {"xp_per_hour": 180000, "mode": "active"},
    "sailing": {"xp_per_hour": 60000, "mode": "afk"},
}
# Directional XP/hour estimates for turning daily XP gains into a simple effective-hours signal.
# Tune these as your preferred training methods change.
EFFECTIVE_XP_PER_HOUR_BY_SKILL = {
    "attack": 80000,
    "strength": 90000,
    "defence": 80000,
    "ranged": 70000,
    "prayer": 150000,
    "magic": 90000,
    "runecraft": 50000,
    "construction": 220000,
    "hitpoints": 45000,
    "agility": 50000,
    "herblore": 200000,
    "thieving": 180000,
    "crafting": 200000,
    "fletching": 180000,
    "slayer": 40000,
    "hunter": 70000,
    "mining": 40000,
    "smithing": 220000,
    "fishing": 40000,
    "cooking": 250000,
    "firemaking": 250000,
    "woodcutting": 70000,
    "farming": 120000,
    "sailing": 60000,
}
GOAL_PROGRESS_BASELINE = {
    "overall": {"level": 2203, "experience": 173773255},
    "attack": {"level": 91, "experience": 6122415},
    "defence": {"level": 90, "experience": 5712800},
    "strength": {"level": 92, "experience": 7038075},
    "hitpoints": {"level": 95, "experience": 9363218},
    "ranged": {"level": 92, "experience": 7052764},
    "prayer": {"level": 89, "experience": 5079595},
    "magic": {"level": 95, "experience": 8857017},
    "cooking": {"level": 99, "experience": 13063406},
    "woodcutting": {"level": 90, "experience": 5440702},
    "fletching": {"level": 99, "experience": 13038303},
    "fishing": {"level": 90, "experience": 5424395},
    "firemaking": {"level": 99, "experience": 13044402},
    "crafting": {"level": 90, "experience": 5382552},
    "smithing": {"level": 90, "experience": 5414717},
    "mining": {"level": 90, "experience": 5367729},
    "herblore": {"level": 90, "experience": 5618952},
    "agility": {"level": 90, "experience": 5361513},
    "thieving": {"level": 87, "experience": 4003425},
    "slayer": {"level": 89, "experience": 4932213},
    "farming": {"level": 99, "experience": 14415682},
    "runecraft": {"level": 83, "experience": 2749504},
    "hunter": {"level": 86, "experience": 3625366},
    "construction": {"level": 90, "experience": 5361184},
    "sailing": {"level": 98, "experience": 12303326},
}


def goal_one_target_level(skill: str) -> int:
    return 90 if skill == "runecraft" else 92


def format_skill_name(skill: str) -> str:
    if skill == "runecraft":
        return "Runecraft"
    return skill.capitalize()


def build_effective_hours_summary(
    gains_by_skill: dict[str, int], xp_per_hour_by_skill: dict[str, int] | None = None
) -> dict:
    rates = xp_per_hour_by_skill or EFFECTIVE_XP_PER_HOUR_BY_SKILL
    by_skill: dict[str, float] = {}
    skipped_skills: list[str] = []

    for skill, xp_gained in gains_by_skill.items():
        if skill == "overall" or xp_gained <= 0:
            continue

        xp_per_hour = rates.get(skill)
        if not xp_per_hour or xp_per_hour <= 0:
            skipped_skills.append(skill)
            continue

        by_skill[skill] = xp_gained / xp_per_hour

    return {
        "totalHours": round(sum(by_skill.values()), 4),
        "bySkill": {skill: round(hours, 4) for skill, hours in by_skill.items()},
        "skippedSkills": sorted(skipped_skills),
    }


def get_top_effective_hour_contributors(
    effective_hours_summary: dict, limit: int = 3
) -> list[tuple[str, float]]:
    return sorted(
        (
            (skill, hours)
            for skill, hours in effective_hours_summary.get("bySkill", {}).items()
            if hours > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]


def build_snapshot_metadata(username: str, effective_hours_summary: dict, last_seven_days_summary: dict) -> dict:
    return {
        "generatedAt": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "effectiveHours": {
            username: effective_hours_summary,
        },
        "lastSevenDays": {
            username: last_seven_days_summary,
        },
    }


def build_top_skill_entries(gains_by_skill: dict[str, int], limit: int = 3) -> list[dict]:
    return [
        {"skill": skill, "xp": xp}
        for skill, xp in sorted(
            ((skill, xp) for skill, xp in gains_by_skill.items() if skill in SKILLS and xp > 0),
            key=lambda item: item[1],
            reverse=True,
        )[:limit]
    ]


def format_last_seven_days_label(date_key: str) -> str:
    return datetime.strptime(date_key, "%Y-%m-%d").strftime("%b %d").replace(" 0", " ")


def normalize_last_seven_days_entry(entry: dict) -> dict | None:
    if not isinstance(entry, dict):
        return None

    date_key = entry.get("dateKey")
    if not isinstance(date_key, str):
        return None

    top_skills = entry.get("topSkills", [])
    normalized_top_skills = []
    if isinstance(top_skills, list):
        normalized_top_skills = [
            {"skill": item["skill"], "xp": int(item["xp"])}
            for item in top_skills
            if isinstance(item, dict)
            and isinstance(item.get("skill"), str)
            and isinstance(item.get("xp"), (int, float))
            and item.get("xp", 0) >= 0
        ]

    total_xp = entry.get("totalXp", 0)
    effective_hours = entry.get("effectiveHours", 0)

    return {
        "dateKey": date_key,
        "label": entry.get("label") if isinstance(entry.get("label"), str) else format_last_seven_days_label(date_key),
        "totalXp": max(int(total_xp), 0) if isinstance(total_xp, (int, float)) else 0,
        "effectiveHours": max(float(effective_hours), 0.0) if isinstance(effective_hours, (int, float)) else 0.0,
        "topSkills": normalized_top_skills[:3],
    }


def build_last_seven_days_entry(report_date: str, gains: dict[str, int], effective_hours_summary: dict) -> dict:
    total_xp = sum(value for skill, value in gains.items() if skill in SKILLS)
    return {
        "dateKey": report_date,
        "label": format_last_seven_days_label(report_date),
        "totalXp": total_xp,
        "effectiveHours": round(float(effective_hours_summary.get("totalHours", 0)), 4),
        "topSkills": build_top_skill_entries(gains),
    }


def summarize_last_seven_days(entries: list[dict]) -> dict:
    sorted_entries = sorted(entries, key=lambda item: item["dateKey"], reverse=True)[:7]
    days_tracked = len(sorted_entries)
    active_days = sum(1 for entry in sorted_entries if entry["totalXp"] > 0 or entry["effectiveHours"] > 0)
    total_xp = sum(entry["totalXp"] for entry in sorted_entries)
    total_effective_hours = round(sum(entry["effectiveHours"] for entry in sorted_entries), 4)

    return {
        "daysTracked": days_tracked,
        "activeDays": active_days,
        "totalXp": total_xp,
        "totalEffectiveHours": total_effective_hours,
        "averageXp": round(total_xp / days_tracked, 2) if days_tracked > 0 else 0,
        "averageEffectiveHours": round(total_effective_hours / days_tracked, 4) if days_tracked > 0 else 0,
        "days": sorted_entries,
    }


def build_last_seven_days_summary(
    previous_all: dict,
    username: str,
    gains: dict[str, int],
    effective_hours_summary: dict,
    report_date: str | None = None,
) -> dict:
    report_date_key = report_date or datetime.now().strftime("%Y-%m-%d")
    previous_entries = (
        previous_all.get(METADATA_KEY, {})
        .get("lastSevenDays", {})
        .get(username, {})
        .get("days", [])
    )
    normalized_previous = [
        normalized
        for normalized in (normalize_last_seven_days_entry(entry) for entry in previous_entries)
        if normalized is not None and normalized["dateKey"] != report_date_key
    ]
    merged_entries = [
        build_last_seven_days_entry(report_date_key, gains, effective_hours_summary),
        *normalized_previous,
    ]
    return summarize_last_seven_days(merged_entries)


def fetch_player(username: str) -> dict:
    """Fetch one player's official OSRS hiscores from the lite CSV endpoint."""
    safe_name = username.replace(" ", "_")
    url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={safe_name}"
    response = requests.get(url, headers=HISCORE_HEADERS, timeout=10)
    response.raise_for_status()

    stats = {}
    lines = response.text.strip().splitlines()

    for index, line in enumerate(lines):
        if index >= len(HISCORE_SKILLS):
            break

        parts = line.strip().split(",")
        if len(parts) < 3:
            continue

        skill = HISCORE_SKILLS[index]
        stats[skill] = {
            "rank": int(parts[0]) if parts[0].strip() != "-1" else -1,
            "level": int(parts[1]),
            "experience": int(parts[2]),
        }

    return stats


def load_previous() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def save_current(your_stats: dict, friends_data: dict, metadata: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    all_stats = {METADATA_KEY: metadata, USERNAME: your_stats, **friends_data}

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(all_stats, file)


def calculate_gains(old_all: dict, username: str, current_stats: dict) -> dict[str, int]:
    gains: dict[str, int] = {}
    previous_stats = old_all.get(username) if old_all else None

    for skill in current_stats:
        if previous_stats and skill in previous_stats:
            gains[skill] = current_stats[skill]["experience"] - previous_stats[skill]["experience"]
        else:
            gains[skill] = 0

    return gains


def level_to_xp(level: int) -> int:
    points = 0

    for current_level in range(1, level):
        points += int(current_level + 300 * 2 ** (current_level / 7.0))

    return int(points / 4)


def days_until(target_date: date) -> int:
    return max((target_date - date.today()).days, 1)


def projected_hours(skill: str, remaining_xp: int) -> tuple[float | None, str]:
    plan = GOAL_TRAINING_PLANS.get(skill)
    if not plan:
        return None, "manual estimate"
    if plan["xp_per_hour"] <= 0:
        if plan["mode"] == "trained via Slayer":
            return 0.0, plan["mode"]
        return None, plan["mode"]

    return remaining_xp / plan["xp_per_hour"], f'{plan["xp_per_hour"]:,} xp/hr ({plan["mode"]})'


def classify_goal(hours_per_day: float | None, manual_skills: list[str]) -> str:
    _ = manual_skills
    if hours_per_day is None:
        return "Off track"
    if hours_per_day <= 1.5:
        return "On track"
    if hours_per_day <= 3:
        return "Tight"
    return "Off track"


def describe_goal_status(status: str) -> str:
    if status == "On track":
        return "is on track"
    if status == "Tight":
        return "looks tight"
    if status == "Off track":
        return "looks off track"
    return "needs review"


def is_slayer_tracked_skill(skill: str) -> bool:
    plan = GOAL_TRAINING_PLANS.get(skill)
    return bool(plan and plan["mode"] == "trained via Slayer")


def clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def partial_level_progress(level: int, experience: int) -> float:
    if level >= MAX_SKILL_LEVEL:
        return 0.0

    current_level_xp = level_to_xp(max(level, 1))
    next_level_xp = level_to_xp(max(level + 1, 2))
    span = max(next_level_xp - current_level_xp, 1)
    progressed_xp = max(experience - current_level_xp, 0)

    return max(0.0, min(1.0, progressed_xp / span))


def effective_total_level(stats: dict) -> float:
    total_level = stats["overall"]["level"] if "overall" in stats else sum(
        stats[skill]["level"] for skill in SKILLS if skill in stats
    )
    partial_progress = sum(
        partial_level_progress(stats[skill]["level"], stats[skill]["experience"])
        for skill in SKILLS
        if skill in stats
    )

    return total_level + partial_progress


def effective_levels_remaining(stats: dict, target_total_level: int) -> float:
    return max(target_total_level - effective_total_level(stats), 0.0)


def pace_pct(target_date: date) -> float:
    total_days = max((target_date - GOAL_PROGRESS_START).days, 1)
    elapsed_days = (date.today() - GOAL_PROGRESS_START).days
    return clamp_pct(elapsed_days / total_days * 100)


def build_runefest_projection(stats: dict, levels_needed: int) -> tuple[float, int, list[str]]:
    if levels_needed <= 0:
        return 0.0, 0, []

    projected = {
        skill: {
            "level": data["level"],
            "experience": data["experience"],
        }
        for skill, data in stats.items()
        if skill in SKILLS
    }
    manual_skills: set[str] = set()
    total_hours = 0.0
    total_xp = 0
    remaining_levels = levels_needed

    while remaining_levels > 0:
        best_skill = None
        best_hours = None

        for skill in SKILLS:
            if skill not in projected:
                continue

            plan = GOAL_TRAINING_PLANS.get(skill)
            if not plan or projected[skill]["level"] >= MAX_SKILL_LEVEL:
                continue

            if is_slayer_tracked_skill(skill):
                continue

            next_level = projected[skill]["level"] + 1
            remaining_xp = max(level_to_xp(next_level) - projected[skill]["experience"], 0)
            if remaining_xp <= 0:
                continue

            level_hours = remaining_xp / plan["xp_per_hour"]

            if best_hours is None or level_hours < best_hours:
                best_skill = skill
                best_hours = level_hours

        if best_skill is None or best_hours is None:
            for skill in SKILLS:
                if skill in projected and projected[skill]["level"] < MAX_SKILL_LEVEL:
                    manual_skills.add(format_skill_name(skill))
            break

        xp_needed = max(level_to_xp(projected[best_skill]["level"] + 1) - projected[best_skill]["experience"], 0)
        projected[best_skill]["level"] += 1
        projected[best_skill]["experience"] = level_to_xp(projected[best_skill]["level"])
        total_hours += best_hours
        total_xp += xp_needed
        remaining_levels -= 1

    return total_hours, total_xp, sorted(manual_skills)


def section(title: str, content_html: str) -> str:
    return f"""
<div style="margin: 24px 0; background: #ffffff; border-radius: 10px;
     border-left: 5px solid #8b5cf6; padding: 16px 20px;
     box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
  <h2 style="margin: 0 0 12px 0; font-size: 15px; font-weight: 700;
      color: #1e1b4b; text-transform: uppercase; letter-spacing: 0.05em;">
    {title}
  </h2>
  {content_html}
</div>"""


def row(label: str, value: str, muted: bool = False) -> str:
    color = "#6b7280" if muted else "#111827"
    return f"""<tr>
  <td style="padding: 4px 0; color: #6b7280; font-size: 13px; width: 55%;">{label}</td>
  <td style="padding: 4px 0; color: {color}; font-size: 13px; font-weight: 600; text-align: right;">{value}</td>
</tr>"""


def pill(text: str, color: str = "#8b5cf6") -> str:
    return (
        f'<span style="display:inline-block; background:{color}; color:#fff; '
        f'border-radius:999px; padding:2px 10px; font-size:12px; '
        f'font-weight:600; margin: 2px 3px;">{text}</span>'
    )


def progress_bar(percent: float, color: str = "#8b5cf6", marker_percent: float | None = None) -> str:
    clamped = min(max(percent, 0), 100)
    marker_html = ""
    if marker_percent is not None:
        marker_html = (
            f'<div style="position:absolute; left:{clamp_pct(marker_percent)}%; top:-2px; bottom:-2px; '
            f'width:2px; margin-left:-1px; border-radius:999px; background:#111827; opacity:0.9;"></div>'
        )
    return f"""
<div style="position:relative; background:#e5e7eb; border-radius:999px; height:8px; margin: 3px 0 8px 0; overflow:hidden;">
  <div style="background:{color}; width:{clamped}%; height:8px; border-radius:999px;"></div>
  {marker_html}
</div>"""


def goal_progress_pct(stats: dict, target: str) -> float:
    if target == "runefest":
        baseline_levels_needed = max(GOAL_RUNEFEST_LEVEL - GOAL_PROGRESS_BASELINE["overall"]["level"], 0)
        _, baseline_xp, _ = build_runefest_projection(GOAL_PROGRESS_BASELINE, baseline_levels_needed)
        current_levels_needed = max(GOAL_RUNEFEST_LEVEL - stats["overall"]["level"], 0)
        _, current_xp, _ = build_runefest_projection(stats, current_levels_needed)
        return clamp_pct(((baseline_xp - current_xp) / baseline_xp) * 100) if baseline_xp > 0 else 100.0

    baseline_needed = 0
    current_remaining = 0

    for skill in SKILLS:
        goal_level = goal_one_target_level(skill) if target == "basegoal" else 99
        baseline = GOAL_PROGRESS_BASELINE[skill]
        if baseline["level"] >= goal_level:
            continue

        target_xp = level_to_xp(goal_level)
        baseline_needed += max(target_xp - baseline["experience"], 0)
        current_remaining += max(target_xp - stats[skill]["experience"], 0)

    return clamp_pct(((baseline_needed - current_remaining) / baseline_needed) * 100) if baseline_needed > 0 else 100.0


def friend_comparison_html(your_gains: dict, friends_data: dict, previous_all: dict) -> str:
    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)

    rows_html = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Your total XP today", f"{your_total_xp:,}")}
</table>
<hr style="border:none; border-top:1px solid #f3f4f6; margin: 12px 0;">"""

    for friend in FRIENDS:
        if friend not in friends_data:
            rows_html += f'<p style="color:#6b7280; font-size:13px;">{friend}: data unavailable</p>'
            continue

        friend_gains = calculate_gains(previous_all, friend, friends_data[friend])
        friend_total_xp = sum(value for skill, value in friend_gains.items() if skill in SKILLS)
        diff = your_total_xp - friend_total_xp

        if diff > 0:
            badge = pill(f"Ahead by {diff:,} xp", "#16a34a")
        elif diff < 0:
            badge = pill(f"Trailing by {abs(diff):,} xp", "#dc2626")
        else:
            badge = pill("Dead even", "#d97706")

        top_three = sorted(
            ((skill, friend_gains[skill]) for skill in SKILLS if friend_gains.get(skill, 0) > 0),
            key=lambda item: item[1],
            reverse=True,
        )[:3]

        if top_three:
            top_three_html = "".join(
                f'<div style="font-size:12px; color:#374151; padding: 2px 0;">'
                f'&bull; {format_skill_name(skill)}: +{xp:,} xp '
                f'(Lv{friends_data[friend][skill]["level"]})</div>'
                for skill, xp in top_three
            )
        else:
            top_three_html = '<div style="font-size:12px; color:#9ca3af;">No xp gained today</div>'

        rows_html += f"""
<div style="margin-bottom: 14px;">
  <div style="font-size:14px; font-weight:700; color:#1e1b4b; margin-bottom:4px;">
    {friend}
    <span style="font-size:12px; font-weight:400; color:#6b7280; margin-left:6px;">{friend_total_xp:,} xp today</span>
    {badge}
  </div>
  <div style="font-size:12px; color:#6b7280; margin-bottom:3px;">Top gains:</div>
  {top_three_html}
</div>"""

    return section("Daily XP - You vs Friends", rows_html)


def goal_one_html(stats: dict, gains: dict) -> str:
    days_left = days_until(GOAL_ONE_DATE)
    progress_pct = goal_progress_pct(stats, "basegoal")
    required_pace_pct = pace_pct(GOAL_ONE_DATE)

    completed = []
    remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue

        target_level = goal_one_target_level(skill)

        if stats[skill]["level"] >= target_level:
            completed.append(skill)
            continue

        current_xp = stats[skill]["experience"]
        goal_xp = level_to_xp(target_level)
        remaining_xp = goal_xp - current_xp
        percent = round(current_xp / goal_xp * 100, 1)
        hours_left, rate_text = projected_hours(skill, remaining_xp)
        remaining.append((skill, stats[skill]["level"], target_level, percent, remaining_xp, hours_left, rate_text))

    remaining.sort(key=lambda item: item[3], reverse=True)
    estimated_hours = sum(item[5] for item in remaining if item[5] is not None)
    manual_skills = [
        format_skill_name(item[0]) for item in remaining if item[5] is None and not is_slayer_tracked_skill(item[0])
    ]
    hours_per_day = estimated_hours / days_left if days_left > 0 else None
    pace_status = classify_goal(hours_per_day, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_ONE_DATE} - RuneFest ({days_left} days left)")}
  {row("Skills at target+", f"{len(completed)}/{len(SKILLS)}", muted=not remaining)}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if remaining else "Complete", muted=not remaining)}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if hours_per_day is not None else "Manual estimate", muted=not remaining)}
  {row("Pace check", pace_status, muted=not remaining)}
</table>"""

    if not remaining:
        content += progress_bar(progress_pct, "#8b5cf6", required_pace_pct)
        content += (
            f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
            f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
        )
        content += '<div style="margin-top:8px; font-size:14px; color:#16a34a; font-weight:700;">Base 92s goal complete.</div>'
        return section("Goal 1 - Base 92s (Runecrafting 90) by RuneFest", content)

    content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Still needed</div>'

    for skill, level, target_level, percent, remaining_xp, hours_left, rate_text in remaining:
        bar_color = "#f59e0b" if percent >= 80 else "#8b5cf6"
        content += f"""
<div style="margin: 6px 0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px; color:#374151;">
    <tr>
      <td style="padding:0; color:#374151;">
        <b>{format_skill_name(skill)}</b> Lv{level} / {target_level}
      </td>
      <td style="padding:0 0 0 16px; color:#6b7280; text-align:right; white-space:nowrap;">
        {percent}% &middot; {remaining_xp:,} xp &middot; {f"{hours_left:.1f}h" if hours_left is not None else rate_text}
      </td>
    </tr>
  </table>
  {progress_bar(percent, bar_color)}
</div>"""

    content += progress_bar(progress_pct, "#8b5cf6", required_pace_pct)
    content += (
        f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
        f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
    )

    return section("Goal 1 - Base 92s (Runecrafting 90) by RuneFest", content)


def total_level_html(stats: dict, gains: dict) -> str:
    days_left = days_until(GOAL_RUNEFEST_DATE)
    total_level = stats["overall"]["level"] if "overall" in stats else sum(
        stats[skill]["level"] for skill in SKILLS if skill in stats
    )
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)
    effective_levels_left = effective_levels_remaining(stats, GOAL_RUNEFEST_LEVEL)
    percent = round(min(total_level / GOAL_RUNEFEST_LEVEL * 100, 100), 1)
    progress_pct = goal_progress_pct(stats, "runefest")
    required_pace_pct = pace_pct(GOAL_RUNEFEST_DATE)

    estimated_hours, _, manual_skills = build_runefest_projection(stats, levels_needed)
    hours_per_day = estimated_hours / days_left if levels_needed > 0 else 0
    effective_levels_per_day = effective_levels_left / days_left if effective_levels_left > 0 else 0
    pace_status = classify_goal(hours_per_day if levels_needed > 0 else 0, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_RUNEFEST_DATE} - RuneFest ({days_left} days left)")}
  {row("Current total level", f"{total_level:,} / {GOAL_RUNEFEST_LEVEL:,}")}
  {row("Levels still needed", f"{effective_levels_left:.2f} effective")}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if levels_needed > 0 else "Complete")}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if levels_needed > 0 else "Complete")}
  {row("Pace check", pace_status)}
</table>"""

    if levels_needed <= 0:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700;">RuneFest goal achieved.</div>'
    else:
        levels_per_day = round(levels_needed / days_left, 2)
        content += (
            f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">'
            f'Need <b>{effective_levels_per_day:.2f}</b> effective levels/day to hit {GOAL_RUNEFEST_LEVEL} in time'
            f' ({levels_per_day:.2f} full levels/day).</div>'
        )


    active = [(skill, gains.get(skill, 0)) for skill in SKILLS if skill in stats and gains.get(skill, 0) > 0]
    active.sort(key=lambda item: item[1], reverse=True)

    if active:
        content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Most active today</div>'
        for skill, xp in active[:5]:
            content += (
                f'<div style="font-size:12px; color:#374151; padding:2px 0;">'
                f'&bull; {format_skill_name(skill)}: +{xp:,} xp (Lv{stats[skill]["level"]})</div>'
            )

    content += progress_bar(progress_pct, "#3b82f6", required_pace_pct)
    content += (
        f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
        f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
    )

    return section(f"Goal 2 - Total Level {GOAL_RUNEFEST_LEVEL} by RuneFest", content)


def max_progress_html(stats: dict, gains: dict) -> str:
    days_left = days_until(GOAL_MAX_DATE)
    goal_xp = level_to_xp(MAX_SKILL_LEVEL)
    progress_pct = goal_progress_pct(stats, "maxcape")
    required_pace_pct = pace_pct(GOAL_MAX_DATE)

    maxed = []
    remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue

        if stats[skill]["level"] >= MAX_SKILL_LEVEL:
            maxed.append(skill)
            continue

        remaining_xp = goal_xp - stats[skill]["experience"]
        hours_left, rate_text = projected_hours(skill, remaining_xp)
        remaining.append((skill, stats[skill]["level"], remaining_xp, hours_left, rate_text))

    remaining.sort(key=lambda item: item[2])
    percent = round(len(maxed) / len(SKILLS) * 100, 1)
    estimated_hours = sum(item[3] for item in remaining if item[3] is not None)
    manual_skills = [
        format_skill_name(item[0]) for item in remaining if item[3] is None and not is_slayer_tracked_skill(item[0])
    ]
    hours_per_day = estimated_hours / days_left if days_left > 0 else None
    pace_status = classify_goal(hours_per_day, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_MAX_DATE} - 33rd birthday ({days_left} days left)")}
  {row("Skills maxed", f"{len(maxed)}/{len(SKILLS)}")}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if remaining else "Complete")}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if hours_per_day is not None else "Manual estimate")}
  {row("Pace check", pace_status)}
</table>"""

    if maxed:
        content += '<div style="margin: 6px 0 10px;">'
        content += "".join(pill(format_skill_name(skill), "#16a34a") for skill in maxed)
        content += "</div>"

    if not remaining:
        content += progress_bar(progress_pct, "#ec4899", required_pace_pct)
        content += (
            f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
            f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
        )
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">Maxed.</div>'
        return section("Goal 3 - Max Cape by 33rd Birthday", content)

    content += '<div style="font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em; margin-top:6px;">Closest to 99</div>'

    for skill, level, remaining_xp, hours_left, rate_text in remaining[:5]:
        skill_percent = round((goal_xp - remaining_xp) / goal_xp * 100, 1)
        content += f"""
<div style="margin: 6px 0;">
  <div style="font-size:12px; color:#374151;">
    <b>{format_skill_name(skill)}</b> Lv{level}
    <span style="color:#6b7280;"> Â· {remaining_xp:,} xp to 99 Â· {f"{hours_left:.1f}h" if hours_left is not None else rate_text}</span>
  </div>
  {progress_bar(skill_percent, "#ec4899")}
</div>"""

    content += progress_bar(progress_pct, "#ec4899", required_pace_pct)
    content += (
        f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
        f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
    )

    return section("Goal 3 - Max Cape by 33rd Birthday", content)


def coaching_html(your_stats: dict) -> str:
    goal_one_hours = []
    goal_one_manual = []
    max_hours = []
    max_manual = []

    for skill in SKILLS:
        if skill not in your_stats:
            continue

        goal_one_level = goal_one_target_level(skill)

        if your_stats[skill]["level"] < goal_one_level:
            remaining_xp = max(level_to_xp(goal_one_level) - your_stats[skill]["experience"], 0)
            hours_left, _ = projected_hours(skill, remaining_xp)
            if hours_left is None:
                if not is_slayer_tracked_skill(skill):
                    goal_one_manual.append(format_skill_name(skill))
            else:
                goal_one_hours.append(hours_left)

        if your_stats[skill]["level"] < 99:
            remaining_xp = max(level_to_xp(99) - your_stats[skill]["experience"], 0)
            hours_left, _ = projected_hours(skill, remaining_xp)
            if hours_left is None:
                if not is_slayer_tracked_skill(skill):
                    max_manual.append(format_skill_name(skill))
            else:
                max_hours.append(hours_left)

    total_level = your_stats["overall"]["level"] if "overall" in your_stats else 0
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)
    runefest_total, _, runefest_manual = build_runefest_projection(your_stats, levels_needed)
    runefest_effective_levels_left = effective_levels_remaining(your_stats, GOAL_RUNEFEST_LEVEL)

    goal_one_days = days_until(GOAL_ONE_DATE)
    runefest_days = days_until(GOAL_RUNEFEST_DATE)
    max_days = days_until(GOAL_MAX_DATE)

    goal_one_total = sum(goal_one_hours)
    max_total = sum(max_hours)

    goal_one_rate = goal_one_total / goal_one_days if goal_one_days > 0 else None
    runefest_rate = runefest_total / runefest_days if runefest_days > 0 else None
    runefest_effective_levels_rate = runefest_effective_levels_left / runefest_days if runefest_days > 0 else 0
    max_rate = max_total / max_days if max_days > 0 else None

    content = "".join(
        [
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'Base 92s <b>{describe_goal_status(classify_goal(goal_one_rate, goal_one_manual))}</b> at '
            f'<b>{goal_one_rate:.2f} hours/day</b> through {GOAL_ONE_DATE}.'

            f'</p>',
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'RuneFest 2250 <b>{describe_goal_status(classify_goal(runefest_rate, runefest_manual))}</b> at '
            f'<b>{runefest_rate:.2f} hours/day</b> and <b>{runefest_effective_levels_rate:.2f} effective levels/day</b>.'

            f'</p>',
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'Max cape <b>{describe_goal_status(classify_goal(max_rate, max_manual))}</b> at '
            f'<b>{max_rate:.2f} hours/day</b> through {GOAL_MAX_DATE}.'

            f'</p>',
        ]
    )

    return section("Daily Coaching Insight", content)


def last_seven_days_html(last_seven_days_summary: dict) -> str:
    days = last_seven_days_summary.get("days", [])
    if not days:
        return section(
            "Last 7 Days",
            '<p style="margin:0; font-size:13px; color:#6b7280;">No seven-day history is available yet.</p>',
        )

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Total progress", f"{last_seven_days_summary.get('totalXp', 0):,} xp")}
  {row("Effective hours", f"{last_seven_days_summary.get('totalEffectiveHours', 0):.1f} h")}
  {row("Active days", f"{last_seven_days_summary.get('activeDays', 0)} / {last_seven_days_summary.get('daysTracked', len(days))}")}
  {row("Average per tracked day", f"{round(last_seven_days_summary.get('averageXp', 0)):,} xp · {last_seven_days_summary.get('averageEffectiveHours', 0):.1f}h")}
</table>"""

    for day in days:
        top_skills = day.get("topSkills", [])
        top_skills_html = " · ".join(
            f"{format_skill_name(item['skill'])} {item['xp']:,} xp"
            for item in top_skills
            if isinstance(item, dict) and item.get("xp", 0) > 0
        )
        content += f"""
<div style="margin-top:10px; border-radius:12px; border:1px solid #e5e7eb; background:#f9fafb; padding:12px;">
  <div style="font-size:13px; font-weight:700; color:#111827; margin-bottom:4px;">{day['label']}</div>
  <div style="font-size:12px; color:#6b7280;">{day['totalXp']:,} xp · {day['effectiveHours']:.1f}h</div>
  {f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">Top skills: {top_skills_html}</div>' if top_skills_html else ''}
</div>"""

    return section("Last 7 Days", content)


def build_html_email(
    your_gains: dict,
    your_stats: dict,
    friends_data: dict,
    previous_all: dict,
    effective_hours_summary: dict,
    last_seven_days_summary: dict,
) -> str:
    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)
    today = datetime.now().strftime("%B %d, %Y")
    top_effective_hours = get_top_effective_hour_contributors(effective_hours_summary)

    top_gains = sorted(
        ((skill, your_gains[skill]) for skill in SKILLS if your_gains.get(skill, 0) > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:5]

    if top_gains:
        top_gains_html = "".join(
            f'<div style="font-size:13px; color:#374151; padding:3px 0;">'
            f'<b>{format_skill_name(skill)}</b>: +{xp:,} xp</div>'
            for skill, xp in top_gains
        )
    else:
        top_gains_html = '<div style="font-size:13px; color:#9ca3af;">No xp gained today</div>'

    if top_effective_hours:
        top_effective_hours_html = "".join(
            f'<div style="font-size:12px; color:rgba(255,255,255,0.78); padding:2px 0;">'
            f'<b>{format_skill_name(skill)}</b>: {hours:.1f}h</div>'
            for skill, hours in top_effective_hours
        )
    else:
        top_effective_hours_html = ""

    header_section = f"""
<div style="background: linear-gradient(135deg, #1e1b4b 0%, #4c1d95 100%);
     border-radius: 12px; padding: 28px 24px; margin-bottom: 8px; color: white;">
  <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em;
       opacity: 0.7; margin-bottom: 6px;">OSRS Daily Report</div>
  <div style="font-size: 26px; font-weight: 800; margin-bottom: 4px;">{today}</div>
  <div style="font-size: 28px; font-weight: 800; margin-top: 16px;">{your_total_xp:,} <span style="font-size:14px; font-weight:400; opacity:0.8;">XP gained today</span></div>
  <div style="margin-top: 12px; font-size: 14px; color: rgba(255,255,255,0.92);">
    Effective hours played today: <b>{effective_hours_summary.get("totalHours", 0):.1f} hours</b>
  </div>
  <div style="margin-top: 8px; font-size: 13px; color: rgba(255,255,255,0.78);">
    Last 7 days: <b>{last_seven_days_summary.get("totalXp", 0):,} xp</b> over
    <b>{last_seven_days_summary.get("totalEffectiveHours", 0):.1f} hours</b>
  </div>
  {f'<div style="margin-top: 10px;">{top_effective_hours_html}</div>' if top_effective_hours_html else ''}
  <div style="margin-top: 14px;">{top_gains_html.replace('color:#374151', 'color:rgba(255,255,255,0.85)').replace('color:#9ca3af', 'color:rgba(255,255,255,0.5)')}</div>
</div>"""

    body = (
        header_section
        + friend_comparison_html(your_gains, friends_data, previous_all)
        + last_seven_days_html(last_seven_days_summary)
        + goal_one_html(your_stats, your_gains)
        + total_level_html(your_stats, your_gains)
        + max_progress_html(your_stats, your_gains)
        + coaching_html(your_stats)
    )

    return f"""
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background:#f3f4f6; font-family: -apple-system, BlinkMacSystemFont,
     'Segoe UI', Helvetica, Arial, sans-serif;">
  <div style="max-width: 600px; margin: 0 auto; padding: 24px 16px;">
    {body}
    <div style="text-align:center; font-size:11px; color:#9ca3af; margin-top:16px; padding-bottom:24px;">
      {USERNAME} Â· OSRS Daily Tracker
    </div>
  </div>
</body>
</html>"""


def send_email(html_content: str, plain_summary: str) -> None:
    if not EMAIL or not EMAIL_PASS or not TO_EMAIL:
        raise RuntimeError("EMAIL_USER and EMAIL_PASS must be set.")

    message = MIMEMultipart("alternative")
    message["Subject"] = "OSRS Daily Report"
    message["From"] = EMAIL
    message["To"] = TO_EMAIL
    message.attach(MIMEText(plain_summary, "plain"))
    message.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(EMAIL, EMAIL_PASS)
        server.send_message(message)


def build_plain_text(
    your_gains: dict,
    friends_data: dict,
    previous_all: dict,
    effective_hours_summary: dict,
    last_seven_days_summary: dict,
) -> str:
    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)
    lines = [
        f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}",
        f"Total XP Today: {your_total_xp:,}",
        f"Effective hours played today: {effective_hours_summary.get('totalHours', 0):.1f} hours",
        f"Last 7 days: {last_seven_days_summary.get('totalXp', 0):,} xp | {last_seven_days_summary.get('totalEffectiveHours', 0):.1f} hours | {last_seven_days_summary.get('activeDays', 0)} active days",
        "",
    ]
    top_effective_hours = get_top_effective_hour_contributors(effective_hours_summary)

    if top_effective_hours:
        lines.append("Top effective-hour contributors:")
        lines.extend(
            f"- {format_skill_name(skill)}: {hours:.1f}h"
            for skill, hours in top_effective_hours
        )
        lines.append("")

    if last_seven_days_summary.get("days"):
        lines.append("Last 7 day breakdown:")
        lines.extend(
            f"- {day['label']}: {day['totalXp']:,} xp | {day['effectiveHours']:.1f}h"
            for day in last_seven_days_summary["days"]
        )
        lines.append("")

    for friend in FRIENDS:
        if friend not in friends_data:
            continue

        friend_gains = calculate_gains(previous_all, friend, friends_data[friend])
        friend_xp = sum(value for skill, value in friend_gains.items() if skill in SKILLS)
        diff = your_total_xp - friend_xp
        status = f"ahead by {diff:,}" if diff >= 0 else f"trailing by {abs(diff):,}"
        lines.append(f"{friend}: {friend_xp:,} xp ({status})")

    return "\n".join(lines)


def fetch_all_stats() -> tuple[dict, dict]:
    your_stats = fetch_player(USERNAME)
    time.sleep(1)

    friends_data = {}
    for friend in FRIENDS:
        try:
            friends_data[friend] = fetch_player(friend)
        except Exception as error:  # noqa: BLE001 - one bad friend fetch should not kill the run
            print(f"Warning: could not fetch stats for {friend}: {error}")
        time.sleep(1)

    return your_stats, friends_data


def main() -> None:
    your_stats, friends_data = fetch_all_stats()
    previous_all = load_previous()
    your_gains = calculate_gains(previous_all, USERNAME, your_stats)
    effective_hours_summary = build_effective_hours_summary(your_gains)
    last_seven_days_summary = build_last_seven_days_summary(previous_all, USERNAME, your_gains, effective_hours_summary)
    snapshot_metadata = build_snapshot_metadata(USERNAME, effective_hours_summary, last_seven_days_summary)

    if effective_hours_summary["skippedSkills"]:
        print(
            "Skipped effective-hours estimates for skills without configured XP/hour assumptions: "
            + ", ".join(format_skill_name(skill) for skill in effective_hours_summary["skippedSkills"])
        )

    html_email = build_html_email(
        your_gains,
        your_stats,
        friends_data,
        previous_all,
        effective_hours_summary,
        last_seven_days_summary,
    )
    plain_email = build_plain_text(
        your_gains,
        friends_data,
        previous_all,
        effective_hours_summary,
        last_seven_days_summary,
    )

    print(plain_email)

    send_email(html_email, plain_email)
    save_current(your_stats, friends_data, snapshot_metadata)


if __name__ == "__main__":
    main()
