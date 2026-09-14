"""Boss KC and weekly raid goal support using the official OSRS HiScores feed."""

from __future__ import annotations


# Curated progression order, deliberately favoring approachable first kills before
# mechanically demanding encounters. There is no official Jagex difficulty order;
# this is a coaching queue, not a tier-list claim.
BOSS_DIFFICULTY_ORDER = [
    "Wintertodt",
    "Tempoross",
    "Obor",
    "Bryophyta",
    "Scurrius",
    "Brutus",
    "Giant Mole",
    "Barrows Chests",
    "Crazy Archaeologist",
    "Deranged Archaeologist",
    "Chaos Fanatic",
    "Hespori",
    "King Black Dragon",
    "Kraken",
    "Sarachnis",
    "Scorpia",
    "Zalcano",
    "Lunar Chests",
    "Amoxliatl",
    "Mad Angel",
    "Maggot King",
    "The Hueycoatl",
    "The Royal Titans",
    "Grotesque Guardians",
    "Skotizo",
    "Mimic",
    "Cal'varion",
    "Spindel",
    "Artio",
    "Chaos Elemental",
    "Dagannoth Rex",
    "Dagannoth Prime",
    "Dagannoth Supreme",
    "Commander Zilyana",
    "General Graardor",
    "K'ril Tsutsaroth",
    "Kree'Arra",
    "Kalphite Queen",
    "Callisto",
    "Venenatis",
    "Vet'ion",
    "Zulrah",
    "Vorkath",
    "Phantom Muspah",
    "Abyssal Sire",
    "Cerberus",
    "Thermonuclear Smoke Devil",
    "Alchemical Hydra",
    "Corporeal Beast",
    "Araxxor",
    "Shellbane Gryphon",
    "Duke Sucellus",
    "Vardorvis",
    "The Leviathan",
    "The Whisperer",
    "The Gauntlet",
    "The Corrupted Gauntlet",
    "Nightmare",
    "Nex",
    "Phosani's Nightmare",
    "Yama",
    "Doom of Mokhaiotl",
    "Chambers of Xeric",
    "Tombs of Amascut",
    "Theatre of Blood",
    "Chambers of Xeric: Challenge Mode",
    "Tombs of Amascut: Expert Mode",
    "Theatre of Blood: Hard Mode",
    "TzTok-Jad",
    "Sol Heredit",
    "TzKal-Zuk",
]

RAID_METRICS = [
    "Chambers of Xeric",
    "Chambers of Xeric: Challenge Mode",
    "Tombs of Amascut",
    "Tombs of Amascut: Expert Mode",
    "Theatre of Blood",
    "Theatre of Blood: Hard Mode",
]


def fetch_boss_kcs(tracker, username: str) -> dict[str, int]:
    """Fetch boss values by activity name from Jagex's JSON HiScores endpoint."""
    safe_name = username.replace(" ", "_")
    url = f"https://secure.runescape.com/m=hiscore_oldschool/index_lite.json?player={safe_name}"
    response = tracker.requests.get(url, headers=tracker.HISCORE_HEADERS, timeout=10)
    response.raise_for_status()
    payload = response.json()
    tracked = set(BOSS_DIFFICULTY_ORDER)
    boss_kcs: dict[str, int] = {}

    for activity in payload.get("activities", []):
        if not isinstance(activity, dict):
            continue
        name = activity.get("name")
        if name not in tracked:
            continue

        score = activity.get("score", -1)
        try:
            boss_kcs[str(name)] = max(int(score), 0)
        except (TypeError, ValueError):
            boss_kcs[str(name)] = 0

    # Keep every configured boss present so the queue remains deterministic if a
    # single activity is temporarily omitted from the upstream response.
    for activity in BOSS_DIFFICULTY_ORDER:
        boss_kcs.setdefault(activity, 0)

    return boss_kcs


def build_boss_progression(boss_kcs: dict[str, int], preview_limit: int = 8) -> dict:
    untried = [name for name in BOSS_DIFFICULTY_ORDER if boss_kcs.get(name, 0) < 1]
    tried_count = len(BOSS_DIFFICULTY_ORDER) - len(untried)
    return {
        "triedCount": tried_count,
        "totalTracked": len(BOSS_DIFFICULTY_ORDER),
        "untriedCount": len(untried),
        "nextUntried": [
            {"name": name, "kc": boss_kcs.get(name, 0), "targetKc": 1}
            for name in untried[:preview_limit]
        ],
    }


def build_weekly_raid_goal(
    tracker,
    current_week_summary: dict,
    previous_all: dict,
    username: str,
    boss_kcs: dict[str, int],
) -> dict:
    week_start = current_week_summary.get("weekStartDateKey")
    previous_metadata = previous_all.get(tracker.METADATA_KEY, {}) if isinstance(previous_all, dict) else {}
    previous_week = previous_metadata.get("currentWeek", {}).get(username, {})
    previous_raid_goal = previous_week.get("raidGoal", {}) if isinstance(previous_week, dict) else {}

    if previous_week.get("weekStartDateKey") == week_start and isinstance(previous_raid_goal.get("baselineKcs"), dict):
        baseline = {
            metric: max(int(previous_raid_goal["baselineKcs"].get(metric, boss_kcs.get(metric, 0))), 0)
            for metric in RAID_METRICS
        }
    else:
        previous_bosses = previous_metadata.get("bosses", {}).get(username, {})
        if isinstance(previous_bosses, dict) and previous_bosses:
            baseline = {metric: max(int(previous_bosses.get(metric, boss_kcs.get(metric, 0))), 0) for metric in RAID_METRICS}
        else:
            baseline = {metric: boss_kcs.get(metric, 0) for metric in RAID_METRICS}

    gains = [
        {
            "name": metric,
            "gained": max(boss_kcs.get(metric, 0) - baseline.get(metric, 0), 0),
        }
        for metric in RAID_METRICS
    ]

    # Binary on purpose: Expert/Hard modes can overlap with a parent raid metric,
    # but the user's goal is simply whether at least one raid was completed.
    completed = 1 if any(item["gained"] > 0 for item in gains) else 0

    return {
        "target": 1,
        "completed": completed,
        "weekStartDateKey": week_start,
        "baselineKcs": baseline,
        "gainsByRaid": [item for item in gains if item["gained"] > 0],
    }


def build_boss_html(tracker, boss_kcs: dict[str, int]) -> str:
    progression = build_boss_progression(boss_kcs)
    pct = tracker.clamp_pct(progression["triedCount"] / max(progression["totalTracked"], 1) * 100)
    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {tracker.row("Bosses/encounters tried", f'{progression["triedCount"]}/{progression["totalTracked"]}')}
  {tracker.row("Still needing first KC", str(progression["untriedCount"]))}
</table>
{tracker.progress_bar(pct, "#ef4444")}
"""

    queue = progression["nextUntried"]
    if not queue:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">First-KC queue complete.</div>'
    else:
        content += (
            '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; '
            'text-transform:uppercase; letter-spacing:.04em;">Next first kills - easier to harder</div>'
        )
        for index, item in enumerate(queue, start=1):
            prefix = "NEXT" if index == 1 else f"#{index}"
            content += (
                '<div style="font-size:12px; color:#374151; padding:3px 0;">'
                f'<b>{prefix}: {item["name"]}</b> <span style="color:#6b7280;">&middot; goal: 1 KC</span></div>'
            )

    return tracker.section("Boss Progression - Get 1 KC", content)


def build_weekly_raid_html(tracker, raid_goal: dict) -> str:
    target = int(raid_goal.get("target", 1))
    completed = min(int(raid_goal.get("completed", 0)), target)
    pct = tracker.clamp_pct(completed / max(target, 1) * 100)
    week_start = raid_goal.get("weekStartDateKey") or "current week"
    content = f"""
<table width="100%" cellpadding="0" cellspacing="0">
  {tracker.row("This week", f"{completed}/{target} raid completion")}
  {tracker.row("Week starts", str(week_start))}
</table>
{tracker.progress_bar(pct, "#f59e0b")}
<div style="font-size:12px; color:#6b7280; margin-top:8px;">
Counts CoX (regular or CM), Tombs of Amascut (regular or expert), or Theatre of Blood (regular or hard mode).
</div>
"""
    gains = raid_goal.get("gainsByRaid", [])
    if completed >= target:
        names = ", ".join(item.get("name", "Raid") for item in gains if item.get("gained", 0) > 0)
        suffix = f" - {names}" if names else ""
        content += (
            '<div style="font-size:13px; color:#16a34a; font-weight:700; margin-top:8px;">'
            f"Weekly raid goal complete{suffix}.</div>"
        )
    else:
        content += '<div style="font-size:13px; color:#b45309; font-weight:700; margin-top:8px;">One raid completion still needed this week.</div>'

    return tracker.section("Weekly Raid Goal - 1 Completion", content)


def build_boss_and_raid_html(tracker, boss_kcs: dict[str, int], raid_goal: dict) -> str:
    return build_boss_html(tracker, boss_kcs) + build_weekly_raid_html(tracker, raid_goal)
