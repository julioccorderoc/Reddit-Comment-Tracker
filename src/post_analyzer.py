import os
import praw
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv

from src.models import PostSchema
from src.utils import get_logger, save_to_json, save_to_csv, send_webhook, build_envelope
from src.date_strategies import DateStrategy
from src.deduplicator import SeenStore

logger = get_logger(__name__)

POST_FETCH_LIMIT = 20


class PostAnalyzer:
    def __init__(self, strategy: DateStrategy):
        load_dotenv()
        self.strategy = strategy
        self.reddit = self._init_reddit()

    def _init_reddit(self):
        if not os.getenv("REDDIT_CLIENT_ID"):
            raise EnvironmentError("Missing REDDIT_CLIENT_ID in .env")
        return praw.Reddit(
            client_id=os.getenv("REDDIT_CLIENT_ID"),
            client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            user_agent=os.getenv("REDDIT_USER_AGENT"),
            check_for_async=False
        )

    def _fetch_posts(self, username: str, start_dt: datetime, end_dt: datetime) -> List[PostSchema]:
        collected = []
        try:
            user = self.reddit.redditor(username)
            for submission in user.submissions.new(limit=POST_FETCH_LIMIT):
                post_date = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

                if post_date > end_dt:
                    continue
                if post_date < start_dt:
                    break

                collected.append(PostSchema(
                    id=submission.id,
                    author=username,
                    title=submission.title,
                    subreddit=str(submission.subreddit),
                    score=submission.score,
                    num_comments=submission.num_comments,
                    post_type="self" if submission.is_self else "link",
                    created_utc=submission.created_utc,
                    created_iso=post_date.isoformat(),
                    permalink=f"https://reddit.com{submission.permalink}",
                ))
        except Exception as e:
            logger.error(f"Failed to fetch posts for {username}: {e}")
        return collected

    def run(self):
        logger.info("Starting Post Tracker Job...")

        # 1. Execute Strategy
        start_dt, end_dt = self.strategy.get_window()
        logger.info(f"Time Window: {start_dt.date()} to {end_dt.date()}")

        # 2. Load Profiles from ENV
        profiles_env = os.getenv("TARGET_PROFILES", "")
        if not profiles_env:
            logger.warning("No TARGET_PROFILES found in .env")
            return

        profiles = [p.strip() for p in profiles_env.split(",") if p.strip()]
        all_posts_data: List[Dict[str, Any]] = []

        # 3. Fetch
        for profile in profiles:
            logger.info(f"Fetching posts: {profile}")
            posts = self._fetch_posts(profile, start_dt, end_dt)
            for post in posts:
                all_posts_data.append(post.model_dump())

        # 4. Save
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        save_to_json(all_posts_data, f"reddit_posts_{timestamp}.json")
        save_to_csv(all_posts_data, f"reddit_posts_{timestamp}.csv")

        # 5. Deduplicate and dispatch
        if os.getenv("POSTS_WEBHOOK_URL"):
            store = SeenStore()
            new_records = store.filter_new("posts", all_posts_data)
            envelope = build_envelope(
                pipeline="posts",
                data=new_records,
                profile_count=len(profiles),
                record_count=len(all_posts_data),
                window={
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
            if send_webhook(os.getenv("POSTS_WEBHOOK_URL"), envelope):
                store.mark_sent("posts", new_records)

        logger.info("Post Tracking Complete.")
