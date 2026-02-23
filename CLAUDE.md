# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for package management.

```bash
# Install dependencies
uv sync

# Run comment tracker
uv run python track_comments.py

# Run post tracker
uv run python track_posts.py

# Run karma tracker
uv run python track_karma.py
```

## Configuration

Two configuration surfaces:

**`.env`** — credentials and targets (never commit):

- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` — PRAW credentials
- `WEBHOOK_URL` — n8n webhook for comment data
- `POSTS_WEBHOOK_URL` — n8n webhook for post data
- `KARMA_WEBHOOK_URL` — n8n webhook for karma stats
- `TARGET_PROFILES` — comma-separated Reddit usernames to track

**`config.json`** — runtime parameters:

- `safety_limit` — max comments fetched per user (default: 500)
- `deep_fetch_replies` — whether to call `praw_comment.refresh()` to count replies (slow; default: false)
- `strategy_params.last_days` — N for `LastDaysStrategy`
- `strategy_params.manual_range` — `start_date`/`end_date` strings for `ManualDateStrategy`

## Architecture

Three independent pipelines share the same `src/` library:

### Comment Tracker (`track_comments.py` → `src/analyzer.py`)

Fetches comments for each profile in `TARGET_PROFILES` within a date window, deduplicates against the seen-IDs store, wraps results in a standard envelope, saves to `output/` as JSON and CSV, then POSTs to `WEBHOOK_URL`.

Date windowing uses the **Strategy pattern** (`src/date_strategies.py`):

- `LastWeekStrategy` — previous Sun–Sat (hardcoded business rule, ignores config)
- `LastDaysStrategy(days=N)` — rolling last N days
- `ManualDateStrategy(start, end)` — fixed range from config

The active mode is set by the `SELECTED_MODE` constant at the top of `track_comments.py` (`"last_week"` | `"last_days"` | `"manual"`). `StrategyFactory` also exists in `date_strategies.py` but is not used by the current entry point.

### Post Tracker (`track_posts.py` → `src/post_analyzer.py`)

Fetches posts for each profile in `TARGET_PROFILES` within a date window, deduplicates against the seen-IDs store, wraps results in a standard envelope, saves to `output/` as JSON and CSV, then POSTs to `POSTS_WEBHOOK_URL`. Post fetch is capped at 20 per profile (hardcoded). Uses the same date strategies and `SELECTED_MODE` constant as the comment tracker.

### Karma Tracker (`track_karma.py` → `src/stats_tracker.py`)

Fetches account-level stats (total karma, comment karma, link/post karma, account age, mod status) for each profile, wraps in a standard envelope, saves to `output/karma_stats_YYYY-MM-DD.{json,csv}`, then POSTs to `KARMA_WEBHOOK_URL`.

### Shared utilities (`src/utils.py`)

- `setup_logging()` / `get_logger()` — call `setup_logging()` once at entry point
- `save_to_json()` / `save_to_csv()` — writes to `output/` directory (auto-created)
- `build_envelope(pipeline, data, profile_count, record_count=None, window=None)` — wraps a data array in the standard webhook envelope (`run_id`, `extracted_at`, `pipeline`, `window`, `profile_count`, `record_count`, `new_record_count`, `data`)
- `send_webhook(url, payload) -> bool` — HTTP POST with 30s timeout; returns `True` on success, `False` on any failure

### Deduplication (`src/deduplicator.py`)

`SeenStore` reads and writes `output/seen_ids.json` (gitignored), keyed by pipeline name. Call `filter_new(pipeline, records)` before dispatch to exclude already-sent IDs, then `mark_sent(pipeline, records)` after a confirmed successful webhook response. If the webhook fails, IDs are not persisted and the records will retry on the next run.

### Data models (`src/models.py`)

- `CommentSchema` — Pydantic model for a single comment. Fields: `id`, `author`, `body`, `subreddit`, `score`, `reply_count`, `is_top_level` (bool — `True` if direct reply to a post, `False` if nested reply to a comment), `created_utc`, `created_iso`, `permalink`
- `PostSchema` — Pydantic model for a single post. Fields: `id`, `author`, `title`, `subreddit`, `score`, `num_comments`, `post_type` (`"self"` or `"link"`), `created_utc`, `created_iso`, `permalink`
- `ProfileStats` — Pydantic model for per-user karma snapshot

All output files land in `output/` (gitignored).
