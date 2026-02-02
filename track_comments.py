import json
import logging
from src.utils import setup_logging
from src.analyzer import RedditAnalyzer
from src.date_strategies import LastWeekStrategy, LastDaysStrategy, ManualDateStrategy

# --- 🎛️ CONTROL PANEL ---
# Options: "last_week", "last_days", "manual"
SELECTED_MODE = "last_week"
# ------------------------

def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)

if __name__ == "__main__":
    setup_logging()
    logger = logging.getLogger(__name__)
    config = load_config()
    
    # 1. Select Strategy
    strategy = None
    params = config.get("strategy_params", {})

    if SELECTED_MODE == "last_week":
        strategy = LastWeekStrategy()
        
    elif SELECTED_MODE == "last_days":
        days = params.get("last_days", 7)
        strategy = LastDaysStrategy(days=days)
        
    elif SELECTED_MODE == "manual":
        m_range = params.get("manual_range", {})
        strategy = ManualDateStrategy(
            start_str=m_range.get("start_date"),
            end_str=m_range.get("end_date")
        )
    else:
        logger.error(f"Invalid Mode Selected: {SELECTED_MODE}")
        exit(1)

    # 2. Inject Strategy into Analyzer
    app = RedditAnalyzer(strategy=strategy, config=config)
    
    # 3. Run
    app.run()