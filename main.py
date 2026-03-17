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

# All 24 skills in OSRS (excluding 'overall')
SKILLS = [
    "attack", "defence", "strength", "hitpoints", "ranged", "prayer",
    "magic", "cooking", "woodcutting", "fletching", "fishing", "firemaking",
    "crafting", "smithing", "mining", "herblore", "agility", "thieving",
    "slayer", "farming", "runecraft", "hunter", "construction", "sailing"
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
# — We now save stats for ALL players so we can compare daily gains
# =========================
def load_previous():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_current(your_stats, friends_data):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    all_stats = {USERNAME: your_stats}
    for friend, stats in friends_data.items():
        all_stats[friend] = stats
    with open(DATA_FILE, "w") as f:
        json.dump(all_stats, f)


# =========================
# CALCULATIONS
# =========================
def calculate_gains(old_all, username, current_stats):
    """Calculate XP gains for a single player given the full previous snapshot dict."""
    gains = {}
    old = old_all.get(username) if old_all else None
    for skill in current_stats:
        if old and skill in old:
            gains[skill] = current_stats[skill]["experience"] - old[skill]["experience"]
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
# FRIEND COMPARISON
# — Daily XP race + top 3 skill gains per friend
# =========================
def friend_comparison_summary(your_gains, your_stats, friends_data, previous_all):
    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)

    lines = []
    lines.append("=== Comparison vs Friends ===")
    lines.append(f"Your total XP today: {your_total_xp:,}\n")

    for friend in FRIENDS:
        if friend not in friends_data:
            lines.append(f"{friend}: (data unavailable)")
            continue

        friend_stats = friends_data[friend]
        friend_gains = calculate_gains(previous_all, friend, friend_stats)

        friend_total_xp = sum(v for k, v in friend_gains.items() if k in SKILLS)

        # XP race result
        diff = your_total_xp - friend_total_xp
        if diff > 0:
            race_result = f"You're ahead by {diff:,} xp today 🟢"
        elif diff < 0:
            race_result = f"They're ahead by {abs(diff):,} xp today 🔴"
        else:
            race_result = "Dead even today 🟡"

        # Skill win/loss (total XP comparison per skill)
        winning = 0
        losing = 0
        for skill in SKILLS:
            if skill not in your_stats or skill not in friend_stats:
                continue
            if your_stats[skill]["experience"] > friend_stats[skill]["experience"]:
                winning += 1
            else:
                losing += 1

        # Friend's top 3 skills gained today
        top3 = sorted(
            [(s, friend_gains[s]) for s in SKILLS if friend_gains.get(s, 0) > 0],
            key=lambda x: x[1], reverse=True
        )[:3]

        lines.append(f"{friend}:")
        lines.append(f"  Daily XP: {friend_total_xp:,} — {race_result}")
        lines.append(f"  Overall skill lead: Winning {winning} / Losing {losing}")
        if top3:
            lines.append(f"  Their top gains today:")
            for skill, xp in top3:
                lines.append(f"    - {skill}: +{xp:,} xp (Lv{friend_stats[skill]['level']})")
        else:
            lines.append(f"  Their top gains today: none recorded")
        lines.append("")

    return "\n".join(lines).rstrip()


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
    lines.append(f"Complete: {len(skills_done)}/{len(SKILLS)} skills at 90+")

    if skills_remaining:
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
    lines.append(f"Maxed skills: {len(skills_maxed)}/{len(SKILLS)}")

    if skills_maxed:
        lines.append(f"  Maxed: {', '.join(skills_maxed)}")

    if skills_remaining:
        skills_remaining.sort(key=lambda x: x[2])
        lines.append("Closest to 99:")
        for skill, level, remaining_xp, eta_str in skills_remaining[:5]:
            lines.append(f"  - {skill}: Lv{level} — {remaining_xp:,} xp to 99 — {eta_str}")
    else:
        lines.append("  ✅ Maxed!")

    return "\n".join(lines)


# =========================
# AI COACHING
# =========================
def generate_ai_coaching(your_gains, your_stats, friends_data, previous_all):
    days_to_base90   = days_until(GOAL_BASE90_DATE)
    days_to_runefest = days_until(GOAL_RUNEFEST_DATE)
    days_to_max      = days_until(GOAL_MAX_DATE)

    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)
    top_gains = sorted(
        [(s, your_gains[s]) for s in SKILLS if your_gains.get(s, 0) > 0],
        key=lambda x: x[1], reverse=True
    )[:5]

    skills_under_90 = [s for s in SKILLS if s in your_stats and your_stats[s]["level"] < 90]
    skills_maxed    = [s for s in SKILLS if s in your_stats and your_stats[s]["level"] >= 99]
    total_level     = your_stats["overall"]["level"] if "overall" in your_stats else 0

    # Build friend XP summary for prompt
    friend_lines = []
    for friend in FRIENDS:
        if friend not in friends_data:
            continue
        friend_gains = calculate_gains(previous_all, friend, friends_data[friend])
        friend_xp = sum(v for k, v in friend_gains.items() if k in SKILLS)
        diff = your_total_xp - friend_xp
        status = f"you're ahead by {diff:,}" if diff >= 0 else f"they're ahead by {abs(diff):,}"
        friend_lines.append(f"- {friend}: {friend_xp:,} xp today ({status})")

    prompt = f"""You are a coaching assistant for an Old School RuneScape player named jhusebachz.
They have three personal goals with real deadlines. Write a motivating, personalized coaching message
(4-6 sentences) referencing their actual numbers, daily XP race vs friends, and which goals are most urgent.

TODAY'S STATS:
- Total XP gained today: {your_total_xp:,}
- Top gains: {', '.join(f"{s} +{xp:,}" for s, xp in top_gains) or 'none today'}

FRIEND XP RACE TODAY:
{chr(10).join(friend_lines) or 'No friend data available'}

GOAL 1 - Base 90 all skills by {GOAL_BASE90_DATE} ({days_to_base90} days left):
- Skills still under 90: {len(skills_under_90)}/{len(SKILLS)}
- Remaining: {', '.join(skills_under_90) if skills_under_90 else 'COMPLETE!'}

GOAL 2 - Total level {GOAL_RUNEFEST_LEVEL} by RuneFest {GOAL_RUNEFEST_DATE} ({days_to_runefest} days left):
- Current total level: {total_level} (need {max(GOAL_RUNEFEST_LEVEL - total_level, 0)} more levels)

GOAL 3 - Max cape by {GOAL_MAX_DATE} — his 33rd birthday ({days_to_max} days left):
- Maxed: {len(skills_maxed)}/{len(SKILLS)} skills at 99

Be specific, reference the deadlines, call out the daily XP race, and prioritize whichever goal is most at risk."""

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
def generate_summary(your_gains, your_stats, friends_data, previous_all):
    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)

    msg = f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    msg += f"Total XP Gained Today: {your_total_xp:,}\n\n"

    # Your top gains
    top = sorted(
        [(s, your_gains[s]) for s in SKILLS if your_gains.get(s, 0) > 0],
        key=lambda x: x[1], reverse=True
    )[:5]
    msg += "Your Top Gains:\n"
    if top:
        for skill, xp in top:
            msg += f"  - {skill}: +{xp:,} xp\n"
    else:
        msg += "  - No xp gained today\n"

    # Friend comparison (new)
    msg += "\n" + friend_comparison_summary(your_gains, your_stats, friends_data, previous_all) + "\n"

    # Goal 1: Base 90
    msg += "\n" + base90_summary(your_stats, your_gains) + "\n"

    # Goal 2: RuneFest total level
    msg += "\n" + total_level_summary(your_stats, your_gains) + "\n"

    # Goal 3: Max by birthday
    msg += "\n" + max_progress_summary(your_stats, your_gains) + "\n"

    # AI Coaching
    msg += "\n=== Coaching Insight ===\n"
    try:
        coaching = generate_ai_coaching(your_gains, your_stats, friends_data, previous_all)
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

    # Step 3: Fetch updated stats for everyone
    your_stats = fetch_player(USERNAME)

    friends_data = {}
    for friend in FRIENDS:
        friends_data[friend] = fetch_player(friend)

    # Step 4: Load previous snapshot (now includes all players)
    previous_all = load_previous()

    # Step 5: Calculate your gains
    your_gains = calculate_gains(previous_all, USERNAME, your_stats)

    # Step 6: Generate report
    summary = generate_summary(your_gains, your_stats, friends_data, previous_all)

    print(summary)

    # Step 7: Send email
    send_email(summary)

    # Step 8: Save current stats for ALL players
    save_current(your_stats, friends_data)


if __name__ == "__main__":
    main()
