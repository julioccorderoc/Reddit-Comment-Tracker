from pydantic import BaseModel, Field, field_validator

class CommentSchema(BaseModel):
    id: str
    author: str
    body: str
    subreddit: str
    score: int
    reply_count: int = Field(default=0, description="Direct replies to this comment")
    is_top_level: bool = Field(description="True if direct reply to a post (t3_), False if nested reply to a comment (t1_)")
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

class PostSchema(BaseModel):
    id: str
    author: str
    title: str
    subreddit: str
    score: int
    num_comments: int
    post_type: str = Field(description='"self" for text posts, "link" for link posts')
    created_utc: float
    created_iso: str
    permalink: str

    @field_validator('author', mode='before')
    def parse_author(cls, v):
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