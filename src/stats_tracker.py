import os
import praw
from datetime import datetime, timezone
from typing import List
from dotenv import load_dotenv

from src.models import ProfileStats
from src.utils import get_logger, save_to_json, save_to_csv, send_webhook, build_envelope

logger = get_logger(__name__)

class RedditStatsTracker:
    def __init__(self):
        load_dotenv()
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

    def _fetch_stats(self, username: str) -> ProfileStats:
        try:
            user = self.reddit.redditor(username)
            # Trigger lazy load
            _ = user.id 
            
            # Calculate Account Age
            created_dt = datetime.fromtimestamp(user.created_utc, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            age_days = (now - created_dt).days

            return ProfileStats(
                date=datetime.now().strftime("%Y-%m-%d"),
                handle=username,
                total_karma=user.total_karma,
                comment_karma=user.comment_karma,
                link_karma=user.link_karma, # 'link_karma' is Post Karma
                account_age_days=age_days,
                is_mod=user.is_mod
            )
        except Exception as e:
            logger.error(f"Failed to fetch stats for {username}: {e}")
            return None

    def run(self):
        logger.info("Starting Karma Tracker Job...")
        
        # 1. Load Profiles
        profiles_env = os.getenv("TARGET_PROFILES", "")
        if not profiles_env:
            logger.warning("No TARGET_PROFILES found in .env")
            return
        
        profiles = [p.strip() for p in profiles_env.split(",") if p.strip()]
        collected_stats = []

        # 2. Fetch Data
        for profile in profiles:
            logger.info(f"Fetching stats: {profile}")
            stats = self._fetch_stats(profile)
            if stats:
                collected_stats.append(stats.model_dump())

        # 3. Save & Send
        if collected_stats:
            timestamp = datetime.now().strftime("%Y-%m-%d")
            
            # Save Local
            save_to_json(collected_stats, f"karma_stats_{timestamp}.json")
            save_to_csv(collected_stats, f"karma_stats_{timestamp}.csv")
            
            # Send Webhook
            COMMENT_WEBHOOK_URL = os.getenv("KARMA_WEBHOOK_URL")
            if COMMENT_WEBHOOK_URL:
                envelope = build_envelope(
                    pipeline="karma",
                    data=collected_stats,
                    profile_count=len(profiles),
                )
                send_webhook(COMMENT_WEBHOOK_URL, envelope)
            else:
                logger.info("Skipping Webhook (KARMA_WEBHOOK_URL not set)")

        logger.info("Karma Tracking Complete.")