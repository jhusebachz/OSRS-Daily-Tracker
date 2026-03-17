import requests
import json
import os
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import anthropic

# =========================
# CONFIG
# =========================
USERNAME = "jhusebachz"
FRIENDS = ["mufkr", "kingxdabber", "beefmissle13", "hedith"]

DATA_FILE = "data/last_stats.json"
GOAL_LEVEL = 90

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


def goal_progress(stats):
    goals = {}
    goal_xp = level_to_xp(GOAL_LEVEL)

    for skill in stats:
        current_xp = stats[skill]["experience"]
        pct = min(current_xp / goal_xp, 1)
        goals[skill] = pct

    return goals


def estimate_eta(gains, stats):
    eta = {}
    goal_xp = level_to_xp(GOAL_LEVEL)

    for skill in stats:
        daily_xp = gains.get(skill, 0)
        if daily_xp <= 0:
            continue

        remaining = goal_xp - stats[skill]["experience"]
        if remaining <= 0:
            continue

        days = remaining / daily_xp
        eta[skill] = round(days, 1)

    return eta


# =========================
# COMPARISON LOGIC
# =========================
def compare_to_friends(your_stats, friends_data):
    results = {}

    for friend, stats in friends_data.items():
        better = 0
        worse = 0

        for skill in your_stats:
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
    goals = goal_progress(stats)
    eta = estimate_eta(gains, stats)
    comparisons = compare_to_friends(stats, friends_data)
    total_xp = sum(gains.values())

    top_gains = sorted(gains.items(), key=lambda x: x[1], reverse=True)[:5]
    top_goals = sorted(goals.items(), key=lambda x: x[1], reverse=True)[:5]
    sorted_eta = sorted(eta.items(), key=lambda x: x[1])[:5]

    prompt = f"""You are a coaching assistant for an Old School RuneScape player.
Analyze their daily stats and give a short, personalized coaching message (3-5 sentences).
Be specific, motivating, and reference actual skills and numbers.

Today's total XP gained: {total_xp:,}

Top skill gains today:
{chr(10).join(f"- {s}: {xp:,} xp" for s, xp in top_gains)}

Progress toward level 90 (top skills):
{chr(10).join(f"- {s}: {round(pct*100)}%" for s, pct in top_goals)}

Fastest skills to reach 90 (ETA in days):
{chr(10).join(f"- {s}: {days} days" for s, days in sorted_eta)}

Friend comparisons (skills where you're winning vs losing):
{chr(10).join(f"- {friend}: Winning {b} / Losing {w}" for friend, (b, w) in comparisons.items())}

Give a personalized coaching insight based on this data."""

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


# =========================
# SUMMARY GENERATION
# =========================
def generate_summary(gains, stats, friends_data):
    total_xp = sum(gains.values())
    goals = goal_progress(stats)
    eta = estimate_eta(gains, stats)
    comparisons = compare_to_friends(stats, friends_data)

    msg = f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    msg += f"Total XP Gained: {total_xp:,}\n\n"

    # Top gains
    top = sorted(gains.items(), key=lambda x: x[1], reverse=True)[:5]
    msg += "Top Gains:\n"
    for skill, xp in top:
        msg += f"- {skill}: {xp:,} xp\n"

    # Friend comparisons
    msg += "\nComparison vs Friends:\n"
    for friend, (better, worse) in comparisons.items():
        msg += f"- {friend}: Winning {better} / Losing {worse}\n"

    # Goal progress
    msg += "\nProgress to 90:\n"
    top_goals = sorted(goals.items(), key=lambda x: x[1], reverse=True)[:5]
    for skill, pct in top_goals:
        msg += f"- {skill}: {round(pct * 100)}%\n"

    # ETA
    msg += "\nFastest Skills to 90 (ETA):\n"
    sorted_eta = sorted(eta.items(), key=lambda x: x[1])[:5]
    for skill, days in sorted_eta:
        msg += f"- {skill}: {days} days\n"

    # AI Coaching
    msg += "\nCoaching Insight:\n"
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
