from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone, time
from typing import Tuple, Dict, Any

# --- Abstract Base Class ---
class DateStrategy(ABC):
    @abstractmethod
    def get_window(self) -> Tuple[datetime, datetime]:
        """Returns (start_date, end_date) in UTC."""
        pass

# --- Concrete Strategies ---

class LastWeekStrategy(DateStrategy):
    """
    Strict Business Rule: previous Sunday to previous Saturday.
    Ignores config parameters entirely.
    """
    def get_window(self) -> Tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        today = now.date()
        
        # Calculate days to subtract to reach the most recent Sunday (Start of current week)
        # Python weekday: Mon=0 ... Sun=6
        # If today is Thu(3) -> (3+1)%7 = 4 days ago was Sunday.
        days_to_current_sunday = (today.weekday() + 1) % 7
        current_week_sunday = today - timedelta(days=days_to_current_sunday)
        
        # We want the FULL PREVIOUS week.
        target_start = current_week_sunday - timedelta(days=7) # Previous Sunday
        target_end = target_start + timedelta(days=6)          # Previous Saturday
        
        # Convert to UTC Datetime
        start_dt = datetime.combine(target_start, time.min).replace(tzinfo=timezone.utc)
        end_dt = datetime.combine(target_end, time.max).replace(tzinfo=timezone.utc)
        
        return start_dt, end_dt

class LastDaysStrategy(DateStrategy):
    """
    Rolling window: Last N days including today.
    """
    def __init__(self, days: int = 7):
        self.days = days

    def get_window(self) -> Tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=self.days)
        # Start at 00:00:00 of the start day
        start_dt = datetime.combine(start_date.date(), time.min).replace(tzinfo=timezone.utc)
        return start_dt, now

class ManualDateStrategy(DateStrategy):
    """
    Specific fixed range defined in config.
    """
    def __init__(self, start_str: str, end_str: str = "today"):
        self.start_str = start_str
        self.end_str = end_str

    def get_window(self) -> Tuple[datetime, datetime]:
        start_dt = datetime.strptime(self.start_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        if not self.end_str or self.end_str.lower() == "today":
            end_dt = datetime.now(timezone.utc)
        else:
            parsed_end = datetime.strptime(self.end_str, "%Y-%m-%d")
            end_dt = datetime.combine(parsed_end.date(), time.max).replace(tzinfo=timezone.utc)
            
        return start_dt, end_dt

# --- The Factory ---
class StrategyFactory:
    @staticmethod
    def create(strategy_name: str, config_params: Dict[str, Any]) -> DateStrategy:
        """
        Instantiates the correct strategy based on the name and passes 
        relevant config parameters if needed.
        """
        if strategy_name == "last_week":
            return LastWeekStrategy()
            
        elif strategy_name == "last_days":
            # Extract 'days' from the 'last_days' section of config, default to 7
            days = config_params.get("last_days", {}).get("days", 7)
            return LastDaysStrategy(days=days)
            
        elif strategy_name == "manual":
            manual_cfg = config_params.get("manual", {})
            return ManualDateStrategy(
                start_str=manual_cfg.get("start_date"),
                end_str=manual_cfg.get("end_date")
            )
        
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")