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
FRIENDS = ["mufkr", "kingxdabber", "beefmissle13", "hedith"]

DATA_FILE = "data/last_stats.json"

GOAL_BASE90_DATE = date(2026, 5, 22)
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


def format_skill_name(skill: str) -> str:
    if skill == "runecraft":
        return "Runecraft"
    return skill.capitalize()


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


def save_current(your_stats: dict, friends_data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    all_stats = {USERNAME: your_stats, **friends_data}

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
    if not plan or plan["xp_per_hour"] <= 0:
        return None, plan["mode"] if plan else "manual estimate"

    return remaining_xp / plan["xp_per_hour"], f'{plan["xp_per_hour"]:,} xp/hr ({plan["mode"]})'


def classify_goal(hours_per_day: float | None, manual_skills: list[str]) -> str:
    if manual_skills:
        return "Needs manual lane"
    if hours_per_day is None:
        return "Off track"
    if hours_per_day <= 1.5:
        return "On track"
    if hours_per_day <= 3:
        return "Tight"
    return "Off track"


def clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


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
            if not plan or plan["xp_per_hour"] <= 0 or projected[skill]["level"] >= MAX_SKILL_LEVEL:
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

    goal_level = 90 if target == "base90" else 99
    baseline_needed = 0
    current_remaining = 0

    for skill in SKILLS:
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


def base90_html(stats: dict, gains: dict) -> str:
    goal_xp = level_to_xp(90)
    days_left = days_until(GOAL_BASE90_DATE)
    progress_pct = goal_progress_pct(stats, "base90")
    required_pace_pct = pace_pct(GOAL_BASE90_DATE)

    completed = []
    remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue

        if stats[skill]["level"] >= 90:
            completed.append(skill)
            continue

        current_xp = stats[skill]["experience"]
        remaining_xp = goal_xp - current_xp
        percent = round(current_xp / goal_xp * 100, 1)
        hours_left, rate_text = projected_hours(skill, remaining_xp)
        remaining.append((skill, stats[skill]["level"], percent, remaining_xp, hours_left, rate_text))

    remaining.sort(key=lambda item: item[2], reverse=True)
    estimated_hours = sum(item[4] for item in remaining if item[4] is not None)
    manual_skills = [format_skill_name(item[0]) for item in remaining if item[4] is None]
    hours_per_day = estimated_hours / days_left if days_left > 0 else None
    pace_status = classify_goal(hours_per_day, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_BASE90_DATE} ({days_left} days left)")}
  {row("Skills at 90+", f"{len(completed)}/{len(SKILLS)}", muted=not remaining)}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if remaining else "Complete", muted=not remaining)}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if hours_per_day is not None else "Manual estimate", muted=not remaining)}
  {row("Pace check", pace_status, muted=not remaining)}
</table>"""

    content += progress_bar(progress_pct, "#8b5cf6", required_pace_pct)
    content += (
        f'<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">'
        f'<span>Actual {progress_pct:.1f}%</span><span>Pace {required_pace_pct:.1f}%</span></div>'
    )

    if not remaining:
        content += '<div style="margin-top:8px; font-size:14px; color:#16a34a; font-weight:700;">Base 90 complete.</div>'
        return section("Goal 1 - Base 90 All Skills", content)

    content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Still needed</div>'

    for skill, level, percent, remaining_xp, hours_left, rate_text in remaining:
        bar_color = "#f59e0b" if percent >= 80 else "#8b5cf6"
        content += f"""
<div style="margin: 6px 0;">
  <table width="100%" cellpadding="0" cellspacing="0" style="font-size:12px; color:#374151;">
    <tr>
      <td style="padding:0; color:#374151;">
        <b>{format_skill_name(skill)}</b> Lv{level}
      </td>
      <td style="padding:0 0 0 16px; color:#6b7280; text-align:right; white-space:nowrap;">
        {percent}% &middot; {remaining_xp:,} xp &middot; {f"{hours_left:.1f}h" if hours_left is not None else rate_text}
      </td>
    </tr>
  </table>
  {progress_bar(percent, bar_color)}
</div>"""

    return section("Goal 1 - Base 90 All Skills", content)


def total_level_html(stats: dict, gains: dict) -> str:
    days_left = days_until(GOAL_RUNEFEST_DATE)
    total_level = stats["overall"]["level"] if "overall" in stats else sum(
        stats[skill]["level"] for skill in SKILLS if skill in stats
    )
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)
    percent = round(min(total_level / GOAL_RUNEFEST_LEVEL * 100, 100), 1)
    progress_pct = goal_progress_pct(stats, "runefest")
    required_pace_pct = pace_pct(GOAL_RUNEFEST_DATE)

    estimated_hours, _, manual_skills = build_runefest_projection(stats, levels_needed)
    hours_per_day = estimated_hours / days_left if levels_needed > 0 else 0
    pace_status = classify_goal(hours_per_day if levels_needed > 0 else 0, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_RUNEFEST_DATE} - RuneFest ({days_left} days left)")}
  {row("Current total level", f"{total_level:,} / {GOAL_RUNEFEST_LEVEL:,}")}
  {row("Levels still needed", str(levels_needed))}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if levels_needed > 0 else "Complete")}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if levels_needed > 0 else "Complete")}
  {row("Pace check", pace_status)}
</table>
{progress_bar(progress_pct, "#3b82f6", required_pace_pct)}
<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">
  <span>Actual {progress_pct:.1f}%</span>
  <span>Pace {required_pace_pct:.1f}%</span>
</div>"""

    if levels_needed <= 0:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700;">RuneFest goal achieved.</div>'
    else:
        levels_per_day = round(levels_needed / days_left, 2)
        content += f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">Need <b>{levels_per_day}</b> levels/day to hit {GOAL_RUNEFEST_LEVEL} in time</div>'
        if manual_skills:
            content += (
                f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">'
                f'Manual estimate still needed for: {", ".join(manual_skills)}</div>'
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
    manual_skills = [format_skill_name(item[0]) for item in remaining if item[3] is None]
    hours_per_day = estimated_hours / days_left if days_left > 0 else None
    pace_status = classify_goal(hours_per_day, manual_skills)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_MAX_DATE} - 33rd birthday ({days_left} days left)")}
  {row("Skills maxed", f"{len(maxed)}/{len(SKILLS)}")}
  {row("Estimated grind", f"{estimated_hours:.1f} hours" if remaining else "Complete")}
  {row("Required pace", f"{hours_per_day:.2f} h/day" if hours_per_day is not None else "Manual estimate")}
  {row("Pace check", pace_status)}
</table>
{progress_bar(progress_pct, "#ec4899", required_pace_pct)}
<div style="display:flex; justify-content:space-between; font-size:11px; color:#6b7280; margin-top:2px;">
  <span>Actual {progress_pct:.1f}%</span>
  <span>Pace {required_pace_pct:.1f}%</span>
</div>"""

    if maxed:
        content += '<div style="margin: 6px 0 10px;">'
        content += "".join(pill(format_skill_name(skill), "#16a34a") for skill in maxed)
        content += "</div>"

    if not remaining:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">Maxed.</div>'
        return section("Goal 3 - Max Cape by 33rd Birthday", content)

    content += '<div style="font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em; margin-top:6px;">Closest to 99</div>'

    for skill, level, remaining_xp, hours_left, rate_text in remaining[:5]:
        skill_percent = round((goal_xp - remaining_xp) / goal_xp * 100, 1)
        content += f"""
<div style="margin: 6px 0;">
  <div style="font-size:12px; color:#374151;">
    <b>{format_skill_name(skill)}</b> Lv{level}
    <span style="color:#6b7280;"> · {remaining_xp:,} xp to 99 · {f"{hours_left:.1f}h" if hours_left is not None else rate_text}</span>
  </div>
  {progress_bar(skill_percent, "#ec4899")}
</div>"""

    return section("Goal 3 - Max Cape by 33rd Birthday", content)


def coaching_html(your_stats: dict) -> str:
    base90_hours = []
    base90_manual = []
    max_hours = []
    max_manual = []

    for skill in SKILLS:
        if skill not in your_stats:
            continue

        if your_stats[skill]["level"] < 90:
            remaining_xp = max(level_to_xp(90) - your_stats[skill]["experience"], 0)
            hours_left, _ = projected_hours(skill, remaining_xp)
            if hours_left is None:
                base90_manual.append(format_skill_name(skill))
            else:
                base90_hours.append(hours_left)

        if your_stats[skill]["level"] < 99:
            remaining_xp = max(level_to_xp(99) - your_stats[skill]["experience"], 0)
            hours_left, _ = projected_hours(skill, remaining_xp)
            if hours_left is None:
                max_manual.append(format_skill_name(skill))
            else:
                max_hours.append(hours_left)

    total_level = your_stats["overall"]["level"] if "overall" in your_stats else 0
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)
    runefest_total, _, runefest_manual = build_runefest_projection(your_stats, levels_needed)

    base90_days = days_until(GOAL_BASE90_DATE)
    runefest_days = days_until(GOAL_RUNEFEST_DATE)
    max_days = days_until(GOAL_MAX_DATE)

    base90_total = sum(base90_hours)
    max_total = sum(max_hours)

    base90_rate = base90_total / base90_days if base90_days > 0 else None
    runefest_rate = runefest_total / runefest_days if runefest_days > 0 else None
    max_rate = max_total / max_days if max_days > 0 else None

    content = "".join(
        [
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'Base 90 is <b>technically {classify_goal(base90_rate, base90_manual).lower()}</b> at '
            f'<b>{base90_rate:.2f} hours/day</b> through {GOAL_BASE90_DATE}.'
            f'{" Manual estimate still needed for: " + ", ".join(base90_manual) + "." if base90_manual else ""}'
            f'</p>',
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'RuneFest 2250 is <b>technically {classify_goal(runefest_rate, runefest_manual).lower()}</b> at '
            f'<b>{runefest_rate:.2f} hours/day</b> and <b>{(levels_needed / runefest_days if runefest_days > 0 else 0):.2f} levels/day</b>.'
            f'{" Manual estimate still needed for: " + ", ".join(runefest_manual) + "." if runefest_manual else ""}'
            f'</p>',
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">'
            f'Max cape is <b>technically {classify_goal(max_rate, max_manual).lower()}</b> at '
            f'<b>{max_rate:.2f} hours/day</b> through {GOAL_MAX_DATE}.'
            f'{" Manual estimate still needed for: " + ", ".join(max_manual) + "." if max_manual else ""}'
            f'</p>',
        ]
    )

    return section("Daily Coaching Insight", content)


def build_html_email(your_gains: dict, your_stats: dict, friends_data: dict, previous_all: dict) -> str:
    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)
    today = datetime.now().strftime("%B %d, %Y")

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

    header_section = f"""
<div style="background: linear-gradient(135deg, #1e1b4b 0%, #4c1d95 100%);
     border-radius: 12px; padding: 28px 24px; margin-bottom: 8px; color: white;">
  <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em;
       opacity: 0.7; margin-bottom: 6px;">OSRS Daily Report</div>
  <div style="font-size: 26px; font-weight: 800; margin-bottom: 4px;">{today}</div>
  <div style="font-size: 28px; font-weight: 800; margin-top: 16px;">{your_total_xp:,} <span style="font-size:14px; font-weight:400; opacity:0.8;">XP gained today</span></div>
  <div style="margin-top: 14px;">{top_gains_html.replace('color:#374151', 'color:rgba(255,255,255,0.85)').replace('color:#9ca3af', 'color:rgba(255,255,255,0.5)')}</div>
</div>"""

    body = (
        header_section
        + friend_comparison_html(your_gains, friends_data, previous_all)
        + base90_html(your_stats, your_gains)
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
      {USERNAME} · OSRS Daily Tracker
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


def build_plain_text(your_gains: dict, friends_data: dict, previous_all: dict) -> str:
    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)
    lines = [
        f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}",
        f"Total XP Today: {your_total_xp:,}",
        "",
    ]

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

    html_email = build_html_email(your_gains, your_stats, friends_data, previous_all)
    plain_email = build_plain_text(your_gains, friends_data, previous_all)

    print(plain_email)

    send_email(html_email, plain_email)
    save_current(your_stats, friends_data)


if __name__ == "__main__":
    main()
