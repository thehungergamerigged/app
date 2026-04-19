"""
TruthStrike — YouTube misinformation monitor.
Runs RSS watcher, triple-AI analysis, Telegram alerts, Airtable storage,
and a FastAPI dashboard all in a single asyncio event loop.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from analysis import claude_agent, gemini_agent, gpt_agent
from analysis.synthesizer import synthesize
from analysis.transcript_fetcher import fetch_transcript
from dashboard.app import broadcast_event, create_app
from monitor.rss_watcher import RSSWatcher
from notifications.telegram_bot import TelegramNotifier
from storage.airtable_client import AirtableClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Module-level singletons (set in main())
_airtable: AirtableClient | None = None
_notifier: TelegramNotifier | None = None


async def process_video(video: dict) -> None:
    logger.info(f"Analyzing: {video['title']} ({video['video_id']})")

    transcript = await fetch_transcript(video["video_id"])
    if transcript:
        video = {**video, "transcript": transcript}
        logger.info(f"  → Transcript available ({len(transcript)} chars)")
    else:
        logger.info("  → No transcript; falling back to title-only analysis")

    gemini_r, claude_r, gpt_r = await asyncio.gather(
        gemini_agent.analyze(video),
        claude_agent.analyze(video),
        gpt_agent.analyze(video),
        return_exceptions=True,
    )

    def _safe(r: object) -> dict:
        if isinstance(r, Exception):
            return {
                "verdict": "UNCERTAIN",
                "confidence": 0,
                "reasoning": f"Agent error: {r}",
                "flags": [],
            }
        return r  # type: ignore[return-value]

    gemini_r, claude_r, gpt_r = _safe(gemini_r), _safe(claude_r), _safe(gpt_r)
    synthesis = synthesize(gemini_r, claude_r, gpt_r)

    verdicts = [gemini_r["verdict"], claude_r["verdict"], gpt_r["verdict"]]
    if verdicts.count("SKIP") >= 2:
        logger.info(f"  → Skipping {video['video_id']}: {verdicts.count('SKIP')}/3 agents returned SKIP")
        return

    logger.info(
        f"  → {synthesis['final_verdict']} "
        f"{synthesis['confidence']}% [{synthesis['consensus']}]"
        f"  Gemini:{gemini_r['verdict']} Claude:{claude_r['verdict']} GPT:{gpt_r['verdict']}"
    )

    if _airtable:
        try:
            _airtable.upsert_video(video, synthesis, gemini_r, claude_r, gpt_r)
        except Exception as exc:
            logger.error(f"Airtable failed: {exc}")

    if _notifier:
        await _notifier.send_alert(video, synthesis, gemini_r, claude_r, gpt_r)

    stats = _airtable.get_stats() if _airtable else {}
    await broadcast_event(
        {
            "type": "new_video",
            "video_id": video["video_id"],
            "title": video["title"],
            "channel": video["channel"],
            "url": video["url"],
            "published_at": video.get("published_at", ""),
            "final_verdict": synthesis["final_verdict"],
            "confidence": synthesis["confidence"],
            "consensus": synthesis["consensus"],
            "reasoning": synthesis["reasoning"][:400],
            "flags": synthesis.get("flags", []),
            "gemini_verdict": gemini_r.get("verdict", "UNCERTAIN"),
            "claude_verdict": claude_r.get("verdict", "UNCERTAIN"),
            "gpt_verdict": gpt_r.get("verdict", "UNCERTAIN"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "stats": stats,
        }
    )


async def main() -> None:
    global _airtable, _notifier

    logger.info("═══════════════════════════════════")
    logger.info("  TruthStrike starting up…")
    logger.info("═══════════════════════════════════")

    if not config.YOUTUBE_CHANNEL_IDS:
        logger.warning("No YOUTUBE_CHANNEL_IDS configured — set them in .env")

    _airtable = AirtableClient()
    _notifier = TelegramNotifier(airtable_client=_airtable)

    watcher = RSSWatcher(
        channel_ids=config.YOUTUBE_CHANNEL_IDS,
        seen_ids_file=config.SEEN_IDS_FILE,
        on_new_video=process_video,
    )

    # Seed on first run so we don't flood on startup
    await watcher.initialize_seen()

    # APScheduler for periodic RSS polling
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        watcher.poll_once,
        trigger="interval",
        minutes=config.POLL_INTERVAL_MINUTES,
        id="rss_poll",
        max_instances=1,
    )
    scheduler.start()
    logger.info(f"Scheduler: polling every {config.POLL_INTERVAL_MINUTES} min")

    # Telegram bot (async polling in same event loop)
    await _notifier.start()

    # FastAPI dashboard
    app = create_app(airtable_client=_airtable)
    server_cfg = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(server_cfg)
    logger.info(f"Dashboard → http://0.0.0.0:{config.PORT}")

    try:
        await server.serve()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Shutting down…")
        scheduler.shutdown(wait=False)
        await _notifier.stop()
        logger.info("TruthStrike stopped.")


if __name__ == "__main__":
    asyncio.run(main())

