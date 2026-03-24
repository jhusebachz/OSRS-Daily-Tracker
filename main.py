import requests
import json
import os
import time
from datetime import datetime, date
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq

# =========================
# CONFIG
# =========================

USERNAME = "jhusebachz"
FRIENDS = ["mufkr", "kingxdabber", "beefmissle13", "hedith"]

DATA_FILE = "data/last_stats.json"

# Personal goals with deadlines
GOAL_BASE90_DATE = date(2026, 5, 22)        # Base 90 all skills
GOAL_RUNEFEST_DATE = date(2026, 10, 3)      # RuneFest 2026 - total level 2250
GOAL_MAX_DATE = date(2027, 3, 15)           # Max by 33rd birthday

GOAL_RUNEFEST_LEVEL = 2250
MAX_SKILL_LEVEL = 99

# Skill order as returned by the official hiscores CSV API
HISCORE_SKILLS = [
    "overall", "attack", "defence", "strength", "hitpoints", "ranged", "prayer",
    "magic", "cooking", "woodcutting", "fletching", "fishing", "firemaking",
    "crafting", "smithing", "mining", "herblore", "agility", "thieving",
    "slayer", "farming", "runecraft", "hunter", "construction", "sailing"
]

# Skills used for XP gain tracking (excludes 'overall')
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
# FETCH DATA (Official Hiscores CSV API — no Cloudflare issues)
# =========================

def fetch_player(username):
    safe_name = username.replace(" ", "_")
    url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={safe_name}"
    headers = {"User-Agent": "OSRS-Daily-Tracker/1.0"}
    res = requests.get(url, headers=headers, timeout=10)
    res.raise_for_status()

    stats = {}
    lines = res.text.strip().split("\n")
    for i, line in enumerate(lines):
        if i >= len(HISCORE_SKILLS):
            break
        parts = line.strip().split(",")
        if len(parts) < 3:
            continue
        skill = HISCORE_SKILLS[i]
        stats[skill] = {
            "rank": int(parts[0]) if parts[0].strip() != "-1" else -1,
            "level": int(parts[1]),
            "experience": int(parts[2])
        }
    return stats

# =========================
# DATA STORAGE
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
# HTML EMAIL BUILDER HELPERS
# =========================

def section(title, emoji, content_html):
    return f"""
<div style="margin: 24px 0; background: #ffffff; border-radius: 10px;
     border-left: 5px solid #8b5cf6; padding: 16px 20px;
     box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
  <h2 style="margin: 0 0 12px 0; font-size: 15px; font-weight: 700;
      color: #1e1b4b; text-transform: uppercase; letter-spacing: 0.05em;">
    {emoji}&nbsp; {title}
  </h2>
  {content_html}
</div>"""

def row(label, value, muted=False):
    color = "#6b7280" if muted else "#111827"
    return f"""<tr>
  <td style="padding: 4px 0; color: #6b7280; font-size: 13px; width: 55%;">{label}</td>
  <td style="padding: 4px 0; color: {color}; font-size: 13px; font-weight: 600; text-align: right;">{value}</td>
</tr>"""

def pill(text, color="#8b5cf6"):
    return (f'<span style="display:inline-block; background:{color}; color:#fff; '
            f'border-radius:999px; padding:2px 10px; font-size:12px; '
            f'font-weight:600; margin: 2px 3px;">{text}</span>')

def progress_bar(pct, color="#8b5cf6"):
    pct = min(max(pct, 0), 100)
    return f"""
<div style="background:#e5e7eb; border-radius:999px; height:8px; margin: 3px 0 8px 0;">
  <div style="background:{color}; width:{pct}%; height:8px; border-radius:999px;"></div>
</div>"""

# =========================
# FRIEND COMPARISON SECTION
# =========================

def friend_comparison_html(your_gains, friends_data, previous_all):
    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)

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
        friend_total_xp = sum(v for k, v in friend_gains.items() if k in SKILLS)
        diff = your_total_xp - friend_total_xp

        if diff > 0:
            badge = pill(f"You +{diff:,} xp ahead", "#16a34a")
        elif diff < 0:
            badge = pill(f"They +{abs(diff):,} xp ahead", "#dc2626")
        else:
            badge = pill("Dead even", "#d97706")

        top3 = sorted(
            [(s, friend_gains[s]) for s in SKILLS if friend_gains.get(s, 0) > 0],
            key=lambda x: x[1], reverse=True
        )[:3]

        if top3:
            top3_html = "".join(
                f'<div style="font-size:12px; color:#374151; padding: 2px 0;">'
                f'&nbsp;&nbsp;• {s.capitalize()}: +{xp:,} xp (Lv{friends_data[friend][s]["level"]})</div>'
                for s, xp in top3
            )
        else:
            top3_html = '<div style="font-size:12px; color:#9ca3af;">No xp gained today</div>'

        rows_html += f"""
<div style="margin-bottom: 14px;">
  <div style="font-size:14px; font-weight:700; color:#1e1b4b; margin-bottom:4px;">
    {friend}
    <span style="font-size:12px; font-weight:400; color:#6b7280; margin-left:6px;">{friend_total_xp:,} xp today</span>
    {badge}
  </div>
  <div style="font-size:12px; color:#6b7280; margin-bottom:3px;">Top gains:</div>
  {top3_html}
</div>"""

    return section("Daily XP — You vs Friends", "⚔️", rows_html)

# =========================
# GOAL 1: BASE 90
# =========================

def base90_html(stats, gains):
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
            eta_str = f"~{round(remaining_xp / daily_xp, 1)}d" if daily_xp > 0 else "no recent xp"
            skills_remaining.append((skill, stats[skill]["level"], pct, remaining_xp, eta_str))

    skills_remaining.sort(key=lambda x: x[2], reverse=True)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_BASE90_DATE} ({days_left} days left)")}
  {row("Skills at 90+", f"{len(skills_done)}/{len(SKILLS)}", muted=not skills_remaining)}
</table>"""

    if skills_remaining:
        content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Still needed</div>'
        for skill, level, pct, remaining_xp, eta_str in skills_remaining:
            bar_color = "#f59e0b" if pct >= 80 else "#8b5cf6"
            content += f"""
<div style="margin: 6px 0;">
  <div style="display:flex; justify-content:space-between; font-size:12px; color:#374151;">
    <span><b>{skill.capitalize()}</b> Lv{level}</span>
    <span style="color:#6b7280;">{pct}% &nbsp;·&nbsp; {remaining_xp:,} xp &nbsp;·&nbsp; {eta_str}</span>
  </div>
  {progress_bar(pct, bar_color)}
</div>"""
    else:
        content += '<div style="margin-top:8px; font-size:14px; color:#16a34a; font-weight:700;">✅ Base 90 complete!</div>'

    return section("Goal 1 · Base 90 All Skills", "🎯", content)

# =========================
# GOAL 2: TOTAL LEVEL 2250 BY RUNEFEST
# =========================

def total_level_html(stats, gains):
    days_left = days_until(GOAL_RUNEFEST_DATE)
    total_level = stats["overall"]["level"] if "overall" in stats else sum(
        stats[s]["level"] for s in SKILLS if s in stats
    )
    levels_needed = max(GOAL_RUNEFEST_LEVEL - total_level, 0)
    pct = round(min(total_level / GOAL_RUNEFEST_LEVEL * 100, 100), 1)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_RUNEFEST_DATE} — RuneFest ({days_left} days left)")}
  {row("Current total level", f"{total_level:,} / {GOAL_RUNEFEST_LEVEL:,}")}
  {row("Levels still needed", str(levels_needed))}
</table>
{progress_bar(pct, "#3b82f6")}"""

    if levels_needed <= 0:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700;">✅ RuneFest goal achieved!</div>'
    else:
        lpd = round(levels_needed / days_left, 2)
        content += f'<div style="font-size:12px; color:#6b7280; margin-top:4px;">Need <b>{lpd}</b> levels/day to hit {GOAL_RUNEFEST_LEVEL} in time</div>'

    active = [(s, gains.get(s, 0)) for s in SKILLS if s in stats and gains.get(s, 0) > 0]
    active.sort(key=lambda x: x[1], reverse=True)

    if active:
        content += '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em;">Most active today</div>'
        for skill, xp in active[:5]:
            content += (f'<div style="font-size:12px; color:#374151; padding:2px 0;">'
                        f'• {skill.capitalize()}: +{xp:,} xp (Lv{stats[skill]["level"]})</div>')

    return section(f"Goal 2 · Total Level {GOAL_RUNEFEST_LEVEL} by RuneFest", "⛵", content)

# =========================
# GOAL 3: MAX BY 33RD BIRTHDAY
# =========================

def max_progress_html(stats, gains):
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
            eta_str = f"~{round(remaining_xp / daily_xp, 1)}d" if daily_xp > 0 else "no recent xp"
            skills_remaining.append((skill, stats[skill]["level"], remaining_xp, eta_str))

    skills_remaining.sort(key=lambda x: x[2])
    pct = round(len(skills_maxed) / len(SKILLS) * 100, 1)

    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {row("Deadline", f"{GOAL_MAX_DATE} — 33rd birthday ({days_left} days left)")}
  {row("Skills maxed", f"{len(skills_maxed)}/{len(SKILLS)}")}
</table>
{progress_bar(pct, "#ec4899")}"""

    if skills_maxed:
        content += '<div style="margin: 6px 0 10px;">'
        for s in skills_maxed:
            content += pill(s.capitalize(), "#16a34a")
        content += '</div>'

    if skills_remaining:
        content += '<div style="font-size:12px; font-weight:700; color:#374151; text-transform:uppercase; letter-spacing:.04em; margin-top:6px;">Closest to 99</div>'
        for skill, level, remaining_xp, eta_str in skills_remaining[:5]:
            goal_xp_val = level_to_xp(MAX_SKILL_LEVEL)
            skill_pct = round((goal_xp_val - remaining_xp) / goal_xp_val * 100, 1)
            content += f"""
<div style="margin: 6px 0;">
  <div style="font-size:12px; color:#374151;">
    <b>{skill.capitalize()}</b> Lv{level}
    <span style="color:#6b7280;"> &nbsp;·&nbsp; {remaining_xp:,} xp to 99 &nbsp;·&nbsp; {eta_str}</span>
  </div>
  {progress_bar(skill_pct, "#ec4899")}
</div>"""
    else:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">✅ Maxed!</div>'

    return section("Goal 3 · Max Cape by 33rd Birthday", "🎂", content)

# =========================
# AI COACHING SECTION
# =========================

def generate_ai_coaching(your_gains, your_stats, friends_data, previous_all):
    days_to_base90 = days_until(GOAL_BASE90_DATE)
    days_to_runefest = days_until(GOAL_RUNEFEST_DATE)
    days_to_max = days_until(GOAL_MAX_DATE)

    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)

    top_gains = sorted(
        [(s, your_gains[s]) for s in SKILLS if your_gains.get(s, 0) > 0],
        key=lambda x: x[1], reverse=True
    )[:5]

    skills_under_90 = [s for s in SKILLS if s in your_stats and your_stats[s]["level"] < 90]
    skills_maxed = [s for s in SKILLS if s in your_stats and your_stats[s]["level"] >= 99]
    total_level = your_stats["overall"]["level"] if "overall" in your_stats else 0

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
(4-6 sentences) referencing their actual numbers, daily XP vs friends, and which goals are most urgent.

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

Be specific, reference the deadlines, and prioritize whichever goal is most at risk."""

    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400
    )
    return response.choices[0].message.content

def coaching_html(your_gains, your_stats, friends_data, previous_all):
    try:
        text = generate_ai_coaching(your_gains, your_stats, friends_data, previous_all)
        paragraphs = "".join(
            f'<p style="margin: 0 0 10px 0; font-size: 14px; color: #374151; line-height: 1.6;">{p.strip()}</p>'
            for p in text.strip().split("\n") if p.strip()
        )
        content = paragraphs
    except Exception as e:
        content = f'<p style="color:#dc2626; font-size:13px;">Could not generate coaching: {e}</p>'
    return section("Daily Coaching Insight", "🧠", content)

# =========================
# FULL HTML EMAIL
# =========================

def build_html_email(your_gains, your_stats, friends_data, previous_all):
    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)
    today = datetime.now().strftime("%B %d, %Y")

    top = sorted(
        [(s, your_gains[s]) for s in SKILLS if your_gains.get(s, 0) > 0],
        key=lambda x: x[1], reverse=True
    )[:5]

    if top:
        top_gains_html = "".join(
            f'<div style="font-size:13px; color:#374151; padding:3px 0;">'
            f'<b>{s.capitalize()}</b>: +{xp:,} xp</div>'
            for s, xp in top
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
      jhusebachz · OSRS Daily Tracker
    </div>
  </div>
</body>
</html>"""

# =========================
# EMAIL
# =========================

def send_email(html_content, plain_summary):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "⚔️ OSRS Daily Report"
    msg["From"] = EMAIL
    msg["To"] = TO_EMAIL
    msg.attach(MIMEText(plain_summary, "plain"))
    msg.attach(MIMEText(html_content, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL, EMAIL_PASS)
        server.send_message(msg)

# =========================
# PLAIN TEXT FALLBACK
# =========================

def build_plain_text(your_gains, your_stats, friends_data, previous_all):
    your_total_xp = sum(v for k, v in your_gains.items() if k in SKILLS)
    lines = [
        f"OSRS Daily Report - {datetime.now().strftime('%Y-%m-%d')}",
        f"Total XP Today: {your_total_xp:,}",
        ""
    ]
    for friend in FRIENDS:
        if friend not in friends_data:
            continue
        fg = calculate_gains(previous_all, friend, friends_data[friend])
        fxp = sum(v for k, v in fg.items() if k in SKILLS)
        diff = your_total_xp - fxp
        status = f"you +{diff:,}" if diff >= 0 else f"them +{abs(diff):,}"
        lines.append(f"{friend}: {fxp:,} xp ({status})")
    return "\n".join(lines)

# =========================
# MAIN
# =========================

def main():
    # Step 1: Fetch stats for yourself and all friends
    # Small delay between requests to be polite to the Jagex hiscores API
    your_stats = fetch_player(USERNAME)
    time.sleep(1)

    friends_data = {}
    for friend in FRIENDS:
        try:
            friends_data[friend] = fetch_player(friend)
        except Exception as e:
            print(f"Warning: could not fetch stats for {friend}: {e}")
        time.sleep(1)

    # Step 2: Load previous snapshot
    previous_all = load_previous()

    # Step 3: Calculate your gains
    your_gains = calculate_gains(previous_all, USERNAME, your_stats)

    # Step 4: Build email
    html_email = build_html_email(your_gains, your_stats, friends_data, previous_all)
    plain_email = build_plain_text(your_gains, your_stats, friends_data, previous_all)

    print(plain_email)

    # Step 5: Send email
    send_email(html_email, plain_email)

    # Step 6: Save current stats for all players
    save_current(your_stats, friends_data)

if __name__ == "__main__":
    main()
