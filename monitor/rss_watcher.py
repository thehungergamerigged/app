import asyncio
import logging
from typing import Awaitable, Callable

import aiohttp
import feedparser

from .dedup import DeduplicationStore

logger = logging.getLogger(__name__)

YOUTUBE_RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


class RSSWatcher:
    def __init__(
        self,
        channel_ids: list[str],
        seen_ids_file: str,
        on_new_video: Callable[[dict], Awaitable[None]],
    ):
        self.channel_ids = channel_ids
        self.dedup = DeduplicationStore(seen_ids_file)
        self.on_new_video = on_new_video

    async def _fetch_feed(
        self, session: aiohttp.ClientSession, channel_id: str
    ) -> list[dict]:
        url = YOUTUBE_RSS_TEMPLATE.format(channel_id=channel_id)
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                content = await resp.text()
        except Exception as exc:
            logger.error(f"Failed to fetch RSS for channel {channel_id}: {exc}")
            return []

        feed = feedparser.parse(content)
        videos: list[dict] = []
        for entry in feed.entries:
            video_id = entry.get("yt_videoid", "")
            if not video_id:
                link = entry.get("link", "")
                if "v=" in link:
                    video_id = link.split("v=")[-1].split("&")[0]
            if not video_id:
                continue
            videos.append(
                {
                    "video_id": video_id,
                    "title": entry.get("title", "No Title"),
                    "channel": feed.feed.get("title", channel_id),
                    "channel_id": channel_id,
                    "url": entry.get(
                        "link", f"https://www.youtube.com/watch?v={video_id}"
                    ),
                    "published_at": entry.get("published", ""),
                }
            )
        return videos

    async def poll_once(self) -> None:
        if not self.channel_ids:
            return
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *[self._fetch_feed(session, cid) for cid in self.channel_ids]
            )
        for videos in results:
            for video in videos:
                vid_id = video["video_id"]
                if not self.dedup.is_seen(vid_id):
                    self.dedup.mark_seen(vid_id)
                    logger.info(f"New video: {video['title']} ({vid_id})")
                    try:
                        await self.on_new_video(video)
                    except Exception as exc:
                        logger.error(f"Error processing video {vid_id}: {exc}")

    async def initialize_seen(self) -> None:
        """Seed seen IDs on first run so existing videos are not processed."""
        if self.dedup.count() > 0:
            logger.info(f"Dedup store has {self.dedup.count()} existing IDs — skipping seed.")
            return
        logger.info("First run: seeding existing video IDs from all feeds...")
        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(
                *[self._fetch_feed(session, cid) for cid in self.channel_ids]
            )
        for videos in results:
            for video in videos:
                self.dedup.mark_seen(video["video_id"])
        logger.info(f"Seeded {self.dedup.count()} video IDs — watching for new uploads.")
