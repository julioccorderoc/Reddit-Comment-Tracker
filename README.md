# Reddit Comment Tracker

Two independent pipelines for monitoring Reddit profiles: one tracks comments within a date window, the other snapshots account-level karma stats. Both save results locally and forward data to n8n webhooks.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- A Reddit app with API credentials ([create one here](https://www.reddit.com/prefs/apps))

## Setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Create a `.env` file (never commit this)

```env
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=your_user_agent_string
WEBHOOK_URL=https://your-n8n-instance/webhook/comments
KARMA_WEBHOOK_URL=https://your-n8n-instance/webhook/karma
TARGET_PROFILES=username1,username2,username3
```

### 3. (Optional) Edit `config.json` to tune runtime behavior

```json
{
  "strategy_params": {
    "last_days": 7,
    "manual_range": {
      "start_date": "2024-01-01",
      "end_date": "2024-01-31"
    }
  },
  "safety_limit": 500,
  "deep_fetch_replies": false
}
```

## Usage

### Comment Tracker

Fetches comments for each profile in `TARGET_PROFILES` within a configurable date window, saves JSON and CSV to `output/`, and POSTs to `WEBHOOK_URL`.

```bash
uv run python track_comments.py
```

Before running, set `SELECTED_MODE` at the top of `track_comments.py`:

| Mode | Behavior |
| --- | --- |
| `last_week` | Previous Sunday–Saturday (default) |
| `last_days` | Rolling last N days (uses `strategy_params.last_days`) |
| `manual` | Fixed range from `strategy_params.manual_range` |

### Karma Tracker

Fetches account-level stats (total karma, comment karma, post karma, account age, mod status) for each profile, saves to `output/karma_stats_YYYY-MM-DD.{json,csv}`, and POSTs to `KARMA_WEBHOOK_URL`.

```bash
uv run python track_karma.py
```

## Output

All files are written to `output/` (gitignored):

- `output/<username>_comments_<date>.json` / `.csv` — comment data per profile
- `output/karma_stats_<date>.json` / `.csv` — karma snapshot across all profiles

## Configuration Reference

### `.env`

| Variable | Description |
| --- | --- |
| `REDDIT_CLIENT_ID` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret |
| `REDDIT_USER_AGENT` | Reddit API user agent string |
| `WEBHOOK_URL` | n8n webhook endpoint for comment data |
| `KARMA_WEBHOOK_URL` | n8n webhook endpoint for karma stats |
| `TARGET_PROFILES` | Comma-separated Reddit usernames to track |

### `config.json`

| Key | Default | Description |
| --- | --- | --- |
| `safety_limit` | `500` | Max comments fetched per user |
| `deep_fetch_replies` | `false` | Call `refresh()` to count replies (slow) |
| `strategy_params.last_days` | `7` | Days to look back for `last_days` mode |
| `strategy_params.manual_range` | — | `start_date` / `end_date` for `manual` mode |
