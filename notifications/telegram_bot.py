import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config

if TYPE_CHECKING:
    from storage.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

_VERDICT_EMOJI = {"REAL": "✅", "FAKE": "❌", "UNCERTAIN": "⚠️"}


def _format_alert(
    video: dict[str, Any],
    synthesis: dict[str, Any],
    gemini: dict[str, Any],
    claude: dict[str, Any],
    gpt: dict[str, Any],
) -> str:
    verdict = synthesis["final_verdict"]
    confidence = synthesis["confidence"]
    emoji = _VERDICT_EMOJI.get(verdict, "⚠️")
    reasoning = synthesis.get("reasoning", "")[:500]
    if len(synthesis.get("reasoning", "")) > 500:
        reasoning += "…"

    return (
        f"🎯 *NEW VIDEO ANALYZED*\n\n"
        f"📺 {_esc(video.get('title', 'Unknown'))}\n"
        f"📊 Verdict: *{emoji} {verdict}* \\({confidence}% confidence\\)\n"
        f"🤖 Gemini: {gemini.get('verdict','?')} \\| Claude: {claude.get('verdict','?')} \\| GPT: {gpt.get('verdict','?')}\n"
        f"🔗 [Watch Video]({video.get('url', '')})\n"
        f"💬 {_esc(reasoning)}"
    )


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


class TelegramNotifier:
    def __init__(self, airtable_client: "AirtableClient | None" = None) -> None:
        self._airtable = airtable_client
        self._app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("stats", self._cmd_stats))
        self._app.add_handler(CommandHandler("latest", self._cmd_latest))

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "🎯 *TruthStrike War Room*\n\n"
            "Commands:\n"
            "/status \\- System status\n"
            "/stats \\- Analysis statistics\n"
            "/latest \\- Last 5 analyzed videos",
            parse_mode="MarkdownV2",
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y\\-%m\\-%d %H:%M UTC")
        await update.message.reply_text(
            f"✅ *TruthStrike is running*\n⏰ {ts}",
            parse_mode="MarkdownV2",
        )

    async def _cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if self._airtable:
            s = self._airtable.get_stats()
            text = (
                f"📊 *TruthStrike Statistics*\n\n"
                f"Total analyzed: {s.get('total', 0)}\n"
                f"✅ REAL: {s.get('REAL', 0)}\n"
                f"❌ FAKE: {s.get('FAKE', 0)}\n"
                f"⚠️ UNCERTAIN: {s.get('UNCERTAIN', 0)}"
            )
        else:
            text = "⚠️ Statistics unavailable\\."
        await update.message.reply_text(text, parse_mode="MarkdownV2")

    async def _cmd_latest(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._airtable:
            await update.message.reply_text("⚠️ Data unavailable\\.", parse_mode="MarkdownV2")
            return
        records = self._airtable.get_recent(limit=5)
        if not records:
            await update.message.reply_text("No videos analyzed yet\\.", parse_mode="MarkdownV2")
            return
        lines = ["📋 *Latest 5 Analyzed Videos*\n"]
        for r in records:
            verdict = r.get("FinalVerdict", "?")
            emoji = _VERDICT_EMOJI.get(verdict, "⚠️")
            title = _esc(r.get("Title", "Unknown")[:50])
            url = r.get("URL", "")
            lines.append(f"{emoji} {title}")
            lines.append(f"   {url}\n")
        await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")

    async def send_alert(
        self,
        video: dict[str, Any],
        synthesis: dict[str, Any],
        gemini: dict[str, Any],
        claude: dict[str, Any],
        gpt: dict[str, Any],
    ) -> None:
        if not config.TELEGRAM_CHAT_ID:
            logger.warning("TELEGRAM_CHAT_ID not configured — skipping alert.")
            return
        text = _format_alert(video, synthesis, gemini, claude, gpt)
        try:
            await self._app.bot.send_message(
                chat_id=config.TELEGRAM_CHAT_ID,
                text=text,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.error(f"Telegram send_message failed: {exc}")

    async def start(self) -> None:
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot polling started.")

    async def stop(self) -> None:
        await self._app.updater.stop()
        await self._app.stop()
        await self._app.shutdown()
        logger.info("Telegram bot stopped.")
