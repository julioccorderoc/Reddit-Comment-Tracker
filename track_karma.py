from src.utils import setup_logging
from src.stats_tracker import RedditStatsTracker

if __name__ == "__main__":
    setup_logging()
    
    tracker = RedditStatsTracker()
    tracker.run()