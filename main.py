import requests
import json
import os
import time
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from groq import Groq

# =========================
# CONFIG
# =========================
USERNAME = "jhusebachz"
FRIENDS = ["mufkr", "kingxdabber", "beefmissle13", "hedith"]

DATA_FILE = "data/last_stats.json"

# Personal goals with deadlines
GOAL_BASE90_DATE      = date(2026, 5, 22)       # Base 90 all skills
GOAL_RUNEFEST_DATE    = date(2026, 10, 3)        # RuneFest 2026 - total level 2250
GOAL_MAX_DATE         = date(2027, 3, 15)        # Max by 33rd birthday
GOAL_RUNEFEST_LEVEL   = 2250                     # Target total level for RuneFest
MAX_SKILL_LEVEL       = 99

# All 23 skills in OSRS (excluding 'overall')
SKILLS = [
    "attack", "defence", "strength", "hitpoints", "ranged", "prayer",
    "magic", "cooking", "woodcutting", "fletching", "fishing", "firemaking",
    "crafting", "smithing", "mining", "herblore", "agility", "thieving",
    "slayer", "farming", "runecraft", "hunter", "construction"
]

EMAIL = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
TO_EMAIL = EMAIL


# =========================
# FETCH & UPDATE DATA
# =========================
def update_player(username):
    url = f"https://api.wiseoldman.net/v2/players/{username}/update"
    try:
        requests.post(url)
    except:
        pass


def fetch_player(username):
    url = f"https://api.wiseoldman.net/v2/players/{username}"
    res = requests.get(url)
    data = res.json()
    return data["latestSnapshot"]["data"]["skills"]


# =========================
# DATA STORAGE
# =========================
def load_previous():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_current(stats):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(stats, f)


# =========================
# CALCULATIONS
# =========================
def calculate_gains(old, new):
    gains = {}
    for skill in new:
        if old:
            gains[skill] = new[skill]["experience"] - old[skill]["experience"]
        else:
            gains[skill] = 0
    return gains


def level_to_xp(level):
    points = 0
    for lvl in range(1, level):
        points += int(lvl + 300 * 2 ** (lvl / 7.0))
    return int(points / 4)


def days_until(target_date):
    return max((target_date - date.today()).days, 1)


# =========================
# GOAL 1: BASE 90
# =========================
def base90_summary(stats, gains):
    goal_xp = level_to_xp(90)
    days_left = days_until(GOAL_BASE90_DATE)

    skills_done = []
    skills_remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue
        if stats[skill]["level"] >= 90:
            skills_done.append(skill)
        else:
            current_xp = stats[skill]["experience"]
            remaining_xp = goal_xp - current_xp
            pct = round(current_xp / goal_xp * 100, 1)
            daily_xp = gains.get(skill, 0)
            if daily_xp > 0:
                eta_str = f"~{round(remaining_xp / daily_xp, 1)}d at current pace"
            else:
                eta_str = "no recent xp"
            skills_remaining.append((skill, stats[skill]["level"], pct, remaining_xp, eta_str))

    lines = []
    lines.append(f"=== GOAL 1: Base 90 All Skills (by {GOAL_BASE90_DATE} — {days_left} days left) ===")
    lines.append(f"Complete: {len(skills_done)}/23 skills at 90+")

    if skills_remaining:
        # Sort by % progress descending (closest to done first)
        skills_remaining.sort(key=lambda x: x[2], reverse=True)
        lines.append(f"Still needed ({len(skills_remaining)} skills):")
        for skill, level, pct, remaining_xp, eta_str in skills_remaining:
            lines.append(f"  - {skill}: Lv{level} ({pct}%) — {remaining_xp:,} xp needed — {eta_str}")
    else:
        lines.append("  ✅ Base 90 complete!")

    return "\n".join(lines)


# =========================
# GOAL 2: TOTAL LEVEL 2250 BY RUNEFEST
# =========================
def total_level_summary(stats, gains):
    days_left = days_until(GOAL_RUNEFEST_DATE)
    total_level = stats["overall"]["level"] if "overall" in stats else sum(
        stats[s]["level"] for s in SKILLS if s in stats
    )
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)

    lines = []
    lines.append(f"=== GOAL 2: Total Level {GOAL_RUNEFEST_LEVEL} by RuneFest ({GOAL_RUNEFEST_DATE} — {days_left} days left) ===")
    lines.append(f"Current total level: {total_level} / {GOAL_RUNEFEST_LEVEL} ({levels_needed} levels to go)")

    if levels_needed <= 0:
        lines.append("  ✅ RuneFest total level goal achieved!")
    else:
        levels_per_day_needed = round(levels_needed / days_left, 2)
        lines.append(f"Pace needed: {levels_per_day_needed} levels/day to hit {GOAL_RUNEFEST_LEVEL} in time")

        # Show most active skills today
        active_skills = [
            (s, gains.get(s, 0)) for s in SKILLS
            if s in stats and gains.get(s, 0) > 0
        ]
        active_skills.sort(key=lambda x: x[1], reverse=True)
        if active_skills:
            lines.append("Most active skills today:")
            for skill, xp in active_skills[:5]:
                lines.append(f"  - {skill}: +{xp:,} xp (Lv{stats[skill]['level']})")

    return "\n".join(lines)


# =========================
# GOAL 3: MAX BY 33RD BIRTHDAY
# =========================
def max_progress_summary(stats, gains):
    days_left = days_until(GOAL_MAX_DATE)
    goal_xp = level_to_xp(MAX_SKILL_LEVEL)

    skills_maxed = []
    skills_remaining = []

    for skill in SKILLS:
        if skill not in stats:
            continue
        if stats[skill]["level"] >= MAX_SKILL_LEVEL:
            skills_maxed.append(skill)
        else:
            remaining_xp = goal_xp - stats[skill]["experience"]
            daily_xp = gains.get(skill, 0)
            eta_str = f"~{round(remaining_xp / daily_xp, 1)}d at current pace" if daily_xp > 0 else "no recent xp"
            skills_remaining.append((skill, stats[skill]["level"], remaining_xp, eta_str))

    lines = []
    lines.append(f"=== GOAL 3: Max Cape by 33rd Birthday ({GOAL_MAX_DATE} — {days_left} days left) ===")
    lines.append(f"Maxed skills: {len(skills_maxed)}/23")

    if skills_maxed:
        lines.append(f"  Maxed: {', '.join(skills_maxed)}")

    if skills_remaining:
        # Show closest to 99 first
        skills_remaining.sort(key=lambda x: x[2])
        lines.append("Closest to 99:")
        for skill, level, remaining_xp, eta_str in skills_remaining[:5]:
            lines.append(f"  - {skill}: Lv{level} — {remaining_xp:,} xp to 99 — {eta_str}")
    else:
        lines.append("  ✅ Maxed!")

    return "\n".join(lines)


# =========================
# COMPARISON LOGIC
# =========================
def compare_to_friends(your_stats, friends_data):
    results = {}
    for friend, stats in friends_data.items():
        better = 0
        worse = 0
        for skill in SKILLS:
            if skill not in your_stats or skill not in stats:
                continue
            if your_stats[skill]["experience"] > stats[skill]["experience"]:
                better += 1
            else:
                worse += 1
        results[friend] = (better, worse)
    return results


# =========================
# AI COACHING
# =========================
def generate_ai_coaching(gains, stats, friends_data):
    days_to_base90   = days_until(GOAL_BASE90_DATE)
    days_to_runefest = days_until(GOAL_RUNEFEST_DATE)
    days_to_max      = days_until(GOAL_MAX_DATE)

    total_xp = sum(gains.values())
    top_gains = sorted(
        [(s, gains[s]) for s in SKILLS if s in gains and gains[s] > 0],
        key=lambda x: x[1], reverse=True
    )[:5]

    skills_under_90 = [s for s in SKILLS if s in stats and stats[s]["level"] < 90]
    skills_maxed    = [s for s in SKILLS if s in stats and stats[s]["level"] >= 99]
    total_level     = stats["overall"]["level"] if "overall" in stats else 0
    comparisons     = compare_to_friends(stats, friends_data)

    prompt = f"""You are a coaching assistant for an Old School RuneScape player named jhusebachz.
They have three personal goals with real deadlines. Write a motivating, personalized coaching message
(4-6 sentences) that references their actual numbers and which goals are most urgent right now.

TODAY'S STATS:
- Total XP gained today: {total_xp:,}
- Top gains: {', '.join(f"{s} +{xp:,}" for s, xp in top_gains) or 'none today'}

GOAL 1 - Base 90 all skills by {GOAL_BASE90_DATE} ({days_to_base90} days left):
- Skills still under 90: {len(skills_under_90)}/23
- Remaining: {', '.join(skills_under_90) if skills_under_90 else 'COMPLETE!'}

GOAL 2 - Total level {GOAL_RUNEFEST_LEVEL} by RuneFest {GOAL_RUNEFEST_DATE} ({days_to_runefest} days left):
- Current total level: {total_level} (need {max(GOAL_RUNEFEST_LEVEL - total_level, 0)} more levels)

GOAL 3 - Max cape by {GOAL_MAX_DATE} — his 33rd birthday ({days_to_max} days left):
- Maxed: {len(skills_maxed)}/23 skills at 99

FRIEND COMPARISONS:
{chr(10).join(f"- {friend}: Winning {b} skills / Losing {w} skills" for friend, (b, w) in comparisons.items())}

Be specific, reference the deadlines, and prioritize whichever goal is most at risk."""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )
    return response.choices[0].message.content


# =========================
# SUMMARY GENERATION
# =========================
def generate_summary(gains, stats, friends_data):
    total_xp = sum(gains.values())
    comparisons = compare_to_friends(stats, friends_data)

    msg = f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    msg += f"Total XP Gained Today: {total_xp:,}\n\n"

    # Top gains
    top = sorted(
        [(s, gains[s]) for s in SKILLS if s in gains and gains[s] > 0],
        key=lambda x: x[1], reverse=True
    )[:5]
    msg += "Top Gains:\n"
    if top:
        for skill, xp in top:
            msg += f"  - {skill}: +{xp:,} xp\n"
    else:
        msg += "  - No xp gained today\n"

    # Friend comparisons
    msg += "\nComparison vs Friends:\n"
    for friend, (better, worse) in comparisons.items():
        msg += f"  - {friend}: Winning {better} / Losing {worse}\n"

    # Goal 1: Base 90
    msg += "\n" + base90_summary(stats, gains) + "\n"

    # Goal 2: RuneFest total level
    msg += "\n" + total_level_summary(stats, gains) + "\n"

    # Goal 3: Max by birthday
    msg += "\n" + max_progress_summary(stats, gains) + "\n"

    # AI Coaching
    msg += "\n=== Coaching Insight ===\n"
    try:
        coaching = generate_ai_coaching(gains, stats, friends_data)
        msg += coaching + "\n"
    except Exception as e:
        msg += f"(Could not generate AI coaching: {e})\n"

    return msg


# =========================
# EMAIL
# =========================
def send_email(message):
    msg = MIMEText(message)
    msg["Subject"] = "OSRS Daily Progress Report"
    msg["From"] = EMAIL
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, EMAIL_PASS)
        server.send_message(msg)


# =========================
# MAIN
# =========================
def main():
    # Step 1: Force update for all players
    update_player(USERNAME)
    for friend in FRIENDS:
        update_player(friend)

    # Step 2: Wait for WOM to refresh data
    time.sleep(10)

    # Step 3: Fetch updated stats
    your_stats = fetch_player(USERNAME)

    friends_data = {}
    for friend in FRIENDS:
        friends_data[friend] = fetch_player(friend)

    # Step 4: Calculate gains
    previous = load_previous()
    gains = calculate_gains(previous, your_stats)

    # Step 5: Generate report
    summary = generate_summary(gains, your_stats, friends_data)

    print(summary)

    # Step 6: Send email
    send_email(summary)

    # Step 7: Save current stats
    save_current(your_stats)


if __name__ == "__main__":
    main()
