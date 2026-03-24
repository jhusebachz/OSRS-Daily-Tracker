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
from groq import Groq


USERNAME = "jhusebachz"
FRIENDS = ["mufkr", "kingxdabber", "beefmissle13", "hedith"]

DATA_FILE = "data/last_stats.json"

GOAL_BASE90_DATE = date(2026, 5, 22)
GOAL_RUNEFEST_DATE = date(2026, 10, 3)
GOAL_MAX_DATE = date(2027, 3, 15)

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

HISCORE_HEADERS = {"User-Agent": "OSRS-Daily-Tracker/1.0"}
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


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


def progress_bar(percent: float, color: str = "#8b5cf6") -> str:
    clamped = min(max(percent, 0), 100)
    return f"""
<div style="background:#e5e7eb; border-radius:999px; height:8px; margin: 3px 0 8px 0;">
  <div style="background:{color}; width:{clamped}%; height:8px; border-radius:999px;"></div>
</div>"""


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
        daily_xp = gains.get(skill, 0)
        eta = f"~{round(remaining_xp / daily_xp, 1)}d" if daily_xp > 0 else "no recent xp"
        remaining.append((skill, stats[skill]["level"], percent, remaining_xp, eta))

    remaining.sort(key=lambda item: item[2], reverse=True)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_BASE90_DATE} ({days_left} days left)")}
  {row("Skills at 90+", f"{len(completed)}/{len(SKILLS)}", muted=not remaining)}
</table>"""

    if not remaining:
        content += '<div style="margin-top:8px; font-size:14px; color:#16a34a; font-weight:700;">Base 90 complete.</div>'
        return section("Goal 1 - Base 90 All Skills", content)

    content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Still needed</div>'

    for skill, level, percent, remaining_xp, eta in remaining:
        bar_color = "#f59e0b" if percent >= 80 else "#8b5cf6"
        content += f"""
<div style="margin: 6px 0;">
  <div style="display:flex; justify-content:space-between; font-size:12px; color:#374151;">
    <span><b>{format_skill_name(skill)}</b> Lv{level}</span>
    <span style="color:#6b7280;">{percent}% · {remaining_xp:,} xp · {eta}</span>
  </div>
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

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_RUNEFEST_DATE} - RuneFest ({days_left} days left)")}
  {row("Current total level", f"{total_level:,} / {GOAL_RUNEFEST_LEVEL:,}")}
  {row("Levels still needed", str(levels_needed))}
</table>
{progress_bar(percent, "#3b82f6")}"""

    if levels_needed <= 0:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700;">RuneFest goal achieved.</div>'
    else:
        levels_per_day = round(levels_needed / days_left, 2)
        content += f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">Need <b>{levels_per_day}</b> levels/day to hit {GOAL_RUNEFEST_LEVEL} in time</div>'

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

    maxed = []
    remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue

        if stats[skill]["level"] >= MAX_SKILL_LEVEL:
            maxed.append(skill)
            continue

        remaining_xp = goal_xp - stats[skill]["experience"]
        daily_xp = gains.get(skill, 0)
        eta = f"~{round(remaining_xp / daily_xp, 1)}d" if daily_xp > 0 else "no recent xp"
        remaining.append((skill, stats[skill]["level"], remaining_xp, eta))

    remaining.sort(key=lambda item: item[2])
    percent = round(len(maxed) / len(SKILLS) * 100, 1)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_MAX_DATE} - 33rd birthday ({days_left} days left)")}
  {row("Skills maxed", f"{len(maxed)}/{len(SKILLS)}")}
</table>
{progress_bar(percent, "#ec4899")}"""

    if maxed:
        content += '<div style="margin: 6px 0 10px;">'
        content += "".join(pill(format_skill_name(skill), "#16a34a") for skill in maxed)
        content += "</div>"

    if not remaining:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">Maxed.</div>'
        return section("Goal 3 - Max Cape by 33rd Birthday", content)

    content += '<div style="font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em; margin-top:6px;">Closest to 99</div>'

    for skill, level, remaining_xp, eta in remaining[:5]:
        skill_percent = round((goal_xp - remaining_xp) / goal_xp * 100, 1)
        content += f"""
<div style="margin: 6px 0;">
  <div style="font-size:12px; color:#374151;">
    <b>{format_skill_name(skill)}</b> Lv{level}
    <span style="color:#6b7280;"> · {remaining_xp:,} xp to 99 · {eta}</span>
  </div>
  {progress_bar(skill_percent, "#ec4899")}
</div>"""

    return section("Goal 3 - Max Cape by 33rd Birthday", content)


def generate_ai_coaching(your_gains: dict, your_stats: dict, friends_data: dict, previous_all: dict) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set.")

    days_to_base90 = days_until(GOAL_BASE90_DATE)
    days_to_runefest = days_until(GOAL_RUNEFEST_DATE)
    days_to_max = days_until(GOAL_MAX_DATE)

    your_total_xp = sum(value for skill, value in your_gains.items() if skill in SKILLS)
    top_gains = sorted(
        ((skill, your_gains[skill]) for skill in SKILLS if your_gains.get(skill, 0) > 0),
        key=lambda item: item[1],
        reverse=True,
    )[:5]

    skills_under_90 = [skill for skill in SKILLS if skill in your_stats and your_stats[skill]["level"] < 90]
    skills_maxed = [skill for skill in SKILLS if skill in your_stats and your_stats[skill]["level"] >= 99]
    total_level = your_stats["overall"]["level"] if "overall" in your_stats else 0

    friend_lines = []
    for friend in FRIENDS:
        if friend not in friends_data:
            continue

        friend_gains = calculate_gains(previous_all, friend, friends_data[friend])
        friend_xp = sum(value for skill, value in friend_gains.items() if skill in SKILLS)
        diff = your_total_xp - friend_xp
        status = f"you're ahead by {diff:,}" if diff >= 0 else f"they're ahead by {abs(diff):,}"
        friend_lines.append(f"- {friend}: {friend_xp:,} xp today ({status})")

    prompt = f"""You are a coaching assistant for an Old School RuneScape player named {USERNAME}.
They have three personal goals with real deadlines. Write a motivating, personalized coaching message
(4-6 sentences) referencing their actual numbers, daily XP vs friends, and which goals are most urgent.

TODAY'S STATS:
- Total XP gained today: {your_total_xp:,}
- Top gains: {", ".join(f"{format_skill_name(skill)} +{xp:,}" for skill, xp in top_gains) or "none today"}

FRIEND XP RACE TODAY:
{chr(10).join(friend_lines) or "No friend data available"}

GOAL 1 - Base 90 all skills by {GOAL_BASE90_DATE} ({days_to_base90} days left):
- Skills still under 90: {len(skills_under_90)}/{len(SKILLS)}
- Remaining: {", ".join(format_skill_name(skill) for skill in skills_under_90) if skills_under_90 else "COMPLETE"}

GOAL 2 - Total level {GOAL_RUNEFEST_LEVEL} by RuneFest {GOAL_RUNEFEST_DATE} ({days_to_runefest} days left):
- Current total level: {total_level} (need {max(GOAL_RUNEFEST_LEVEL - total_level, 0)} more levels)

GOAL 3 - Max cape by {GOAL_MAX_DATE} ({days_to_max} days left):
- Maxed: {len(skills_maxed)}/{len(SKILLS)} skills at 99

Be specific, reference the deadlines, and prioritize whichever goal is most at risk."""

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    return response.choices[0].message.content


def coaching_html(your_gains: dict, your_stats: dict, friends_data: dict, previous_all: dict) -> str:
    try:
        text = generate_ai_coaching(your_gains, your_stats, friends_data, previous_all)
        paragraphs = "".join(
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">{line.strip()}</p>'
            for line in text.strip().splitlines()
            if line.strip()
        )
        content = paragraphs
    except Exception as error:  # noqa: BLE001 - this is an intentional user-facing fallback
        content = f'<p style="color:#dc2626; font-size:13px;">Could not generate coaching: {error}</p>'

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
        + coaching_html(your_gains, your_stats, friends_data, previous_all)
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
