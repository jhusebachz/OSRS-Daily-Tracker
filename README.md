# OSRS Daily Tracker

[![Daily OSRS Tracker](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml/badge.svg)](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml)

Automated Old School RuneScape progress tracking for `jhusebachz` and a small comparison group.

This project pulls fresh hiscores from the official OSRS hiscore API, compares the latest numbers against the previous saved snapshot, generates a polished daily progress email, and commits the newest raw stats JSON back into the repository for downstream use.

## What It Does

- Fetches official hiscore data for your account and tracked friends
- Saves the latest snapshot to [`data/last_stats.json`](./data/last_stats.json)
- Calculates day-over-day XP gains from the last saved snapshot
- Tracks progress against three personal goals:
  - Base 92s with Runecrafting at 90 by RuneFest
  - Total level `2250` by RuneFest
  - Max cape by your 33rd birthday
- Projects goal pace from expected hourly XP rates instead of sample daily gain assumptions
- Treats Slayer-trained combat skills as accounted-for zero-hour progress instead of manual-estimate gaps
- Uses only On track, Tight, and Off track pace statuses in the daily report
- Measures actual goal progress from a fixed `2026-03-25` baseline
- Draws pace-check bars so each goal shows actual progress versus where the account should be by today
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
and `Kriid`. Their skill XP and boss KC snapshots feed both the daily email and
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

The script currently measures progress against:

- `Base 92s` with `Runecrafting 90` by `2026-10-03`
- `Total level 2250` by `2026-10-03`
- `Max cape` by `2027-03-15`

Those values are defined directly in [`main.py`](./main.py), so the repo can be adjusted later if the goals or deadlines change.

The daily report now evaluates each goal in two ways:

- estimated grind hours remaining based on expected hourly XP rates, including Slayer-trained combat skills that are intentionally treated as zero-hour side progress
- actual progress since `2026-03-25` compared with the pace required to hit the deadline

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
