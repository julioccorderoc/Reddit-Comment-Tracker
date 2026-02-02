from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

class CommentSchema(BaseModel):
    id: str
    author: str
    body: str
    subreddit: str
    score: int
    reply_count: int = Field(default=0, description="Direct replies to this comment")
    created_utc: float
    created_iso: str
    permalink: str

    @field_validator('author', mode='before')
    def parse_author(cls, v):
        # PRAW returns a Redditor object, we need the string name
        return str(v) if v else "[deleted]"

    @field_validator('subreddit', mode='before')
    def parse_subreddit(cls, v):
        return str(v)

class ProfileStats(BaseModel):
    date: str
    handle: str
    total_karma: int
    comment_karma: int
    link_karma: int
    account_age_days: int
    is_mod: bool