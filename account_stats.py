"""Full own-account skill snapshots from the same automation pull as the report."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def number(value):
    return value if isinstance(value, (int, float)) and value >= 0 else None


def build_report(tracker, all_stats: dict, generated_at: str | None) -> dict:
    accounts = []
    for name in [tracker.USERNAME, *tracker.OWN_ACCOUNTS]:
        player = all_stats.get(name)
        overall = player.get("overall", {}) if isinstance(player, dict) else {}
        available = isinstance(overall, dict) and number(overall.get("level")) is not None
        skills = []
        for skill in tracker.SKILLS:
            stat = player.get(skill, {}) if isinstance(player, dict) else {}
            stat = stat if isinstance(stat, dict) else {}
            skills.append({"skill": skill, "level": number(stat.get("level")), "xp": number(stat.get("experience"))})
        accounts.append({
            "name": name, "available": available,
            "totalLevel": number(overall.get("level")) if available else None,
            "totalXp": number(overall.get("experience")) if available else None,
            "skills": skills,
        })
    return {"generatedAt": generated_at, "accounts": accounts}


def timestamp_label(report: dict) -> str:
    value = report.get("generatedAt")
    if not isinstance(value, str):
        return "Timestamp unavailable"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "Timestamp unavailable"
        return parsed.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %I:%M %p %Z")
    except ValueError:
        return "Timestamp unavailable"


def formatted(value) -> str:
    return f"{value:,}" if value is not None else "Unavailable"


def build_html(tracker, report: dict) -> str:
    accounts = report["accounts"]
    content = f'<p style="font-size:12px;color:#6b7280;">Automation snapshot: {timestamp_label(report)}</p>'
    for account in accounts:
        if not account["available"]:
            content += f'<p style="font-size:12px;color:#6b7280;">{account["name"]}: no stats in this automation snapshot.</p>'
    content += '<table width="100%" cellpadding="0" cellspacing="0" style="table-layout:fixed;border-collapse:collapse;font-size:12px;color:#374151;"><tr><th align="left" width="28%">Stat</th>'
    content += "".join(f'<th align="right" style="word-break:break-word;">{account["name"]}</th>' for account in accounts) + "</tr>"
    for label, key in (("Total level", "totalLevel"), ("Total XP", "totalXp")):
        content += f'<tr><td style="padding:7px 0;font-weight:700;">{label}</td>'
        content += "".join(f'<td align="right" style="padding:7px 0;font-weight:700;">{formatted(account[key])}</td>' for account in accounts) + "</tr>"
    for index, skill in enumerate(tracker.SKILLS):
        content += f'<tr><td style="padding:6px 0;border-top:1px solid #e5e7eb;">{tracker.format_skill_name(skill)}</td>'
        for account in accounts:
            stat = account["skills"][index]
            level = f'Lv{stat["level"]}' if stat["level"] is not None else "Unavailable"
            xp = f'{stat["xp"]:,} xp' if stat["xp"] is not None else "XP unavailable"
            content += f'<td align="right" style="padding:6px 0;border-top:1px solid #e5e7eb;">{level}<br><span style="font-size:10px;color:#6b7280;">{xp}</span></td>'
        content += "</tr>"
    return tracker.section("Current Account Stats", content + "</table>")


def build_plain_text(tracker, report: dict) -> str:
    lines = ["CURRENT ACCOUNT STATS", f'Automation snapshot: {timestamp_label(report)}']
    for account in report["accounts"]:
        lines.extend(["", account["name"]])
        if not account["available"]:
            lines.append("No stats in this automation snapshot.")
            continue
        lines.extend([f'Total level: {formatted(account["totalLevel"])}', f'Total XP: {formatted(account["totalXp"])}'])
        for stat in account["skills"]:
            level = f'Lv{stat["level"]}' if stat["level"] is not None else "Unavailable"
            xp = f'{stat["xp"]:,} xp' if stat["xp"] is not None else "XP unavailable"
            lines.append(f'{tracker.format_skill_name(stat["skill"])}: {level} | {xp}')
    return "\n".join(lines)
