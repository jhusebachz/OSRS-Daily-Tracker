# OSRS Daily Tracker

[![Daily OSRS Tracker](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml/badge.svg)](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml)

Automated Old School RuneScape progress tracking for `jhusebachz` and a small comparison group.

`JorbisBTW` has an Ironman base-level ladder (30, 40, 50, 60, 70, 80, 90, and 99), with no imposed hours or deadline. It tracks total level, how many skills meet the current tier, the remaining skills, and a preview of the next tier. `IronXDabber` now appears in the ordinary friends comparison; the former head-to-head rivalry is no longer shown. Legacy paired-comparison metadata is retained for compatibility.

The main account's Max Cape deadline is **December 31, 2027**. Its cumulative hours-ahead/behind figure compares the training hours completed since the fixed November 10, 2026 HiScores baseline with the hours expected by the report date. Combat skills are tracked toward 99 but excluded from the hours clock because Slayer trains them simultaneously. Both goals are published in `_meta.maxCapePace` and `_meta.ironmanMilestone` for Lil Johnny.

The achievement diary goal has been removed. Both email alternatives end with **Current Account Stats** for `jhusebachz` and `JorbisBTW`, including total level, total XP, and every skill's level and XP. These are the exact stats captured by that automation run, with its saved timestamp; the app reads the same raw snapshot. Missing or unranked values are marked unavailable rather than replaced with prior stats.

This project pulls fresh hiscores from the official OSRS hiscore API, compares the latest numbers against the previous saved snapshot, generates a polished daily progress email, and commits the newest raw stats JSON back into the repository for downstream use.

## What It Does

- Fetches official hiscore data for your account and tracked friends
- Saves the latest snapshot to [`data/last_stats.json`](./data/last_stats.json)
- Calculates day-over-day XP gains from the last saved snapshot
- Tracks all-99 XP progress and cumulative estimated training hours ahead/behind the December 31, 2027 deadline
- Tracks JorbisBTW through progressively higher base-level milestones without XP/hour assumptions
- Retains the nearly completed Base 92s (Runecrafting 90) checklist until completed
- Excludes Slayer-trained combat skills from timed pace calculations, while still showing their levels and XP
- Sends a styled HTML email summary
- Uses a GitHub Actions workflow to run automatically on a schedule

## Why This Repo Exists

This repository is the source of truth for the live OSRS snapshot data used elsewhere in your tooling, including the Lil Johnny app. The app consumes the committed JSON output directly from GitHub, so this repo acts as both:

- the daily tracker job
- the published data feed

## Repo Structure

```text
.
|-- .github/workflows/daily.yml   # Scheduled GitHub Actions workflow
|-- boss_progression.py           # Boss ladder, KC deltas, and weekly raid goal
|-- max_pace.py                   # Fixed-baseline cumulative maxing hours and email card
|-- ironman_milestones.py         # Automatic Ironman base-level ladder
|-- data/last_stats.json          # Latest saved hiscore snapshot
|-- main.py                       # Tracker, goal logic, and email generation
|-- run_current.py                # Current roster and goal configuration entrypoint
|-- requirements.txt              # Python dependencies
`-- README.md
```

## Data Output

The tracker writes a JSON file at [`data/last_stats.json`](./data/last_stats.json) with this high-level structure:

```json
{
  "_meta": {
    "bosses": {
      "jhusebachz": {
        "Vorkath": 407
      },
      "3Sixteen": {
        "Zulrah": 25
      }
    },
    "dailyBossActivity": {
      "byPlayer": {
        "jhusebachz": {
          "totalBossKcGained": 8,
          "bossGains": {
            "Vorkath": 5,
            "Phantom Muspah": 3
          }
        }
      },
      "topPlayers": [
        {
          "name": "jhusebachz",
          "totalBossKcGained": 8,
          "bossGains": {
            "Vorkath": 5,
            "Phantom Muspah": 3
          }
        }
      ]
    },
    "bossProgression": {
      "jhusebachz": {
        "triedCount": 37,
        "totalTracked": 71,
        "untriedCount": 34,
        "remainingByTier": {
          "Easy": [],
          "Medium": [{ "name": "Sarachnis", "kc": 0, "targetKc": 1, "tier": "Medium" }],
          "Hard": [],
          "Elite": [],
          "Master": [],
          "Grandmaster": []
        }
      }
    }
  },
  "jhusebachz": {
    "overall": {
      "rank": 0,
      "level": 0,
      "experience": 0
    },
    "attack": {
      "rank": 0,
      "level": 0,
      "experience": 0
    }
  }
}
```

Each tracked player includes:

- `overall`
- every tracked OSRS skill in hiscore order
- `rank`, `level`, and `experience` for each entry

Boss KC is fetched by activity name from Jagex's official JSON HiScores endpoint. `_meta.bosses` stores the latest configured boss KC for every tracked player, `_meta.dailyBossActivity` stores positive changes since the prior snapshot plus the already-ranked top three players, and `_meta.bossProgression` stores the primary account's complete tiered first-KC checklist. A missing previous boss snapshot establishes a baseline and never reports historical KC as a new gain.

## Automation

The active friend roster in `run_current.py` is `3Sixteen`, `beefmissle13`,
`kingxdabber`, `hedith`, `TooClose42`, `HB_Reborn`, `Dummyhead38`, `RebelMontana`,
`Kriid`, and `IronXDabber`. Their skill XP and boss KC snapshots feed both the daily email and
Lil Johnny. A new friend's first snapshot establishes a baseline; later runs
report gains from that baseline instead of counting historical progress as new.

The scheduled workflow lives in [`daily.yml`](./.github/workflows/daily.yml).

Current behavior:

- runs on a daily cron schedule
- can also be triggered manually with `workflow_dispatch`
- installs Python dependencies
- runs [`run_current.py`](./run_current.py)
- commits the updated snapshot JSON back into the repo

## Required Secrets

To run successfully in GitHub Actions, the repository needs these secrets:

- `EMAIL_USER`
- `EMAIL_PASS`

The script sends the daily report email using the configured mailbox.

## Local Setup

1. Clone the repo:

```bash
git clone https://github.com/jhusebachz/OSRS-Daily-Tracker.git
cd OSRS-Daily-Tracker
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

3. Set the required environment variables:

```powershell
$env:EMAIL_USER="you@example.com"
$env:EMAIL_PASS="your-app-password"
```

4. Run the tracker:

```bash
python run_current.py
```

## Personal Goals Tracked

The active main-account target is all 24 skills at 99 by **December 31, 2027**. The hours clock begins from the saved November 10, 2026 snapshot, with the baseline pinned in [`max_pace.py`](./max_pace.py) and the user's configurable XP/hour estimates in [`main.py`](./main.py). For example, completing 108 estimated training hours when the date calls for 100 means **8.0 cumulative hours ahead**, regardless of the last week's playing pace. Combat levels have no hourly timeline. The Base 92s checklist automatically disappears from the scheduled email once complete.

The Ironman goal automatically advances only after all 24 skill levels meet the current threshold. It does not project hours or deadlines. Missing skill data cannot be treated as a completed milestone.

## Notes

- Skills are fetched from the official Jagex lite HiScores feed; boss KC is fetched from the official JSON HiScores endpoint by activity name.
- The script intentionally spaces requests slightly to stay polite to the API.
- The repo stores the latest snapshot only, not a full history database.
- If a friend lookup fails, the script continues and reports the issue instead of failing the full run.

## Future Improvements

- store historical snapshots instead of only the latest file
- separate configuration from code
- support multiple tracker profiles
- publish a cleaner machine-readable report alongside the raw snapshot
- make email delivery optional so the repo can be used as a pure data pipeline

## License / Use

This is a personal automation project built around one player profile and a small comparison group. If you want to adapt it, update the tracked usernames, deadlines, and email settings before running it yourself.
