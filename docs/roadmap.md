# ROADMAP

* **Version:** 0.2.0
* **Last Updated:** 2026-02-23
* **Primary Human Owner:** NCL Team

## Operating Rules for the Planner Agent

1. You may only move one Epic to `Active` at a time.
2. Before marking an Epic `Complete`, you must verify all its Verification Criteria are met in the main branch.
3. Do not activate Epics that depend on incomplete prerequisites.

## Epic Ledger

### EPIC-001 — Webhook Envelope

* **Status:** Complete
* **Dependencies:** None
* **Business Objective:** Give every webhook payload a self-describing wrapper so downstream n8n workflows can correlate payloads to specific runs, detect data gaps, and track deduplication results without relying on external metadata.
* **Technical Boundary:** Modify `src/utils.py → send_webhook()` to accept an envelope dict and wrap the data array before dispatch. Update `src/analyzer.py` and `src/stats_tracker.py` to build and pass the envelope. No changes to `CommentSchema` or `ProfileStats`. Envelope fields: `run_id` (UUID4), `extracted_at` (ISO UTC), `pipeline`, `window` (comments/posts only), `profile_count`, `record_count`, `new_record_count`, `data`.
* **Verification Criteria (Definition of Done):**
  * Every webhook POST body is a JSON object (not a raw array) containing all envelope fields.
  * `pipeline` correctly identifies `"comments"` or `"karma"` per call.
  * `window` is present and accurate on comment payloads; absent on karma payloads.
  * `record_count` equals the number of items in `data`.
  * `new_record_count` equals `record_count` (dedup not yet implemented; field reserved for EPIC-003).
  * Existing comment and karma pipelines continue to function end-to-end.

---

### EPIC-002 — Comment Thread Depth

* **Status:** Complete
* **Dependencies:** None
* **Business Objective:** Allow analysts to distinguish between standalone community contributions (top-level comments) and conversational replies, improving the quality of engagement reporting.
* **Technical Boundary:** Add `is_top_level: bool` field to `CommentSchema` in `src/models.py`. Populate it in `src/analyzer.py → _fetch_comments()` by inspecting `praw_comment.parent_id` prefix (`t3_` = top-level, `t1_` = nested reply). No additional API calls.
* **Verification Criteria (Definition of Done):**
  * `is_top_level` is present on every record in the comment JSON/CSV output.
  * A comment replying directly to a post has `is_top_level: true`.
  * A comment replying to another comment has `is_top_level: false`.
  * No increase in PRAW API call count per comment (derived from existing `parent_id` attribute).

---

### EPIC-003 — Deduplication

* **Status:** Complete
* **Dependencies:** EPIC-001
* **Business Objective:** Ensure that consecutive tracker runs covering overlapping date windows do not re-send records already dispatched, keeping downstream counts and dashboards accurate.
* **Technical Boundary:** Create `src/deduplicator.py` with a `SeenStore` class that reads/writes `output/seen_ids.json`. Keyed by pipeline (`"comments"`, `"posts"`). Integrate into `src/analyzer.py` and (later) `src/post_analyzer.py`: filter collected records against the store before dispatch, then write new IDs to the store only after a successful webhook response. Update the envelope's `new_record_count` to reflect the post-filter count. State file is gitignored.
* **Verification Criteria (Definition of Done):**
  * Running the comment tracker twice in the same date window sends zero duplicate records on the second run.
  * `record_count` reflects total records collected; `new_record_count` reflects records actually sent.
  * A failed webhook call does not add IDs to the state file (records retry on next run).
  * `output/seen_ids.json` is created automatically if it does not exist.
  * `output/seen_ids.json` is listed in `.gitignore`.

---

### EPIC-004 — Post Tracking

* **Status:** Complete
* **Dependencies:** EPIC-001, EPIC-003
* **Business Objective:** Capture post-level activity for each tracked account so the team can measure both comment and post contributions to target communities, supporting complete quarterly rock reporting.
* **Technical Boundary:** Add `PostSchema` to `src/models.py` (fields: `id`, `author`, `title`, `subreddit`, `score`, `num_comments`, `post_type`, `created_utc`, `created_iso`, `permalink`). Create `src/post_analyzer.py` mirroring `src/analyzer.py`, using `redditor.submissions.new()`. Create `track_posts.py` entry point reusing existing date strategy and config. Add `POSTS_WEBHOOK_URL` to `.env`. Apply the envelope (EPIC-001) and dedup store (EPIC-003) from day one. Output saved to `output/reddit_posts_YYYY-MM-DD_HHMMSS.{json,csv}`.
* **Verification Criteria (Definition of Done):**
  * `uv run python track_posts.py` fetches posts for all `TARGET_PROFILES` within the active date window.
  * Output files are written to `output/` with the correct naming convention.
  * Payload is dispatched to `POSTS_WEBHOOK_URL` (separate from `WEBHOOK_URL`).
  * Envelope `pipeline` field reads `"posts"`.
  * Deduplication applies: consecutive runs in the same window send only new posts.
  * Post fetch is capped at `20` per profile (hardcoded, separate from the comment `safety_limit`).
  * Existing comment and karma pipelines are unaffected.
