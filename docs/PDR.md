# Product Design Review — Reddit Activity Tracker

**Status:** Draft
**Date:** 2026-02-23
**Author:** NCL Team

---

## 1. Background & Context

As part of the company's AEO/SEO strategy, we maintain a presence across multiple Reddit communities where we educate and help users on topics related to our ecommerce business. This effort is a **quarterly rock**, which means it needs measurable tracking to report progress, validate impact, and guide future content decisions.

To satisfy this requirement, a lightweight Reddit tracker was built using PRAW (Python Reddit API Wrapper) and n8n webhooks. It fetches comment and karma data for a set of target Reddit accounts and forwards the results downstream for analysis.

---

## 2. Problem Statement

The current tool only tracks **comments** and **karma snapshots**. This leaves a gap because:

1. **Posts are not tracked at all.** Our accounts also create posts (not just comments), and those interactions are equally important for measuring community engagement.
2. **Duplicate data is sent on repeated runs.** Running the tracker twice within the same date window re-sends all the same records with no way to distinguish them downstream.
3. **Comment context is minimal.** It's not possible to tell whether a comment is a direct reply to a post or a nested reply to another user — which affects how the engagement is interpreted.
4. **Webhook payloads carry no metadata.** Downstream workflows (n8n) receive a raw array with no run identifier, timestamp, or record count, making it hard to correlate payloads to runs or detect data gaps.

---

## 3. Current Capabilities

| Pipeline | What it collects | Granularity |
|---|---|---|
| `track_comments.py` | Comments within a configurable date window | Per comment (id, author, body, subreddit, score, reply\_count, permalink, timestamps) |
| `track_karma.py` | Account-level stats | One snapshot per profile per run (total\_karma, comment\_karma, link\_karma, account\_age\_days, is\_mod) |

**Date windowing** is handled by a Strategy pattern: `LastWeekStrategy`, `LastDaysStrategy`, and `ManualDateStrategy`. The active strategy is set by a constant in `track_comments.py`.

All output is saved to `output/` as JSON and CSV, then POSTed to a configured n8n webhook.

---

## 4. Proposed Features

### 4.1 Post Tracking

**Why:** Posts are the other primary activity type on Reddit. They carry title, score, comment volume, and subreddit — all directly relevant to measuring engagement quality and topic resonance.

**Scope:** High-level interaction data only. We don't need body text or media content — just enough to answer "did we post, where, and how did it land?"

**Proposed `PostSchema`:**

| Field | Type | Source | Notes |
|---|---|---|---|
| `id` | string | `submission.id` | Reddit post ID |
| `author` | string | `submission.author` | Username |
| `title` | string | `submission.title` | Post title |
| `subreddit` | string | `submission.subreddit` | Community name |
| `score` | int | `submission.score` | Net upvotes |
| `num_comments` | int | `submission.num_comments` | Total comment count on the post |
| `post_type` | string | derived | `"link"` if `submission.is_self == False`, else `"self"` |
| `created_utc` | float | `submission.created_utc` | Unix timestamp |
| `created_iso` | string | derived | ISO 8601 UTC string |
| `permalink` | string | `submission.permalink` | Full Reddit URL |

**Implementation path:**
- Add `PostSchema` to `src/models.py`
- Create `src/post_analyzer.py` mirroring the structure of `src/analyzer.py`, using `redditor.submissions.new(limit=N)` instead of `redditor.comments.new()`
- Create `track_posts.py` entry point, reusing the same date strategy and config structure
- Uses a dedicated `POSTS_WEBHOOK_URL` env variable (separate from `WEBHOOK_URL`)

**Acceptance criteria:**
- Running `uv run python track_posts.py` fetches posts for all `TARGET_PROFILES` within the active date window
- Output is saved to `output/reddit_posts_YYYY-MM-DD_HHMMSS.{json,csv}`
- Payload is sent to the configured webhook
- The same `safety_limit` from `config.json` applies

---

### 4.2 Deduplication

**Why:** The tracker is run on a schedule. Without deduplication, records sent in a previous run are re-sent on the next run if they fall within the same date window. This inflates counts and pollutes downstream reporting.

**Proposed approach:** A local state file at `output/seen_ids.json` tracks all comment and post IDs that have already been dispatched to the webhook. Before sending, the tracker filters out any records whose ID is already in the state file. After a successful webhook dispatch, the new IDs are appended.

**State file structure:**
```json
{
  "comments": ["abc123", "def456"],
  "posts": ["xyz789"]
}
```

**Behavior:**
- State is checked before webhook dispatch (not before saving to local JSON/CSV — local files always get the full result)
- If the webhook call fails, the IDs are **not** added to the state file (records will retry on the next run)
- State file is gitignored alongside the rest of `output/`

**Acceptance criteria:**
- Running the tracker twice in the same date window sends new records only on the second run
- A failed webhook does not mark records as seen
- State file is created automatically if it doesn't exist

---

### 4.3 Comment Thread Depth

**Why:** Knowing whether a comment is a direct reply to a post (top-level) or a nested reply to another user affects how we interpret the engagement. A top-level comment is a standalone contribution; a nested reply is a conversation response.

**PRAW limitation:** True depth (e.g., depth = 3) would require traversing the parent chain upward, which means one additional API call per comment. This is too slow and expensive for a batch tracker.

**Proposed approach:** Add a single boolean field `is_top_level` to `CommentSchema`, derived cheaply from the `parent_id` attribute that PRAW already returns in the comment object.

- `parent_id` starts with `t3_` → comment is a direct reply to a post → `is_top_level = True`
- `parent_id` starts with `t1_` → comment is a reply to another comment → `is_top_level = False`

No additional API calls required.

**Updated `CommentSchema`:**

| Field | Type | Notes |
|---|---|---|
| (existing fields) | | No changes |
| `is_top_level` | bool | `True` if replying to a post, `False` if replying to a comment |

**What this enables downstream:**
- Segment comments by contribution type (standalone vs conversation)
- Measure what share of activity is direct community engagement vs follow-up replies

**Acceptance criteria:**
- `is_top_level` is present on every `CommentSchema` object
- Derived from `parent_id` with no extra API calls
- Correctly reflects top-level vs nested position in thread

---

### 4.4 Webhook Envelope

**Why:** The current payload is a raw JSON array. Downstream n8n workflows cannot tell which run a payload belongs to, how many records to expect, or what time window was used. Adding an envelope makes every payload self-describing.

**Proposed envelope structure:**

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
|---|---|
| `run_id` | UUID4, generated fresh per run |
| `extracted_at` | ISO timestamp of when the job ran |
| `pipeline` | `"comments"`, `"posts"`, or `"karma"` |
| `window` | Only present on comment and post pipelines; omitted for karma |
| `profile_count` | Number of profiles processed |
| `record_count` | Total records collected (before dedup filter) |
| `new_record_count` | Records actually sent (after dedup filter); equal to `record_count` if dedup is not enabled |
| `data` | Array of records (existing structure unchanged) |

**Note:** The karma pipeline wraps its array in the same envelope, using `"pipeline": "karma"` and omitting `window`.

**Acceptance criteria:**
- Every webhook call is wrapped in this envelope
- `record_count` and `new_record_count` are accurate
- Existing `data` array structure is unchanged (no breaking change for n8n)

---

## 5. Out of Scope

The following were considered but are not in scope for this iteration:

- **Real-time or streaming tracking** — batch runs on a schedule are sufficient
- **Edit/deletion detection** — PRAW only returns the current state of a comment; no diff tracking
- **True thread depth** — traversing parent chains requires per-comment API calls; `is_top_level` is sufficient for the reporting use case
- **Parent post body in comment records** — the `permalink` field already points to the thread; fetching and storing post content would be redundant
- **Moderation action tracking** — removed/locked comments, mod log entries
- **Subreddit aggregate rollups** — computing per-subreddit stats is a downstream/n8n concern, not a collection concern
- **NLP or sentiment analysis**

---

## 6. Success Criteria

| Metric | Target |
|---|---|
| Posts tracked | Posts for all `TARGET_PROFILES` collected within the active date window |
| Deduplication | Zero duplicate records sent across consecutive runs covering the same window |
| Thread depth | `is_top_level` present and accurate on 100% of comment records |
| Webhook envelope | Every POST includes `run_id`, `extracted_at`, `record_count`, and `new_record_count` |
| No regressions | Existing comment and karma pipelines continue to function without modification |

---

## 7. Open Questions

| # | Question | Owner |
|---|---|---|
| 1 | ~~Should posts share the existing `WEBHOOK_URL` or use a dedicated `POSTS_WEBHOOK_URL`?~~ **Decided:** dedicated `POSTS_WEBHOOK_URL`. | — |
| 2 | ~~Should `seen_ids.json` be reset on a cadence (e.g., monthly) to avoid unbounded growth?~~ **Decided:** no reset, grow indefinitely for simplicity. | — |
| 3 | ~~What is the `safety_limit` for posts?~~ **Decided:** `20` posts per profile. | — |
