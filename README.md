# Reddit Comment Tracker

Three independent pipelines for monitoring Reddit profiles: comment tracking, post tracking, and account-level karma snapshots. All save results locally and forward data to n8n webhooks inside a standard envelope that includes run metadata and deduplication counts.

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
POSTS_WEBHOOK_URL=https://your-n8n-instance/webhook/posts
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

Fetches comments for each profile in `TARGET_PROFILES` within a configurable date window, deduplicates against previously sent records, saves JSON and CSV to `output/`, and POSTs to `WEBHOOK_URL`.

```bash
uv run python track_comments.py
```

### Post Tracker

Fetches posts for each profile in `TARGET_PROFILES` within a configurable date window (capped at 20 per profile), deduplicates against previously sent records, saves JSON and CSV to `output/`, and POSTs to `POSTS_WEBHOOK_URL`.

```bash
uv run python track_posts.py
```

Both comment and post trackers share the same date mode setting. Before running either, set `SELECTED_MODE` at the top of the respective entry point:

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

## Webhook Payload

Every webhook call is wrapped in a standard envelope:

```json
{
  "run_id": "a3f2c1d4-...",
  "extracted_at": "2026-02-23T09:00:00+00:00",
  "pipeline": "comments",
  "window": {
    "start": "2026-02-16T00:00:00+00:00",
    "end": "2026-02-22T23:59:59+00:00"
  },
  "profile_count": 3,
  "record_count": 47,
  "new_record_count": 12,
  "data": [ ... ]
}
```

| Field | Notes |
| --- | --- |
| `run_id` | UUID4, unique per run |
| `extracted_at` | ISO UTC timestamp of when the job ran |
| `pipeline` | `"comments"`, `"posts"`, or `"karma"` |
| `window` | Date range used — present on comment and post payloads, absent on karma |
| `record_count` | Total records collected this run |
| `new_record_count` | Records actually sent (after deduplication filter) |
| `data` | Array of records |

### Comment record fields

| Field | Description |
| --- | --- |
| `id` | Reddit comment ID |
| `author` | Username |
| `body` | Comment text |
| `subreddit` | Community name |
| `score` | Net upvotes |
| `reply_count` | Direct replies (0 unless `deep_fetch_replies: true`) |
| `is_top_level` | `true` if direct reply to a post; `false` if nested reply to a comment |
| `created_utc` | Unix timestamp |
| `created_iso` | ISO 8601 UTC string |
| `permalink` | Full Reddit URL |

### Post record fields

| Field | Description |
| --- | --- |
| `id` | Reddit post ID |
| `author` | Username |
| `title` | Post title |
| `subreddit` | Community name |
| `score` | Net upvotes |
| `num_comments` | Total comment count on the post |
| `post_type` | `"self"` for text posts, `"link"` for link posts |
| `created_utc` | Unix timestamp |
| `created_iso` | ISO 8601 UTC string |
| `permalink` | Full Reddit URL |

### Karma record fields

| Field | Description |
| --- | --- |
| `date` | Report date (YYYY-MM-DD) |
| `handle` | Username |
| `total_karma` | Sum of comment + link karma |
| `comment_karma` | Karma from comments |
| `link_karma` | Karma from posts |
| `account_age_days` | Days since account creation |
| `is_mod` | Whether the user is a moderator |

## Deduplication

The comment and post trackers share a state file at `output/seen_ids.json` that records which IDs have already been dispatched, keyed by pipeline. On each run, only new records are sent to the webhook. If the webhook call fails, IDs are not persisted — those records will be retried on the next run.

The state file grows indefinitely and is gitignored alongside the rest of `output/`.

## Output

All files are written to `output/` (gitignored):

| File | Description |
| --- | --- |
| `reddit_data_YYYY-MM-DD_HHMMSS.json` / `.csv` | Comment data for the run |
| `reddit_posts_YYYY-MM-DD_HHMMSS.json` / `.csv` | Post data for the run |
| `karma_stats_YYYY-MM-DD.json` / `.csv` | Karma snapshot across all profiles |
| `seen_ids.json` | Deduplication state (auto-created, never reset) |

## Configuration Reference

### `.env`

| Variable | Description |
| --- | --- |
| `REDDIT_CLIENT_ID` | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit app client secret |
| `REDDIT_USER_AGENT` | Reddit API user agent string |
| `WEBHOOK_URL` | n8n webhook endpoint for comment data |
| `POSTS_WEBHOOK_URL` | n8n webhook endpoint for post data |
| `KARMA_WEBHOOK_URL` | n8n webhook endpoint for karma stats |
| `TARGET_PROFILES` | Comma-separated Reddit usernames to track |

### `config.json`

| Key | Default | Description |
| --- | --- | --- |
| `safety_limit` | `500` | Max comments fetched per user |
| `deep_fetch_replies` | `false` | Call `refresh()` to count replies (slow) |
| `strategy_params.last_days` | `7` | Days to look back for `last_days` mode |
| `strategy_params.manual_range` | — | `start_date` / `end_date` for `manual` mode |
