"""Compare Ironmen over the same interval between successful paired snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def valid_stats(stats) -> bool:
    overall = stats.get("overall") if isinstance(stats, dict) else None
    return isinstance(overall, dict) and all(
        isinstance(overall.get(key), (int, float)) and overall[key] >= 0
        for key in ("level", "experience")
    )


def valid_timestamp(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def build_comparison(tracker, accounts_data: dict, previous_all: dict, generated_at: str | None = None) -> dict:
    period_end = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata = previous_all.get(tracker.METADATA_KEY, {})
    previous_comparison = metadata.get("ironmanComparison", {})
    baseline = previous_comparison.get("baseline", {})
    baseline_at = previous_comparison.get("baselineAt")
    names = list(tracker.IRONMAN_ACCOUNTS)

    if not all(valid_stats(baseline.get(name)) for name in names) or not valid_timestamp(baseline_at):
        # Migration can use the last report only if it already contains both accounts.
        baseline = {name: previous_all.get(name) for name in names}
        baseline_at = metadata.get("generatedAt")
    has_baseline = all(valid_stats(baseline.get(name)) for name in names) and valid_timestamp(baseline_at)
    both_available = all(valid_stats(accounts_data.get(name)) for name in names)
    status = "comparison" if both_available and has_baseline else "baseline" if both_available else "unavailable"
    accounts = []
    for name, account_type in tracker.IRONMAN_ACCOUNTS.items():
        stats = accounts_data.get(name)
        available = valid_stats(stats)
        previous = baseline.get(name) if status == "comparison" else None
        top_skills = []
        if previous is not None:
            for skill in tracker.SKILLS:
                current_skill = stats.get(skill)
                old_skill = previous.get(skill)
                if not isinstance(current_skill, dict) or not isinstance(old_skill, dict):
                    continue
                xp = max(current_skill["experience"] - max(old_skill["experience"], 0), 0)
                if xp > 0:
                    top_skills.append({
                        "skill": skill, "xp": xp, "level": current_skill["level"],
                        "levelsGained": max(current_skill["level"] - old_skill["level"], 0),
                    })
            top_skills.sort(key=lambda item: item["xp"], reverse=True)
        accounts.append({
            "name": name, "accountType": account_type, "available": available,
            "totalLevel": stats["overall"]["level"] if available else 0,
            "totalXp": stats["overall"]["experience"] if available else 0,
            "gainedXp": max(stats["overall"]["experience"] - previous["overall"]["experience"], 0) if previous else None,
            "gainedLevels": max(stats["overall"]["level"] - previous["overall"]["level"], 0) if previous else None,
            "topSkills": top_skills[:5],
        })
    return {
        "status": status, "periodStart": baseline_at if status == "comparison" else None,
        "periodEnd": period_end, "accounts": accounts,
        # A failed lookup must never advance only one account's comparison baseline.
        "baselineAt": period_end if both_available else baseline_at if has_baseline else None,
        "baseline": {name: accounts_data[name] for name in names} if both_available else baseline if has_baseline else {},
    }


def period_label(comparison: dict) -> str:
    if comparison["status"] == "baseline":
        return "Baseline established; comparison begins with the next successful report."
    if comparison["status"] != "comparison":
        return "Comparison paused until both HiScores lookups succeed."
    def local_time(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York")).strftime("%b %d, %I:%M %p")
    return f'Since previous paired report: {local_time(comparison["periodStart"])} to {local_time(comparison["periodEnd"])} ET'


def comparison_leads(comparison: dict) -> list[str]:
    if comparison["status"] != "comparison":
        return []
    left, right = comparison["accounts"]
    lines = []
    for key, unit in (("gainedXp", "XP"), ("gainedLevels", "total levels")):
        diff = left[key] - right[key]
        if diff == 0:
            lines.append(f"{unit} gained: tied.")
        else:
            leader = left if diff > 0 else right
            lines.append(f'{leader["name"]} gained {abs(diff):,} more {unit}.')
    return lines


def build_html(tracker, comparison: dict) -> str:
    content = f'<p style="font-size:12px;color:#6b7280;">{period_label(comparison)}</p>'
    content += "".join(f'<p style="font-size:13px;color:#374151;">{line}</p>' for line in comparison_leads(comparison))
    cells = []
    for account in comparison["accounts"]:
        details = f'<h3 style="font-size:14px;color:#111827;">{account["name"]} - Ironman</h3>'
        if not account["available"]:
            details += '<p style="font-size:13px;color:#6b7280;">HiScores data unavailable.</p>'
        else:
            details += '<table width="100%" cellpadding="0" cellspacing="0">'
            details += tracker.row("Total level", f'{account["totalLevel"]:,}')
            details += tracker.row("Total XP", f'{account["totalXp"]:,}')
            details += tracker.row("Levels gained", f'+{account["gainedLevels"]:,}' if account["gainedLevels"] is not None else "Pending")
            details += tracker.row("XP gained", f'+{account["gainedXp"]:,}' if account["gainedXp"] is not None else "Pending")
            details += '</table><p style="font-size:12px;font-weight:700;color:#374151;">Top 5 skill gains (by XP)</p>'
            for skill in account["topSkills"]:
                details += (
                    '<div style="font-size:12px;color:#374151;padding:4px 0;">'
                    f'<b>{tracker.format_skill_name(skill["skill"])}</b> Lv{skill["level"]} (+{skill["levelsGained"]})'
                    f'<br>+{skill["xp"]:,} xp</div>'
                )
            if not account["topSkills"]:
                details += '<p style="font-size:12px;color:#6b7280;">' + ("No skill XP gained this period." if comparison["status"] == "comparison" else "Waiting for a comparison period.") + "</p>"
        cells.append(f'<td width="50%" valign="top" style="padding:0 6px;word-break:break-word;">{details}</td>')
    return tracker.section("Ironman Progress - You vs IronXDabber", content + '<table width="100%" cellpadding="0" cellspacing="0" style="table-layout:fixed;"><tr>' + "".join(cells) + "</tr></table>")


def build_plain_text(tracker, comparison: dict) -> str:
    lines = ["IRONMAN PROGRESS - YOU VS IRONXDABBER", period_label(comparison), *comparison_leads(comparison)]
    for account in comparison["accounts"]:
        lines.extend(["", f'{account["name"]} - Ironman'])
        if not account["available"]:
            lines.append("HiScores data unavailable.")
            continue
        lines.extend([f'Total level: {account["totalLevel"]:,}', f'Total account XP: {account["totalXp"]:,}'])
        if account["gainedXp"] is not None:
            lines.extend([f'Levels gained: +{account["gainedLevels"]:,}', f'XP gained: +{account["gainedXp"]:,}'])
        lines.append("Top 5 skill gains (by XP):")
        lines.extend(f'- {tracker.format_skill_name(skill["skill"])} Lv{skill["level"]} (+{skill["levelsGained"]}): +{skill["xp"]:,} xp' for skill in account["topSkills"])
        if not account["topSkills"]:
            lines.append("No skill XP gained this period." if comparison["status"] == "comparison" else "Waiting for a comparison period.")
    return "\n".join(lines)
