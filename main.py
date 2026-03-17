import requests
import json
import os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

USERNAME = "YOUR_RS_USERNAME"

WOM_API = f"https://api.wiseoldman.net/v2/players/{jhusebachz}"

DATA_FILE = "data/last_stats.json"

EMAIL = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
TO_EMAIL = EMAIL


def fetch_stats():
    res = requests.get(WOM_API)
    data = res.json()
    return data["latestSnapshot"]["data"]["skills"]


def load_previous():
    if not os.path.exists(DATA_FILE):
        return None
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_current(stats):
    with open(DATA_FILE, "w") as f:
        json.dump(stats, f)


def calculate_gains(old, new):
    gains = {}
    for skill in new:
        if old:
            gains[skill] = new[skill]["experience"] - old[skill]["experience"]
        else:
            gains[skill] = 0
    return gains


def generate_summary(gains):
    sorted_gains = sorted(gains.items(), key=lambda x: x[1], reverse=True)

    top = sorted_gains[:3]
    total_xp = sum(gains.values())

    msg = f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"

    msg += f"Total XP Gained: {total_xp:,}\n\n"

    msg += "Top Gains:\n"
    for skill, xp in top:
        msg += f"- {skill.capitalize()}: {xp:,} xp\n"

    # Coaching logic
    if total_xp < 50000:
        msg += "\n⚠️ You’re falling behind your pace. Consider AFK NMZ or fishing during work.\n"
    elif total_xp < 150000:
        msg += "\n👍 Solid progress. You’re maintaining momentum.\n"
    else:
        msg += "\n🔥 Strong day. You’re accelerating toward your goals.\n"

    return msg


def send_email(message):
    msg = MIMEText(message)
    msg["Subject"] = "Daily OSRS Progress Report"
    msg["From"] = EMAIL
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, EMAIL_PASS)
        server.send_message(msg)


def main():
    current = fetch_stats()
    previous = load_previous()

    gains = calculate_gains(previous, current)
    summary = generate_summary(gains)

    print(summary)

    send_email(summary)
    save_current(current)


if __name__ == "__main__":
    main()
