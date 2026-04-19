import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from storage.airtable_client import AirtableClient

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# SSE subscriber queues — one per connected client
_subscribers: list[asyncio.Queue] = []


async def broadcast_event(data: dict[str, Any]) -> None:
    """Push an event to all connected SSE clients."""
    dead: list[asyncio.Queue] = []
    for q in _subscribers:
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        try:
            _subscribers.remove(q)
        except ValueError:
            pass


def create_app(airtable_client: "AirtableClient | None" = None) -> FastAPI:
    app = FastAPI(title="TruthStrike", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        records: list[dict] = []
        stats: dict[str, Any] = {"total": 0, "REAL": 0, "FAKE": 0, "UNCERTAIN": 0}
        if airtable_client:
            records = airtable_client.get_recent(50)
            stats = airtable_client.get_stats()
        return _templates.TemplateResponse(
            "index.html",
            {"request": request, "records": records, "stats": stats},
        )

    @app.get("/api/stats")
    async def api_stats() -> dict[str, Any]:
        if airtable_client:
            return airtable_client.get_stats()
        return {"total": 0, "REAL": 0, "FAKE": 0, "UNCERTAIN": 0}

    @app.get("/api/videos")
    async def api_videos(limit: int = 50) -> list[dict]:
        if airtable_client:
            return airtable_client.get_recent(limit)
        return []

    @app.get("/events")
    async def sse_endpoint(request: Request) -> StreamingResponse:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        _subscribers.append(q)

        async def generator() -> AsyncGenerator[str, None]:
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        data = await asyncio.wait_for(q.get(), timeout=25.0)
                        yield f"data: {json.dumps(data)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                try:
                    _subscribers.remove(q)
                except ValueError:
                    pass

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
