"""PlatformAdapter — unified interface for XHS/Douyin/Bilibili."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawComment:
    platform: str
    platform_comment_id: str
    platform_post_id: str
    platform_user_id: str
    platform_username: str
    content: str
    like_count: int = 0
    reply_count: int = 0
    parent_platform_comment_id: str | None = None
    is_from_creator: bool = False
    platform_created_at: datetime | None = None


class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def platform_name(self) -> str:
        ...

    @abstractmethod
    async def fetch_comments(self, post_url: str, cookie_data: dict | None = None) -> list[RawComment]:
        ...

    @abstractmethod
    async def send_reply(self, comment_id: str, content: str, cookie_data: dict) -> bool:
        ...

    async def dry_run_send(self, comment_id: str, content: str) -> dict:
        """Simulate send for testing (Harness Module 2)."""
        return {"status": "dry_run", "would_send_to": self.platform_name}
