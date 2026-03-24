# OSRS Daily Tracker

[![Daily OSRS Tracker](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml/badge.svg)](https://github.com/jhusebachz/OSRS-Daily-Tracker/actions/workflows/daily.yml)

Automated Old School RuneScape progress tracking for `jhusebachz` and a small comparison group.

This project pulls fresh hiscores from the official OSRS hiscore API, compares the latest numbers against the previous saved snapshot, generates a polished daily progress email, and commits the newest raw stats JSON back into the repository for downstream use.

## What It Does

- Fetches official hiscore data for your account and tracked friends
- Saves the latest snapshot to [`data/last_stats.json`](./data/last_stats.json)
- Calculates day-over-day XP gains from the last saved snapshot
- Tracks progress against three personal goals:
  - Base 90 all skills
  - Total level `2250` by RuneFest
  - Max cape by your 33rd birthday
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
|-- data/last_stats.json          # Latest saved hiscore snapshot
|-- main.py                       # Tracker, goal logic, and email generation
|-- requirements.txt              # Python dependencies
`-- README.md
```

## Data Output

The tracker writes a JSON file at [`data/last_stats.json`](./data/last_stats.json) with this high-level structure:

```json
{
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

## Automation

The scheduled workflow lives in [`daily.yml`](./.github/workflows/daily.yml).

Current behavior:

- runs on a daily cron schedule
- can also be triggered manually with `workflow_dispatch`
- installs Python dependencies
- runs [`main.py`](./main.py)
- commits the updated snapshot JSON back into the repo

## Required Secrets

To run successfully in GitHub Actions, the repository needs these secrets:

- `EMAIL_USER`
- `EMAIL_PASS`
- `GROQ_API_KEY`

The script sends the daily report email using the configured mailbox and uses Groq for the coaching summary section.

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
$env:GROQ_API_KEY="your-key"
```

4. Run the tracker:

```bash
python main.py
```

## Personal Goals Tracked

The script currently measures progress against:

- `Base 90 all skills` by `2026-05-22`
- `Total level 2250` by `2026-10-03`
- `Max cape` by `2027-03-15`

Those values are defined directly in [`main.py`](./main.py), so the repo can be adjusted later if the goals or deadlines change.

## Notes

- Hiscores are fetched from the official Jagex lite hiscore endpoint.
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
