"""Boss KC, daily boss activity, and weekly raid goal support."""

from __future__ import annotations


# The OSRS Wiki Bossing Ladder is the backbone for progression. Tier order and,
# where possible, order within a tier follow the Wiki guide. Encounters not yet
# placed on the Wiki ladder are inserted conservatively beside comparable bosses.
# This is intentionally a first-KC learning path, not a profitability tier list.
BOSS_LADDER_TIERS = {
    "Easy": [
        "Brutus",
        "Wintertodt",
        "Tempoross",
        "Barrows Chests",
        "Obor",
        "Bryophyta",
        "Giant Mole",
        "Deranged Archaeologist",
        "Scurrius",
    ],
    "Medium": [
        "Amoxliatl",
        # Newer mid-game encounter; community guidance places it just above Amoxliatl.
        "Mad Angel",
        "The Hueycoatl",
        "Hespori",
        "Crazy Archaeologist",
        "Chaos Fanatic",
        # Jagex describes Shellbane as a mid-level Slayer boss.
        "Shellbane Gryphon",
        "Kraken",
        "Sarachnis",
        "King Black Dragon",
        "Zalcano",
        "Lunar Chests",
        "Thermonuclear Smoke Devil",
        "Mimic",
        "The Royal Titans",
        # The Wiki puts God Wars bosses in teams at the end of Medium tier.
        "Commander Zilyana",
        "General Graardor",
        "K'ril Tsutsaroth",
        "Kree'Arra",
    ],
    "Hard": [
        "Scorpia",
        "Chaos Elemental",
        "Cal'varion",
        "Vet'ion",
        "Spindel",
        "Venenatis",
        "Artio",
        "Callisto",
        "Dagannoth Rex",
        "Dagannoth Prime",
        "Dagannoth Supreme",
        "Kalphite Queen",
        "Grotesque Guardians",
        "Skotizo",
        "The Gauntlet",
        "TzTok-Jad",
    ],
    "Elite": [
        "Zulrah",
        "Vorkath",
        "Phantom Muspah",
        "Duke Sucellus",
        "Abyssal Sire",
        "Cerberus",
        "Araxxor",
        "Alchemical Hydra",
        "The Corrupted Gauntlet",
        "The Whisperer",
        "The Leviathan",
        "Vardorvis",
        "Corporeal Beast",
        "Nex",
        "Tombs of Amascut",
    ],
    "Master": [
        "Chambers of Xeric",
        "Nightmare",
        "Phosani's Nightmare",
        # Current guides place Maggot King around Phosani-level mechanical difficulty.
        "Maggot King",
        "Yama",
        "Doom of Mokhaiotl",
        "Theatre of Blood",
    ],
    "Grandmaster": [
        "Chambers of Xeric: Challenge Mode",
        "Tombs of Amascut: Expert Mode",
        "Theatre of Blood: Hard Mode",
        "Sol Heredit",
        "TzKal-Zuk",
    ],
}

BOSS_DIFFICULTY_ORDER = [
    boss
    for tier_bosses in BOSS_LADDER_TIERS.values()
    for boss in tier_bosses
]

BOSS_ORDER_INDEX = {
    boss: index
    for index, boss in enumerate(BOSS_DIFFICULTY_ORDER)
}

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

    # Keep every configured boss present so snapshots remain deterministic if a
    # single activity is temporarily omitted from the upstream response.
    for activity in BOSS_DIFFICULTY_ORDER:
        boss_kcs.setdefault(activity, 0)

    return boss_kcs


def normalize_boss_kcs(boss_kcs: dict | None) -> dict[str, int]:
    """Normalize persisted or fetched KC values for every configured encounter."""
    source = boss_kcs if isinstance(boss_kcs, dict) else {}
    normalized: dict[str, int] = {}

    for boss in BOSS_DIFFICULTY_ORDER:
        value = source.get(boss, 0)
        try:
            normalized[boss] = max(int(value), 0)
        except (TypeError, ValueError):
            normalized[boss] = 0

    return normalized


def build_boss_progression(boss_kcs: dict[str, int]) -> dict:
    normalized = normalize_boss_kcs(boss_kcs)
    remaining_by_tier = {
        tier: [
            {
                "name": name,
                "kc": normalized[name],
                "targetKc": 1,
                "tier": tier,
            }
            for name in tier_bosses
            if normalized[name] < 1
        ]
        for tier, tier_bosses in BOSS_LADDER_TIERS.items()
    }
    untried_count = sum(len(bosses) for bosses in remaining_by_tier.values())
    tried_count = len(BOSS_DIFFICULTY_ORDER) - untried_count
    return {
        "triedCount": tried_count,
        "totalTracked": len(BOSS_DIFFICULTY_ORDER),
        "untriedCount": untried_count,
        "remainingByTier": remaining_by_tier,
    }


def get_previous_boss_kcs(previous_all: dict, tracker, username: str) -> dict[str, int] | None:
    """Read a player's prior KC snapshot, including the gwahpy rename fallback."""
    if not isinstance(previous_all, dict):
        return None

    metadata = previous_all.get(tracker.METADATA_KEY, {})
    bosses_by_player = metadata.get("bosses", {}) if isinstance(metadata, dict) else {}
    if not isinstance(bosses_by_player, dict):
        return None

    previous = bosses_by_player.get(username)
    if previous is None and username == "3Sixteen":
        previous = bosses_by_player.get("gwahpy")
    if not isinstance(previous, dict):
        return None

    return normalize_boss_kcs(previous)


def build_daily_boss_activity(
    tracker,
    current_by_player: dict[str, dict[str, int]],
    previous_all: dict,
    player_order: list[str],
    leaderboard_limit: int = 3,
) -> dict:
    """Calculate positive boss-KC changes since the immediately prior snapshot."""
    by_player = {}

    for username in player_order:
        current = current_by_player.get(username)
        if not isinstance(current, dict):
            continue

        normalized_current = normalize_boss_kcs(current)
        previous = get_previous_boss_kcs(previous_all, tracker, username)
        boss_gains = {}

        # No previous player snapshot means this run establishes the baseline.
        if previous is not None:
            positive_gains = [
                (boss, normalized_current[boss] - previous[boss])
                for boss in BOSS_DIFFICULTY_ORDER
                if normalized_current[boss] - previous[boss] > 0
            ]
            positive_gains.sort(
                key=lambda item: (-item[1], BOSS_ORDER_INDEX[item[0]], item[0])
            )
            boss_gains = {boss: gained for boss, gained in positive_gains}

        by_player[username] = {
            "totalBossKcGained": sum(boss_gains.values()),
            "bossGains": boss_gains,
        }

    player_index = {username: index for index, username in enumerate(player_order)}
    ranked = sorted(
        (
            {"name": username, **summary}
            for username, summary in by_player.items()
            if summary["totalBossKcGained"] > 0
        ),
        key=lambda item: (
            -item["totalBossKcGained"],
            player_index.get(item["name"], len(player_order)),
            item["name"].casefold(),
        ),
    )

    return {
        "byPlayer": by_player,
        "topPlayers": ranked[:leaderboard_limit],
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
  {tracker.row("Bosses/encounters completed once", f'{progression["triedCount"]} / {progression["totalTracked"]}')}
  {tracker.row("Remaining", str(progression["untriedCount"]))}
</table>
{tracker.progress_bar(pct, "#ef4444")}
"""

    remaining_by_tier = progression["remainingByTier"]
    if progression["untriedCount"] == 0:
        content += '<div style="font-size:14px; color:#16a34a; font-weight:700; margin-top:8px;">Every tracked boss or encounter has at least 1 KC.</div>'
    else:
        content += (
            '<div style="margin-top:10px; font-size:12px; font-weight:700; color:#374151; '
            'text-transform:uppercase; letter-spacing:.04em;">Bosses Remaining</div>'
        )
        for tier, bosses in remaining_by_tier.items():
            if not bosses:
                continue
            content += (
                '<div style="font-size:12px; color:#6b7280; font-weight:800; margin-top:10px; '
                f'text-transform:uppercase; letter-spacing:.05em;">{tier}</div>'
            )
            for item in bosses:
                content += (
                    '<div style="font-size:12px; color:#374151; padding:3px 0;">'
                    f'&bull; <b>{item["name"]}</b> '
                    f'<span style="color:#6b7280;">&middot; {item["kc"]} KC</span></div>'
                )

    return tracker.section("Boss Completion Checklist - Get 1 KC", content)


def build_daily_boss_activity_html(tracker, daily_activity: dict) -> str:
    """Build the player-level top-three boss activity section when KC changed."""
    top_players = daily_activity.get("topPlayers", []) if isinstance(daily_activity, dict) else []
    if not top_players:
        return ""

    content = ""
    for rank, player in enumerate(top_players, start=1):
        content += (
            '<div style="font-size:14px; color:#111827; font-weight:800; '
            f'margin-top:{"0" if rank == 1 else "12px"};">'
            f'{rank}. {player["name"]} &mdash; {player["totalBossKcGained"]:,} KC</div>'
        )
        for boss, gained in player.get("bossGains", {}).items():
            content += (
                '<div style="font-size:12px; color:#4b5563; padding:2px 0 0 16px;">'
                f'&bull; {boss} +{gained:,}</div>'
            )

    return tracker.section("Boss Kills Since Last Update", content)


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


def build_boss_and_raid_html(
    tracker,
    boss_kcs: dict[str, int],
    raid_goal: dict,
    daily_activity: dict | None = None,
) -> str:
    return (
        build_boss_html(tracker, boss_kcs)
        + build_daily_boss_activity_html(tracker, daily_activity or {})
        + build_weekly_raid_html(tracker, raid_goal)
    )
