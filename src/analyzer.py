import os
import praw
from datetime import datetime, timezone
from typing import List, Dict, Any
from dotenv import load_dotenv

from src.models import CommentSchema
from src.utils import get_logger, save_to_json, save_to_csv, send_webhook, build_envelope
from src.date_strategies import DateStrategy
from src.deduplicator import SeenStore

logger = get_logger(__name__)

class RedditAnalyzer:
    def __init__(self, strategy: DateStrategy, config: Dict[str, Any]):
        """
        :param strategy: An instance of a DateStrategy class.
        :param config: The loaded config dictionary.
        """
        load_dotenv()
        self.strategy = strategy
        self.config = config
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

    def _fetch_comments(self, username: str, start_dt: datetime, end_dt: datetime) -> List[CommentSchema]:
        safety_limit = self.config.get("safety_limit", 500)
        deep_fetch = self.config.get("deep_fetch_replies", False)
        collected = []

        try:
            user = self.reddit.redditor(username)
            for praw_comment in user.comments.new(limit=safety_limit):
                comment_date = datetime.fromtimestamp(praw_comment.created_utc, tz=timezone.utc)

                if comment_date > end_dt: continue
                if comment_date < start_dt: break

                reply_count = 0
                if deep_fetch:
                    try:
                        praw_comment.refresh()
                        reply_count = len(praw_comment.replies)
                    except: pass

                collected.append(CommentSchema(
                    id=praw_comment.id,
                    author=username,
                    body=praw_comment.body,
                    subreddit=str(praw_comment.subreddit),
                    score=praw_comment.score,
                    reply_count=reply_count,
                    is_top_level=praw_comment.parent_id.startswith("t3_"),
                    created_utc=praw_comment.created_utc,
                    created_iso=comment_date.isoformat(),
                    permalink=f"https://reddit.com{praw_comment.permalink}"
                ))
        except Exception as e:
            logger.error(f"Failed to fetch {username}: {e}")
        
        return collected

    def run(self):
        logger.info("Starting Reddit Analysis Job...")
        
        # 1. Execute Strategy
        start_dt, end_dt = self.strategy.get_window()
        logger.info(f"Time Window: {start_dt.date()} to {end_dt.date()}")

        # 2. Load Profiles from ENV
        profiles_env = os.getenv("TARGET_PROFILES", "")
        if not profiles_env:
            logger.warning("No TARGET_PROFILES found in .env")
            return
        
        # Convert "a, b, c" -> ["a", "b", "c"]
        profiles = [p.strip() for p in profiles_env.split(",") if p.strip()]
        
        all_comments_data = []

        # 3. Process
        for profile in profiles:
            logger.info(f"Analyzing: {profile}")
            comments = self._fetch_comments(profile, start_dt, end_dt)
            
            # CHANGED: Flatten the structure immediately
            for c in comments:
                all_comments_data.append(c.model_dump())

        # 4. Save
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        save_to_json(all_comments_data, f"reddit_data_{timestamp}.json")
        save_to_csv(all_comments_data, f"reddit_data_{timestamp}.csv")

        if os.getenv("WEBHOOK_URL"):
            store = SeenStore()
            new_records = store.filter_new("comments", all_comments_data)
            envelope = build_envelope(
                pipeline="comments",
                data=new_records,
                profile_count=len(profiles),
                record_count=len(all_comments_data),
                window={
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            )
            if send_webhook(os.getenv("WEBHOOK_URL"), envelope):
                store.mark_sent("comments", new_records)
        
        logger.info("Job Complete.")